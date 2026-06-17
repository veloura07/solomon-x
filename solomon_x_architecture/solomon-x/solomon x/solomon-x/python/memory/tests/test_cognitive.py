import os
import shutil
import tempfile
import pytest
from python.anticipatory.hood import HOODTracker
from python.cognitive_twin.tracker import CognitiveTracker

@pytest.fixture
def temp_hood_path():
    temp_dir = tempfile.mkdtemp()
    model_path = os.path.join(temp_dir, "hood_model.json")
    yield model_path
    if os.path.exists(model_path):
        os.remove(model_path)
    try:
        os.rmdir(temp_dir)
    except Exception:
        pass

@pytest.fixture
def temp_state_path():
    temp_dir = tempfile.mkdtemp()
    state_path = os.path.join(temp_dir, "current_user_state.json")
    # Write default profile
    import json
    with open(state_path, "w") as f:
        json.dump({
            "user_id": "test_usr",
            "active_profile": {"name": "Test User", "trust_level": 2},
            "cognitive_state": {"focus_index": 0.8, "cognitive_load": 0.4, "mental_momentum": 0.7}
        }, f)
        
    yield state_path
    
    if os.path.exists(state_path):
        os.remove(state_path)
    try:
        os.rmdir(temp_dir)
    except Exception:
        pass

def test_hood_model_predictions(temp_hood_path):
    # Initialize
    tracker = HOODTracker(temp_hood_path)
    
    # Check default state load
    assert "code" in tracker.transitions
    
    # Make predictions for 'code'
    preds = tracker.predict("code", limit=2)
    assert len(preds) <= 2
    assert preds[0][0] in ["debug", "compile"]
    assert preds[0][1] > 0.0

    # Record some observations
    tracker.observe("code", "debug")
    tracker.observe("code", "debug")
    
    # Assert online count increases
    assert tracker.transitions["code"]["debug"] > 6 # base defaults + new observations
    
    # Verify save file exists
    assert os.path.exists(temp_hood_path)

def test_cognitive_tracker_flow(temp_state_path):
    tracker = CognitiveTracker(temp_state_path)
    
    # Assert initial values
    assert tracker.focus_index == 0.85
    assert tracker.cognitive_load == 0.35
    
    # Run simulation update loop manually
    tracker.start()
    
    # Allow simulated loop to sync once
    import time
    time.sleep(0.5)
    
    tracker.stop()
    
    # Verify values updated state vector
    vector = tracker.get_state_vector()
    assert "focus_index" in vector
    assert "cognitive_load" in vector
    
    # Verify state file on disk has updated parameters
    with open(temp_state_path, "r") as f:
        import json
        state = json.load(f)
        assert "cognitive_state" in state
        assert "focus_index" in state["cognitive_state"]
