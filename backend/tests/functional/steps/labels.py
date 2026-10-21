"""BANT Label feature의 step: 목록·추가·이름 변경·삭제와 생성자 퇴사 확인.

Given은 공개 API로 사전 상태를 만들고(필요한 역할로 로그인한 상태에서 호출), When은 HTTP API 하나를
호출하며, Then은 응답과 다시 조회한 목록만 본다.
"""

from typing import TYPE_CHECKING, Literal, cast

from tests.fakes.catalog_seed import DEFAULT_LABELS
from tests.functional.steps.auth import ME, USERS

if TYPE_CHECKING:
    from httpx import Response

    from tests.functional.conftest import Api

LABELS = "/api/v1/bant-labels"

Category = Literal["budget", "authority", "need", "timeline"]
DEFAULT_ORDER = [(c, name) for c, names in DEFAULT_LABELS.items() for name in names]
LABEL_FIELDS = {
    "id",
    "category",
    "name",
    "is_default",
    "created_by",
    "created_at",
    "updated_at",
    "usage_count",
}


# --- Given ---


async def given_label_list(api: Api) -> list[dict[str, object]]:
    response = await api.get(LABELS)
    assert response.status_code == 200, response.text
    return list(response.json())


async def given_label_id(api: Api, *, category: Category, name: str) -> int:
    found = [
        x for x in await given_label_list(api) if (x["category"], x["name"]) == (category, name)
    ]
    assert len(found) == 1, (category, name)
    return cast("int", found[0]["id"])


async def given_current_user_id(api: Api) -> int:
    """지금 로그인한 사용자의 id."""
    response = await api.get(ME)
    assert response.status_code == 200, response.text
    return int(response.json()["user_id"])


async def given_label_created(api: Api, *, category: Category, name: str) -> dict[str, object]:
    """지금 로그인한 사용자가 Label을 만들어 두었다(응답 본문을 돌려준다)."""
    response = await when_create_label(api, category=category, name=name)
    assert response.status_code == 201, response.text
    return dict(response.json())


async def given_labels_created(api: Api, *, category: Category, names: list[str]) -> None:
    """지금 로그인한 사용자가 Label들을 차례로 만들어 두었다."""
    for name in names:
        await given_label_created(api, category=category, name=name)


# --- When (HTTP API 하나) ---


async def when_list_labels(api: Api) -> Response:
    return await api.get(LABELS)


async def when_create_label(api: Api, *, category: str, name: str) -> Response:
    return await api.post(LABELS, json={"category": category, "name": name})


async def when_rename_label(api: Api, *, label_id: object, name: str) -> Response:
    return await api.patch(f"{LABELS}/{label_id}", json={"name": name})


async def when_delete_label(api: Api, *, label_id: object) -> Response:
    return await api.delete(f"{LABELS}/{label_id}")


async def when_delete_user_account(api: Api, *, user_id: object) -> Response:
    """admin이 사용자를 삭제한다(연결이 있으면 퇴사 처리)."""
    return await api.delete(f"{USERS}/{user_id}")


# --- Then ---


def then_labels_are_the_defaults(response: Response) -> None:
    """기본 Label 23개가 구분 순서와 시드 순서대로 있고, 아직 아무 Deal도 쓰지 않는다."""
    labels = response.json()
    assert [(x["category"], x["name"]) for x in labels] == DEFAULT_ORDER
    assert all(x["is_default"] is True and x["created_by"] is None for x in labels)
    assert all(x["usage_count"] == 0 for x in labels)


def then_every_label_has_the_documented_fields(response: Response) -> None:
    for label in response.json():
        assert set(label) == LABEL_FIELDS, label


def then_location_points_to_the_created(response: Response) -> None:
    assert response.headers["location"] == f"{LABELS}/{response.json()['id']}"


async def then_label_names_are(api: Api, *, category: Category, names: list[str]) -> None:
    """다시 조회한 해당 구분의 Label 이름이 순서까지 같다."""
    listed = [x["name"] for x in await given_label_list(api) if x["category"] == category]
    assert listed == names


async def then_label_creator_is(api: Api, *, name: str, user_id: int, resigned: bool) -> None:
    """다시 조회한 목록에서 그 이름의 Label은 한 개이고 만든 사람이 user_id(퇴사 여부 포함)다."""
    created = [x for x in await given_label_list(api) if x["name"] == name]
    assert [x["created_by"]["id"] for x in created] == [user_id]  # type: ignore[index]
    assert [x["created_by"]["resigned"] for x in created] == [resigned]  # type: ignore[index]


async def then_label_exists(api: Api, *, category: Category, name: str) -> None:
    assert (category, name) in [(x["category"], x["name"]) for x in await given_label_list(api)]


async def then_label_is_gone(api: Api, *, category: Category, name: str) -> None:
    assert (category, name) not in [(x["category"], x["name"]) for x in await given_label_list(api)]


async def then_label_count_is(api: Api, *, count: int) -> None:
    assert len(await given_label_list(api)) == count
