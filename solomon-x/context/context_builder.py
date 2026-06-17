"""
Solomon X Context Builder.
Assembles prompt payloads for LLM invocation by consolidating memories, user states, and goals.
"""

import logging
from typing import Dict, Any, List

logger = logging.getLogger("solomon.context")

class ContextBuilder:
    """
    Constructs the contextual grounding frame to feed into the Model Router.
    """

    def __init__(self) -> None:
        pass

    def build_prompt_payload(
        self,
        raw_user_input: str,
        user_state: Dict[str, Any],
        relevant_memories: List[Dict[str, Any]],
        system_instructions: str
    ) -> Dict[str, Any]:
        """
        Assembles a comprehensive grounding payload for downstream model completion.
        
        Args:
            raw_user_input: The message typed/spoken by the user.
            user_state: Current user profile, active goals, and cognitive states.
            relevant_memories: Retrieved L1-L9 memory items relevant to the query.
            system_instructions: Underlying system prompts/invariants.
            
        Returns:
            A structured dict payload containing the consolidated context window map.
        """
        logger.info("Assembling contextual grounding payload...")

        # Segment active goals and profile state
        profile = user_state.get("active_profile", {})
        active_goals = user_state.get("current_context", {}).get("active_goals", [])
        cognitive_telemetry = user_state.get("cognitive_state", {})

        # Grounding text composition
        grounding_blocks = []
        
        # User details block
        grounding_blocks.append(
            f"User Profile: {profile.get('name', 'User')} | Clearance: {profile.get('role', 'Developer')} (Trust Level: {profile.get('trust_level', 1)})"
        )
        
        # Cognitive telemetry details block
        grounding_blocks.append(
            f"User Cognitive Telemetry -> Focus Index: {cognitive_telemetry.get('focus_index', 1.0)}, Load: {cognitive_telemetry.get('cognitive_load', 0.0)}, Momentum: {cognitive_telemetry.get('mental_momentum', 1.0)}"
        )

        # Active Goals segment
        if active_goals:
            goals_text = "\n".join(f"- {goal}" for goal in active_goals)
            grounding_blocks.append(f"Active Goals:\n{goals_text}")

        # Relevant Memories segment
        if relevant_memories:
            memories_text = "\n".join(
                f"[{m.get('timestamp', 'past')}] ({m.get('horizon', 'L3')}): {m.get('content', '')}"
                for m in relevant_memories
            )
            grounding_blocks.append(f"Relevant Contextual Memories:\n{memories_text}")

        # Construct final unified prompt context
        combined_grounding = "\n\n".join(grounding_blocks)

        payload = {
            "system_prompt": system_instructions,
            "grounding_context": combined_grounding,
            "user_query": raw_user_input,
            "metadata": {
                "active_project": user_state.get("current_context", {}).get("active_project_path", "")
            }
        }

        logger.debug(f"Payload generated with grounding size: {len(combined_grounding)} chars.")
        return payload
