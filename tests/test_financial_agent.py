import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent.parent / "scripts" / "utils"))

from financial_agent import FinancialAgent

def test_agent_initialization():
    """Test agent initializes with or without API key."""
    agent = FinancialAgent(api_key="test-key", model="moonshot-v1-128k")
    assert agent.model == "moonshot-v1-128k"

def test_build_prompt():
    """Test prompt construction."""
    agent = FinancialAgent(api_key="test-key")
    data = {
        "technical": {"close": 89.5, "macd": -0.08},
        "reports": [{"title": "Test Report", "institution": "Test Bank"}],
        "announcements": [],
        "fundflow": [],
        "news": [],
        "sentiment": [],
    }
    prompt = agent._build_prompt("圣邦股份", "300661", data)
    assert "圣邦股份" in prompt
    assert "300661" in prompt
    assert "Test Report" in prompt
