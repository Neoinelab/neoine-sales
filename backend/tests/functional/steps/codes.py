"""코드(Status·Forecast) feature의 step: 목록·사용 수·추가·이름 변경·순서 변경·삭제.

Given은 공개 API로 사전 상태를 만들고(admin으로 로그인한 상태에서 호출), When은 HTTP API 하나를
호출하며, Then은 응답과 다시 조회한 목록만 본다. 공통 Then(상태 코드, Problem)은
`steps/common.py`, 로그인은 `steps/auth.py`를 쓴다.
"""

from typing import TYPE_CHECKING, Literal
from uuid import uuid4

from tests.functional.steps.deals import customer_draft, given_deal, given_sales_owner

if TYPE_CHECKING:
    from httpx import Response

    from tests.functional.conftest import Api

CODES = "/api/v1/codes"
CODE_USAGE = "/api/v1/codes/usage"
CODE_ORDER = "/api/v1/codes/order"

Kind = Literal["status", "forecast"]
GROUPS = {"status": "statuses", "forecast": "forecasts"}
CODE_FIELDS = {"id", "kind", "key", "name", "order", "locked", "outcome", "probability_hint"}

# 사용자에게 보이는 문구(계획 4.2)
LOCKED_MESSAGE = "시스템과 연결된 코드는 삭제할 수 없습니다. 이름과 순서는 변경할 수 있습니다."
DUPLICATE_MESSAGE = "같은 이름의 코드가 이미 있습니다."
BLANK_MESSAGE = "이름을 입력하세요."
REORDER_MESSAGE = "순서 목록이 올바르지 않습니다."


def in_use_message(count: int) -> str:
    return f"사용 중인 코드는 삭제할 수 없습니다. (Deal {count}건)"


def unknown_id() -> str:
    """어떤 코드·Label에도 없는 id."""
    return str(uuid4())


# --- Given ---


async def given_code_list(api: Api, *, kind: Kind) -> list[dict[str, object]]:
    """GET /codes로 본 해당 종류의 코드 목록(순서대로)."""
    response = await api.get(CODES)
    assert response.status_code == 200, response.text
    return list(response.json()[GROUPS[kind]])


async def given_code_id(api: Api, *, kind: Kind, key: str) -> str:
    codes = [c for c in await given_code_list(api, kind=kind) if c["key"] == key]
    assert len(codes) == 1, (kind, key)
    return str(codes[0]["id"])


async def given_code_ids(api: Api, *, kind: Kind) -> list[str]:
    return [str(c["id"]) for c in await given_code_list(api, kind=kind)]


async def given_code_created(
    api: Api, *, kind: Kind, name: str, probability_hint: str | None = None
) -> dict[str, object]:
    """admin이 코드를 추가해 두었다(응답 본문을 돌려준다)."""
    response = await when_create_code(api, kind=kind, name=name, probability_hint=probability_hint)
    assert response.status_code == 201, response.text
    return dict(response.json())


async def given_deal_in_status(api: Api, *, status_key: str, number: int = 1) -> None:
    """영업 담당자가 Owner인 Deal 1건이 해당 Status에 있다(admin 로그인 상태에서 부른다).

    계약완료는 Forecast Won과 함께만 있을 수 있어 그 경우 Forecast를 Won으로 둔다. 고객은
    Deal 등록 입력(ContactDraft)으로 함께 만들어진다.
    """
    await given_deal(
        api,
        owner_user_id=await given_sales_owner(api),
        status_key=status_key,
        forecast_key="won" if status_key == "contract_completed" else "pipeline",
        customer=customer_draft(company=f"고객{number}"),
    )


# --- When (HTTP API 하나) ---


async def when_list_codes(api: Api) -> Response:
    return await api.get(CODES)


async def when_list_code_usage(api: Api, *, kind: Kind) -> Response:
    return await api.get(CODE_USAGE, params={"kind": kind})


async def when_create_code(
    api: Api, *, kind: Kind, name: str, probability_hint: str | None = None
) -> Response:
    body: dict[str, object] = {"kind": kind, "name": name}
    if probability_hint is not None:
        body["probability_hint"] = probability_hint
    return await api.post(CODES, json=body)


async def when_rename_code(api: Api, *, code_id: str, name: str) -> Response:
    return await api.patch(f"{CODES}/{code_id}", json={"name": name})


async def when_reorder_codes(api: Api, *, kind: Kind, ordered_ids: list[str]) -> Response:
    return await api.put(CODE_ORDER, json={"kind": kind, "ordered_ids": ordered_ids})


async def when_delete_code(api: Api, *, code_id: str) -> Response:
    return await api.delete(f"{CODES}/{code_id}")


# --- Then ---


def then_code_keys_are(response: Response, *, kind: Kind, keys: list[str]) -> None:
    """GET /codes 응답의 해당 종류 코드 key가 순서까지 같다."""
    assert [c["key"] for c in response.json()[GROUPS[kind]]] == keys


def then_every_code_has_the_documented_fields(response: Response, *, kind: Kind) -> None:
    for code in response.json()[GROUPS[kind]]:
        assert set(code) == CODE_FIELDS, code


def then_usage_keys_are(response: Response, keys: list[str]) -> None:
    """GET /codes/usage 응답의 코드 key가 순서까지 같다."""
    assert [c["key"] for c in response.json()] == keys


def then_usage_counts_are(response: Response, expected: dict[str, int]) -> None:
    """usage 응답에서 key별 usage_count가 expected와 같다(expected에 없는 key는 0이어야 한다)."""
    counts = {c["key"]: c["usage_count"] for c in response.json()}
    assert counts == {key: expected.get(key, 0) for key in counts}, counts
    assert set(expected) <= set(counts), counts


def then_detail_is(response: Response, detail: str) -> None:
    assert response.json()["detail"] == detail


def then_location_points_to_the_created(response: Response) -> None:
    assert response.headers["location"] == f"{CODES}/{response.json()['id']}"


async def then_kind_order_is(api: Api, *, kind: Kind, keys: list[str]) -> None:
    """다시 조회한 해당 종류 코드가 key 순서와 order 1..n으로 정렬되어 있다."""
    codes = await given_code_list(api, kind=kind)
    assert [c["key"] for c in codes] == keys
    assert [c["order"] for c in codes] == list(range(1, len(keys) + 1))


async def then_code_name_is(api: Api, *, kind: Kind, key: str, name: str) -> None:
    codes = [c for c in await given_code_list(api, kind=kind) if c["key"] == key]
    assert [c["name"] for c in codes] == [name]


async def then_code_exists(api: Api, *, kind: Kind, key: str) -> None:
    assert key in [c["key"] for c in await given_code_list(api, kind=kind)]


async def then_code_is_gone(api: Api, *, kind: Kind, key: str) -> None:
    assert key not in [c["key"] for c in await given_code_list(api, kind=kind)]


async def then_code_count_is(api: Api, *, kind: Kind, count: int) -> None:
    assert len(await given_code_list(api, kind=kind)) == count
