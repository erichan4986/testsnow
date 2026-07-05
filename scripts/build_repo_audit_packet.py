#!/usr/bin/env python3
"""Build a compact repo-health audit packet for external GPT review.

The packet is intentionally evidence-oriented and marks sample reports as
stale when their mtime predates the current HEAD commit timestamp.
"""

from __future__ import annotations

import argparse
import os
import subprocess
import zipfile
from datetime import datetime
from pathlib import Path


DEFAULT_REPORTS = (
    "reports/中际旭创_20260630.md",
    "reports/黑芝麻智能_20260630.md",
    "reports/圣邦股份_20260630.md",
)

GPT_REPO_AUDIT_PROMPT = """# testsnow Repo Health Audit Prompt

You are an external repo health auditor for `testsnow`, an A/HK Chinese stock
research report generation system. Do not write code. Audit only from this
packet, and explicitly mark stale report samples as lower-confidence evidence.

Output:
1. Executive Verdict
2. P0/P1/P2/P3 Findings
3. Deletion / Archive Candidates
4. Report Pipeline Risk Map
5. Agent Guardrails
6. 30-Day Cleanup Plan
"""


def main() -> int:
    parser = argparse.ArgumentParser(description="Build a compact testsnow repo audit packet")
    parser.add_argument("--output", default="/tmp/testsnow_repo_audit_packet", help="Output directory")
    parser.add_argument("--zip-output", default="/tmp/testsnow_repo_audit_packet.zip", help="Zip output path")
    parser.add_argument("--report", action="append", dest="reports", help="Sample report path; repeatable")
    args = parser.parse_args()

    repo_root = Path(__file__).resolve().parent.parent
    output_dir = Path(args.output)
    output_dir.mkdir(parents=True, exist_ok=True)
    head_timestamp = _head_commit_timestamp(repo_root)
    report_paths = [Path(path) for path in (args.reports or DEFAULT_REPORTS)]

    _write(output_dir / "README.md", _readme())
    _write(output_dir / "gpt_repo_audit_prompt.md", GPT_REPO_AUDIT_PROMPT)
    _write(output_dir / "00_project_rules.md", _safe_read(repo_root / "AGENTS.md", max_chars=30000))
    _write(output_dir / "01_tree_summary.txt", _tree_summary(repo_root))
    _write(output_dir / "02_git_tracked_files.txt", _run(repo_root, ["git", "ls-files"], max_chars=120000))
    _write(output_dir / "03_largest_files.txt", _largest_files(repo_root))
    _write(output_dir / "04_recent_commits.txt", _run(repo_root, ["git", "log", "--oneline", "--decorate", "-25"]))
    _write(output_dir / "05_entrypoints.md", _entrypoints(repo_root))
    _write(output_dir / "06_report_pipeline_map.md", _pipeline_map())
    _write(output_dir / "10_sample_reports.md", _sample_reports(repo_root, report_paths, head_timestamp))
    _write(output_dir / "11_known_issues.md", _known_issues())
    _write(output_dir / "manifest.txt", f"generated_at={datetime.now().isoformat(timespec='seconds')}\n")
    _zip_dir(output_dir, Path(args.zip_output))

    print(f"Wrote {output_dir}")
    print(f"Wrote {args.zip_output}")
    return 0


def report_sample_status_line(report_path: Path, repo_root: Path, head_timestamp: int | None) -> str:
    if not report_path.exists():
        return f"- `{_display_path(report_path, repo_root)}`: MISSING"
    mtime = int(report_path.stat().st_mtime)
    stale = bool(head_timestamp is not None and mtime < head_timestamp)
    mtime_text = datetime.fromtimestamp(mtime).isoformat(timespec="seconds")
    return (
        f"- `{_display_path(report_path, repo_root)}`: "
        f"mtime={mtime_text}, stale_sample={str(stale).lower()}"
    )


def _sample_reports(repo_root: Path, report_paths: list[Path], head_timestamp: int | None) -> str:
    lines = ["# Sample Report Excerpts", "", "## Sample freshness", ""]
    resolved_paths = [_resolve_under_repo(repo_root, path) for path in report_paths]
    for report in resolved_paths:
        lines.append(report_sample_status_line(report, repo_root=repo_root, head_timestamp=head_timestamp))
    lines.append("")
    for report in resolved_paths:
        lines.append(f"## `{_display_path(report, repo_root)}`")
        lines.append("")
        if not report.exists():
            lines.append("MISSING")
            lines.append("")
            continue
        text = _safe_read(report, max_chars=120000)
        lines.append(report_sample_status_line(report, repo_root=repo_root, head_timestamp=head_timestamp))
        lines.append("")
        headings = [line for line in text.splitlines() if line.startswith("#")]
        lines.append("### Headings")
        lines.extend(f"- {heading}" for heading in headings[:80])
        for heading in ("## 四、深度分析", "## 七、风险提示", "## 八、最终建议"):
            excerpt = _section_excerpt(text, heading, max_chars=6000)
            if excerpt:
                lines.extend(["", f"### Excerpt: {heading}", "", "```markdown", excerpt, "```"])
        lines.append("")
    return "\n".join(lines).rstrip() + "\n"


def _tree_summary(repo_root: Path) -> str:
    rows = []
    for child in sorted(repo_root.iterdir(), key=lambda p: p.name):
        if child.name in {".git", "__pycache__"}:
            continue
        size, count = _path_size(child)
        rows.append(f"- {child.name}{'/' if child.is_dir() else ''}: {count} files, {_fmt_bytes(size)}")
    return "# Top-Level Tree Summary\n\n" + "\n".join(rows) + "\n"


def _largest_files(repo_root: Path) -> str:
    files = []
    for base, dirs, names in os.walk(repo_root):
        dirs[:] = [d for d in dirs if d not in {".git", "__pycache__", ".pytest_cache"}]
        for name in names:
            path = Path(base) / name
            try:
                files.append((path.stat().st_size, path))
            except OSError:
                continue
    lines = ["# Largest Files", ""]
    for size, path in sorted(files, reverse=True)[:150]:
        lines.append(f"{_fmt_bytes(size):>9}  {_display_path(path, repo_root)}")
    return "\n".join(lines) + "\n"


def _entrypoints(repo_root: Path) -> str:
    scripts_dir = repo_root / "scripts"
    lines = ["# Entrypoints Inventory", ""]
    for path in sorted(scripts_dir.glob("*.py")):
        cli_like = _safe_read(path, max_chars=5000).find("argparse") >= 0 or path.name.startswith("run_")
        lines.append(f"- `{_display_path(path, repo_root)}` ({_fmt_bytes(path.stat().st_size)}), cli_like={cli_like}")
    return "\n".join(lines) + "\n"


def _pipeline_map() -> str:
    return """# Report Pipeline Map

`scripts/run_stock_report.py` / `scripts/run_*.py`
-> `PerStockReporter`
-> `report_skills` pipeline
-> source intake / AgentReach / periodic cards / broker digest
-> `SynthesisSkill` + `KnowledgeSynthesizer`
-> section renderers, including `deep_analysis_renderer.py`
-> scoring / risk / technical / final Markdown and HTML.

Critical boundary: 4.1-4.3 should use formal/professional sources under
`formal_first`; social/WeChat/Zhihu/Xueqiu viewpoints should remain in 4.4
display-only material unless reduced to a verified bridge summary.
"""


def _known_issues() -> str:
    return """# Known Issues

- Repo has accumulated generated reports, raw data, debug artifacts, historical workflow docs, previews, and smoke tools.
- Source boundary must be enforced in final report text, not only in code-level gates.
- Recommendation/EV/risk/technical entry labels can drift and need a shared consistency check.
- Live API/LLM/browser/PDF validation is not fully reproducible; deterministic fixtures are preferred for gates.
"""


def _readme() -> str:
    return """# testsnow Repo Audit Packet

Upload this packet to GPT/ChatGPT and ask it to start from
`gpt_repo_audit_prompt.md`. Report samples include `mtime` and
`stale_sample` markers; stale samples should not be treated as current runtime
truth without rerunning the report.
"""


def _section_excerpt(text: str, heading: str, max_chars: int) -> str:
    start = text.find(heading)
    if start < 0:
        return ""
    match = re_search_next_h2(text[start + len(heading) :])
    end = start + len(heading) + match if match is not None else min(len(text), start + max_chars)
    return text[start : min(end, start + max_chars)].strip()


def re_search_next_h2(text: str) -> int | None:
    import re

    match = re.search(r"\n## [^#]", text)
    return None if match is None else match.start()


def _resolve_under_repo(repo_root: Path, path: Path) -> Path:
    if path.is_absolute():
        return path
    return repo_root / path


def _display_path(path: Path, repo_root: Path) -> str:
    try:
        return str(path.relative_to(repo_root))
    except ValueError:
        return str(path)


def _head_commit_timestamp(repo_root: Path) -> int | None:
    raw = _run(repo_root, ["git", "log", "-1", "--format=%ct"]).strip()
    return int(raw) if raw.isdigit() else None


def _path_size(path: Path) -> tuple[int, int]:
    if path.is_file():
        return path.stat().st_size, 1
    total = 0
    count = 0
    for base, dirs, names in os.walk(path):
        dirs[:] = [d for d in dirs if d not in {".git", "__pycache__"}]
        for name in names:
            file_path = Path(base) / name
            try:
                total += file_path.stat().st_size
                count += 1
            except OSError:
                continue
    return total, count


def _fmt_bytes(size: int) -> str:
    value = float(size)
    for unit in ("B", "KB", "MB", "GB"):
        if value < 1024 or unit == "GB":
            return f"{value:.1f}{unit}"
        value /= 1024
    return f"{size}B"


def _safe_read(path: Path, max_chars: int) -> str:
    if not path.exists():
        return ""
    text = path.read_text(encoding="utf-8", errors="replace")
    if len(text) > max_chars:
        return text[:max_chars] + f"\n... [truncated at {max_chars} chars]\n"
    return text


def _run(repo_root: Path, cmd: list[str], max_chars: int = 20000) -> str:
    proc = subprocess.run(cmd, cwd=repo_root, text=True, capture_output=True, timeout=30)
    text = proc.stdout + proc.stderr
    if len(text) > max_chars:
        return text[:max_chars] + f"\n... [truncated at {max_chars} chars]\n"
    return text


def _write(path: Path, text: str) -> None:
    path.write_text(text, encoding="utf-8")


def _zip_dir(source_dir: Path, zip_path: Path) -> None:
    zip_path.parent.mkdir(parents=True, exist_ok=True)
    if zip_path.exists():
        zip_path.unlink()
    with zipfile.ZipFile(zip_path, "w", compression=zipfile.ZIP_DEFLATED) as zf:
        for path in sorted(source_dir.iterdir()):
            if path.is_file():
                zf.write(path, arcname=f"{source_dir.name}/{path.name}")


if __name__ == "__main__":
    raise SystemExit(main())
