"""사용자 선택 목록 시나리오의 Then step."""

from typing import TYPE_CHECKING

from tests.functional.steps.common import then_status_is
from tests.functional.steps.users import USER_REF_KEYS

if TYPE_CHECKING:
    from httpx import Response


def then_every_item_has_only_the_ref_fields(response: Response) -> None:
    """항목이 있고 모든 항목이 {id, name, resigned, label, role}만 담으며 이메일이 새지 않는다."""
    then_status_is(response, 200)
    body = response.json()
    assert body["items"]
    for item in body["items"]:
        assert set(item) == USER_REF_KEYS
    assert "@" not in str(body)  # 이메일(hong@corp.test, kim@corp.test)이 새지 않는다


def then_options_are(response: Response, expected: list[tuple[str, str]]) -> None:
    """선택 목록 응답의 (표시 이름, role)이 순서까지 같다."""
    then_status_is(response, 200)
    assert [(i["name"], i["role"]) for i in response.json()["items"]] == expected
