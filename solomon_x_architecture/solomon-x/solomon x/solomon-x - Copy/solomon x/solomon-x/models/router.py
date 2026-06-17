"""
Solomon X Model Router.
Dispatches prompt payloads to the designated model provider.
"""

import logging
from typing import Dict, Any, Optional

logger = logging.getLogger("solomon.models")

class ModelRouter:
    """
    Decides which model configuration and provider gets queried for a given context frame.
    Supports fallback pathways for resilience.
    """

    def __init__(self) -> None:
        self.default_model: str = "qwen2.5:1.5b"

    async def route_completion(
        self,
        payload: Dict[str, Any],
        preferred_model: Optional[str] = None
    ) -> str:
        """
        Dispatches prompt requests to the appropriate model wrapper.
        
        Args:
            payload: Grounding payload compiled by ContextBuilder and ContextCompressor.
            preferred_model: Optional override model ID (e.g. 'phi3', 'qwen2.5:1.5b').
            
        Returns:
            The raw text completion result.
        """
        target_model = preferred_model or self.default_model
        logger.info(f"Routing completion payload to model: '{target_model}'")

        # Mock dispatch logic
        if "phi3" in target_model.lower():
            logger.info("Delegating execution to Phi3Provider adapter...")
            from models.providers.phi3 import Phi3Provider
            provider = Phi3Provider()
            return await provider.generate_completion(payload)
        
        # Default fallback (Ollama client mock or similar)
        logger.debug("Running default Qwen path completion...")
        return f"Hello, I am Solomon. I processed your request: '{payload.get('user_query')}'"
