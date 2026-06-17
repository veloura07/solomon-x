"""
Solomon X Knowledge Graph Entities.
Defines semantic nodes and properties for the Lorentzian Reality Graph.
"""

from typing import Dict, Any, List, Optional
from pydantic import BaseModel, Field

class EntityNode(BaseModel):
    """
    Base node representation inside the Knowledge Graph.
    """
    id: str = Field(..., description="Unique identifier for the node (e.g. ent_01)")
    label: str = Field(..., description="Display name / label of the entity")
    entity_type: str = Field(..., description="Type classification (User, Agent, Project, Task, Tool)")
    properties: Dict[str, Any] = Field(default_factory=dict, description="Metadata dictionary")
    mass: float = Field(default=1.0, description="Goal gravity mass distorting metric space dimensions")

class SemanticRelationship(BaseModel):
    """
    Directed semantic edge connecting nodes within the Riemannian manifold.
    """
    source_id: str = Field(..., description="Source EntityNode ID")
    target_id: str = Field(..., description="Target EntityNode ID")
    predicate: str = Field(..., description="Type of edge relationship (e.g., OWNS, ASSIGNED_TO, DEPENDS_ON)")
    properties: Dict[str, Any] = Field(default_factory=dict, description="Edge property variables")
    weight: float = Field(default=1.0, description="Heuristic strength of the association")
