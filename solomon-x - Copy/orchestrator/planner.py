"""
Solomon X Task Planner.
Decomposes user requests into sequential sub-tasks.
"""

import logging
from typing import Dict, List, Any
from pydantic import BaseModel

logger = logging.getLogger("solomon.orchestrator")

class TaskStep(BaseModel):
    step_id: int
    subsystem: str
    action: str
    parameters: Dict[str, Any]
    status: str = "PENDING"

class ExecutionPlan(BaseModel):
    plan_id: str
    steps: List[TaskStep]

class TaskPlanner:
    """
    Analyzes raw goals and user queries to structure sequence paths for execution.
    """

    def __init__(self) -> None:
        pass

    def create_plan(self, query: str, active_context: Dict[str, Any]) -> ExecutionPlan:
        """
        Decomposes an instruction into structured sequential task steps.
        """
        logger.info(f"Generating execution steps for: '{query}'")

        steps: List[TaskStep] = []
        
        # Simple rule-based planner stub
        if "compile" in query.lower() or "build" in query.lower():
            steps.append(TaskStep(
                step_id=1,
                subsystem="TrustOS",
                action="verify_permissions",
                parameters={"scope": "workspace_write"}
            ))
            steps.append(TaskStep(
                step_id=2,
                subsystem="MemoryOS",
                action="retrieve_context",
                parameters={"keywords": ["build", "compile"]}
            ))
            steps.append(TaskStep(
                step_id=3,
                subsystem="Agents",
                action="compile_workspace",
                parameters={"path": active_context.get("active_project_path", "")}
            ))
        else:
            # Default conversational path
            steps.append(TaskStep(
                step_id=1,
                subsystem="MemoryOS",
                action="retrieve_session_history",
                parameters={}
            ))
            steps.append(TaskStep(
                step_id=2,
                subsystem="Orchestrator",
                action="generate_reply",
                parameters={"query": query}
            ))

        plan = ExecutionPlan(
            plan_id="plan_default_0x01",
            steps=steps
        )
        logger.info(f"Plan created with {len(steps)} steps.")
        return plan
