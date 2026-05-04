"""SQLAlchemy event listeners to auto-inject workspace_id on INSERT/UPDATE."""

from sqlalchemy import event

from app.services.tenant_context import get_workspace_id
from app.models.lead import Lead
from app.models.deal import Deal
from app.models.campaign import Campaign
from app.models.booking import Booking
from app.models.phone_call import PhoneCall
from app.models.proposal import Proposal
from app.models.payment import Payment
from app.models.sequence import EmailSequence
from app.models.setting import AppSetting
from app.models.object_metadata import ObjectMetadata
from app.models.field_metadata import FieldMetadata
from app.models.dynamic_record import DynamicRecord
from app.models.view import View, ViewField, ViewFilter, ViewSort


_WORKSPACE_MODELS = [
    Lead, Deal, Campaign, Booking, PhoneCall,
    Proposal, Payment, EmailSequence, AppSetting,
    ObjectMetadata, FieldMetadata, DynamicRecord,
    View, ViewField, ViewFilter, ViewSort,
]


def _set_workspace_id(mapper, connection, target):
    ws_id = get_workspace_id()
    if ws_id and getattr(target, "workspace_id", None) is None:
        target.workspace_id = ws_id


def register_workspace_hooks():
    """Register before_insert listeners on all workspace-scoped models."""
    for model in _WORKSPACE_MODELS:
        event.listen(model, "before_insert", _set_workspace_id)
