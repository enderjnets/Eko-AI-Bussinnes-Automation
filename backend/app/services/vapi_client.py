"""VAPI.ai client for AI voice calling."""
import os
from typing import Optional, Dict, Any
import httpx

from app.config import get_settings

settings = get_settings()

VAPI_BASE_URL = "https://api.vapi.ai"


def _get_headers() -> dict:
    api_key = settings.VAPI_API_KEY or os.environ.get("VAPI_API_KEY", "")
    return {
        "Authorization": f"Bearer {api_key}",
        "Content-Type": "application/json",
    }


async def create_call(
    phone_number: str,
    assistant_id: Optional[str] = None,
    lead_id: Optional[int] = None,
    name: Optional[str] = None,
    first_message: Optional[str] = None,
    custom_variables: Optional[Dict[str, Any]] = None,
) -> dict:
    """
    Create and start an outbound phone call via VAPI.
    
    Args:
        phone_number: The phone number to call (E.164 format)
        assistant_id: Optional VAPI assistant ID. If not provided, uses default.
        lead_id: Our internal lead ID for tracking
        name: Name of the person/business being called
        first_message: Custom first message (overrides assistant's firstMessage)
        custom_variables: Variables injected into the assistant context
    """
    api_key = settings.VAPI_API_KEY or os.environ.get("VAPI_API_KEY", "")
    if not api_key:
        return {"error": "VAPI_API_KEY not configured"}
    
    payload: dict = {
        "phoneNumberId": None,  # VAPI will use default configured number
        "type": "outboundPhoneCall",
        "phoneNumber": phone_number,
        "customer": {
            "number": phone_number,
            "name": name or "",
        },
    }
    
    if assistant_id:
        payload["assistantId"] = assistant_id
    
    if first_message:
        payload["assistantOverrides"] = {
            "firstMessage": first_message,
        }
    
    # Merge custom variables for assistant context
    vars_payload = custom_variables or {}
    if lead_id:
        vars_payload["lead_id"] = str(lead_id)
    
    if vars_payload:
        payload.setdefault("assistantOverrides", {})
        payload["assistantOverrides"]["variables"] = vars_payload
    
    async with httpx.AsyncClient(timeout=30.0) as client:
        try:
            response = await client.post(
                f"{VAPI_BASE_URL}/call",
                headers=_get_headers(),
                json=payload,
            )
            response.raise_for_status()
            return response.json()
        except httpx.HTTPStatusError as e:
            return {
                "error": f"VAPI HTTP error: {e.response.status_code}",
                "detail": e.response.text,
            }
        except Exception as e:
            return {"error": f"VAPI request failed: {str(e)}"}


async def get_call(call_id: str) -> dict:
    """Get details of a VAPI call by ID."""
    async with httpx.AsyncClient(timeout=30.0) as client:
        try:
            response = await client.get(
                f"{VAPI_BASE_URL}/call/{call_id}",
                headers=_get_headers(),
            )
            response.raise_for_status()
            return response.json()
        except httpx.HTTPStatusError as e:
            return {
                "error": f"VAPI HTTP error: {e.response.status_code}",
                "detail": e.response.text,
            }
        except Exception as e:
            return {"error": f"VAPI request failed: {str(e)}"}


async def list_calls(
    limit: int = 50,
    cursor: Optional[str] = None,
    assistant_id: Optional[str] = None,
    phone_number_id: Optional[str] = None,
    status: Optional[str] = None,
) -> dict:
    """List VAPI calls with pagination."""
    params: dict = {"limit": limit}
    if cursor:
        params["cursor"] = cursor
    if assistant_id:
        params["assistantId"] = assistant_id
    if phone_number_id:
        params["phoneNumberId"] = phone_number_id
    if status:
        params["status"] = status
    
    async with httpx.AsyncClient(timeout=30.0) as client:
        try:
            response = await client.get(
                f"{VAPI_BASE_URL}/call",
                headers=_get_headers(),
                params=params,
            )
            response.raise_for_status()
            return response.json()
        except httpx.HTTPStatusError as e:
            return {
                "error": f"VAPI HTTP error: {e.response.status_code}",
                "detail": e.response.text,
            }
        except Exception as e:
            return {"error": f"VAPI request failed: {str(e)}"}


async def create_assistant(
    name: str,
    system_prompt: str,
    first_message: str,
    voice_provider: str = "11labs",
    voice_id: str = "EXAVITQu4vr4xnSDxMaL",
    model: str = "gpt-4o",
) -> dict:
    """
    Create a VAPI assistant with a custom system prompt.
    
    Args:
        name: Assistant name
        system_prompt: The system prompt/instructions for the AI
        first_message: The first message the assistant says when the call connects
        voice_provider: Voice provider (11labs, playht, etc.)
        voice_id: Voice ID
        model: LLM model to use
    """
    payload = {
        "name": name,
        "model": {
            "provider": "openai",
            "model": model,
            "temperature": 0.7,
            "systemPrompt": system_prompt,
        },
        "voice": {
            "provider": voice_provider,
            "voiceId": voice_id,
        },
        "firstMessage": first_message,
        "recordingEnabled": True,
        "transcriber": {
            "provider": "deepgram",
            "model": "nova-2",
            "language": "es",
        },
    }
    
    async with httpx.AsyncClient(timeout=30.0) as client:
        try:
            response = await client.post(
                f"{VAPI_BASE_URL}/assistant",
                headers=_get_headers(),
                json=payload,
            )
            response.raise_for_status()
            return response.json()
        except httpx.HTTPStatusError as e:
            return {
                "error": f"VAPI HTTP error: {e.response.status_code}",
                "detail": e.response.text,
            }
        except Exception as e:
            return {"error": f"VAPI request failed: {str(e)}"}


async def update_assistant(
    assistant_id: str,
    updates: dict,
) -> dict:
    """Update an existing VAPI assistant."""
    async with httpx.AsyncClient(timeout=30.0) as client:
        try:
            response = await client.patch(
                f"{VAPI_BASE_URL}/assistant/{assistant_id}",
                headers=_get_headers(),
                json=updates,
            )
            response.raise_for_status()
            return response.json()
        except httpx.HTTPStatusError as e:
            return {
                "error": f"VAPI HTTP error: {e.response.status_code}",
                "detail": e.response.text,
            }
        except Exception as e:
            return {"error": f"VAPI request failed: {str(e)}"}


def build_sales_assistant_prompt(company_name: str = "Eko AI") -> str:
    """Build a default sales assistant system prompt."""
    return f"""Eres un asistente de ventas profesional de {company_name}. Tu objetivo es contactar a prospectos por teléfono, presentar nuestros servicios de automatización con IA, y agendar reuniones.

REGLAS IMPORTANTES:
1. Siempre saluda cordialmente y menciona que llamas de {company_name}.
2. Escucha activamente las objeciones y responde con empatía.
3. Si el prospecto muestra interés, sugiere agendar una reunión breve de 15 minutos.
4. Si no pueden hablar ahora, pregunta cuál es el mejor momento para llamar de nuevo.
5. Nunca seas agresivo ni insistente. Respeta si dicen "no".
6. Si pide más información por email, confirma la dirección de email y ofrece enviar un resumen.
7. Mantén las llamadas concisas (máximo 3-5 minutos).
8. Habla en español, a menos que el prospecto prefiera inglés.

SERVICIOS QUE OFRECEMOS:
- Automatización de prospección y outreach
- Agentes de IA para email y voz
- Análisis de leads con IA
- Automatización de propuestas y seguimiento
- Integración con CRM y calendario

AL FINAL DE CADA LLAMADA:
- Resume brevemente lo conversado
- Registra el nivel de interés (alto, medio, bajo, ninguno)
- Anota la próxima acción sugerida"""
