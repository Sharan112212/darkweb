from typing import Optional, List, Dict, Any
from pydantic import BaseModel, Field

class CategoryScore(BaseModel):
    score: float = Field(default=0.0, ge=0.0, le=1.0)
    state: str = "not_available"
    evidence_ids: List[str] = Field(default_factory=list)

class CandidateLink(BaseModel):
    link_id: str
    link_version: int = 1
    left_entity_id: str
    right_entity_id: str
    state: str = "proposed"
    score: float = Field(..., ge=0.0, le=1.0)
    tier: str
    score_status: str = "observed"
    category_breakdown: Dict[str, Any] = Field(default_factory=dict)
    evidence_ids: List[str] = Field(default_factory=list)
    conflict_set_id: Optional[str] = None
    competing_link_ids: List[str] = Field(default_factory=list)
    explanation: str
    limitations: List[str] = Field(default_factory=list)
    score_model_version: str = "scoring-v1.0"
    calculation_input_hash: str
    created_at: str
    updated_at: str
