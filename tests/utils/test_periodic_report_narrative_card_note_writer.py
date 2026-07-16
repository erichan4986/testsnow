from pathlib import Path


def test_obsolete_per_card_markdown_writer_is_removed() -> None:
    root = Path(__file__).parent.parent.parent

    assert not (
        root / "scripts" / "utils" / "periodic_report_narrative_card_note_writer.py"
    ).exists()
