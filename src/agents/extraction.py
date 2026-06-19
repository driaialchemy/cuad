import asyncio
import json
import re
import zipfile
from pathlib import Path
from typing import Any, Dict, List, Optional, Set

from src.agents.base import BaseAgent
from src.orchestrator.state import AgentState, ClauseExtraction

DATA_ZIP_PATH = Path(r"C:\Users\msell\OneDrive\AIAlchemy\cuaddataset\data.zip")
CUAD_JSON_NAME = "CUADv1.json"
CLAUSE_PATTERN = re.compile(r'related to ["\']([^"\']+)["\']')

PROJECT_ROOT = Path(__file__).resolve().parent.parent.parent
PLAYBOOK_PATH = PROJECT_ROOT / "data" / "playbook.json"


def _load_playbook_clause_types() -> Set[str]:
    with open(PLAYBOOK_PATH, encoding="utf-8") as playbook_file:
        playbook_data: Dict[str, Any] = json.load(playbook_file)
    return set(playbook_data.keys())


def _load_contract_from_zip(zip_path: Path, contract_title: str) -> Dict[str, Any]:
    with zipfile.ZipFile(zip_path, "r") as archive:
        raw_json = archive.read(CUAD_JSON_NAME)
    dataset: Dict[str, Any] = json.loads(raw_json)
    for contract in dataset.get("data", []):
        if contract.get("title") == contract_title:
            return contract
    raise ValueError(f"Contract not found in CUAD dataset: {contract_title}")


def _extract_clause_type(question: str) -> Optional[str]:
    match = CLAUSE_PATTERN.search(question)
    if match:
        return match.group(1)
    return None


def _build_extractions(contract: Dict[str, Any], playbook_types: Set[str]) -> tuple[List[ClauseExtraction], str]:
    extractions: List[ClauseExtraction] = []
    contract_context = ""

    paragraphs = contract.get("paragraphs", [])
    if paragraphs:
        contract_context = paragraphs[0].get("context", "")

    for paragraph in paragraphs:
        for qa in paragraph.get("qas", []):
            clause_type = _extract_clause_type(qa.get("question", ""))
            if clause_type is None or clause_type not in playbook_types:
                continue

            is_impossible = bool(qa.get("is_impossible", False))
            answers = qa.get("answers", [])
            question_id = qa.get("id", "")

            if is_impossible or not answers:
                extractions.append(
                    ClauseExtraction(
                        clause_type=clause_type,
                        extracted_text="",
                        is_impossible=True,
                        answer_start=None,
                        question_id=question_id,
                    )
                )
            else:
                first_answer = answers[0]
                extractions.append(
                    ClauseExtraction(
                        clause_type=clause_type,
                        extracted_text=first_answer.get("text", ""),
                        is_impossible=False,
                        answer_start=first_answer.get("answer_start"),
                        question_id=question_id,
                    )
                )

    return extractions, contract_context


class ExtractionAgent(BaseAgent):
    name = "ExtractionAgent"

    async def process(self, state: AgentState) -> AgentState:
        if state.current_step != "extraction":
            return state

        input_received = {
            "contract_title": state.contract_title,
            "current_step": state.current_step,
        }

        try:
            playbook_types = await asyncio.to_thread(_load_playbook_clause_types)
            contract = await asyncio.to_thread(
                _load_contract_from_zip, DATA_ZIP_PATH, state.contract_title
            )
            extractions, contract_context = _build_extractions(contract, playbook_types)

            found_count = sum(1 for item in extractions if not item.is_impossible)
            impossible_count = sum(1 for item in extractions if item.is_impossible)

            state.shared_data["extractions"] = [item.model_dump() for item in extractions]
            state.shared_data["contract_context"] = contract_context[:5000]

            rationale = (
                f"Extracted {len(extractions)} playbook clause entries from contract "
                f"'{state.contract_title}': {found_count} clauses found with text, "
                f"{impossible_count} marked impossible (absent)."
            )
            output = {
                "extraction_count": len(extractions),
                "found_count": found_count,
                "impossible_count": impossible_count,
            }
            self.log_trace(state, input_received, rationale, output)
            state.current_step = "risk_assessment"

        except Exception as exc:
            state.errors.append(f"ExtractionAgent error: {exc}")

        return state
