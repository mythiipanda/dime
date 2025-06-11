"""
Base class for LangGraph agents, providing a common interface for execution.
"""

from abc import ABC, abstractmethod
from typing import Dict, Any
from langgraph_agent.state import AgentState

class BaseAgent(ABC):
    """
    Abstract base class for all specialized agents in the LangGraph workflow.
    Defines the common interface for agent execution.
    """

    @abstractmethod
    def execute(self, state: AgentState) -> Dict[str, Any]:
        """
        Executes the logic for this agent, processing the current state
        and returning updates to the state.

        Args:
            state: The current AgentState.

        Returns:
            A dictionary of state updates.
        """
        pass