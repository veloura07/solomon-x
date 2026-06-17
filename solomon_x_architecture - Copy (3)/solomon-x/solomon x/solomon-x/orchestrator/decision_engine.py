"""
Solomon X Decision Engine.
Evaluates agent suitability for tasks using capability/trust utility formulas.
"""

import logging
from typing import Dict, List, Any
from pydantic import BaseModel

logger = logging.getLogger("solomon.orchestrator")

class AgentProposalScore(BaseModel):
    agent_id: str
    confidence: float
    trust: float
    capability: float
    goal_alignment: float
    composite_score: float

class DecisionEngine:
    """
    Selects the optimal agent congregation or executor for any incoming user task.
    Replaces economic VCG bidding loops with deterministic capability/trust scoring.
    """

    def __init__(self) -> None:
        pass

    def select_best_executor(
        self,
        task_requirements: Dict[str, Any],
        candidate_agents: List[Dict[str, Any]]
    ) -> AgentProposalScore:
        """
        Calculates utility scores for candidate agents using:
        Score = Confidence * Trust * Capability * Goal Alignment
        
        Args:
            task_requirements: Requirements dictionary (e.g. required capabilities, goals).
            candidate_agents: List of available agents with their capabilities and stats.
            
        Returns:
            The highest scoring AgentProposalScore.
        """
        logger.info("Evaluating candidate agents for the active task...")
        
        scored_proposals: List[AgentProposalScore] = []
        
        for agent in candidate_agents:
            agent_id = agent.get("id", "agent_unknown")
            confidence = agent.get("confidence_rating", 0.5)
            trust = agent.get("trust_level", 0.5)
            
            # Capability matching score (simple overlap check)
            required_caps = task_requirements.get("required_capabilities", [])
            provided_caps = agent.get("capabilities", [])
            if required_caps:
                overlap = set(required_caps).intersection(set(provided_caps))
                capability = len(overlap) / len(required_caps)
            else:
                capability = 0.5
                
            # Goal alignment matching score
            goal_alignment = agent.get("goal_alignment_index", 0.5)
            
            # Core MVP scoring formula
            composite = confidence * trust * capability * goal_alignment
            
            proposal = AgentProposalScore(
                agent_id=agent_id,
                confidence=confidence,
                trust=trust,
                capability=capability,
                goal_alignment=goal_alignment,
                composite_score=composite
            )
            scored_proposals.append(proposal)
            logger.debug(f"Agent '{agent_id}' scored: {composite:.4f}")

        if not scored_proposals:
            raise ValueError("No candidates available to execute the task.")

        # Sort descending and return the best
        scored_proposals.sort(key=lambda x: x.composite_score, reverse=True)
        winner = scored_proposals[0]
        
        logger.info(f"Selected executor: '{winner.agent_id}' with score: {winner.composite_score:.4f}")
        return winner
