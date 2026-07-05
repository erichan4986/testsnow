import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent.parent / "scripts" / "utils"))

from obsidian_writer import ObsidianWriter
import tempfile

def test_write_atomic_note():
    with tempfile.TemporaryDirectory() as tmpdir:
        writer = ObsidianWriter(vault_root=tmpdir)
        writer.write_atomic_note(
            stock_name="圣邦股份",
            code="300661",
            date="20250523",
            category="技术指标",
            data={"close": 89.5, "macd": -0.08},
            data_source="mootdx",
            analysis="MACD 在零轴下方粘合",
        )
        note_path = Path(tmpdir) / "10-Stocks" / "圣邦股份" / "20250523-技术指标.md"
        assert note_path.exists()
        content = note_path.read_text(encoding="utf-8")
        assert "圣邦股份" in content
        assert "89.5" in content
        assert "MACD 在零轴下方粘合" in content
