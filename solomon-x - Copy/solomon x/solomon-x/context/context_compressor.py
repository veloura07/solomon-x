"""
Solomon X Context Compressor.
Optimizes the context window footprint by summarizing or ranking memory items.
"""

import logging
from typing import Dict, Any, List

logger = logging.getLogger("solomon.context")

class ContextCompressor:
    """
    Compresses long grounding payloads to optimize LLM input token footprints.
    """

    def __init__(self, token_limit: int = 4096) -> None:
        self.token_limit: int = token_limit

    def compress_grounding(
        self, 
        payload: Dict[str, Any], 
        approx_tokens_per_char: float = 0.25
    ) -> Dict[str, Any]:
        """
        Trims or condenses the grounding text in a prompt payload if it exceeds target token constraints.
        
        Args:
            payload: Output of ContextBuilder.
            approx_tokens_per_char: Simple heuristic ratio to convert chars to tokens.
            
        Returns:
            The optimized/compressed payload dictionary.
        """
        grounding = payload.get("grounding_context", "")
        estimated_tokens = int(len(grounding) * approx_tokens_per_char)

        if estimated_tokens <= self.token_limit:
            return payload

        logger.info(f"Context payload size ({estimated_tokens} tokens) exceeds limit ({self.token_limit}). Initiating compression...")

        # For MVP, implement a priority-based line trimmer
        # Keeps user details and active goals but truncates older episodic memories first
        lines = grounding.split("\n")
        reconstructed_lines: List[str] = []
        current_token_count = 0

        for line in lines:
            line_tokens = int(len(line) * approx_tokens_per_char)
            # Prioritize goals and profiles over episodic memory dumps
            if "Memories" in line and current_token_count + line_tokens > (self.token_limit * 0.7):
                continue
            
            if current_token_count + line_tokens <= self.token_limit:
                reconstructed_lines.append(line)
                current_token_count += line_tokens

        compressed_grounding = "\n".join(reconstructed_lines)
        payload["grounding_context"] = compressed_grounding
        payload["metadata"]["compressed"] = True

        logger.info(f"Grounding compressed down to ~{current_token_count} tokens.")
        return payload
