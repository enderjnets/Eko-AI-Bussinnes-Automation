import json
from typing import Optional
from app.utils.ai_client import generate_completion


async def analyze_email_reply(
    reply_text: str,
    lead_name: str,
    business_name: str,
    previous_email_subject: Optional[str] = None,
) -> dict:
    """
    Analyze an email reply using AI to extract sentiment, intent,
    and recommended next action.
    
    Returns:
        {
            "sentiment": "positive" | "neutral" | "negative",
            "intent": "interested" | "needs_info" | "not_interested" | "out_of_office" | "forwarded" | "unclear",
            "summary": str,
            "next_action": str,
            "priority": "high" | "medium" | "low",
            "key_points": list[str],
        }
    """
    system_prompt = """You are an expert sales assistant analyzing email replies from business leads.
Analyze the reply and return ONLY valid JSON with these exact fields:
- sentiment: one of ["positive", "neutral", "negative"]
- intent: one of ["interested", "needs_info", "not_interested", "out_of_office", "forwarded", "unclear"]
- summary: a 1-sentence summary of what the lead is saying
- next_action: a specific recommended next step for the sales rep
- priority: one of ["high", "medium", "low"] based on urgency and interest
- key_points: an array of 1-3 key points or questions from the reply

Be concise and actionable."""

    context = f"Lead: {lead_name} ({business_name})"
    if previous_email_subject:
        context += f"\nPrevious email subject: {previous_email_subject}"

    user_prompt = f"""{context}

Reply text:
---
{reply_text}
---

Analyze this reply and return JSON only."""

    try:
        response = await generate_completion(
            system_prompt=system_prompt,
            user_prompt=user_prompt,
            temperature=0.3,
            max_tokens=800,
            json_mode=True,
        )
        result = json.loads(response)
        
        # Normalize and validate
        return {
            "sentiment": result.get("sentiment", "neutral").lower(),
            "intent": result.get("intent", "unclear").lower(),
            "summary": result.get("summary", ""),
            "next_action": result.get("next_action", ""),
            "priority": result.get("priority", "medium").lower(),
            "key_points": result.get("key_points", []),
        }
    except Exception:
        # Fallback if AI fails
        return {
            "sentiment": "neutral",
            "intent": "unclear",
            "summary": reply_text[:200] + "..." if len(reply_text) > 200 else reply_text,
            "next_action": "Review reply manually",
            "priority": "medium",
            "key_points": [],
        }


def determine_status_from_intent(intent: str, current_status: str) -> Optional[str]:
    """
    Determine the new lead status based on reply intent.
    Returns None if no change is recommended.
    """
    intent = intent.lower()
    
    if intent == "interested":
        if current_status in ["discovered", "enriched", "scored", "contacted"]:
            return "engaged"
    elif intent == "not_interested":
        if current_status in ["contacted", "engaged"]:
            return "closed_lost"
    elif intent == "needs_info":
        if current_status == "contacted":
            return "engaged"
    elif intent == "forwarded":
        if current_status in ["contacted", "engaged"]:
            return "engaged"
    
    return None
