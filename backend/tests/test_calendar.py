"""Tests for Calendar and Booking integration."""

import pytest
from datetime import datetime, timedelta
from unittest.mock import AsyncMock, MagicMock, patch

from app.models.booking import BookingStatus


class TestBookingModel:
    def test_booking_status_values(self):
        assert BookingStatus.PENDING == "pending"
        assert BookingStatus.CONFIRMED == "confirmed"
        assert BookingStatus.CANCELLED == "cancelled"
        assert BookingStatus.COMPLETED == "completed"
        assert BookingStatus.NO_SHOW == "no_show"


class TestCalendarAPI:
    @pytest.mark.asyncio
    async def test_list_bookings(self):
        from app.api.v1.calendar import list_bookings

        mock_booking = MagicMock()
        mock_db = AsyncMock()
        mock_db.execute.return_value.scalars.return_value.all.return_value = [mock_booking]

        mock_user = MagicMock()
        mock_user.is_superuser = True
        mock_user.role.value = "admin"

        result = await list_bookings(db=mock_db, current_user=mock_user)
        assert len(result) == 1

    @pytest.mark.asyncio
    async def test_get_event_types(self):
        from app.api.v1.calendar import get_event_types

        mock_user = MagicMock()

        with patch("app.api.v1.calendar.CalComClient") as mock_client_class:
            mock_client = AsyncMock()
            mock_client.get_event_types.return_value = [{"id": 1, "title": "Demo"}]
            mock_client.close = AsyncMock()
            mock_client_class.return_value = mock_client

            result = await get_event_types(current_user=mock_user)
            assert "event_types" in result
            assert len(result["event_types"]) == 1

    @pytest.mark.asyncio
    async def test_create_booking_no_lead(self):
        from app.api.v1.calendar import create_booking
        from fastapi import HTTPException

        mock_db = AsyncMock()
        mock_db.execute.return_value.scalar_one_or_none.return_value = None

        mock_user = MagicMock()
        mock_user.is_superuser = True

        data = MagicMock()
        data.lead_id = 999
        data.event_type_id = None
        data.start_time = datetime.utcnow()
        data.title = None
        data.notes = None
        data.location_type = "video"

        with pytest.raises(HTTPException) as exc_info:
            await create_booking(data=data, db=mock_db, current_user=mock_user)
        assert exc_info.value.status_code == 404

    @pytest.mark.asyncio
    async def test_cancel_booking(self):
        from app.api.v1.calendar import cancel_booking

        mock_booking = MagicMock()
        mock_booking.cal_com_booking_id = None
        mock_booking.status = BookingStatus.CONFIRMED

        mock_db = AsyncMock()
        mock_db.execute.return_value.scalar_one_or_none.return_value = mock_booking
        mock_db.commit = AsyncMock()

        mock_user = MagicMock()

        result = await cancel_booking(
            booking_id=1, reason="Test cancel", db=mock_db, current_user=mock_user
        )
        assert result.status == BookingStatus.CANCELLED


class TestBookingSchemas:
    def test_booking_create(self):
        from app.schemas.booking import BookingCreate

        data = BookingCreate(
            lead_id=1,
            start_time=datetime.utcnow(),
            event_type_id=42,
        )
        assert data.lead_id == 1
        assert data.event_type_id == 42

    def test_availability_request(self):
        from app.schemas.booking import AvailabilityRequest

        data = AvailabilityRequest(
            event_type_id=1,
            start_date="2026-04-24",
            end_date="2026-04-30",
        )
        assert data.start_date == "2026-04-24"

    def test_booking_link_request(self):
        from app.schemas.booking import BookingLinkRequest

        data = BookingLinkRequest(
            lead_id=1,
            event_type_id=42,
            message="Let's chat",
        )
        assert data.lead_id == 1
        assert data.message == "Let's chat"
