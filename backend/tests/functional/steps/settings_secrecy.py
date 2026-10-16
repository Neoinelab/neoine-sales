"""AD 설정 비밀번호 비노출 시나리오의 When·Then step."""

from typing import TYPE_CHECKING

from tests.functional.steps.auth import ADMIN_LOGIN
from tests.functional.steps.settings import (
    SETTINGS,
    SETTINGS_TEST,
    dump_tables,
    probe_payload,
    update_payload,
)

if TYPE_CHECKING:
    from collections.abc import Sequence

    from httpx import Response

    from tests.functional.conftest import Api


async def when_admin_saves_and_tests_with_wrong_and_right_passwords(
    api: Api, *, right: str, wrong: str, base_dn: str
) -> list[Response]:
    """admin이 같은 설정을 틀린 비밀번호·맞는 비밀번호로 각각 저장하고 연결 테스트한다."""
    return [
        await api.put(SETTINGS, json=update_payload(1, wrong, base_dn=base_dn)),
        await api.put(SETTINGS, json=update_payload(1, right, base_dn=base_dn)),
        await api.post(SETTINGS_TEST, json=probe_payload(wrong)),
        await api.post(SETTINGS_TEST, json=probe_payload(right)),
    ]


async def then_no_table_holds_the_passwords(
    api: Api, tables: Sequence[str], *, passwords: Sequence[str], saved_base_dn: str
) -> None:
    """저장·실패 카운터는 남았지만 어떤 테이블에도 입력한 비밀번호가 없다."""
    dumped = await dump_tables(api, tuple(tables))
    assert saved_base_dn in dumped["directory_settings"], "저장이 일어나지 않아 검사가 의미 없다"
    assert dumped["login_failures"], "실패 카운터가 남지 않아 검사가 의미 없다"
    for table, content in dumped.items():
        for password in passwords:
            assert password not in content, table
    assert ADMIN_LOGIN not in dumped["login_failures"]
