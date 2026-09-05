from typing import Optional
from pydantic import BaseModel, Field

class Capture(BaseModel):
    capture_id: str
    source_id: str
    url: str
    mode: str = "fixture_replay"
    authorization_status: str = "approved"
    captured_at: str
    source_claimed_time: Optional[str] = None
    http_status: Optional[int] = 200
    content_type: Optional[str] = "text/html"
    sha256: Optional[str] = None
    raw_object_reference: Optional[str] = None
    status: str = "succeeded"
    not_collected_reason: Optional[str] = None
