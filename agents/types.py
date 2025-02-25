from dataclasses import dataclass
from typing import Dict, Any, Optional, List

@dataclass
class AgentResponse:
    agent_name: str
    response: str

@dataclass
class ToolResponse:
    success: bool
    output: str

@dataclass
class OrchestratorConfiguration:
    agents: List[Any]
    default_agent_name: str