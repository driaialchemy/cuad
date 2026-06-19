from datetime import datetime, timezone
from typing import Any, Dict, List

from src.agents.base import BaseAgent
from src.orchestrator.state import AgentState, ClauseExtraction, RiskFlag

PLAYBOOK_CLAUSE_COUNT = 10
PRIORITY_SEVERITIES = {"critical", "high"}


class SummaryAgent(BaseAgent):
    name = "SummaryAgent"

    async def process(self, state: AgentState) -> AgentState:
        if state.current_step != "advisory":
            return state

        input_received = {
            "contract_title": state.contract_title,
            "current_step": state.current_step,
        }

        try:
            raw_extractions = state.shared_data.get("extractions", [])
            raw_risk_flags = state.shared_data.get("risk_flags", [])
            risk_summary: Dict[str, Any] = state.shared_data.get("risk_summary", {})

            extractions = [ClauseExtraction.model_validate(item) for item in raw_extractions]
            risk_flags = [RiskFlag.model_validate(item) for item in raw_risk_flags]

            clauses_found = sum(1 for item in extractions if not item.is_impossible)
            clauses_missing = sum(1 for item in extractions if item.is_impossible)
            overall_severity = risk_summary.get("overall_severity", "none")
            total_risk_flags = risk_summary.get("total_flags", 0)

            flag_by_clause = {flag.clause_type: flag for flag in risk_flags}
            extraction_by_clause = {item.clause_type: item for item in extractions}

            primary_concerns = [
                flag.clause_type
                for flag in risk_flags
                if flag.severity in PRIORITY_SEVERITIES
            ]
            concerns_text = ", ".join(primary_concerns) if primary_concerns else "none identified"

            top_flag = next(
                (flag for flag in risk_flags if flag.severity in PRIORITY_SEVERITIES),
                None,
            )
            top_flag_text = (
                f"{top_flag.clause_type} ({top_flag.severity})"
                if top_flag
                else "no critical or high severity items"
            )

            executive_summary = (
                f"Contract '{state.contract_title}' reviewed across {PLAYBOOK_CLAUSE_COUNT} "
                f"key clause categories. {clauses_found} clauses were identified, "
                f"{clauses_missing} were absent. Overall risk posture is {overall_severity}. "
                f"Primary concerns are {concerns_text}. "
                f"Immediate attention required on {top_flag_text}."
            )

            clause_by_clause: List[Dict[str, str]] = []
            for clause_type in flag_by_clause:
                extraction = extraction_by_clause.get(clause_type)
                flag = flag_by_clause[clause_type]
                status = "missing" if extraction is None or extraction.is_impossible else "found"
                extracted_preview = ""
                if extraction is not None and extraction.extracted_text:
                    extracted_preview = extraction.extracted_text[:150]
                clause_by_clause.append(
                    {
                        "clause_type": clause_type,
                        "status": status,
                        "extracted_text": extracted_preview,
                        "severity": flag.severity,
                        "recommendation": flag.recommendation,
                    }
                )

            priority_flags = [
                flag
                for flag in risk_flags
                if flag.severity in PRIORITY_SEVERITIES
            ]
            severity_rank = {"critical": 0, "high": 1}
            priority_flags.sort(key=lambda flag: severity_rank.get(flag.severity, 99))

            top_priority_actions = [
                f"{index + 1}. {flag.clause_type}: {flag.recommendation}"
                for index, flag in enumerate(priority_flags[:3])
            ]

            final_report: Dict[str, Any] = {
                "contract_title": state.contract_title,
                "session_id": state.session_id,
                "review_date": datetime.now(timezone.utc).isoformat(),
                "overall_risk_severity": overall_severity,
                "total_clauses_reviewed": PLAYBOOK_CLAUSE_COUNT,
                "clauses_found": clauses_found,
                "clauses_missing": clauses_missing,
                "total_risk_flags": total_risk_flags,
                "executive_summary": executive_summary,
                "clause_by_clause": clause_by_clause,
                "top_priority_actions": top_priority_actions,
            }

            state.shared_data["final_report"] = final_report

            rationale = (
                f"Generated executive risk brief for '{state.contract_title}' with "
                f"{total_risk_flags} non-none risk flags and overall severity "
                f"'{overall_severity}'."
            )
            output = {
                "overall_risk_severity": overall_severity,
                "total_risk_flags": total_risk_flags,
                "top_priority_actions_count": len(top_priority_actions),
            }
            self.log_trace(state, input_received, rationale, output)
            state.current_step = "complete"

        except Exception as exc:
            state.errors.append(f"SummaryAgent error: {exc}")

        return state
