"""Action 라우터(`/deals/{code}/actions`, `/deal-actions/{id}`) 단위 테스트(AC).

FakeUseCases 위의 앱으로 상태 코드, Location, 응답 모양, 역할별 권한, 인증을 본다.
내용 규칙·판정 순서는 유스케이스 테스트(`tests/unit/application/test_*deal_action*.py`)가 맡는다.
"""

from typing import TYPE_CHECKING, Any, Final

import pytest

from app.domain.auth.principal import Role
from tests.factories_deal import seed_deal
from tests.fakes.catalog_seed import seed_action_types, seed_catalog
from tests.fakes.use_cases import FakeUseCases
from tests.support.ids import MAX_ID
from tests.support.user_ids import OWNER_ID
from tests.support.user_seed import ensure_users
from tests.unit.web.saved_report_http import clients, problem

if TYPE_CHECKING:
    from httpx import AsyncClient

CODE: Final = "20261016-A001"
DEAL_ACTIONS: Final = f"/api/v1/deals/{CODE}/actions"
SINGLE: Final = "/api/v1/deal-actions"
READ_ONLY: Final = "이 작업을 할 권한이 없습니다(읽기 전용 계정)"
USERS: Final = {
    "anon": Role.USER,
    "boss": Role.ADMIN,
    "kim": Role.SALES,
    "lee": Role.SALES,
    "viewer": Role.USER,
}
RESPONSE_KEYS: Final = {
    "id",
    "deal_code",
    "action_type",
    "action",
    "next_action",
    "due_date",
    "next_action_status",
    "next_action_closed_at",
    "memo",
    "acted_at",
    "actor",
    "status_key",
    "forecast_key",
    "created_at",
    "updated_at",
}
BODY: Final[dict[str, Any]] = {
    "action_type": {"name": "미팅"},
    "action": "킥오프 미팅",
    "next_action": "요구사항 문서 전달",
    "due_date": "2027-01-15",
    "memo": "요구사항 정리",
}


async def _use_cases_with_deal() -> FakeUseCases:
    """Owner·Deal 하나(CODE)·기본 코드·기본 Action 유형 8개가 있는 Fake 앱 상태."""
    use_cases = FakeUseCases()
    seed_catalog(use_cases.uow)
    seed_action_types(use_cases.uow)
    async with use_cases.uow as uow:
        await ensure_users(uow.users, OWNER_ID)
        await seed_deal(uow, code=CODE, commit=False, owner_user_id=OWNER_ID)
        await uow.commit()
    return use_cases


async def _register(http: AsyncClient) -> dict[str, Any]:
    response = await http.post(DEAL_ACTIONS, json=BODY)
    assert response.status_code == 201, response.text
    return dict(response.json())


async def test_post_creates_the_action_with_location_and_the_server_decided_values() -> None:
    """등록하면 201과 Location이 오고 담당자·상태를 서버가 정한다.

    테스트 코드: AC-001
    """
    # given: Deal이 있고 sales KIM이 로그인했다
    use_cases = await _use_cases_with_deal()
    async with clients(use_cases, USERS) as c:
        # when: KIM이 기본 Action 입력으로 등록한다
        response = await c["kim"].post(DEAL_ACTIONS, json=BODY)
        body = response.json()
        again = await c["kim"].get(f"{SINGLE}/{body['id']}")

    # then: 201이고 Location이 /api/v1/deal-actions/<id>다
    assert response.status_code == 201, response.text
    assert response.headers["Location"] == f"{SINGLE}/{body['id']}"
    # then: 담당자는 KIM(sales), 상태는 Open이고 유형은 {id, name}이다
    assert (body["actor"]["role"], body["next_action_status"]) == ("sales", "open")
    assert body["next_action_closed_at"] is None
    assert body["action_type"]["name"] == "미팅"
    # then: 같은 id로 다시 읽어도 같은 값이다
    assert again.json() == body


async def test_post_response_has_exactly_the_documented_keys_and_integer_ids() -> None:
    """등록 응답은 문서화된 15개 키를 가지고 id류는 JSON 정수다.

    테스트 코드: AC-002
    """
    # given: Deal이 있고 sales KIM이 로그인했다
    use_cases = await _use_cases_with_deal()
    async with clients(use_cases, USERS) as c:
        # when: KIM이 기본 Action을 등록한다
        body = await _register(c["kim"])

    # then: 키가 정확히 15개이고 유형은 {id, name}이며 id는 정수다
    assert set(body) == RESPONSE_KEYS
    assert set(body["action_type"]) == {"id", "name"}
    assert type(body["id"]) is int
    assert type(body["action_type"]["id"]) is int


@pytest.mark.parametrize("who", ["viewer", "anon"])
async def test_post_by_a_read_only_user_or_anonymous_visitor_is_rejected(who: str) -> None:
    """user는 읽기 전용 403, 미인증은 본문이 잘못돼도 401이고 Action이 생기지 않는다.

    테스트 코드: AC-014
    """
    # given: Deal이 있고 user와 로그인하지 않은 방문자가 있다
    use_cases = await _use_cases_with_deal()
    async with clients(use_cases, USERS) as c:
        # when: 잘못된 본문으로 등록한다
        response = await c[who].post(DEAL_ACTIONS, json={"action": 1})

    # then: user는 403 읽기 전용 문구, 방문자는 401이고 Action이 없다
    if who == "viewer":
        assert problem(response, 403, "forbidden")["detail"] == READ_ONLY
    else:
        problem(response, 401, "unauthenticated")
    assert use_cases.uow.deal_actions._items == {}


async def test_put_by_a_read_only_user_or_anonymous_visitor_is_rejected() -> None:
    """user의 수정은 읽기 전용 403, 미인증은 401이고 Action은 그대로다.

    테스트 코드: AC-058
    """
    # given: KIM이 남긴 Action이 있다
    use_cases = await _use_cases_with_deal()
    async with clients(use_cases, USERS) as c:
        created = await _register(c["kim"])
        # when: user가 그 Action을, 방문자가 없는 id를 고친다
        viewer = await c["viewer"].put(f"{SINGLE}/{created['id']}", json={**BODY, "action": "x"})
        anon = await c["anon"].put(f"{SINGLE}/{MAX_ID}", json=BODY)
        stored = await c["kim"].get(f"{SINGLE}/{created['id']}")

    # then: user는 403 읽기 전용 문구, 방문자는 401이다
    assert problem(viewer, 403, "forbidden")["detail"] == READ_ONLY
    problem(anon, 401, "unauthenticated")
    # then: Action은 그대로다
    assert stored.json()["action"] == "킥오프 미팅"


async def test_delete_by_a_read_only_user_is_forbidden_even_for_a_missing_id() -> None:
    """user의 삭제는 없는 id여도 읽기 전용 403, 미인증은 401이다.

    테스트 코드: AC-064
    """
    # given: KIM이 남긴 Action이 있다
    use_cases = await _use_cases_with_deal()
    async with clients(use_cases, USERS) as c:
        created = await _register(c["kim"])
        # when: user가 그 Action과 없는 id를 지우고, 방문자도 지운다
        existing = await c["viewer"].delete(f"{SINGLE}/{created['id']}")
        missing = await c["viewer"].delete(f"{SINGLE}/{MAX_ID}")
        anon = await c["anon"].delete(f"{SINGLE}/{created['id']}")
        stored = await c["kim"].get(f"{SINGLE}/{created['id']}")

    # then: user는 둘 다 403 읽기 전용 문구, 방문자는 401이다
    assert problem(existing, 403, "forbidden")["detail"] == READ_ONLY
    assert problem(missing, 403, "forbidden")["detail"] == READ_ONLY
    problem(anon, 401, "unauthenticated")
    # then: Action은 그대로다
    assert stored.status_code == 200


@pytest.mark.parametrize("who", ["viewer", "kim", "lee", "boss"])
async def test_every_role_can_read_the_list_and_a_single_action(who: str) -> None:
    """어떤 역할이든 목록과 한 건을 읽는다.

    테스트 코드: AC-068
    """
    # given: KIM이 남긴 Action이 있다
    use_cases = await _use_cases_with_deal()
    async with clients(use_cases, USERS) as c:
        created = await _register(c["kim"])
        # when: 해당 역할이 목록과 그 Action 한 건을 읽는다
        listed = await c[who].get(DEAL_ACTIONS)
        single = await c[who].get(f"{SINGLE}/{created['id']}")

    # then: 둘 다 200이고 목록은 {items}에 그 Action을 담는다
    assert listed.status_code == 200, listed.text
    assert [item["id"] for item in listed.json()["items"]] == [created["id"]]
    assert set(listed.json()) == {"items"}
    assert single.status_code == 200, single.text
    assert single.json()["action_type"] == created["action_type"]


async def test_reading_a_missing_action_or_deal_is_not_found_even_for_the_maximum_id() -> None:
    """없는 Action 한 건은 상한 id여도 404, 없는 Deal의 목록도 404다.

    테스트 코드: AC-069
    """
    # given: Deal만 있고 Action은 없다
    use_cases = await _use_cases_with_deal()
    async with clients(use_cases, USERS) as c:
        # when: 없는 id와 상한 id로 한 건을, 없는 code의 목록을 읽는다
        missing = await c["kim"].get(f"{SINGLE}/{MAX_ID - 1}")
        maximum = await c["kim"].get(f"{SINGLE}/{MAX_ID}")
        no_deal = await c["kim"].get("/api/v1/deals/20260101-ZZZZ/actions")

    # then: 모두 404 not-found이고 500이 아니다
    assert problem(missing, 404, "not-found")["detail"] == "Action을 찾을 수 없습니다."
    assert problem(maximum, 404, "not-found")["detail"] == "Action을 찾을 수 없습니다."
    assert problem(no_deal, 404, "not-found")["detail"] == "Deal을 찾을 수 없습니다."
