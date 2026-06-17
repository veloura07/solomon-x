"""
Solomon X Lifecycle Management and Monitoring.
Defines states, transitions, heartbeat checks, and health metrics.
"""

import time
import logging
from typing import Dict, Any, Optional

logger = logging.getLogger("solomon.lifecycle")

class SystemHealth:
    """
    Tracks telemetry, latency indicators, and heartbeat statuses for running services.
    """
    def __init__(self) -> None:
        self.start_time: float = time.time()
        self.heartbeats: Dict[str, float] = {}
        self.latencies: Dict[str, float] = {}
        self.failure_counts: Dict[str, int] = {}

    def record_heartbeat(self, subsystem: str) -> None:
        """Records a heartbeat timestamp for a subsystem."""
        self.heartbeats[subsystem] = time.time()
        logger.debug(f"Heartbeat received from subsystem '{subsystem}'")

    def record_latency(self, subsystem: str, latency_ms: float) -> None:
        """Records service execution latency metrics."""
        self.latencies[subsystem] = latency_ms

    def record_failure(self, subsystem: str, error: Optional[str] = None) -> None:
        """Records a failure event and logs diagnostics."""
        self.failure_counts[subsystem] = self.failure_counts.get(subsystem, 0) + 1
        logger.error(f"Failure occurred in subsystem '{subsystem}': {error or 'Unknown error'}")

    def get_uptime(self) -> float:
        """Returns overall system uptime in seconds."""
        return time.time() - self.start_time

    def get_diagnostic_report(self) -> Dict[str, Any]:
        """Assembles a full telemetry and diagnostic status report."""
        report = {
            "uptime_seconds": self.get_uptime(),
            "active_heartbeats": {k: time.time() - v for k, v in self.heartbeats.items()},
            "recorded_latencies_ms": self.latencies,
            "failure_events": self.failure_counts,
        }
        return report
