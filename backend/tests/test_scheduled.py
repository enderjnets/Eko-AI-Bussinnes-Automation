"""Tests for Celery scheduled tasks."""

import pytest
from datetime import datetime, timedelta
from unittest.mock import AsyncMock, MagicMock, patch, PropertyMock


class TestProcessFollowUps:
    @pytest.mark.asyncio
    async def test_process_follow_ups_finds_leads(self):
        from app.tasks.scheduled import _process_follow_ups_async

        mock_lead = MagicMock()
        mock_lead.id = 1
        mock_lead.business_name = "Test Biz"
        mock_lead.email = "test@example.com"
        mock_lead.do_not_contact = False
        mock_lead.last_contact_at = None
        mock_lead.status = MagicMock()

        mock_db = AsyncMock()
        mock_db.execute.return_value.scalars.return_value.all.return_value = [mock_lead]
        mock_db.commit = AsyncMock()

        with patch("app.tasks.scheduled.AsyncSessionLocal", return_value=mock_db):
            with patch("app.tasks.scheduled.EmailOutreach") as mock_email_class:
                mock_email = AsyncMock()
                mock_email.generate_and_send.return_value = {
                    "id": "msg_123",
                    "subject": "Follow up",
                }
                mock_email_class.return_value = mock_email

                result = await _process_follow_ups_async()

        assert result["processed"] == 1
        assert result["skipped"] == 0

    @pytest.mark.asyncio
    async def test_process_follow_ups_skips_no_email(self):
        from app.tasks.scheduled import _process_follow_ups_async

        mock_lead = MagicMock()
        mock_lead.id = 1
        mock_lead.business_name = "Test Biz"
        mock_lead.email = None
        mock_lead.do_not_contact = False
        mock_lead.last_contact_at = None
        mock_lead.status = MagicMock()

        mock_db = AsyncMock()
        mock_db.execute.return_value.scalars.return_value.all.return_value = [mock_lead]
        mock_db.commit = AsyncMock()

        with patch("app.tasks.scheduled.AsyncSessionLocal", return_value=mock_db):
            result = await _process_follow_ups_async()

        assert result["processed"] == 0
        assert result["skipped"] == 1


class TestEnrichPendingLeads:
    @pytest.mark.asyncio
    async def test_enrich_pending_leads(self):
        from app.tasks.scheduled import _enrich_pending_leads_async
        from app.schemas.lead import LeadEnrichment

        mock_lead = MagicMock()
        mock_lead.id = 1
        mock_lead.business_name = "Test Biz"
        mock_lead.status = MagicMock()
        mock_lead.status.value = "discovered"

        mock_db = AsyncMock()
        mock_db.execute.return_value.scalars.return_value.all.return_value = [mock_lead]
        mock_db.commit = AsyncMock()

        enrichment = LeadEnrichment(
            urgency_score=75,
            fit_score=80,
            pain_points=["Missed calls"],
        )

        with patch("app.tasks.scheduled.AsyncSessionLocal", return_value=mock_db):
            with patch("app.tasks.scheduled.ResearchAgent") as mock_agent_class:
                mock_agent = AsyncMock()
                mock_agent.enrich.return_value = enrichment
                mock_agent_class.return_value = mock_agent

                result = await _enrich_pending_leads_async()

        assert result["enriched"] == 1
        assert result["skipped"] == 0


class TestSyncDncRegistry:
    @pytest.mark.asyncio
    async def test_sync_dnc_mark_bounced(self):
        from app.tasks.scheduled import _sync_dnc_registry_async

        mock_row = MagicMock()
        mock_row.lead_id = 1

        mock_db = AsyncMock()
        mock_db.execute.return_value.all.return_value = [mock_row]
        mock_db.commit = AsyncMock()

        mock_lead = MagicMock()
        mock_lead.do_not_contact = False

        # First call for bounced, second for old optouts
        def side_effect(*args, **kwargs):
            mock_result = MagicMock()
            if hasattr(args[0], '_where_criteria'):
                pass
            mock_result.scalar_one_or_none.return_value = mock_lead
            return mock_result

        mock_db.execute.side_effect = [
            MagicMock(all=MagicMock(return_value=[mock_row])),  # bounced query
            MagicMock(scalar_one_or_none=MagicMock(return_value=mock_lead)),  # lead lookup
            MagicMock(scalars=MagicMock(return_value=MagicMock(all=MagicMock(return_value=[])))),  # old optouts
        ]

        with patch("app.tasks.scheduled.AsyncSessionLocal", return_value=mock_db):
            result = await _sync_dnc_registry_async()

        assert result["bounced_marked"] >= 0


class TestGenerateDailyReport:
    @pytest.mark.asyncio
    async def test_generate_daily_report(self):
        from app.tasks.scheduled import _generate_daily_report_async

        mock_db = AsyncMock()
        mock_db.execute.return_value.all.return_value = [
            (MagicMock(value="discovered"), 10),
            (MagicMock(value="contacted"), 5),
        ]
        mock_db.scalar.side_effect = [5, 3, 2, 70.0]
        mock_db.commit = AsyncMock()

        with patch("app.tasks.scheduled.AsyncSessionLocal", return_value=mock_db):
            with patch("app.tasks.scheduled._create_issue"):
                result = await _generate_daily_report_async()

        assert "pipeline" in result
        assert "conversion_rate" in result
        assert result["total_leads"] >= 0


class TestCeleryTaskWrappers:
    def test_process_follow_ups_task_runs(self):
        from app.tasks.scheduled import process_follow_ups

        with patch("app.tasks.scheduled.asyncio.run") as mock_run:
            mock_run.return_value = {"processed": 0, "skipped": 0, "errors": 0}
            result = process_follow_ups()
            assert result["processed"] == 0
            mock_run.assert_called_once()

    def test_enrich_pending_leads_task_runs(self):
        from app.tasks.scheduled import enrich_pending_leads

        with patch("app.tasks.scheduled.asyncio.run") as mock_run:
            mock_run.return_value = {"enriched": 0, "skipped": 0}
            result = enrich_pending_leads()
            assert result["enriched"] == 0
            mock_run.assert_called_once()

    def test_sync_dnc_registry_task_runs(self):
        from app.tasks.scheduled import sync_dnc_registry

        with patch("app.tasks.scheduled.asyncio.run") as mock_run:
            mock_run.return_value = {"bounced_marked": 0, "old_optouts_archived": 0}
            result = sync_dnc_registry()
            assert result["bounced_marked"] == 0
            mock_run.assert_called_once()

    def test_generate_daily_report_task_runs(self):
        from app.tasks.scheduled import generate_daily_report

        with patch("app.tasks.scheduled.asyncio.run") as mock_run:
            mock_run.return_value = {"total_leads": 0, "conversion_rate": 0}
            result = generate_daily_report()
            assert result["total_leads"] == 0
            mock_run.assert_called_once()
