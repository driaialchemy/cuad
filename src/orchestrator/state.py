from pydantic import BaseModel, Field
from typing import Dict, Any, List, Optional
from datetime import datetime

class ClauseExtraction(BaseModel):
    clause_type: str
    extracted_text: str
    is_impossible: bool
    answer_start: Optional[int] = None
    question_id: str

class RiskFlag(BaseModel):
    clause_type: str
    severity: str        # "critical", "high", "medium", "low", "none"
    deviation: str
    playbook_standard: str
    extracted_value: str
    recommendation: str

class ValidationResult(BaseModel):
    clause_type: str
    ground_truth_text: str
    agent_extracted_text: str
    match: bool
    match_score: float   # 0.0 to 1.0, simple overlap ratio

class StepExecutionTrace(BaseModel):
    agent_name: str
    timestamp: datetime = Field(default_factory=datetime.utcnow)
    input_received: Dict[str, Any]
    agent_rationale: str
    output_generated: Dict[str, Any]

class AgentState(BaseModel):
    session_id: str
    contract_title: str
    current_step: str = "extraction"
    shared_data: Dict[str, Any] = Field(default_factory=dict)
    execution_traces: List[StepExecutionTrace] = Field(default_factory=list)
    errors: List[str] = Field(default_factory=list)
