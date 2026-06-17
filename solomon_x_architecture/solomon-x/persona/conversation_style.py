"""
Solomon X Persona Conversation Style Engine.
Dynamically calculates response parameters based on active profiles and user state.
"""

import logging
from typing import Dict, Any
from pydantic import BaseModel, Field

logger = logging.getLogger("solomon.persona")

class StyleMetrics(BaseModel):
    formality: float = Field(default=0.5, ge=0.0, le=1.0)
    humor: float = Field(default=0.5, ge=0.0, le=1.0)
    empathy: float = Field(default=0.5, ge=0.0, le=1.0)
    verbosity: float = Field(default=0.5, ge=0.0, le=1.0)

class ConversationStyleManager:
    """
    Adjusts LLM conversational behaviors dynamically based on cognitive load levels.
    """

    def __init__(self) -> None:
        self.default_style = StyleMetrics()

    def determine_optimal_style(
        self,
        focus_index: float,
        cognitive_load: float,
        user_preference: Dict[str, Any]
    ) -> StyleMetrics:
        """
        Adapts formality, humor, empathy, and verbosity based on metrics.
        If cognitive load is high, reduces verbosity and humor to minimize friction.
        """
        logger.info(f"Computing optimal conversational style for load: {cognitive_load:.2f}")

        # Extract base preferences
        pref_style = user_preference.get("preferred_style", "mentor")
        humor_weight = user_preference.get("humor_intensity", 0.5)
        empathy_weight = user_preference.get("empathy_index", 0.5)

        # Base defaults
        formality = 0.6
        verbosity = 0.5
        humor = humor_weight
        empathy = empathy_weight

        if pref_style == "companion":
            humor = min(1.0, humor + 0.2)
            formality = 0.3
        elif pref_style == "strategist":
            formality = 0.8
            verbosity = 0.4
            humor = max(0.0, humor - 0.2)

        # Adapt to cognitive load
        if cognitive_load > 0.7:
            # Drop verbosity, humors to avoid distracting the user
            logger.warning("Spike in cognitive load detected. Restricting conversation payload footprint.")
            verbosity = 0.2
            humor = max(0.0, humor - 0.4)
            formality = min(1.0, formality + 0.1)

        return StyleMetrics(
            formality=formality,
            humor=humor,
            empathy=empathy,
            verbosity=verbosity
        )
