"""
Solomon X Agent Registry.
Registers and exposes capability configurations for the 4 core agents:
Guardian Core, Engineer Specialist, Strategist Core, Companion Core
"""

import logging
from typing import Dict, List, Any, Optional
from pydantic import BaseModel, Field

logger = logging.getLogger("solomon.agents")

class AgentMetadata(BaseModel):
    id: str
    name: str
    capabilities: List[str]
    confidence_rating: float = Field(default=0.8, ge=0.0, le=1.0)
    trust_level: float = Field(default=0.8, ge=0.0, le=1.0)
    goal_alignment_index: float = Field(default=0.9, ge=0.0, le=1.0)
    system_role: str

class AgentRegistry:
    """
    Maintains active profiles and configuration states for Solomon X agent nodes.
    """

    def __init__(self) -> None:
        self._agents: Dict[str, AgentMetadata] = {}
        self._load_core_agents()

    def _load_core_agents(self) -> None:
        """Bootstraps configuration vectors for the 4 core agents."""
        self.register_agent(AgentMetadata(
            id="guardian_core",
            name="Guardian Core",
            capabilities=["verify_permissions", "validate_signature", "audit_log"],
            confidence_rating=0.95,
            trust_level=0.99,
            goal_alignment_index=1.0,
            system_role="Security, boundary constraint compliance, and permission gating."
        ))
        
        self.register_agent(AgentMetadata(
            id="engineer_spec",
            name="Engineer Specialist",
            capabilities=["compile_workspace", "write_file", "execute_terminal", "git_commit"],
            confidence_rating=0.88,
            trust_level=0.85,
            goal_alignment_index=0.90,
            system_role="Code design, synthesis, automated testing, and execution tasks."
        ))

        self.register_agent(AgentMetadata(
            id="strategist_core",
            name="Strategist Core",
            capabilities=["decompose_goal", "schedule_milestone", "prioritize_task"],
            confidence_rating=0.90,
            trust_level=0.90,
            goal_alignment_index=0.95,
            system_role="Goal gravity assessment, task sequencing, and project planning."
        ))

        self.register_agent(AgentMetadata(
            id="companion_core",
            name="Companion Core",
            capabilities=["generate_reply", "parse_sentiment", "adjust_style"],
            confidence_rating=0.85,
            trust_level=0.95,
            goal_alignment_index=0.95,
            system_role="Aesthetic conversation, style tracking, and user empathy interface."
        ))

    def register_agent(self, agent: AgentMetadata) -> None:
        """Adds or updates an agent in the registry."""
        self._agents[agent.id] = agent
        logger.info(f"Registered agent: '{agent.name}' (ID: {agent.id})")

    def get_agent(self, agent_id: str) -> Optional[AgentMetadata]:
        """Retrieves metadata of a registered agent by ID."""
        return self._agents.get(agent_id)

    def list_agents(self) -> List[Dict[str, Any]]:
        """Returns raw dict representation of all active agents."""
        return [agent.model_dump() for agent in self._agents.values()]
