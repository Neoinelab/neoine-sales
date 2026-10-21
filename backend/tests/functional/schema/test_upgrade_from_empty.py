"""Feature: 운영자는 빈 DB를 head까지 올리고, 과거 리비전 체인은 base로 내렸다 다시 올린다.

When: 운영자 명령(alembic upgrade/downgrade). 운영자에게 공개된 인터페이스는 HTTP가 아니라
이 명령이다. head(BIGINT id 리비전)는 되돌릴 수 없으므로(`test_bigint_ids_migration.py`가 거부를
검증한다) base로 내리는 시나리오는 그 아래 마지막 리비전(`deals_users_required_revision()`)에서
시작한다. 올리는 쪽은 head까지 올려 새 스키마를 확인한다.
"""

from typing import TYPE_CHECKING

import pytest

from tests.functional.steps.schema import (
    given_schema_at,
    table_names,
    when_operator_downgrades,
    when_operator_upgrades,
)
from tests.support.revisions import deals_users_required_revision

if TYPE_CHECKING:
    from sqlalchemy.engine import URL

pytestmark = pytest.mark.integration

EXPECTED_TABLES = {
    "contacts",
    "codes",  # 코드(Status·Forecast)
    "bant_labels",  # BANT Label
    "alert_settings",  # 경고 기준
    "deals",
    "deal_actions",
    "auth_sessions",
    "deal_partners",
    "deal_bant_labels",
    "deal_history",
    "users",
    "login_failures",
    "directory_settings",
    "storage_settings",  # P2b
    "deal_attachments",  # P2b
    "vendors",  # Vendor·Solution 관리
    "solutions",
    "action_types",  # Action 유형 카탈로그
}
# contacts로 통합된 customers·partners, 이력 테이블로 바뀐 deal_stage_changes는 head에 없다
RETIRED_TABLES = {"customers", "partners", "deal_stage_changes"}


async def test_operator_upgrade_to_head_creates_the_expected_tables(blank_database: URL) -> None:
    """Scenario: 빈 DB에 head까지 올리면 업무·인증 테이블이 모두 생긴다."""
    # Given
    # (마이그레이션이 하나도 적용되지 않은 빈 DB)
    # When
    await when_operator_upgrades(blank_database)
    # Then
    tables = await table_names(blank_database)
    assert tables >= EXPECTED_TABLES
    assert not RETIRED_TABLES & tables


async def test_operator_downgrade_to_base_removes_the_tables(blank_database: URL) -> None:
    """Scenario: BIGINT id 리비전 아래의 마지막 리비전에서 base로 내리면 모든 테이블이 사라진다."""
    # Given
    await given_schema_at(blank_database, deals_users_required_revision())
    assert EXPECTED_TABLES & await table_names(blank_database)
    # When
    await when_operator_downgrades(blank_database, target="base")
    # Then
    assert not (EXPECTED_TABLES & await table_names(blank_database))


async def test_operator_upgrade_after_a_full_downgrade_restores_the_tables(
    blank_database: URL,
) -> None:
    """Scenario: base까지 내린 DB를 다시 head로 올리면 테이블이 돌아온다."""
    # Given
    await given_schema_at(blank_database, deals_users_required_revision())
    await when_operator_downgrades(blank_database, target="base")
    # When
    await when_operator_upgrades(blank_database)
    # Then
    assert await table_names(blank_database) >= EXPECTED_TABLES
