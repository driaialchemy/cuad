import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List

LOGS_DIR = Path(r"C:\Users\msell\OneDrive\AIAlchemy\cuad\data\logs")


class SessionAuditReport:
    def __init__(self, session_log: List[Dict[str, Any]]) -> None:
        self.session_log = session_log

    def _severity_bucket(self, severity: str) -> str:
        normalized = severity.lower()
        if normalized == "critical":
            return "critical"
        if normalized == "high":
            return "high"
        if normalized == "medium":
            return "medium"
        return "low_none"

    def _entry_overall_severity(self, entry: Dict[str, Any]) -> str:
        final_report = entry.get("final_report", {})
        if final_report.get("overall_risk_severity"):
            return str(final_report["overall_risk_severity"])
        risk_summary = entry.get("risk_summary", {})
        if risk_summary.get("overall_severity"):
            return str(risk_summary["overall_severity"])
        return "unknown"

    def _entry_counts(self, entry: Dict[str, Any]) -> Dict[str, int]:
        final_report = entry.get("final_report", {})
        risk_summary = entry.get("risk_summary", {})
        return {
            "critical": int(risk_summary.get("critical_count", 0)),
            "high": int(risk_summary.get("high_count", 0)),
            "medium": int(risk_summary.get("medium_count", 0)),
            "low": int(risk_summary.get("low_count", 0)),
            "clauses_found": int(final_report.get("clauses_found", 0)),
            "clauses_missing": int(final_report.get("clauses_missing", 0)),
        }

    def _risk_distribution(self) -> Dict[str, int]:
        distribution = {
            "critical": 0,
            "high": 0,
            "medium": 0,
            "low_none": 0,
        }
        for entry in self.session_log:
            bucket = self._severity_bucket(self._entry_overall_severity(entry))
            distribution[bucket] += 1
        return distribution

    def _session_summary_rows(self) -> List[str]:
        rows: List[str] = []
        for entry in self.session_log:
            counts = self._entry_counts(entry)
            contract_name = entry.get("contract_title", "Unknown")
            overall_risk = self._entry_overall_severity(entry)
            timestamp = entry.get("timestamp", "")
            rows.append(
                f"| {contract_name} | {overall_risk} | {counts['critical']} | "
                f"{counts['high']} | {counts['clauses_found']} | "
                f"{counts['clauses_missing']} | {timestamp} |"
            )
        return rows

    def _per_contract_sections(self) -> List[str]:
        sections: List[str] = []
        for entry in self.session_log:
            final_report = entry.get("final_report", {})
            contract_name = entry.get("contract_title", "Unknown")
            session_id = entry.get("session_id", "")
            severity = self._entry_overall_severity(entry)
            executive_summary = final_report.get(
                "executive_summary",
                "Executive summary not available for this pipeline mode.",
            )
            top_actions = final_report.get("top_priority_actions", [])
            clause_rows = self._clause_table_rows(final_report.get("clause_by_clause", []))

            sections.extend(
                [
                    f"### {contract_name}",
                    "",
                    f"- Session ID: {session_id}",
                    f"- Risk Severity: {severity}",
                    f"- Executive Summary: {executive_summary}",
                    "- Top Priority Actions:",
                ]
            )
            if top_actions:
                for index, action in enumerate(top_actions, start=1):
                    sections.append(f"  {index}. {action}")
            else:
                sections.append("  - None recorded")

            sections.extend(
                [
                    "- Clause-by-Clause Table:",
                    "",
                    "| Clause | Status | Severity | Recommendation |",
                    "| --- | --- | --- | --- |",
                ]
            )
            sections.extend(clause_rows)
            sections.append("")

        return sections

    def _clause_table_rows(self, clause_entries: List[Dict[str, Any]]) -> List[str]:
        rows: List[str] = []
        for clause in clause_entries:
            rows.append(
                f"| {clause.get('clause_type', '')} | {clause.get('status', '')} | "
                f"{clause.get('severity', '')} | {clause.get('recommendation', '')} |"
            )
        if not rows:
            rows.append("| — | — | — | No clause data available |")
        return rows

    def generate(self, output_path: str) -> str:
        generated_at = datetime.now(timezone.utc).isoformat()
        distribution = self._risk_distribution()
        summary_rows = self._session_summary_rows()
        per_contract = self._per_contract_sections()

        lines: List[str] = [
            "# CUAD Pipeline — Session Audit Report",
            f"Generated: {generated_at}",
            f"Total Contracts Reviewed: {len(self.session_log)}",
            "",
            "## Session Summary Table",
            "",
            "| Contract Name | Overall Risk | Critical Flags | High Flags | "
            "Clauses Found | Clauses Missing | Session Timestamp |",
            "| --- | --- | --- | --- | --- | --- | --- |",
        ]
        lines.extend(summary_rows)
        lines.extend(
            [
                "",
                "## Risk Distribution",
                "",
                f"- Contracts rated CRITICAL: {distribution['critical']}",
                f"- Contracts rated HIGH: {distribution['high']}",
                f"- Contracts rated MEDIUM: {distribution['medium']}",
                f"- Contracts rated LOW/NONE: {distribution['low_none']}",
                "",
                "## Per-Contract Detail",
                "",
            ]
        )
        lines.extend(per_contract)

        output = Path(output_path)
        output.parent.mkdir(parents=True, exist_ok=True)
        output.write_text("\n".join(lines), encoding="utf-8")
        return str(output.resolve())

    def to_json(self, output_path: str) -> str:
        output = Path(output_path)
        output.parent.mkdir(parents=True, exist_ok=True)
        output.write_text(
            json.dumps(self.session_log, indent=2, default=str),
            encoding="utf-8",
        )
        return str(output.resolve())
