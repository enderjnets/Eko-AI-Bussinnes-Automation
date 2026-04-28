import json
from typing import Optional
from app.utils.ai_client import generate_completion
from app.services.brand_extractor import extract_brand_from_website


async def generate_proposal_html(
    business_name: str,
    category: Optional[str],
    description: Optional[str],
    pain_points: Optional[list],
    services: Optional[list],
    pricing_info: Optional[str],
    about_text: Optional[str],
    deal_name: str,
    deal_value: float,
    deal_description: Optional[str],
    brand_primary_color: Optional[str] = "#3b82f6",
    brand_secondary_color: Optional[str] = "#1e40af",
    brand_logo_url: Optional[str] = None,
) -> tuple[str, str]:
    """
    Generate a personalized HTML proposal using AI.
    Returns: (html_content, plain_text)
    """
    
    primary = brand_primary_color or "#3b82f6"
    secondary = brand_secondary_color or "#1e40af"
    
    system_prompt = """You are an expert sales copywriter and web designer. You generate beautiful, professional HTML business proposals.

Generate a complete HTML proposal page with INLINE CSS only (no external stylesheets). The proposal should:
- Use the provided brand colors for headings, buttons, accents
- Be responsive and look great on mobile and desktop
- Include a professional header with the business name
- Have clear sections: Problem, Solution, Services, Pricing, Timeline, Call-to-Action
- Use modern CSS: rounded corners, subtle shadows, gradients
- Include a prominent "Accept Proposal" button and a "Request Changes" button
- The style should feel premium and trustworthy

CRITICAL: Return ONLY the HTML content (no markdown, no code fences, no explanations). The HTML must be a complete document starting with <html> or <div> and containing ALL styles inline.

Use this exact color scheme:
- Primary color for main headings and CTAs
- Secondary color for accents and borders
- White/light backgrounds for cards
- Dark text for readability"""

    pain_points_str = "\n".join([f"- {p}" for p in (pain_points or [])]) or "No pain points identified"
    services_str = "\n".join([f"- {s}" for s in (services or [])]) or "Custom services tailored to your needs"
    
    user_prompt = f"""Generate a personalized business proposal for:

Business: {business_name}
Category: {category or "Business Services"}
Description: {description or "A growing business looking to improve operations"}

Pain Points:
{pain_points_str}

Services we offer:
{services_str}

Pricing context: {pricing_info or "Custom pricing based on requirements"}
About: {about_text or ""}

Deal Details:
- Proposal title: {deal_name}
- Estimated value: ${deal_value:,.0f}
- Description: {deal_description or ""}

Brand Colors:
- Primary: {primary}
- Secondary: {secondary}
- Logo URL: {brand_logo_url or "Not available"}

Generate the complete HTML proposal now."""

    try:
        response = await generate_completion(
            system_prompt=system_prompt,
            user_prompt=user_prompt,
            temperature=0.7,
            max_tokens=4000,
        )
        
        html = response.strip()
        # Remove markdown code fences if present
        if html.startswith("```html"):
            html = html[7:]
        if html.startswith("```"):
            html = html[3:]
        if html.endswith("```"):
            html = html[:-3]
        html = html.strip()
        
        # Ensure it starts with a tag
        if not html.startswith(("<", "<!DOCTYPE")):
            html = f"<div>{html}</div>"
        
        # Generate plain text version
        plain_text = f"""Propuesta para {business_name}

Hola equipo de {business_name},

Hemos preparado una propuesta personalizada para ustedes basada en nuestra investigación.

Propuesta: {deal_name}
Valor estimado: ${deal_value:,.0f}

Nos encantaría discutir los detalles. Por favor revisen la propuesta completa y háganos saber si tienen preguntas.

Saludos,
Eko AI Team
"""
        
        return html, plain_text
    except Exception as e:
        # Fallback simple HTML
        fallback_html = f"""<div style="font-family:Arial,sans-serif;max-width:600px;margin:0 auto;padding:24px;background:#0f172a;color:#fff;border-radius:12px;">
  <h1 style="color:{primary};font-size:24px;margin-bottom:8px;">Propuesta para {business_name}</h1>
  <h2 style="color:{secondary};font-size:18px;margin-bottom:16px;">{deal_name}</h2>
  <p style="color:#94a3b8;line-height:1.6;">
    Hemos preparado una propuesta personalizada para {business_name} basada en nuestra investigación.
  </p>
  <div style="background:#1e293b;border-radius:8px;padding:16px;margin:16px 0;">
    <p style="margin:0;color:#fff;font-size:20px;font-weight:bold;">${deal_value:,.0f}</p>
    <p style="margin:4px 0 0;color:#94a3b8;font-size:12px;">Valor estimado</p>
  </div>
  <p style="color:#94a3b8;line-height:1.6;">
    {deal_description or ""}
  </p>
  <div style="display:flex;gap:12px;margin-top:24px;">
    <a href="#" style="background:{primary};color:#fff;padding:12px 24px;border-radius:8px;text-decoration:none;font-weight:600;">Aceptar Propuesta</a>
    <a href="#" style="background:transparent;color:{primary};padding:12px 24px;border-radius:8px;text-decoration:none;font-weight:600;border:1px solid {primary};">Solicitar Cambios</a>
  </div>
</div>"""
        return fallback_html, plain_text


async def extract_brand_for_lead(website_url: str) -> tuple[Optional[str], Optional[str], Optional[str]]:
    """Extract brand colors and logo from a lead's website."""
    if not website_url:
        return None, None, None
    return extract_brand_from_website(website_url)
