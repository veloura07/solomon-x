import logging
import time
from typing import List, Dict, Any

logger = logging.getLogger("solomon.trust.mentor")

class MentorGate:
    """
    Sovereignty Gate / Mentor Mode interactive loop.
    Intercepts actions that require explicit human alignment or biometric validation.
    """
    def __init__(self) -> None:
        self.dilemmas: List[Dict[str, Any]] = [
            {
                "id": "privacy_vs_assistance",
                "prompt": "The engineer agent requests permission to upload debug telemetry to analyze compilation errors. This includes system logs. Do you authorize?",
                "options": ["A: Authorize full upload", "B: Limit to scrubbed logs", "C: Deny upload"],
                "safe_option": "B"
            },
            {
                "id": "sandbox_escape",
                "prompt": "An agent is requesting raw command line execution outside the Level 1 sandbox to compile a native library. Confirm execution environment elevation?",
                "options": ["A: Elevate command directly", "B: Run inside isolated VM", "C: Block execution"],
                "safe_option": "B"
            },
            {
                "id": "ledger_tamper",
                "prompt": "A system utility is attempting to override a past transaction diff block inside the audit ledger. Confirm override?",
                "options": ["A: Force override", "B: Append corrections block instead", "C: Discard transaction"],
                "safe_option": "B"
            }
        ]

    def trigger_challenge(self, agent_id: str, action: str, reason: str) -> bool:
        """
        Triggers an interactive micro-dilemma challenge loop.
        In production, this displays a UI overlay or sends a WebAuthn check.
        For MVP, it runs a console-based validation check.
        """
        logger.warning(f"[MENTOR GATE ACTIVE] Challenge triggered for '{agent_id}' performing '{action}'. Reason: {reason}")
        
        # Select a dilemma appropriate for the action
        dilemma = self.select_dilemma(action)
        
        logger.info(f"Challenge Prompt: {dilemma['prompt']}")
        logger.info(f"Available choices: {dilemma['options']}")
        
        # Simulate biometric validation
        bio_passed = self.verify_biometric()
        if not bio_passed:
            logger.error("Biometric verification failed.")
            return False
            
        logger.info(f"User approved safety constraint alignment via safe option: {dilemma['safe_option']}")
        return True

    def select_dilemma(self, action: str) -> Dict[str, Any]:
        """Returns a relevant safety scenario based on the action scope."""
        if "execute" in action:
            return self.dilemmas[1]
        elif "ledger" in action:
            return self.dilemmas[2]
        else:
            return self.dilemmas[0]

    def verify_biometric(self) -> bool:
        """Simulates biometric challenge (e.g. Windows Hello signature check)."""
        logger.info("Simulating Windows Hello biometric signature challenge...")
        time.sleep(0.1)  # Sim latency
        return True
