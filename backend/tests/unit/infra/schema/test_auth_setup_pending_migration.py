from typing import TYPE_CHECKING

import pytest

from tests.support.raw_sql import run_sql
from tests.support.schema_catalog import then_schema_is_at, when_operator_upgrades

if TYPE_CHECKING:
    from sqlalchemy.engine import URL

pytestmark = pytest.mark.integration


async def test_upgrade_preserves_existing_mode_and_marks_setup_complete(
    blank_database: URL,
) -> None:
    """기존 인증 설정을 보존하고 배포만으로 재설정을 요구하지 않는다."""
    # given: 직전 리비전에 인증 설정이 있다
    await when_operator_upgrades(blank_database, target="c5e9a2f7d104")
    await run_sql(
        blank_database,
        "INSERT INTO auth_settings (id, mode, updated_at) VALUES (1, 'local', CURRENT_TIMESTAMP)",
    )
    before = await run_sql(blank_database, "SELECT id, mode, updated_at FROM auth_settings")

    # when: 재설정 진행 상태 컬럼을 추가한다
    await when_operator_upgrades(blank_database, target="f7a2c9e4b610")

    # then: 저장된 값은 그대로이고 재설정을 요구하지 않는다
    await then_schema_is_at(blank_database, "f7a2c9e4b610")
    assert await run_sql(blank_database, "SELECT id, mode, updated_at FROM auth_settings") == before
    assert await run_sql(blank_database, "SELECT setup_pending FROM auth_settings") == [(False,)]
