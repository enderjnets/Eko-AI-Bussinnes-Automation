"""Tests for CRM endpoints."""

import pytest
from datetime import datetime


def test_pipeline_transitions_valid():
    """Test that pipeline transitions are correctly defined."""
    from app.api.v1.crm import VALID_TRANSITIONS
    from app.models.lead import LeadStatus
    
    # Ensure all statuses have transitions defined
    for status in LeadStatus:
        assert status in VALID_TRANSITIONS or status in [
            LeadStatus.CLOSED_WON, LeadStatus.CLOSED_LOST, LeadStatus.CHURNED
        ]
    
    # Test specific transitions
    assert LeadStatus.CONTACTED in VALID_TRANSITIONS[LeadStatus.SCORED]
    assert LeadStatus.MEETING_BOOKED in VALID_TRANSITIONS[LeadStatus.ENGAGED]


def test_email_templates_exist():
    """Test that email templates are defined."""
    from app.agents.outreach.channels.email import EMAIL_TEMPLATES
    
    assert "initial_outreach" in EMAIL_TEMPLATES
    assert "follow_up" in EMAIL_TEMPLATES
    assert "meeting_request" in EMAIL_TEMPLATES
    assert "proposal" in EMAIL_TEMPLATES
    
    for key, template in EMAIL_TEMPLATES.items():
        assert "subject" in template
        assert "context" in template


def test_compliance_footer_format():
    """Test that compliance footer includes required elements."""
    from app.agents.outreach.channels.email import EmailOutreach
    
    email = EmailOutreach()
    body = "<p>Test email</p>"
    result = email._add_compliance_footer(body, lead_id=123)
    
    assert "[AI-generated message]" in result
    assert "Unsubscribe" in result
    assert "Reply STOP to opt out" in result
    assert "lead_id=123" in result
