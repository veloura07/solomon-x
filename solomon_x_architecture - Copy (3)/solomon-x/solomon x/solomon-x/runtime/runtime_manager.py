"""
Solomon X Subsystem Coordinator.
Coordinates startup dependencies, verification, and shutdown of all system layers:
TrustOS -> MemoryOS -> IdentityOS -> Models -> Agents -> Orchestrator -> Voice -> Avatar
"""

import logging
from typing import Dict, List, Optional
from enum import Enum

logger = logging.getLogger("solomon.runtime")

class SubsystemState(Enum):
    UNINITIALIZED = "UNINITIALIZED"
    INITIALIZING = "INITIALIZING"
    RUNNING = "RUNNING"
    DEGRADED = "DEGRADED"
    STOPPED = "STOPPED"
    FAILED = "FAILED"

class SubsystemInfo:
    def __init__(self, name: str, dependencies: List[str]):
        self.name: str = name
        self.dependencies: List[str] = dependencies
        self.state: SubsystemState = SubsystemState.UNINITIALIZED
        self.error_message: Optional[str] = None

class RuntimeManager:
    """
    Manages the lifecycle and startup sequence of all Solomon X subsystems.
    Enforces strict dependency startup ordering.
    """

    def __init__(self) -> None:
        self.subsystems: Dict[str, SubsystemInfo] = {}
        self._initialize_startup_graph()

    def _initialize_startup_graph(self) -> None:
        # Define strict startup order dependencies
        # TrustOS has no dependencies.
        # MemoryOS depends on TrustOS.
        # IdentityOS depends on TrustOS.
        # Models depend on TrustOS.
        # Agents depend on MemoryOS, IdentityOS, and Models.
        # Orchestrator depends on Agents.
        # Voice and Avatar depend on Orchestrator and Models.
        self.register_subsystem("TrustOS", [])
        self.register_subsystem("MemoryOS", ["TrustOS"])
        self.register_subsystem("IdentityOS", ["TrustOS"])
        self.register_subsystem("Models", ["TrustOS"])
        self.register_subsystem("Agents", ["MemoryOS", "IdentityOS", "Models"])
        self.register_subsystem("Orchestrator", ["Agents"])
        self.register_subsystem("Voice", ["Orchestrator", "Models"])
        self.register_subsystem("Avatar", ["Orchestrator", "Models"])

    def register_subsystem(self, name: str, dependencies: List[str]) -> None:
        """Registers a subsystem and its dependencies in the lifecycle manager."""
        self.subsystems[name] = SubsystemInfo(name, dependencies)
        logger.info(f"Registered subsystem '{name}' with dependencies: {dependencies}")

    def get_subsystem_state(self, name: str) -> SubsystemState:
        """Returns the current state of a registered subsystem."""
        if name in self.subsystems:
            return self.subsystems[name].state
        return SubsystemState.UNINITIALIZED

    async def startup_all(self) -> bool:
        """
        Sequentially boots all subsystems based on the dependency topology.
        Returns True if all systems started successfully, False otherwise.
        """
        logger.info("Initiating Solomon X runtime startup sequence...")
        
        # Simple topological sort/resolve logic for startup
        started: List[str] = []
        pending = list(self.subsystems.keys())
        
        while pending:
            progress = False
            for name in list(pending):
                info = self.subsystems[name]
                # Check if all dependencies are running
                deps_satisfied = all(
                    self.get_subsystem_state(dep) == SubsystemState.RUNNING 
                    for dep in info.dependencies
                )
                
                if deps_satisfied:
                    info.state = SubsystemState.INITIALIZING
                    logger.info(f"Initializing subsystem '{name}'...")
                    
                    # Simulate initialization tasks
                    success = await self._boot_subsystem(name)
                    if success:
                        info.state = SubsystemState.RUNNING
                        started.append(name)
                        pending.remove(name)
                        logger.info(f"Subsystem '{name}' is now RUNNING.")
                        progress = True
                    else:
                        info.state = SubsystemState.FAILED
                        info.error_message = "Startup verification failed."
                        logger.error(f"Subsystem '{name}' failed during boot. Aborting startup sequence.")
                        return False
            
            if not progress and pending:
                logger.error("Circular dependency detected or dependencies unresolvable.")
                return False
                
        logger.info("All Solomon X subsystems booted successfully.")
        return True

    async def shutdown_all(self) -> None:
        """Gracefully shuts down all active subsystems in reverse dependency order."""
        logger.info("Initiating Solomon X runtime shutdown sequence...")
        # Shutdown in reverse order of startup or registration
        active_subsystems = [name for name, info in self.subsystems.items() if info.state == SubsystemState.RUNNING]
        
        for name in reversed(active_subsystems):
            info = self.subsystems[name]
            info.state = SubsystemState.STOPPED
            logger.info(f"Subsystem '{name}' has been stopped.")

    async def _boot_subsystem(self, name: str) -> bool:
        """Boots a subsystem and registers its instances in the ServiceRegistry."""
        try:
            from core.service_registry import ServiceRegistry
            registry = ServiceRegistry()

            if name == "TrustOS":
                from trust.pcr_validator import PCRValidator
                from trust.policy_engine import PolicyEngine
                from trust.mentor_gate import MentorGate
                
                validator = PCRValidator()
                # Run boot PCR validation (will fallback to warning in sandbox without seed)
                integrity = validator.validate_boot_integrity()
                if not integrity:
                    logger.warning("Platform boot PCR validation failed. System operating in debug fallback trust mode.")
                
                # Register components in container
                registry.register(PCRValidator, validator)
                registry.register(PolicyEngine, PolicyEngine())
                registry.register(MentorGate, MentorGate())
                return True
                
            elif name == "MemoryOS":
                from python.memory.store import memory_store
                registry.register(type(memory_store), memory_store)
                return True
                
            # Generic stub fallback for remaining subsystems
            return True
        except Exception as e:
            logger.error(f"Failed to boot subsystem '{name}': {e}")
            return False
