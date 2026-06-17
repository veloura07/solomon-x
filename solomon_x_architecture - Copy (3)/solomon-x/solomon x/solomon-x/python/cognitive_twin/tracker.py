import os
import time
import json
import logging
import threading
from typing import Dict, Any

logger = logging.getLogger("solomon.cognitive.tracker")

class CognitiveTracker:
    """
    Cognitive Twin Telemetry Tracker.
    Calculates Focus Index, Cognitive Load, and Mental Momentum indices.
    Hooks keyboard/mouse timing distributions or simulates fluctuations in headless environments.
    """
    def __init__(self, state_path: str = "./state/current_user_state.json") -> None:
        self.state_path = state_path
        self.focus_index = 0.85
        self.cognitive_load = 0.35
        self.mental_momentum = 0.72
        
        # Internal raw variables
        self.last_input_time = time.time()
        self.keystroke_intervals = []
        self.mouse_move_times = []
        
        self.running = False
        self.listener_thread = None
        self._try_init_pynput()

    def _try_init_pynput(self) -> None:
        try:
            import pynput
            self.has_pynput = True
            logger.info("pynput available. Initializing physical I/O telemetry listeners.")
        except ImportError:
            self.has_pynput = False
            logger.warning("pynput not installed. Telemetry tracker will run in simulated fallback loop.")

    def start(self) -> None:
        self.running = True
        if self.has_pynput:
            self._start_physical_listeners()
        else:
            self._start_simulation_loop()

    def stop(self) -> None:
        self.running = False
        if self.listener_thread:
            self.listener_thread.join(timeout=1.0)
            logger.info("Cognitive tracker thread stopped.")

    def _start_physical_listeners(self) -> None:
        from pynput import keyboard, mouse
        
        def on_press(key):
            now = time.time()
            interval = now - self.last_input_time
            self.last_input_time = now
            
            self.keystroke_intervals.append(interval)
            if len(self.keystroke_intervals) > 100:
                self.keystroke_intervals.pop(0)
                
            self._calculate_metrics()

        def on_move(x, y):
            now = time.time()
            self.last_input_time = now
            self.mouse_move_times.append(now)
            if len(self.mouse_move_times) > 100:
                self.mouse_move_times.pop(0)
            self._calculate_metrics()

        # Spawning pynput async listener threads
        self.k_listener = keyboard.Listener(on_press=on_press)
        self.m_listener = mouse.Listener(on_move=on_move)
        
        self.k_listener.start()
        self.m_listener.start()
        
        # Spawn daemon update thread
        self.listener_thread = threading.Thread(target=self._update_loop, daemon=True)
        self.listener_thread.start()
        logger.info("Physical I/O hooks launched successfully.")

    def _start_simulation_loop(self) -> None:
        self.listener_thread = threading.Thread(target=self._update_loop, daemon=True)
        self.listener_thread.start()
        logger.info("Simulated telemetry loop launched successfully.")

    def _update_loop(self) -> None:
        """Periodic background update thread to compute metrics and sync state."""
        import random
        while self.running:
            time.sleep(3.0) # Sync intervals
            
            if not self.has_pynput:
                # Generate realistic random-walk time-series fluctuations
                self.focus_index = max(0.1, min(1.0, self.focus_index + random.uniform(-0.05, 0.05)))
                self.cognitive_load = max(0.0, min(1.0, self.cognitive_load + random.uniform(-0.08, 0.08)))
                self.mental_momentum = max(0.1, min(1.0, self.mental_momentum + random.uniform(-0.05, 0.05)))
            else:
                # Standard decay over idle periods
                idle_duration = time.time() - self.last_input_time
                if idle_duration > 15.0:
                    self.focus_index = max(0.5, self.focus_index - 0.02)
                    self.mental_momentum = max(0.2, self.mental_momentum - 0.05)
            
            self._write_state_to_disk()

    def _calculate_metrics(self) -> None:
        """Calculates telemetry metrics based on actual input timings."""
        import numpy as np
        if not self.keystroke_intervals:
            return

        # Focus: derived from typing interval standard deviation (consistency)
        if len(self.keystroke_intervals) > 5:
            std_dev = np.std(self.keystroke_intervals)
            # High consistency -> Low std_dev -> High focus
            self.focus_index = max(0.1, min(1.0, 1.0 - (std_dev / 2.0)))
        
        # Momentum: typing density over the last 30 seconds
        now = time.time()
        activity_window = [t for t in self.mouse_move_times if now - t < 10.0]
        self.mental_momentum = max(0.1, min(1.0, len(self.keystroke_intervals) / 50.0 + len(activity_window) / 100.0))

        # Load: variance in mouse moves and high typing rates
        self.cognitive_load = max(0.0, min(1.0, (self.focus_index * 0.4) + (self.mental_momentum * 0.6)))

    def _write_state_to_disk(self) -> None:
        """Persists the updated state vector to current_user_state.json."""
        target_path = self.state_path
        if not os.path.isabs(target_path) and not os.path.exists(target_path):
            target_path = os.path.join(os.getcwd(), "state", "current_user_state.json")

        if os.path.exists(target_path):
            try:
                # Load current
                with open(target_path, "r") as f:
                    state = json.load(f)
                
                # Update cognitive metrics
                state["cognitive_state"] = {
                    "focus_index": round(self.focus_index, 3),
                    "cognitive_load": round(self.cognitive_load, 3),
                    "mental_momentum": round(self.mental_momentum, 3),
                    "last_updated": time.time()
                }
                
                # Write back
                with open(target_path, "w") as f:
                    json.dump(state, f, indent=2)
            except Exception as e:
                logger.error(f"Failed to sync telemetry to disk: {e}")

    def get_state_vector(self) -> Dict[str, float]:
        return {
            "focus_index": self.focus_index,
            "cognitive_load": self.cognitive_load,
            "mental_momentum": self.mental_momentum
        }

if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)
    tracker = CognitiveTracker()
    tracker.start()
    try:
        for _ in range(5):
            time.sleep(2)
            print(f"Active telemetry: {tracker.get_state_vector()}")
    finally:
        tracker.stop()
