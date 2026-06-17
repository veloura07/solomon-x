import pytest
import asyncio
from runtime.runtime_manager import RuntimeManager, SubsystemState
from core.service_registry import ServiceRegistry

@pytest.fixture(autouse=True)
def clean_registry():
    ServiceRegistry().clear()
    yield
    ServiceRegistry().clear()

def test_runtime_startup_and_shutdown():
    async def run_sequence():
        manager = RuntimeManager()
        
        # Verify initial state
        assert manager.get_subsystem_state("TrustOS") == SubsystemState.UNINITIALIZED
        assert manager.get_subsystem_state("MemoryOS") == SubsystemState.UNINITIALIZED
        
        # Perform dependency-ordered boot
        success = await manager.startup_all()
        assert success
        
        # Confirm states transitioned to RUNNING
        assert manager.get_subsystem_state("TrustOS") == SubsystemState.RUNNING
        assert manager.get_subsystem_state("MemoryOS") == SubsystemState.RUNNING
        
        # Confirm that systems populated the ServiceRegistry container
        registry = ServiceRegistry()
        from trust.pcr_validator import PCRValidator
        from trust.policy_engine import PolicyEngine
        from trust.mentor_gate import MentorGate
        from python.memory.store import MemoryStore
        
        assert registry.has_service(PCRValidator)
        assert registry.has_service(PolicyEngine)
        assert registry.has_service(MentorGate)
        assert registry.has_service(MemoryStore)
        
        # Graceful reverse-order shutdown
        await manager.shutdown_all()
        assert manager.get_subsystem_state("TrustOS") == SubsystemState.STOPPED
        assert manager.get_subsystem_state("MemoryOS") == SubsystemState.STOPPED
        
    asyncio.run(run_sequence())
