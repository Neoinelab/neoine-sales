"""Repository 계약 테스트용 fixture.

같은 계약 테스트가 InMemory Fake와 SQLAlchemy 구현(실제 PostgreSQL 임시 DB) 양쪽에서 돈다.
SQL 구현 case에는 integration 마커가 붙고, DB를 쓸 수 없으면 건너뛴다.
새 구현은 각 `*_case.py`의 PARAMS와 open 함수에 추가해 같은 테스트를 적용한다.

연락처(고객·파트너 통합)는 `contact_case.py`의 `contacts` fixture를 쓴다(Port 모양이 다르다).
"""

from typing import TYPE_CHECKING

import pytest
import pytest_asyncio

from tests.unit.repositories.action_type_case import PARAMS as ACTION_TYPE_PARAMS
from tests.unit.repositories.action_type_case import ActionTypeCase, open_action_type_case
from tests.unit.repositories.attachment_case import PARAMS as ATTACHMENT_PARAMS
from tests.unit.repositories.attachment_case import AttachmentCase, open_attachment_case
from tests.unit.repositories.catalog_case import PARAMS as CATALOG_PARAMS
from tests.unit.repositories.catalog_case import CatalogCase, open_catalog
from tests.unit.repositories.contact_case import PARAMS as CONTACT_PARAMS
from tests.unit.repositories.contact_case import ContactCase, open_contacts
from tests.unit.repositories.dashboard_case import PARAMS as DASHBOARD_PARAMS
from tests.unit.repositories.dashboard_case import DashboardCase, open_dashboard_case
from tests.unit.repositories.deal_action_case import PARAMS as ACTION_PARAMS
from tests.unit.repositories.deal_action_case import Case as ActionCase
from tests.unit.repositories.deal_action_case import open_case
from tests.unit.repositories.deal_case import PARAMS as DEAL_PARAMS
from tests.unit.repositories.deal_case import DealCase, open_deal_case
from tests.unit.repositories.file_storage_case import PARAMS as FILE_STORAGE_PARAMS
from tests.unit.repositories.file_storage_case import (
    FileStorageCase,
    open_fake_case,
    open_local_case,
)
from tests.unit.repositories.forecast_case import PARAMS as FORECAST_PARAMS
from tests.unit.repositories.forecast_case import ForecastCase, open_forecast_case
from tests.unit.repositories.forecast_snapshot_case import PARAMS as SNAPSHOT_PARAMS
from tests.unit.repositories.forecast_snapshot_case import SnapshotCase, open_snapshot_case
from tests.unit.repositories.partner_meeting_case import PARAMS as MEETING_PARAMS
from tests.unit.repositories.partner_meeting_case import MeetingCase, open_meeting_case
from tests.unit.repositories.report_case import PARAMS as REPORT_PARAMS
from tests.unit.repositories.report_case import ReportCase, open_report_case
from tests.unit.repositories.saved_report_case import PARAMS as SAVED_REPORT_PARAMS
from tests.unit.repositories.saved_report_case import SavedReportCase, open_saved_report_case
from tests.unit.repositories.vendor_case import PARAMS as VENDOR_PARAMS
from tests.unit.repositories.vendor_case import VendorCase, open_vendor_case

if TYPE_CHECKING:
    from collections.abc import AsyncIterator, Callable
    from pathlib import Path


@pytest.fixture(params=FILE_STORAGE_PARAMS)
def file_case(request: pytest.FixtureRequest, tmp_path: Path) -> FileStorageCase:
    """FileStorage 계약 테스트용 case (fake / local, local은 tmp_path 아래 실제 디렉터리)."""
    if request.param == "fake":
        return open_fake_case()
    return open_local_case(tmp_path)


@pytest_asyncio.fixture(params=DEAL_PARAMS)
async def deal_case(request: pytest.FixtureRequest) -> AsyncIterator[DealCase]:
    """DealRepository·DealHistoryRepository 계약 테스트용 case (fake / sql)."""
    url = request.getfixturevalue("test_database_url") if request.param == "sql" else None
    async with open_deal_case(request.param, url) as provided:
        yield provided


@pytest_asyncio.fixture(params=CONTACT_PARAMS)
async def contacts(request: pytest.FixtureRequest) -> AsyncIterator[ContactCase]:
    """ContactRepository(와 연락처를 참조하는 Deal) 계약 테스트용 case (fake / sql)."""
    url = request.getfixturevalue("test_database_url") if request.param == "sql" else None
    async with open_contacts(request.param, url) as provided:
        yield provided


@pytest_asyncio.fixture(params=CATALOG_PARAMS)
async def catalog(request: pytest.FixtureRequest) -> AsyncIterator[CatalogCase]:
    """CodeRepository·BantLabelRepository 계약 테스트용 case (fake / sql)."""
    url = request.getfixturevalue("test_database_url") if request.param == "sql" else None
    async with open_catalog(request.param, url) as provided:
        yield provided


@pytest_asyncio.fixture(params=ACTION_PARAMS)
async def action_case(request: pytest.FixtureRequest) -> AsyncIterator[ActionCase]:
    """DealActionRepository 계약 테스트용 case (fake / sql)."""
    url = request.getfixturevalue("test_database_url") if request.param == "sql" else None
    async with open_case(request.param, url) as provided:
        yield provided


@pytest_asyncio.fixture(params=ATTACHMENT_PARAMS)
async def attachment_case(request: pytest.FixtureRequest) -> AsyncIterator[AttachmentCase]:
    """AttachmentRepository 계약 테스트용 case (fake / sql)."""
    url = request.getfixturevalue("test_database_url") if request.param == "sql" else None
    async with open_attachment_case(request.param, url) as provided:
        yield provided


@pytest_asyncio.fixture(params=VENDOR_PARAMS)
async def vendor_case(request: pytest.FixtureRequest) -> AsyncIterator[VendorCase]:
    """VendorRepository 계약 테스트용 case (fake / sql)."""
    url = request.getfixturevalue("test_database_url") if request.param == "sql" else None
    async with open_vendor_case(request.param, url) as provided:
        yield provided


@pytest_asyncio.fixture(params=ACTION_TYPE_PARAMS)
async def action_type_case(request: pytest.FixtureRequest) -> AsyncIterator[ActionTypeCase]:
    """ActionTypeRepository 계약 테스트용 case (fake / sql)."""
    url = request.getfixturevalue("test_database_url") if request.param == "sql" else None
    async with open_action_type_case(request.param, url) as provided:
        yield provided


@pytest_asyncio.fixture(params=FORECAST_PARAMS)
async def forecast_case(request: pytest.FixtureRequest) -> AsyncIterator[ForecastCase]:
    """ForecastTallyRepository 계약 테스트용 case (fake / sql)."""
    url = request.getfixturevalue("test_database_url") if request.param == "sql" else None
    async with open_forecast_case(request.param, url) as provided:
        yield provided


@pytest_asyncio.fixture(params=SNAPSHOT_PARAMS)
async def snapshot_case(request: pytest.FixtureRequest) -> AsyncIterator[SnapshotCase]:
    """ForecastSnapshotRepository 계약 테스트용 case (fake / sql)."""
    url = request.getfixturevalue("test_database_url") if request.param == "sql" else None
    async with open_snapshot_case(request.param, url) as provided:
        yield provided


@pytest_asyncio.fixture(params=DASHBOARD_PARAMS)
async def dashboard_case(request: pytest.FixtureRequest) -> AsyncIterator[DashboardCase]:
    """DashboardTallyRepository 계약 테스트용 case (fake / sql)."""
    url = request.getfixturevalue("test_database_url") if request.param == "sql" else None
    async with open_dashboard_case(request.param, url) as provided:
        yield provided


@pytest_asyncio.fixture(params=REPORT_PARAMS)
async def report_case(
    request: pytest.FixtureRequest, local_tz: Callable[[str], None]
) -> AsyncIterator[ReportCase]:
    """ReportQueryRunner(SQL 전용) 계약 테스트용 case. 업무 시간대를 Asia/Seoul로 맞춘다."""
    local_tz("Asia/Seoul")
    url = request.getfixturevalue("test_database_url")
    async with open_report_case(request.param, url) as provided:
        yield provided


@pytest_asyncio.fixture(params=SAVED_REPORT_PARAMS)
async def saved_report_case(request: pytest.FixtureRequest) -> AsyncIterator[SavedReportCase]:
    """ReportRepository(저장 리포트) 계약 테스트용 case (fake / sql)."""
    url = request.getfixturevalue("test_database_url") if request.param == "sql" else None
    async with open_saved_report_case(request.param, url) as provided:
        yield provided


@pytest_asyncio.fixture(params=MEETING_PARAMS)
async def meeting_case(request: pytest.FixtureRequest) -> AsyncIterator[MeetingCase]:
    """PartnerMeetingRepository 계약 테스트용 case (fake / sql)."""
    url = request.getfixturevalue("test_database_url") if request.param == "sql" else None
    async with open_meeting_case(request.param, url) as provided:
        yield provided
