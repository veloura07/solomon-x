import pytest
import os
import asyncio
from context.context_builder import ContextBuilder
from context.context_compressor import ContextCompressor
from agents.registry import AgentRegistry, AgentMetadata
from orchestrator.decision_engine import DecisionEngine
from orchestrator.planner import TaskPlanner

def test_agent_registry():
    registry = AgentRegistry()
    
    # Verify core agents exist
    guardian = registry.get_agent("guardian_core")
    assert guardian is not None
    assert guardian.name == "Guardian Core"
    assert "verify_permissions" in guardian.capabilities
    
    engineer = registry.get_agent("engineer_spec")
    assert engineer is not None
    assert "compile_workspace" in engineer.capabilities

    # List agents raw dict format
    agents_list = registry.list_agents()
    assert len(agents_list) == 4

def test_decision_engine_ranking():
    engine = DecisionEngine()
    
    # Scenario: User wants to compile a program
    task_requirements = {
        "required_capabilities": ["compile_workspace"]
    }
    
    registry = AgentRegistry()
    candidates = registry.list_agents()
    
    # Evaluate
    winner = engine.select_best_executor(task_requirements, candidates)
    
    # Engineer Specialist should win because it is the only one with "compile_workspace" capability
    assert winner.agent_id == "engineer_spec"
    assert winner.composite_score > 0.0

def test_task_planner():
    planner = TaskPlanner()
    
    # Compile query
    plan_compile = planner.create_plan("Please build and compile the workspace.", {})
    assert len(plan_compile.steps) == 3
    assert plan_compile.steps[0].subsystem == "TrustOS"
    assert plan_compile.steps[2].action == "compile_workspace"
    
    # Conversational query
    plan_chat = planner.create_plan("Hello, how are you?", {})
    assert len(plan_chat.steps) == 2
    assert plan_chat.steps[1].subsystem == "Orchestrator"

def test_end_to_end_context_orchestration():
    # 1. User state simulation
    user_state = {
        "active_profile": {
            "name": "Namir",
            "trust_level": 2,
            "role": "Lead Architect"
        },
        "cognitive_state": {
            "focus_index": 0.9,
            "cognitive_load": 0.2,
            "mental_momentum": 0.8
        },
        "current_context": {
            "active_project_path": "c:/Users/namir/Downloads/solomon-x",
            "active_goals": ["Build a cognitive system"]
        }
    }
    
    # 2. Retrieved memories list
    memories = [
        {"timestamp": 1781567900.0, "horizon": "L1", "content": "Initial workspace consolidated"},
        {"timestamp": 1781567920.0, "horizon": "L2", "content": "LanceDB setup completed"}
    ]
    
    # 3. Context Grounding
    builder = ContextBuilder()
    payload = builder.build_prompt_payload(
        raw_user_input="Compile the code",
        user_state=user_state,
        relevant_memories=memories,
        system_instructions="You are Solomon X."
    )
    
    assert "User Profile" in payload["grounding_context"]
    assert "LanceDB setup" in payload["grounding_context"]
    
    # 4. Context Compression (simulate a tight token limit)
    compressor = ContextCompressor(token_limit=100) # tight limit
    compressed_payload = compressor.compress_grounding(payload, approx_tokens_per_char=0.5)
    
    assert compressed_payload["metadata"].get("compressed")
    
    # 5. Planning
    planner = TaskPlanner()
    plan = planner.create_plan(payload["user_query"], user_state["current_context"])
    assert len(plan.steps) > 0
    
    # 6. Dispatch step to best agent
    registry = AgentRegistry()
    engine = DecisionEngine()
    
    # Find agent for compiling step
    compile_step = next(s for s in plan.steps if s.action == "compile_workspace")
    reqs = {"required_capabilities": [compile_step.action]}
    candidates = registry.list_agents()
    
    executor = engine.select_best_executor(reqs, candidates)
    assert executor.agent_id == "engineer_spec"
