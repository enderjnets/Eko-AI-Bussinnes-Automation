"""Tests for Email Sequences."""

import pytest
from datetime import datetime, timedelta
from unittest.mock import AsyncMock, MagicMock, patch

from app.schemas.sequence import (
    EmailSequenceCreate,
    SequenceStepCreate,
    SequenceStepType,
    SequenceExecuteRequest,
)
from app.models.sequence import SequenceStatus


class TestSequenceSchemas:
    def test_email_sequence_create(self):
        data = EmailSequenceCreate(
            name="Test Sequence",
            description="A test sequence",
            entry_criteria={"status": "scored"},
        )
        assert data.name == "Test Sequence"
        assert data.entry_criteria == {"status": "scored"}

    def test_sequence_step_create(self):
        step = SequenceStepCreate(
            position=0,
            step_type=SequenceStepType.EMAIL,
            name="Welcome Email",
            template_key="initial_outreach",
            delay_hours=24,
        )
        assert step.position == 0
        assert step.template_key == "initial_outreach"
        assert step.ai_generate is True

    def test_sequence_execute_request(self):
        req = SequenceExecuteRequest(lead_ids=[1, 2, 3], dry_run=True)
        assert req.lead_ids == [1, 2, 3]
        assert req.dry_run is True


class TestSequenceModels:
    def test_sequence_status_values(self):
        assert SequenceStatus.DRAFT == "draft"
        assert SequenceStatus.ACTIVE == "active"
        assert SequenceStatus.PAUSED == "paused"
        assert SequenceStatus.COMPLETED == "completed"

    def test_step_type_values(self):
        assert SequenceStepType.EMAIL == "email"
        assert SequenceStepType.WAIT == "wait"
        assert SequenceStepType.CONDITION == "condition"
        assert SequenceStepType.SMS == "sms"
        assert SequenceStepType.CALL == "call"


class TestSequenceAPI:
    @pytest.mark.asyncio
    async def test_list_sequences(self):
        from app.api.v1.sequences import list_sequences

        mock_db = AsyncMock()
        mock_seq = MagicMock()
        mock_db.execute.return_value.scalars.return_value.all.return_value = [mock_seq]

        result = await list_sequences(db=mock_db)
        assert len(result) == 1

    @pytest.mark.asyncio
    async def test_get_sequence_not_found(self):
        from app.api.v1.sequences import get_sequence
        from fastapi import HTTPException

        mock_db = AsyncMock()
        mock_db.execute.return_value.scalar_one_or_none.return_value = None

        with pytest.raises(HTTPException) as exc_info:
            await get_sequence(sequence_id=999, db=mock_db)
        assert exc_info.value.status_code == 404

    @pytest.mark.asyncio
    async def test_execute_sequence_no_enrollments(self):
        from app.api.v1.sequences import execute_sequence

        mock_db = AsyncMock()
        mock_seq = MagicMock()
        mock_seq.status = SequenceStatus.ACTIVE
        mock_db.execute.return_value.scalar_one_or_none.return_value = mock_seq
        mock_db.execute.return_value.scalars.return_value.all.return_value = []

        req = SequenceExecuteRequest(lead_ids=[1], dry_run=False)
        result = await execute_sequence(sequence_id=1, request=req, db=mock_db)

        assert result["executed"] == 0
        assert result["message"] == "No enrollments ready for next step"
