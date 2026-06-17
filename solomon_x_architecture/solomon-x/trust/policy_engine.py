import os
import json
import logging
from typing import Dict, Any, List

logger = logging.getLogger("solomon.trust.policy")

class PolicyEngine:
    """
    Rego-lite Policy Engine for Solomon X.
    Evaluates actions against a granular permission matrix.
    Supports JSON-based rules representation of Rego security policies.
    """
    def __init__(self, policy_path: str = "./config/policies.json"):
        self.policy_path = policy_path
        self.permissions: Dict[str, Any] = {}
        self._load_default_policies()

    def _load_default_policies(self):
        """Loads permission matrix from config, falling back to a secure default if missing."""
        target_path = self.policy_path
        if not os.path.isabs(target_path) and not os.path.exists(target_path):
            # Fall back to root relative config directory if run from subdir
            target_path = os.path.join(os.getcwd(), "config", "policies.json")

        if os.path.exists(target_path):
            try:
                with open(target_path, "r") as f:
                    self.permissions = json.load(f)
                return
            except Exception as e:
                logger.error(f"Failed to load policy file {target_path}: {e}")
        
        # Secure default policy matrix matching core Solomon-X spec
        self.permissions = {
            "version": "1.0",
            "roles": {
                "guardian_core": {"trust_level": 3, "allowed_scopes": ["*"]},
                "engineer_spec": {"trust_level": 2, "allowed_scopes": ["read_memory", "write_memory", "execute_command"]},
                "strategist_core": {"trust_level": 2, "allowed_scopes": ["read_memory", "write_memory"]},
                "companion_core": {"trust_level": 1, "allowed_scopes": ["read_memory"]}
            },
            "actions": {
                "read_memory": {"min_trust": 1, "min_confidence": 0.5},
                "write_memory": {"min_trust": 2, "min_confidence": 0.7, "requires_approval_below": 0.85},
                "execute_command": {"min_trust": 2, "min_confidence": 0.85, "requires_approval_below": 0.95},
                "network_access": {"min_trust": 3, "min_confidence": 0.9, "requires_approval_below": 0.98},
                "modify_ledger": {"min_trust": 3, "min_confidence": 0.95, "requires_approval_below": 1.0}
            }
        }
        self.save_policies(target_path)

    def save_policies(self, path: str = None):
        target_path = path or self.policy_path
        os.makedirs(os.path.dirname(target_path), exist_ok=True)
        try:
            with open(target_path, "w") as f:
                json.dump(self.permissions, f, indent=4)
        except Exception as e:
            logger.error(f"Failed to save policies to {target_path}: {e}")

    def evaluate_rule(self, agent_id: str, action: str, confidence: float) -> Dict[str, Any]:
        """
        Evaluates whether an agent is allowed to execute an action.
        Returns:
            Dict containing:
                - "allow": bool
                - "reason": str
                - "requires_mentor_gate": bool
        """
        # 1. Resolve agent role and allowed scopes
        role_info = self.permissions["roles"].get(agent_id)
        if not role_info:
            return {"allow": False, "reason": f"Agent '{agent_id}' is unrecognized.", "requires_mentor_gate": False}

        trust_level = role_info["trust_level"]
        allowed_scopes = role_info["allowed_scopes"]

        # 2. Check scope wildcard or exact match
        if "*" not in allowed_scopes and action not in allowed_scopes:
            return {
                "allow": False,
                "reason": f"Agent '{agent_id}' lacks permission scope for '{action}'.",
                "requires_mentor_gate": False
            }

        # 3. Resolve action constraints
        action_constraints = self.permissions["actions"].get(action)
        if not action_constraints:
            return {
                "allow": False,
                "reason": f"Action '{action}' is not defined in permission matrix.",
                "requires_mentor_gate": False
            }

        min_trust = action_constraints["min_trust"]
        min_confidence = action_constraints["min_confidence"]
        requires_approval_below = action_constraints.get("requires_approval_below", 0.0)

        # 4. Enforce trust tier check
        if trust_level < min_trust:
            return {
                "allow": False,
                "reason": f"Agent trust level ({trust_level}) is below action requirement ({min_trust}).",
                "requires_mentor_gate": False
            }

        # 5. Enforce confidence checks
        if confidence < min_confidence:
            return {
                "allow": False,
                "reason": f"Execution confidence ({confidence}) is below minimal action threshold ({min_confidence}).",
                "requires_mentor_gate": False
            }

        # 6. Check if it triggers the Mentor Mode interactive challenge gate
        if confidence < requires_approval_below:
            return {
                "allow": True,
                "reason": f"Action is permitted but requires Mentor Mode challenge validation.",
                "requires_mentor_gate": True
            }

        return {
            "allow": True,
            "reason": "Action authorized autonomously.",
            "requires_mentor_gate": False
        }
