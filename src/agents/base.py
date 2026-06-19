from abc import ABC, abstractmethod
from typing import Any, Dict

from src.orchestrator.state import AgentState, StepExecutionTrace


class BaseAgent(ABC):
    name: str

    @abstractmethod
    async def process(self, state: AgentState) -> AgentState:
        ...

    def log_trace(
        self,
        state: AgentState,
        input_received: Dict[str, Any],
        rationale: str,
        output: Dict[str, Any],
    ) -> None:
        trace = StepExecutionTrace(
            agent_name=self.name,
            input_received=input_received,
            agent_rationale=rationale,
            output_generated=output,
        )
        state.execution_traces.append(trace)
