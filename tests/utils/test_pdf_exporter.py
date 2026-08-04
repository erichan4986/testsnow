from types import SimpleNamespace

from scripts.utils.pdf_exporter import _md_to_html, export_pdf


def test_pdf_html_constrains_report_images_for_a4_pages():
    html = _md_to_html("![技术面分析](/tmp/technical.png)")

    assert "img {" in html
    assert "max-width: 100%;" in html
    assert "max-height: 210mm;" in html
    assert "object-fit: contain;" in html


def test_pdf_html_keeps_decision_chain_with_executive_summary():
    html = _md_to_html("![投资决策链](/tmp/任意股票_20260720_decision.png)")

    assert 'img[src$="_decision.png"] {' in html
    assert "max-height: 148mm;" in html
    assert 'p:has(> img[src$="_decision.png"]) {' in html


def test_pdf_html_resolves_markdown_and_raw_local_images(tmp_path):
    relative = tmp_path / "decision.png"
    absolute = tmp_path / "technical.png"
    relative.write_bytes(b"png")
    absolute.write_bytes(b"png")

    html = _md_to_html(
        f"![决策链](decision.png)\n\n<img src=\"{absolute}\" alt=\"技术图\">",
        base_dir=tmp_path,
    )

    assert relative.resolve().as_uri() in html
    assert absolute.resolve().as_uri() in html


def test_pdf_html_leaves_remote_and_data_images_unchanged(tmp_path):
    html = _md_to_html(
        '<img src="https://example.com/a.png"><img src="data:image/png;base64,abc">',
        base_dir=tmp_path,
    )

    assert 'src="https://example.com/a.png"' in html
    assert 'src="data:image/png;base64,abc"' in html


def test_pdf_html_fails_clearly_for_missing_local_image(tmp_path):
    import pytest

    with pytest.raises(FileNotFoundError, match="missing.png"):
        _md_to_html("![缺图](missing.png)", base_dir=tmp_path)


def test_pdf_html_fails_for_missing_file_uri(tmp_path):
    import pytest

    missing = (tmp_path / "missing-file-uri.png").as_uri()
    with pytest.raises(FileNotFoundError, match="missing-file-uri.png"):
        _md_to_html(f'<img src="{missing}">', base_dir=tmp_path)


def test_export_pdf_waits_for_local_images_before_pdf(tmp_path, monkeypatch):
    md_path = tmp_path / "report.md"
    image_path = tmp_path / "decision.png"
    pdf_path = tmp_path / "report.pdf"
    image_path.write_bytes(b"png")
    md_path.write_text("![决策链](decision.png)", encoding="utf-8")
    events = []

    class Page:
        def goto(self, *args, **kwargs):
            events.append("goto")

        def wait_for_function(self, expression):
            assert "file:" in expression
            events.append("wait_images")

        def wait_for_timeout(self, _timeout):
            events.append("wait_font")

        def pdf(self, **kwargs):
            events.append("pdf")

    class Browser:
        def new_page(self):
            return Page()

        def close(self):
            events.append("close")

    class Playwright:
        chromium = SimpleNamespace(launch=lambda: Browser())

    class Manager:
        def __enter__(self):
            return Playwright()

        def __exit__(self, *_args):
            return False

    monkeypatch.setattr("playwright.sync_api.sync_playwright", lambda: Manager())

    export_pdf(str(md_path), str(pdf_path))

    assert events.index("wait_images") < events.index("pdf")
