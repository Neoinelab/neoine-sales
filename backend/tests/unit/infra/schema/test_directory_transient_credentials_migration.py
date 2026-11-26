from typing import TYPE_CHECKING

import pytest

from tests.support.raw_sql import run_sql
from tests.support.schema_catalog import then_schema_is_at, when_operator_upgrades

if TYPE_CHECKING:
    from sqlalchemy.engine import URL

pytestmark = pytest.mark.integration


async def test_upgrade_clears_legacy_credentials_and_preserves_connection(
    blank_database: URL,
) -> None:
    await when_operator_upgrades(blank_database, target="a4d8e2c6f901")
    await run_sql(
        blank_database,
        "insert into directory_settings"
        " (id, revision, host, port, security, bind_account, bind_password_encrypted,"
        " base_dn, user_filter, connect_timeout_seconds, updated_at)"
        " values (1, 7, 'dc1.corp.test', 636, 'ssl', 'legacy-service', 'old-ciphertext',"
        " 'dc=corp,dc=test', '(sAMAccountName={login_id})', 5, now())",
    )
    query = (
        "select revision, host, port, security, base_dn, user_filter,"
        " connect_timeout_seconds, updated_at from directory_settings"
    )
    before = await run_sql(blank_database, query)
    await when_operator_upgrades(blank_database, target="b6e1f8a3d902")
    await then_schema_is_at(blank_database, "b6e1f8a3d902")
    assert await run_sql(blank_database, query) == before
    assert await run_sql(
        blank_database,
        "select bind_account, bind_password_encrypted from directory_settings",
    ) == [(None, None)]
