import os
import tempfile
import pytest
from trust.pcr_validator import PCRValidator
from trust.policy_engine import PolicyEngine
from trust.mentor_gate import MentorGate

@pytest.fixture
def temp_boot_token():
    temp_dir = tempfile.mkdtemp()
    token_path = os.path.join(temp_dir, "boot_token.bin")
    with open(token_path, "wb") as f:
        f.write(os.urandom(32))
        
    yield token_path
    
    if os.path.exists(token_path):
        os.remove(token_path)
    try:
        os.rmdir(temp_dir)
    except Exception:
        pass

def test_pcr_validator_missing_token():
    validator = PCRValidator("./nonexistent_path.bin")
    assert not validator.validate_boot_integrity()

def test_pcr_validator_valid_token(temp_boot_token):
    validator = PCRValidator(temp_boot_token)
    assert validator.validate_boot_integrity()

def test_policy_engine_evaluation():
    with tempfile.NamedTemporaryFile(suffix=".json", delete=False) as tmp:
        policy_path = tmp.name
        
    try:
        engine = PolicyEngine(policy_path)
        
        # Test 1: Companion agent tries to read memory (allow autonomously)
        res = engine.evaluate_rule("companion_core", "read_memory", 0.9)
        assert res["allow"]
        assert not res["requires_mentor_gate"]
        
        # Test 2: Companion agent tries to execute command (deny scope restriction)
        res = engine.evaluate_rule("companion_core", "execute_command", 0.9)
        assert not res["allow"]
        
        # Test 3: Unrecognized agent (deny role resolve)
        res = engine.evaluate_rule("rogue_agent", "read_memory", 0.9)
        assert not res["allow"]
        
        # Test 4: Engineer agent tries to write memory below approval threshold (mentor gate required)
        res = engine.evaluate_rule("engineer_spec", "write_memory", 0.75)
        assert res["allow"]
        assert res["requires_mentor_gate"]
        
        # Test 5: Engineer agent tries to execute command above approval threshold (allow autonomously)
        res = engine.evaluate_rule("engineer_spec", "execute_command", 0.98)
        assert res["allow"]
        assert not res["requires_mentor_gate"]
        
    finally:
        if os.path.exists(policy_path):
            try:
                os.remove(policy_path)
            except Exception:
                pass

def test_mentor_gate_selection():
    gate = MentorGate()
    
    dilemma_exec = gate.select_dilemma("execute_command")
    assert "sandbox" in dilemma_exec["id"]
    
    dilemma_ledger = gate.select_dilemma("modify_ledger")
    assert "ledger" in dilemma_ledger["id"]
    
    dilemma_read = gate.select_dilemma("read_memory")
    assert "privacy" in dilemma_read["id"]

def test_mentor_gate_challenge():
    gate = MentorGate()
    assert gate.trigger_challenge("engineer_spec", "execute_command", "Confidence is 0.91 (threshold: 0.95)")
