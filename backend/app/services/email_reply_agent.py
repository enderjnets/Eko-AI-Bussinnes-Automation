from typing import Optional, List
from app.utils.ai_client import generate_completion
from app.models.lead import Lead, Interaction


async def generate_ai_reply(
    lead: Lead,
    inbound_email: Interaction,
    conversation_history: List[Interaction],
    tone: str = "professional",
    max_length: str = "medium",
    custom_instructions: Optional[str] = None,
) -> dict:
    """
    Generate an AI-powered reply to an inbound email.
    
    Returns: {
        "subject": str,
        "body": str,
        "tone": str,
        "confidence": float,
        "suggested_next_action": str,
    }
    """
    
    # Build conversation context
    history_text = ""
    for i, interaction in enumerate(conversation_history[-5:]):  # Last 5 interactions
        direction = "Nosotros" if interaction.direction == "outbound" else "Cliente"
        history_text += f"\n[{direction}] {interaction.subject or 'No subject'}:\n{interaction.content or ''}\n"
    
    # Lead context
    lead_context = f"""Información del lead:
- Nombre del negocio: {lead.business_name}
- Categoría: {lead.category or 'No especificada'}
- Ciudad: {lead.city or 'No especificada'}
- Estado en pipeline: {lead.status.value if lead.status else 'desconocido'}
- Descripción: {lead.description or 'No disponible'}
- Servicios: {', '.join(lead.services or []) or 'No especificados'}
- Pain points: {', '.join(lead.pain_points or []) or 'No identificados'}
- Score: {lead.total_score or 0}/100
"""

    # Inbound email analysis
    inbound_analysis = f"""Email recibido:
Asunto: {inbound_email.subject or 'Sin asunto'}
Contenido: {inbound_email.content or ''}
"""
    
    # Get AI analysis from meta if available
    meta = inbound_email.meta or {}
    if meta.get("sentiment") or meta.get("intent"):
        inbound_analysis += f"""
Análisis AI del email:
- Sentimiento: {meta.get('sentiment', 'desconocido')}
- Intención: {meta.get('intent', 'desconocida')}
- Resumen: {meta.get('summary', '')}
- Puntos clave: {', '.join(meta.get('key_points', []))}
- Próxima acción sugerida: {meta.get('next_action', '')}
"""

    # Tone guidance
    tone_guidance = {
        "professional": "Profesional y cordial. Usa lenguaje de negocios formal pero cercano.",
        "friendly": "Amigable y cercano. Como si hablaras con un conocido.",
        "assertive": "Asertivo y directo. Ve al grano con confianza.",
        "consultative": "Consultivo. Haz preguntas, ofrece valor, no vendas directamente.",
    }.get(tone, tone_guidance["professional"])

    length_guidance = {
        "short": "Máximo 3-4 oraciones. Breve y directo.",
        "medium": "Máximo 2-3 párrafos cortos. Balanceado.",
        "long": "3-4 párrafos con detalle. Incluye ejemplos o propuesta de siguiente paso.",
    }.get(max_length, length_guidance["medium"])

    custom = f"\nInstrucciones adicionales: {custom_instructions}\n" if custom_instructions else ""

    system_prompt = f"""Eres un experto en ventas B2B y comunicación comercial. Generas respuestas a emails de prospectos que son:

1. ALTAMENTE PERSONALIZADAS: Usa el nombre del negocio, referencias a su industria/ciudad, y contexto de conversaciones previas.
2. CONTEXTUALES: Responde DIRECTAMENTE a lo que el prospecto dijo. No generéricas.
3. CON TONO ADECUADO: {tone_guidance}
4. DE LONGITUD ADECUADA: {length_guidance}
5. CON CTA CLARO: Siempre termina con una pregunta o sugerencia de siguiente paso concreto.
6. EN ESPAÑOL: Responde en español, a menos que el email recibido esté en inglés.

REGLAS:
- Nunca uses "Espero que este mensaje te encuentre bien" o frases genéricas de apertura.
- Menciona algo específico del negocio del lead si tienes información.
- Si el lead muestra interés, sugiere una reunión o demo.
- Si el lead tiene objeciones, respóndelas con datos o ejemplos.
- Si el lead pide información, proporciónala de forma concisa.
- Firma como "Equipo Eko AI" o similar profesional.

Responde ÚNICAMENTE con un JSON válido con esta estructura:
{{"subject": "...", "body": "...", "tone": "...", "confidence": 0.0-1.0, "suggested_next_action": "..."}}"""

    user_prompt = f"""Genera una respuesta al siguiente email de un prospecto:

{lead_context}

{inbound_analysis}

Historial de conversación:{history_text or ' (No hay historial previo)'}

{custom}

Genera la respuesta ahora."""

    try:
        response = await generate_completion(
            system_prompt=system_prompt,
            user_prompt=user_prompt,
            temperature=0.7,
            max_tokens=2000,
        )
        
        # Parse JSON response
        import json
        text = response.strip()
        
        # Remove markdown code fences if present
        if text.startswith("```json"):
            text = text[7:]
        if text.startswith("```"):
            text = text[3:]
        if text.endswith("```"):
            text = text[:-3]
        text = text.strip()
        
        result = json.loads(text)
        
        return {
            "subject": result.get("subject", f"Re: {inbound_email.subject or ''}"),
            "body": result.get("body", ""),
            "tone": result.get("tone", tone),
            "confidence": float(result.get("confidence", 0.8)),
            "suggested_next_action": result.get("suggested_next_action", ""),
        }
    except Exception as e:
        # Fallback reply
        return {
            "subject": f"Re: {inbound_email.subject or ''}",
            "body": f"""Hola {lead.business_name},

Gracias por tu mensaje. Hemos recibido tu email y queremos asegurarnos de darte la mejor respuesta posible.

{custom_instructions or ''}

¿Podrías confirmarnos cuál es el mejor horario para una breve llamada de 15 minutos? Nos encantaría entender mejor tus necesidades.

Saludos,
Equipo Eko AI
""",
            "tone": tone,
            "confidence": 0.5,
            "suggested_next_action": "Programar llamada de seguimiento",
        }


async def get_conversation_history(
    lead_id: int,
    db,
    limit: int = 10,
) -> List[Interaction]:
    """Get recent email interactions for a lead."""
    from sqlalchemy import select, desc
    from app.models.lead import Interaction
    
    result = await db.execute(
        select(Interaction)
        .where(Interaction.lead_id == lead_id)
        .where(Interaction.interaction_type == "email")
        .order_by(desc(Interaction.created_at))
        .limit(limit)
    )
    return result.scalars().all()
