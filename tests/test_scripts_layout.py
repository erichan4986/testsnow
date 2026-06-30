from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parent.parent
SCRIPTS_DIR = REPO_ROOT / "scripts"
OLD_PREVIEWS_ARCHIVE = SCRIPTS_DIR / "archive" / "old_previews"

ARCHIVED_OLD_PREVIEWS = [
    "curated_external_analysis_preview.py",
    "curated_external_candidate_discovery_preview.py",
    "curated_external_section_preview.py",
    "curated_external_to_synthesis_preview.py",
    "curated_external_video_subtitle_preview.py",
]


def test_old_curated_external_preview_scripts_are_archived():
    for filename in ARCHIVED_OLD_PREVIEWS:
        assert not (SCRIPTS_DIR / filename).exists(), f"{filename} should not remain in scripts/"
        assert (OLD_PREVIEWS_ARCHIVE / filename).exists(), f"{filename} should live in old preview archive"
