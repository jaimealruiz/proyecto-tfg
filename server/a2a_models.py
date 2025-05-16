# server/a2a_models.py

from pydantic import BaseModel, HttpUrl
from datetime import datetime
from typing import Any, Dict, Literal, Optional


class AgentInfo(BaseModel):
    name: str
    callback_url: HttpUrl
    capabilities: Dict[str, Any]
    agent_id: Optional[str] = None


class A2AMessage(BaseModel):
    """
    Mensaje de aplicación entre agentes; va dentro de Envelope.payload.
    """
    message_id: str                   # ID único del mensaje Lógico
    sender: str                       # agent_id emisor
    recipient: str                    # agent_id destinatario
    timestamp: datetime                    # ISO timestamp
    type: Literal["query", "response", "heartbeat", "ack"]
    body: Dict[str, Any]              # payload específico (sql, resultado, etc.)


class Envelope(BaseModel):
    """
    Sobre de transporte A2A según Google A2A (simplificado).
    Envuelve un A2AMessage en payload.
    """
    version: str = "1.0"                             # Versión del protocolo
    message_id: str                                  # ID único de este envelope
    timestamp: datetime                              # cuándo se envía
    type: Literal["query", "response", "heartbeat", "ack"]
    sender: str                                      # agent_id emisor
    recipient: str                                   # agent_id destinatario
    payload: Dict[str, Any]                          # el A2AMessage.model_dump()


class ServiceCard(BaseModel):
    service_id: str
    description: str
    input_schema: Dict[str, Any]   # p.ej. {"sql": "string"}
    output_schema: Dict[str, Any]  # p.ej. {"resultado": "list[dict]"}
    version: str = "1.0"
