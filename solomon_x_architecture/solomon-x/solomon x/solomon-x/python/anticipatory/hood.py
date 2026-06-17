import os
import json
import logging
from typing import List, Tuple, Dict

logger = logging.getLogger("solomon.anticipatory.hood")

class HOODTracker:
    """
    Hidden-Markov-Model-lite (HOOD) for online workflow anticipation.
    Tracks state transitions dynamically based on user context sequences.
    """
    def __init__(self, model_path: str = "./data/hood_model.json") -> None:
        self.model_path = model_path
        self.transitions: Dict[str, Dict[str, int]] = {}
        self.state_totals: Dict[str, int] = {}
        self.load_model()

    def load_model(self) -> None:
        target_path = self.model_path
        if not os.path.isabs(target_path) and not os.path.exists(target_path):
            target_path = os.path.join(os.getcwd(), "data", "hood_model.json")

        if os.path.exists(target_path):
            try:
                with open(target_path, "r") as f:
                    data = json.load(f)
                    self.transitions = data.get("transitions", {})
                    self.state_totals = data.get("state_totals", {})
                return
            except Exception as e:
                logger.error(f"Failed to load HOOD model: {e}")

        # Initialize with baseline defaults representing typical developer flows
        self.transitions = {
            "idle": {"code": 5, "browse": 3, "pause": 2},
            "code": {"debug": 6, "compile": 4, "idle": 2},
            "debug": {"code": 8, "compile": 3, "pause": 1},
            "compile": {"debug": 3, "code": 5, "idle": 2}
        }
        self.state_totals = {
            "idle": 10,
            "code": 12,
            "debug": 12,
            "compile": 10
        }
        self.save_model(target_path)

    def save_model(self, path: str = None) -> None:
        target_path = path or self.model_path
        os.makedirs(os.path.dirname(target_path), exist_ok=True)
        try:
            with open(target_path, "w") as f:
                json.dump({
                    "transitions": self.transitions,
                    "state_totals": self.state_totals
                }, f, indent=4)
        except Exception as e:
            logger.error(f"Failed to save HOOD model to {target_path}: {e}")

    def observe(self, previous_state: str, current_state: str) -> None:
        """
        Record a transition sequence event.
        Updates model frequency counts online.
        """
        prev = str(previous_state).strip().lower()
        curr = str(current_state).strip().lower()

        if prev not in self.transitions:
            self.transitions[prev] = {}
        
        self.transitions[prev][curr] = self.transitions[prev].get(curr, 0) + 1
        self.state_totals[prev] = self.state_totals.get(prev, 0) + 1
        
        logger.debug(f"HOOD: Observed transition {prev} -> {curr}")
        self.save_model()

    def predict(self, current_state: str, limit: int = 3) -> List[Tuple[str, float]]:
        """
        Calculates outcome probabilities based on transition counts.
        """
        curr = str(current_state).strip().lower()
        
        state_transitions = self.transitions.get(curr)
        total = self.state_totals.get(curr, 0)
        
        if not state_transitions or total == 0:
            # Fallback uniform probability distribution
            return [("idle", 0.5), ("continue_task", 0.5)]

        predictions = []
        for next_state, count in state_transitions.items():
            prob = float(count) / float(total)
            predictions.append((next_state, prob))

        # Sort by probability descending
        predictions.sort(key=lambda x: x[1], reverse=True)
        return predictions[:limit]
