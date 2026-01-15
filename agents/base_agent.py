from abc import ABC, abstractmethod
from typing import Any, Dict, List, Optional, Callable
from swarm import Agent as SwarmAgent


class BaseAgent(ABC):
    """Base class for all agents"""

    def __init__(self, name: str, instructions: str, functions: List[Callable]):
        """
        Initialize the agent

        Args:
            name (str): Agent name
            instructions (str): Agent instructions
            functions (List[Callable]): List of functions this agent can use
        """
        self.name = name
        self.instructions = instructions
        self.functions = functions
        self.swarm_agent = SwarmAgent(
            name=name,
            model="claude",  # デフォルトモデル
            instructions=instructions,
            functions=functions,
        )

    def get_agent(self) -> SwarmAgent:
        """Get the swarm agent instance"""
        return self.swarm_agent

    def get_functions(self) -> List[Callable]:
        """Get the list of functions this agent can use"""
        return self.functions

    def get_instructions(self) -> str:
        """Get the agent's instructions"""
        return self.instructions

    @abstractmethod
    async def process(self, query: str) -> str:
        """
        Process a query and return a response

        Args:
            query (str): The query to process

        Returns:
            str: The response to the query
        """
        pass
