from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parent.parent
SCRIPTS_DIR = REPO_ROOT / "scripts"
HIGH_RISK_DIR = SCRIPTS_DIR / "high_risk"
OLD_PREVIEWS_ARCHIVE = SCRIPTS_DIR / "archive" / "old_previews"
LEGACY_MAINTENANCE_ARCHIVE = SCRIPTS_DIR / "archive" / "legacy_maintenance"
ACTIVE_PREVIEWS_DIR = SCRIPTS_DIR / "previews"

DELETED_OLD_PREVIEWS = [
    "curated_external_analysis_preview.py",
    "curated_external_candidate_discovery_preview.py",
    "curated_external_section_preview.py",
    "curated_external_to_synthesis_preview.py",
    "curated_external_video_subtitle_preview.py",
]

ACTIVE_PREVIEWS = [
    "broker_research_digest_preview.py",
    "curated_external_full_body_viewpoint_preview.py",
    "formal_first_source_policy_preview.py",
    "iwencai_industry_research_preview.py",
    "periodic_report_fulltext_preview.py",
    "periodic_report_narrative_cards_acceptance.py",
    "periodic_report_narrative_cards_preview.py",
    "wechat_candidate_selector_preview.py",
    "wechat_targeted_discovery_preview.py",
]

ARCHIVED_LEGACY_MAINTENANCE = [
    "generate_periodic_report.py",
    "sync_vault_from_raw.py",
]

HIGH_RISK_SCRIPTS = [
    "batch_fetch_quality_posts.py",
    "extract_detail.py",
    "extract_detail_via_cdp.py",
    "fetch_xueqiu.py",
    "start_chrome_cdp.command",
    "start_chrome_cdp.sh",
]


def test_old_curated_external_preview_scripts_are_deleted():
    for filename in DELETED_OLD_PREVIEWS:
        assert not (SCRIPTS_DIR / filename).exists(), f"{filename} should not remain in scripts/"
        assert not (OLD_PREVIEWS_ARCHIVE / filename).exists(), f"{filename} should be deleted from old preview archive"


def test_active_preview_scripts_live_in_previews_dir():
    for filename in ACTIVE_PREVIEWS:
        assert not (SCRIPTS_DIR / filename).exists(), f"{filename} should not remain in scripts/"
        assert (ACTIVE_PREVIEWS_DIR / filename).exists(), f"{filename} should live in scripts/previews/"


def test_legacy_maintenance_scripts_are_archived():
    for filename in ARCHIVED_LEGACY_MAINTENANCE:
        assert not (SCRIPTS_DIR / filename).exists(), f"{filename} should not remain in scripts/"
        assert (LEGACY_MAINTENANCE_ARCHIVE / filename).exists(), (
            f"{filename} should live in scripts/archive/legacy_maintenance/"
        )


def test_high_risk_collection_scripts_live_in_high_risk_dir():
    for filename in HIGH_RISK_SCRIPTS:
        assert not (SCRIPTS_DIR / filename).exists(), f"{filename} should not remain in scripts/"
        assert (HIGH_RISK_DIR / filename).exists(), f"{filename} should live in scripts/high_risk/"
