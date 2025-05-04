from pydantic import BaseModel, HttpUrl
from typing import Dict, Any, Optional

class AgentInfo(BaseModel):
    name: str
    callback_url: HttpUrl
    capabilities: Dict[str, Any] = {}
    agent_id: Optional[str] = None

class A2AMessage(BaseModel):
    message_id: str
    sender: str
    recipient: str
    timestamp: str     # ISO
    type: str          # p.ej. "query" | "response" | "notification"
    body: Dict[str, Any]
