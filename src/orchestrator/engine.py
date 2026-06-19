import asyncio
from datetime import datetime, timezone
from pathlib import Path
from typing import List

from src.agents.extraction import ExtractionAgent
from src.agents.risk import RiskAgent
from src.agents.summary import SummaryAgent
from src.orchestrator.state import AgentState, RiskFlag, StepExecutionTrace

PROJECT_ROOT = Path(__file__).resolve().parent.parent.parent
EXECUTION_LOG_PATH = PROJECT_ROOT / "EXECUTION_LOG.md"


def _format_trace_outputs(trace: StepExecutionTrace) -> str:
    output_parts: List[str] = []
    for key, value in trace.output_generated.items():
        output_parts.append(f"{key}={value}")
    return "; ".join(output_parts) if output_parts else "—"


def _format_risk_table_rows(state: AgentState) -> List[str]:
    rows: List[str] = []
    raw_flags = state.shared_data.get("risk_flags", [])
    for raw_flag in raw_flags:
        flag = RiskFlag.model_validate(raw_flag)
        rows.append(
            f"| {flag.clause_type} | {flag.severity} | {flag.deviation} | {flag.recommendation} |"
        )
    return rows


async def export_execution_log(state: AgentState) -> None:
    timestamp = datetime.now(timezone.utc).isoformat()
    risk_rows = _format_risk_table_rows(state)
    final_report = state.shared_data.get("final_report", {})
    top_actions = final_report.get("top_priority_actions", [])

    lines: List[str] = [
        "# CUAD Contract Review — Execution Log",
        "",
        f"**Session ID:** {state.session_id}",
        f"**Contract Title:** {state.contract_title}",
        f"**Final Step:** {state.current_step}",
        f"**Timestamp:** {timestamp}",
        "",
        "## Agent Execution Table",
        "",
        "| Agent | Timestamp | Rationale | Key Outputs |",
        "| --- | --- | --- | --- |",
    ]

    for trace in state.execution_traces:
        lines.append(
            f"| {trace.agent_name} | {trace.timestamp.isoformat()} | "
            f"{trace.agent_rationale} | {_format_trace_outputs(trace)} |"
        )

    lines.extend(
        [
            "",
            "## Risk Summary",
            "",
            "| Clause Type | Severity | Deviation | Recommendation |",
            "| --- | --- | --- | --- |",
        ]
    )
    lines.extend(risk_rows)

    lines.extend(["", "## Top Priority Actions", ""])
    if top_actions:
        for action in top_actions:
            lines.append(f"{action}")
    else:
        lines.append("No critical or high priority actions identified.")

    lines.extend(
        [
            "",
            "## Validation Note",
            "",
            "Ground truth answers available in CUAD dataset for independent verification",
            "",
        ]
    )

    content = "\n".join(lines)

    def _write_log() -> None:
        EXECUTION_LOG_PATH.write_text(content, encoding="utf-8")

    await asyncio.to_thread(_write_log)


async def run_pipeline(state: AgentState) -> AgentState:
    agents = [
        ExtractionAgent(),
        RiskAgent(),
        SummaryAgent(),
    ]

    for agent in agents:
        if state.errors:
            break

        if state.current_step == "complete":
            break

        expected_steps = {
            "ExtractionAgent": "extraction",
            "RiskAgent": "risk_assessment",
            "SummaryAgent": "advisory",
        }
        if state.current_step != expected_steps.get(agent.name, ""):
            continue

        state = await agent.process(state)

        if state.errors:
            failed_step = state.current_step
            state.errors.append(f"Pipeline halted at step '{failed_step}' due to agent failure.")
            return state

    if state.current_step == "complete" and not state.errors:
        await export_execution_log(state)

    return state
