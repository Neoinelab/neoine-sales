from typing import TYPE_CHECKING

import pytest

from tests.support.raw_sql import run_sql
from tests.support.schema_catalog import then_schema_is_at, when_operator_upgrades

if TYPE_CHECKING:
    from sqlalchemy.engine import URL

pytestmark = pytest.mark.integration


async def test_upgrade_preserves_completed_auth_settings_without_reopening_setup(
    blank_database: URL,
) -> None:
    """기존 인증 설정을 보존하고 배포만으로 AD 관리자 등록을 다시 요구하지 않는다."""
    # given: 직전 리비전에서 AD 설정을 완료한 상태다
    await when_operator_upgrades(blank_database, target="f7a2c9e4b610")
    await run_sql(
        blank_database,
        "INSERT INTO auth_settings (id, mode, updated_at) VALUES (1, 'ad', CURRENT_TIMESTAMP)",
    )
    before = await run_sql(
        blank_database, "SELECT id, mode, updated_at, setup_pending FROM auth_settings"
    )

    # when: AD 관리자 등록 진행 상태 컬럼을 추가한다
    await when_operator_upgrades(blank_database, target="a4d8e2c6f901")

    # then: 기존 설정은 그대로이며 관리자 등록은 완료 상태다
    await then_schema_is_at(blank_database, "a4d8e2c6f901")
    after = await run_sql(
        blank_database, "SELECT id, mode, updated_at, setup_pending FROM auth_settings"
    )
    assert after == before
    admin_pending = await run_sql(blank_database, "SELECT admin_setup_pending FROM auth_settings")
    assert admin_pending == [(False,)]
