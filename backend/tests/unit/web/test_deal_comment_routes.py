"""Deal Comment 라우터(`/deals/{code}/comments`, `/deal-comments/{id}`) 단위 테스트(CM).

FakeUseCases 위의 앱으로 상태 코드, Location, 응답 모양, 요청 형식 오류, 역할별 권한, 인증, 판정
순서(401 -> 403 -> 422 -> 404)를 본다. 본문 규칙·이력은 유스케이스 테스트가 맡는다.
"""

from typing import Any

import pytest

from tests.support.ids import MAX_ID, MISSING_ID
from tests.unit.web.deal_comment_http import (
    BLANK,
    CODE,
    DEAL_COMMENTS,
    NOT_FOUND,
    OTHER,
    READ_ONLY,
    RESPONSE_KEYS,
    SINGLE,
    USERS,
    clients,
    post_action,
    post_comment,
    problem,
    seed,
)

DEAL_NOT_FOUND = "Deal을 찾을 수 없습니다."
ACTION_NOT_IN_DEAL = "선택한 Action이 이 Deal에 없습니다."


async def test_post_creates_a_deal_comment_with_location_and_the_server_decided_values() -> None:
    """Comment를 쓰면 201과 Location이 오고 응답 키가 정확하며 작성자·시각을 서버가 정한다.

    테스트 코드: CM-001
    """
    # given: Deal이 있고 sales PARK(Owner가 아님)이 로그인했다
    use_cases = await seed()
    async with clients(use_cases, USERS) as c:
        # when: PARK이 본문 "고객사 예산 회의 예정"으로 쓰고 같은 id로 다시 읽는다
        response = await c["park"].post(DEAL_COMMENTS, json={"body": "고객사 예산 회의 예정"})
        body = response.json()
        again = await c["viewer"].get(f"{SINGLE}/{body['id']}")

    # then: 201이고 Location이 /api/v1/deal-comments/<id>다
    assert response.status_code == 201, response.text
    assert response.headers["Location"] == f"{SINGLE}/{body['id']}"
    # then: 응답 키는 정확히 아홉 개이고 Deal Comment라 action_id·action은 null이다
    assert set(body) == RESPONSE_KEYS
    assert (body["deal_code"], body["action_id"], body["body"]) == (
        CODE,
        None,
        "고객사 예산 회의 예정",
    )
    assert body["action"] is None
    assert body["read_at"] is None  # PARK은 Owner가 아니므로 읽지 않음
    # then: 작성자는 PARK이고 두 시각이 같으며 id는 정수다
    assert body["author"]["label"] == "사용자 park"
    assert body["created_at"] == body["updated_at"]
    assert type(body["id"]) is int
    # then: 같은 id로 다시 읽어도 같은 값이다
    assert again.json() == body


async def test_a_null_action_id_is_a_deal_comment_and_an_action_id_links_the_action() -> None:
    """action_id가 null이면 Deal Comment이고 값이 있으면 그 Action의 Action Comment다.

    테스트 코드: CM-005, CM-008
    """
    # given: Deal과 그 Deal의 Action
    use_cases = await seed()
    async with clients(use_cases, USERS) as c:
        action_id = await post_action(c["kim"])
        # when: action_id null과 Action id로 각각 쓴다
        deal_level = await c["park"].post(DEAL_COMMENTS, json={"body": "a", "action_id": None})
        on_action = await c["park"].post(
            DEAL_COMMENTS, json={"body": "견적서 초안 공유함", "action_id": action_id}
        )

    # then: 둘 다 201이고 연결이 각각 null과 Action id다
    assert deal_level.status_code == 201, deal_level.text
    assert deal_level.json()["action_id"] is None
    assert on_action.status_code == 201, on_action.text
    assert on_action.json()["action_id"] == action_id


@pytest.mark.parametrize(
    "payload",
    [
        {},
        {"body": None},
        {"body": 1},
        {"body": "a", "action_id": "1"},
        {"body": "a", "action_id": 0},
        {"body": "a", "action_id": 9_007_199_254_740_992},
        {"body": "a", "author_user_id": 1},
        {"body": "a", "memo": "x"},
    ],
    ids=[
        "empty",
        "null-body",
        "numeric-body",
        "string-action-id",
        "zero-action-id",
        "over-max-action-id",
        "author-key",
        "memo-key",
    ],
)
async def test_a_malformed_create_body_is_a_request_validation_error(
    payload: dict[str, Any],
) -> None:
    """작성 요청 형식이 틀리면 422 request-validation이고 아무것도 저장되지 않는다.

    테스트 코드: CM-005
    """
    # given: Deal이 있고 sales KIM이 로그인했다
    use_cases = await seed()
    async with clients(use_cases, USERS) as c:
        # when: 형식이 틀린 본문으로 쓴다
        response = await c["kim"].post(DEAL_COMMENTS, json=payload)

    # then: 422 request-validation이고 Comment가 없다
    problem(response, 422, "request-validation")
    assert use_cases.uow.deal_comments._items == {}


@pytest.mark.parametrize("code", ["20991231-ZZZZ", "not-a-code"])
async def test_a_missing_or_malformed_deal_code_is_404_even_with_a_blank_body(code: str) -> None:
    """없는 Deal·형식이 틀린 code는 본문이 잘못돼도 404가 먼저다.

    테스트 코드: CM-006
    """
    # given: sales KIM이 로그인했다
    use_cases = await seed()
    async with clients(use_cases, USERS) as c:
        # when: 없는 Deal에 빈 본문으로 쓴다
        response = await c["kim"].post(f"/api/v1/deals/{code}/comments", json={"body": ""})

    # then: 404 not-found "Deal을 찾을 수 없습니다."다
    assert problem(response, 404, "not-found")["detail"] == DEAL_NOT_FOUND


async def test_blank_and_nul_bodies_and_foreign_actions_are_422_invalid_value() -> None:
    """빈 본문·NUL·다른 Deal의 Action·없는 Action은 422 invalid-value이고 저장되지 않는다.

    테스트 코드: CM-003, CM-004, CM-009
    """
    # given: Deal D·E와 E의 Action
    use_cases = await seed()
    async with clients(use_cases, USERS) as c:
        foreign = await post_action(c["kim"], OTHER)
        # when: 빈 본문, NUL 본문, E의 Action, 없는 Action으로 D에 쓴다
        blank = await c["kim"].post(DEAL_COMMENTS, json={"body": "  \n "})
        nul = await c["kim"].post(DEAL_COMMENTS, json={"body": "가\x00나"})
        other_deal = await c["kim"].post(DEAL_COMMENTS, json={"body": "a", "action_id": foreign})
        missing = await c["kim"].post(DEAL_COMMENTS, json={"body": "a", "action_id": MISSING_ID})

    # then: 모두 422 invalid-value이고 문구가 문서대로다
    assert problem(blank, 422, "invalid-value")["detail"] == BLANK
    assert problem(nul, 422, "invalid-value")["detail"] == "Comment에는 NUL 문자를 쓸 수 없습니다"
    assert problem(other_deal, 422, "invalid-value")["detail"] == ACTION_NOT_IN_DEAL
    assert problem(missing, 422, "invalid-value")["detail"] == ACTION_NOT_IN_DEAL
    assert use_cases.uow.deal_comments._items == {}


@pytest.mark.parametrize("code", [CODE, "20991231-ZZZZ"])
async def test_a_read_only_user_cannot_write_even_to_a_missing_deal_and_anonymous_gets_401(
    code: str,
) -> None:
    """user의 작성은 없는 Deal이어도 읽기 전용 403, 미인증은 401이고 Comment가 없다.

    테스트 코드: CM-007
    """
    # given: Deal과 user, 로그인하지 않은 방문자
    use_cases = await seed()
    url = f"/api/v1/deals/{code}/comments"
    async with clients(use_cases, USERS) as c:
        # when: user와 방문자가 쓴다
        viewer = await c["viewer"].post(url, json={"body": "a"})
        anon = await c["anon"].post(url, json={"body": "a"})

    # then: user는 403 읽기 전용 문구, 방문자는 401이다
    assert problem(viewer, 403, "forbidden")["detail"] == READ_ONLY
    problem(anon, 401, "unauthenticated")
    assert use_cases.uow.deal_comments._items == {}


async def test_every_role_reads_the_list_and_one_comment_and_anonymous_gets_401() -> None:
    """user를 포함한 어떤 로그인 역할이든 목록과 한 건을 읽고 미인증은 401이다(목록 키는 items뿐).

    테스트 코드: CM-013, CM-015
    """
    # given: KIM이 쓴 Comment 하나
    use_cases = await seed()
    async with clients(use_cases, USERS) as c:
        created = await post_comment(c["kim"])
        # when: 각 역할이 목록과 한 건을 읽고 방문자도 읽는다
        responses = {
            who: (
                await c[who].get(DEAL_COMMENTS),
                await c[who].get(f"{SINGLE}/{created['id']}"),
            )
            for who in ("viewer", "kim", "park", "boss", "anon")
        }

    # then: 로그인한 역할은 200이고 목록은 {items}에 그 Comment를 담는다
    for who in ("viewer", "kim", "park", "boss"):
        listed, single = responses[who]
        assert listed.status_code == 200, listed.text
        assert set(listed.json()) == {"items"}
        assert [item["id"] for item in listed.json()["items"]] == [created["id"]]
        assert single.status_code == 200
    # then: 방문자는 둘 다 401이다
    for response in responses["anon"]:
        problem(response, 401, "unauthenticated")


async def test_the_list_filters_by_action_and_rejects_a_malformed_action_id() -> None:
    """action_id로 거르면 그 Action의 Comment만 나오고, 형식이 틀리면 422 request-validation이다.

    테스트 코드: CM-014
    """
    # given: Deal Comment 하나와 Action A의 Action Comment 하나, 다른 Deal의 Action B
    use_cases = await seed()
    async with clients(use_cases, USERS) as c:
        action_a = await post_action(c["kim"])
        action_b = await post_action(c["kim"], OTHER)
        await post_comment(c["kim"], "딜")
        on_a = await post_comment(c["kim"], "액션", action_id=action_a)
        # when: A, B, 없는 id, 숫자가 아닌 id로 거른다
        of_a = await c["kim"].get(DEAL_COMMENTS, params={"action_id": action_a})
        of_b = await c["kim"].get(DEAL_COMMENTS, params={"action_id": action_b})
        of_missing = await c["kim"].get(DEAL_COMMENTS, params={"action_id": MISSING_ID})
        malformed = await c["kim"].get(DEAL_COMMENTS, params={"action_id": "abc"})

    # then: A는 그 Comment만, B·없는 id는 빈 목록, 형식 오류는 422다
    assert [i["id"] for i in of_a.json()["items"]] == [on_a["id"]]
    assert of_b.json() == {"items": []}
    assert of_missing.json() == {"items": []}
    problem(malformed, 422, "request-validation")


async def test_listing_a_missing_deal_is_404() -> None:
    """없는 Deal의 목록은 404 "Deal을 찾을 수 없습니다."다.

    테스트 코드: CM-015
    """
    # given: 로그인한 user
    use_cases = await seed()
    async with clients(use_cases, USERS) as c:
        # when: 없는 Deal의 목록을 읽는다
        response = await c["viewer"].get("/api/v1/deals/20991231-ZZZZ/comments")

    # then: 404다
    assert problem(response, 404, "not-found")["detail"] == DEAL_NOT_FOUND


async def test_a_missing_comment_is_404_for_the_maximum_id_and_422_for_an_invalid_id() -> None:
    """없는 Comment 한 건은 상한 id여도 404이고 0은 422다.

    테스트 코드: CM-016
    """
    # given: 로그인한 sales
    use_cases = await seed()
    async with clients(use_cases, USERS) as c:
        # when: 상한 id와 0으로 읽는다
        maximum = await c["kim"].get(f"{SINGLE}/{MAX_ID}")
        zero = await c["kim"].get(f"{SINGLE}/0")

    # then: 상한 id는 404 "Comment를 찾을 수 없습니다.", 0은 422다
    assert problem(maximum, 404, "not-found")["detail"] == NOT_FOUND
    problem(zero, 422, "request-validation")


async def test_put_is_405_and_the_comment_is_unchanged() -> None:
    """수정 경로가 없어 PUT은 어떤 역할이든 405이고 Comment 본문·이력이 그대로다.

    테스트 코드: CM-057
    """
    # given: KIM이 쓴 Comment와 현재 이력 수
    use_cases = await seed()
    async with clients(use_cases, USERS) as c:
        created = await post_comment(c["kim"], "자료 전달")
        url = f"{SINGLE}/{created['id']}"
        history_before = await c["kim"].get(f"/api/v1/deals/{CODE}/history")

        # when: 작성자 KIM, admin, user가 PUT으로 고치려 한다
        responses = [
            await c[who].put(url, json={"body": "바꿈"}) for who in ("kim", "boss", "viewer")
        ]
        again = await c["kim"].get(url)
        history_after = await c["kim"].get(f"/api/v1/deals/{CODE}/history")

    # then: 모두 405이고 본문과 이력이 그대로다
    assert [r.status_code for r in responses] == [405, 405, 405]
    assert again.json()["body"] == "자료 전달"
    assert history_after.json() == history_before.json()


async def test_the_list_is_newest_first_and_each_action_comment_carries_the_action_summary() -> (
    None
):
    """목록은 최근순이고 Action Comment는 연결 Action 요약을, Deal Comment는 null을 담는다.

    테스트 코드: CM-013, CM-056
    """
    # given: KIM이 Deal Comment, Action Comment, Deal Comment를 차례로 쓴다
    use_cases = await seed()
    async with clients(use_cases, USERS) as c:
        action_id = await post_action(c["kim"])
        first = await post_comment(c["kim"], "c1")
        second = await post_comment(c["kim"], "c2", action_id=action_id)
        third = await post_comment(c["kim"], "c3")
        # when: user가 목록을 읽는다
        listed = (await c["viewer"].get(DEAL_COMMENTS)).json()["items"]

    # then: c3, c2, c1 순서이고 키는 정확히 아홉 개다
    assert [item["id"] for item in listed] == [third["id"], second["id"], first["id"]]
    assert all(set(item) == RESPONSE_KEYS for item in listed)
    # then: c2의 action은 {id, acted_on, action, next_action}이고 Deal Comment는 null이다
    summary = listed[1]["action"]
    assert set(summary) == {"id", "acted_on", "action", "next_action"}
    assert (summary["id"], summary["action"]) == (action_id, "킥오프")
    assert type(summary["acted_on"]) is str
    assert len(summary["acted_on"]) == 10  # YYYY-MM-DD
    assert listed[0]["action"] is None
    assert listed[2]["action"] is None


async def test_delete_returns_204_and_a_second_delete_is_404() -> None:
    """작성자가 지우면 204(본문 없음)이고 한 건 조회가 404이며 다시 지우면 404다.

    테스트 코드: CM-024
    """
    # given: KIM의 Comment
    use_cases = await seed()
    async with clients(use_cases, USERS) as c:
        created = await post_comment(c["kim"], "예산 확인")
        url = f"{SINGLE}/{created['id']}"
        # when: KIM이 지우고 다시 지우고 읽는다
        first = await c["kim"].delete(url)
        second = await c["kim"].delete(url)
        read = await c["kim"].get(url)

    # then: 204 + 빈 본문, 두 번째와 읽기는 404다
    assert first.status_code == 204
    assert first.content == b""
    assert problem(second, 404, "not-found")["detail"] == NOT_FOUND
    problem(read, 404, "not-found")


async def test_delete_permissions_other_sales_403_admin_204_user_403_before_lookup() -> None:
    """다른 sales의 삭제는 403, admin은 남의 Comment를 지우고, user는 없는 id여도 403이다.

    테스트 코드: CM-025
    """
    # given: KIM의 Comment k
    use_cases = await seed()
    async with clients(use_cases, USERS) as c:
        created = await post_comment(c["kim"], "원문")
        url = f"{SINGLE}/{created['id']}"
        # when: PARK, user(없는 id), 방문자, admin이 차례로 지운다
        other = await c["park"].delete(url)
        viewer = await c["viewer"].delete(f"{SINGLE}/{MISSING_ID}")
        anon = await c["anon"].delete(url)
        stored = await c["kim"].get(url)
        admin = await c["boss"].delete(url)

    # then: PARK은 403 고정 문구이고 k가 남아 있다
    assert (
        problem(other, 403, "forbidden")["detail"]
        == "본인 Comment 또는 admin만 삭제할 수 있습니다."
    )
    assert stored.status_code == 200
    # then: user는 없는 id여도 읽기 전용 403, 방문자는 401, admin은 204다
    assert problem(viewer, 403, "forbidden")["detail"] == READ_ONLY
    problem(anon, 401, "unauthenticated")
    assert admin.status_code == 204
