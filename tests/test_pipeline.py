import asyncio
from typing import Any, Dict
from unittest.mock import patch

import pytest

from src.agents.extraction import ExtractionAgent
from src.agents.risk import RiskAgent
from src.agents.summary import SummaryAgent
from src.orchestrator.engine import export_execution_log, run_pipeline
from src.orchestrator.state import AgentState, ClauseExtraction

PROJECT_ROOT = __import__("pathlib").Path(__file__).resolve().parent.parent
EXECUTION_LOG_PATH = PROJECT_ROOT / "EXECUTION_LOG.md"


def _build_synthetic_contract() -> Dict[str, Any]:
    return {
        "title": "TEST_CONTRACT",
        "paragraphs": [
            {
                "context": "This is a synthetic contract for unit testing purposes.",
                "qas": [
                    {
                        "question": (
                            "Highlight the parts (if any) of this contract "
                            "related to 'Governing Law'..."
                        ),
                        "id": "qa-governing-law",
                        "is_impossible": False,
                        "answers": [
                            {
                                "text": "governed by the laws of Delaware",
                                "answer_start": 100,
                            }
                        ],
                    },
                    {
                        "question": (
                            "Highlight the parts (if any) of this contract "
                            "related to 'Cap On Liability'..."
                        ),
                        "id": "qa-cap-liability",
                        "is_impossible": True,
                        "answers": [],
                    },
                    {
                        "question": (
                            "Highlight the parts (if any) of this contract "
                            "related to 'IP Ownership Assignment'..."
                        ),
                        "id": "qa-ip-ownership",
                        "is_impossible": False,
                        "answers": [
                            {
                                "text": "IP assigned to Client",
                                "answer_start": 500,
                            }
                        ],
                    },
                ],
            }
        ],
    }


def _make_state() -> AgentState:
    return AgentState(session_id="test-session-001", contract_title="TEST_CONTRACT")


@pytest.fixture
def mock_contract_loader() -> Any:
    contract = _build_synthetic_contract()
    with patch(
        "src.agents.extraction._load_contract_from_zip",
        return_value=contract,
    ) as mock_loader:
        yield mock_loader


def test_extraction_agent_populates_extractions(mock_contract_loader: Any) -> None:
    agent = ExtractionAgent()
    state = _make_state()

    result = asyncio.run(agent.process(state))

    assert "extractions" in result.shared_data
    extractions = [ClauseExtraction.model_validate(item) for item in result.shared_data["extractions"]]
    assert len(extractions) == 3

    governing_law = next(item for item in extractions if item.clause_type == "Governing Law")
    assert governing_law.extracted_text == "governed by the laws of Delaware"
    assert governing_law.answer_start == 100
    assert governing_law.is_impossible is False

    cap_liability = next(item for item in extractions if item.clause_type == "Cap On Liability")
    assert cap_liability.is_impossible is True
    assert cap_liability.extracted_text == ""

    ip_ownership = next(item for item in extractions if item.clause_type == "IP Ownership Assignment")
    assert ip_ownership.extracted_text == "IP assigned to Client"
    assert ip_ownership.is_impossible is False


def test_extraction_agent_advances_step(mock_contract_loader: Any) -> None:
    agent = ExtractionAgent()
    state = _make_state()

    result = asyncio.run(agent.process(state))

    assert result.current_step == "risk_assessment"


def test_risk_agent_flags_missing_cap_on_liability(mock_contract_loader: Any) -> None:
    extraction_agent = ExtractionAgent()
    risk_agent = RiskAgent()
    state = _make_state()

    state = asyncio.run(extraction_agent.process(state))
    state = asyncio.run(risk_agent.process(state))

    risk_flags = state.shared_data["risk_flags"]
    cap_flag = next(item for item in risk_flags if item["clause_type"] == "Cap On Liability")
    assert cap_flag["severity"] == "critical"


def test_risk_agent_populates_summary(mock_contract_loader: Any) -> None:
    extraction_agent = ExtractionAgent()
    risk_agent = RiskAgent()
    state = _make_state()

    state = asyncio.run(extraction_agent.process(state))
    state = asyncio.run(risk_agent.process(state))

    summary = state.shared_data["risk_summary"]
    assert "total_flags" in summary
    assert "critical_count" in summary
    assert "high_count" in summary
    assert "medium_count" in summary
    assert "low_count" in summary
    assert "overall_severity" in summary
    assert summary["critical_count"] >= 1


def test_risk_agent_advances_step(mock_contract_loader: Any) -> None:
    extraction_agent = ExtractionAgent()
    risk_agent = RiskAgent()
    state = _make_state()

    state = asyncio.run(extraction_agent.process(state))
    state = asyncio.run(risk_agent.process(state))

    assert state.current_step == "advisory"


def test_summary_agent_produces_final_report(mock_contract_loader: Any) -> None:
    extraction_agent = ExtractionAgent()
    risk_agent = RiskAgent()
    summary_agent = SummaryAgent()
    state = _make_state()

    state = asyncio.run(extraction_agent.process(state))
    state = asyncio.run(risk_agent.process(state))
    state = asyncio.run(summary_agent.process(state))

    report = state.shared_data["final_report"]
    required_keys = [
        "contract_title",
        "session_id",
        "review_date",
        "overall_risk_severity",
        "total_clauses_reviewed",
        "clauses_found",
        "clauses_missing",
        "total_risk_flags",
        "executive_summary",
        "clause_by_clause",
        "top_priority_actions",
    ]
    for key in required_keys:
        assert key in report


def test_summary_agent_sets_complete(mock_contract_loader: Any) -> None:
    extraction_agent = ExtractionAgent()
    risk_agent = RiskAgent()
    summary_agent = SummaryAgent()
    state = _make_state()

    state = asyncio.run(extraction_agent.process(state))
    state = asyncio.run(risk_agent.process(state))
    state = asyncio.run(summary_agent.process(state))

    assert state.current_step == "complete"


def test_full_pipeline_produces_three_traces(mock_contract_loader: Any) -> None:
    state = _make_state()

    result = asyncio.run(run_pipeline(state))

    assert len(result.execution_traces) == 3
    assert result.current_step == "complete"
    assert not result.errors


def test_extraction_error_halts_pipeline() -> None:
    state = _make_state()

    with patch(
        "src.agents.extraction._load_contract_from_zip",
        side_effect=FileNotFoundError("zip not found"),
    ):
        result = asyncio.run(run_pipeline(state))

    assert result.errors
    assert result.current_step == "extraction"
    assert len(result.execution_traces) == 0


def test_export_execution_log_creates_file(mock_contract_loader: Any) -> None:
    state = _make_state()
    state = asyncio.run(run_pipeline(state))

    if EXECUTION_LOG_PATH.exists():
        EXECUTION_LOG_PATH.unlink()

    asyncio.run(export_execution_log(state))

    assert EXECUTION_LOG_PATH.exists()
    content = EXECUTION_LOG_PATH.read_text(encoding="utf-8")
    assert "Session ID" in content
    assert state.contract_title in content
    assert "Risk Summary" in content

    EXECUTION_LOG_PATH.unlink()
