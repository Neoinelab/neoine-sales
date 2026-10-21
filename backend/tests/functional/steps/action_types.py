"""Action 유형 feature의 step: 목록·추가·이름 변경·삭제와 사용 수, 생성자 퇴사 확인.

Given은 공개 API로 사전 상태를 만들고(필요한 역할로 로그인한 상태에서 호출), When은 HTTP API 하나를
호출하며, Then은 응답과 다시 조회한 목록만 본다. 마이그레이션 직후 DB의 기본 유형 id는 무작위이므로
id는 항상 이름으로 목록에서 찾는다.
"""

from typing import TYPE_CHECKING, Final, cast

from tests.factories_action_type import DEFAULT_ACTION_TYPE_NAMES
from tests.functional.steps.auth import USERS

if TYPE_CHECKING:
    from httpx import Response

    from tests.functional.conftest import Api

TYPES: Final = "/api/v1/action-types"
DEFAULT_ORDER: Final = list(DEFAULT_ACTION_TYPE_NAMES)
TYPE_FIELDS: Final = {
    "id",
    "name",
    "is_default",
    "created_by",
    "usage_count",
    "created_at",
    "updated_at",
}
DUPLICATE_MESSAGE: Final = "이미 있는 유형 이름입니다."
REQUIRED_MESSAGE: Final = "유형을 입력하세요."
TOO_LONG_MESSAGE: Final = "유형은 50자 이내로 입력하세요."
UNKNOWN_MESSAGE: Final = "선택한 유형이 없습니다. 목록에서 다시 선택하세요."
ADMIN_REQUIRED: Final = "관리자 권한이 필요합니다"


# --- Given ---


async def given_type_list(api: Api) -> list[dict[str, object]]:
    response = await api.get(TYPES)
    assert response.status_code == 200, response.text
    return list(response.json())


async def given_type_id(api: Api, name: str) -> int:
    """이름이 name인 유형의 id(대소문자 그대로 일치하는 한 개)."""
    found = [x for x in await given_type_list(api) if x["name"] == name]
    assert len(found) == 1, name
    return cast("int", found[0]["id"])


async def given_type_created(api: Api, name: str) -> dict[str, object]:
    """지금 로그인한 사용자가 유형을 만들어 두었다(응답 본문을 돌려준다)."""
    response = await when_create_type(api, name)
    assert response.status_code == 201, f"Given 실패 {response.status_code}: {response.text}"
    return dict(response.json())


# --- When (HTTP API 하나) ---


async def when_list_types(api: Api) -> Response:
    return await api.get(TYPES)


async def when_create_type(api: Api, name: str) -> Response:
    return await api.post(TYPES, json={"name": name})


async def when_rename_type(api: Api, type_id: object, name: str) -> Response:
    return await api.patch(f"{TYPES}/{type_id}", json={"name": name})


async def when_delete_type(api: Api, type_id: object) -> Response:
    return await api.delete(f"{TYPES}/{type_id}")


async def when_delete_user_account(api: Api, *, user_id: object) -> Response:
    """admin이 사용자를 삭제한다(연결이 있으면 퇴사 처리)."""
    return await api.delete(f"{USERS}/{user_id}")


# --- Then (관찰 가능한 결과) ---


def then_types_are_the_defaults(response: Response) -> None:
    """기본 유형 8개가 시드 순서대로 있고 생성자도 쓰는 Action도 없다."""
    items = response.json()
    assert [x["name"] for x in items] == DEFAULT_ORDER, items
    assert all(x["is_default"] is True and x["created_by"] is None for x in items)
    assert all(x["usage_count"] == 0 for x in items)


def then_every_type_has_the_documented_fields(response: Response) -> None:
    for item in response.json():
        assert set(item) == TYPE_FIELDS, item


def then_location_points_to_the_created(response: Response) -> None:
    assert response.headers["location"] == f"{TYPES}/{response.json()['id']}"


async def then_type_names_are(api: Api, names: list[str]) -> None:
    """다시 조회한 유형 이름이 순서까지 같다."""
    assert [x["name"] for x in await given_type_list(api)] == names


async def then_type_count_is(api: Api, count: int) -> None:
    assert len(await given_type_list(api)) == count


async def then_type_usage_is(api: Api, name: str, count: int) -> None:
    found = [x for x in await given_type_list(api) if x["name"] == name]
    assert [x["usage_count"] for x in found] == [count], found


async def then_type_creator_is(api: Api, *, name: str, user_id: int, resigned: bool) -> None:
    """다시 조회한 목록에서 그 이름의 유형은 한 개이고 만든 사람이 user_id(퇴사 여부 포함)다."""
    created = [x for x in await given_type_list(api) if x["name"] == name]
    assert [x["created_by"]["id"] for x in created] == [user_id]  # type: ignore[index]
    assert [x["created_by"]["resigned"] for x in created] == [resigned]  # type: ignore[index]
