"""Comment 읽음 처리·읽지 않은 수 라우터(`POST .../comment-reads`, `GET .../comment-counts`).

Deal의 Owner는 sales KIM이다(`seed(owner=KIM_ID)`). 상태 코드, 본문 형식 422, 역할·Owner 판정과
판정 순서(401 -> CSRF 403 -> user 403 -> 422 -> 404 -> Owner 403), 읽음 시각이 같게 보이는지,
집계 응답 모양을 본다. 규칙의 나머지는 유스케이스 테스트가 맡는다.
"""

from typing import Any

import pytest

from tests.support.ids import MAX_ID
from tests.support.user_ids import uid
from tests.unit.web.deal_comment_http import (
    CODE,
    COUNTS,
    DEAL_COMMENTS,
    OTHER,
    READ_FORBIDDEN,
    READ_ONLY,
    READS,
    SINGLE,
    USERS,
    clients,
    post_action,
    post_comment,
    problem,
    seed,
)

KIM_ID = uid("kim")
DEAL_NOT_FOUND = "Deal을 찾을 수 없습니다."


async def _read_at(http: Any, comment_id: int) -> Any:  # noqa: ANN401
    return (await http.get(f"{SINGLE}/{comment_id}")).json()["read_at"]


async def test_a_comment_written_by_the_owner_is_read_and_by_others_unread() -> None:
    """Owner가 쓴 Comment의 응답은 read_at이 작성 시각이고 다른 사람이 쓰면 null이다.

    테스트 코드: CM-048
    """
    # given: Deal의 Owner는 KIM
    use_cases = await seed(KIM_ID)
    async with clients(use_cases, USERS) as c:
        # when: KIM(Owner), PARK, admin이 각각 쓴다
        by_owner = await post_comment(c["kim"], "owner")
        by_park = await post_comment(c["park"], "park")
        by_boss = await post_comment(c["boss"], "boss")

    # then: Owner의 것만 작성 시각이 읽음 시각이다
    assert by_owner["read_at"] == by_owner["created_at"]
    assert by_park["read_at"] is None
    assert by_boss["read_at"] is None


async def test_the_owner_marks_read_with_204_and_everyone_sees_the_read_time() -> None:
    """Owner가 읽음 처리하면 204(본문 없음)이고 누가 읽어도 read_at이 채워져 있다.

    테스트 코드: CM-049
    """
    # given: PARK·admin이 쓴 읽지 않은 Comment 둘
    use_cases = await seed(KIM_ID)
    async with clients(use_cases, USERS) as c:
        p1 = await post_comment(c["park"], "p1")
        r1 = await post_comment(c["boss"], "r1")
        # when: Owner KIM이 읽음 처리한다
        response = await c["kim"].post(READS, json={"comment_ids": [p1["id"], r1["id"]]})
        seen = {who: await c[who].get(DEAL_COMMENTS) for who in ("kim", "park", "boss", "viewer")}

    # then: 204이고 본문이 없다
    assert response.status_code == 204
    assert response.content == b""
    # then: 모든 역할에게 두 Comment의 read_at이 같은 값으로 채워져 있다
    stamps = set()
    for listed in seen.values():
        items = listed.json()["items"]
        assert all(item["read_at"] is not None for item in items)
        stamps |= {item["read_at"] for item in items}
    assert len(stamps) == 1


async def test_a_non_owner_is_403_a_user_is_read_only_403_and_anonymous_is_401() -> None:
    """Owner 아닌 sales·admin은 403, user는 읽기 전용 403, 미인증은 401이고 아무것도 바뀌지 않는다.

    테스트 코드: CM-050
    """
    # given: PARK의 읽지 않은 Comment
    use_cases = await seed(KIM_ID)
    async with clients(use_cases, USERS) as c:
        p1 = await post_comment(c["park"], "p1")
        body = {"comment_ids": [p1["id"]]}
        # when: PARK, admin, user, 방문자가 읽음 처리한다
        park = await c["park"].post(READS, json=body)
        boss = await c["boss"].post(READS, json=body)
        viewer = await c["viewer"].post(READS, json=body)
        viewer_bad = await c["viewer"].post(READS, json={})  # 형식 오류보다 user 403이 먼저
        anon = await c["anon"].post(READS, json=body)
        unread = await _read_at(c["kim"], p1["id"])

    # then: 403 고정 문구, user 403, 방문자 401이고 p1은 읽지 않음 그대로다
    assert problem(park, 403, "forbidden")["detail"] == READ_FORBIDDEN
    assert problem(boss, 403, "forbidden")["detail"] == READ_FORBIDDEN
    assert problem(viewer, 403, "forbidden")["detail"] == READ_ONLY
    assert problem(viewer_bad, 403, "forbidden")["detail"] == READ_ONLY
    problem(anon, 401, "unauthenticated")
    assert unread is None


async def test_a_request_without_the_csrf_header_is_403_and_nothing_changes() -> None:
    """CSRF 헤더가 없으면 Owner여도 403 csrf이고 read_at이 바뀌지 않는다.

    테스트 코드: CM-050
    """
    # given: 읽지 않은 Comment와 CSRF 헤더 없는 Owner 클라이언트
    use_cases = await seed(KIM_ID)
    async with clients(use_cases, USERS) as c:
        p1 = await post_comment(c["park"], "p1")
    async with clients(use_cases, USERS, csrf=False) as bare:
        # when: Owner가 헤더 없이 읽음 처리한다
        response = await bare["kim"].post(READS, json={"comment_ids": [p1["id"]]})
        unread = await _read_at(bare["kim"], p1["id"])

    # then: 403 csrf이고 읽지 않음 그대로다
    problem(response, 403, "csrf")
    assert unread is None


async def test_other_deals_missing_and_already_read_ids_are_skipped_with_204() -> None:
    """다른 Deal·없는·이미 읽은 id는 건너뛰고 204이며 이미 읽은 read_at은 그대로다.

    테스트 코드: CM-051
    """
    # given: p1은 이미 읽음, r1은 읽지 않음, 다른 Deal E의 읽지 않은 Comment e1
    use_cases = await seed(KIM_ID)
    async with clients(use_cases, USERS) as c:
        p1 = await post_comment(c["park"], "p1")
        r1 = await post_comment(c["boss"], "r1")
        await c["kim"].post(READS, json={"comment_ids": [p1["id"]]})
        first = await _read_at(c["kim"], p1["id"])
        e1 = (await c["park"].post(f"/api/v1/deals/{OTHER}/comments", json={"body": "e1"})).json()
        # when: [p1, p1, e1, 상한 id, r1]을 D로 보낸다
        response = await c["kim"].post(
            READS, json={"comment_ids": [p1["id"], p1["id"], e1["id"], MAX_ID, r1["id"]]}
        )
        after = (
            await _read_at(c["kim"], p1["id"]),
            await _read_at(c["kim"], r1["id"]),
            await _read_at(c["kim"], e1["id"]),
        )

    # then: 204이고 p1은 처음 값 그대로, r1은 채워지고, e1은 읽지 않음 그대로다
    assert response.status_code == 204
    assert after[0] == first
    assert after[1] is not None
    assert after[2] is None


@pytest.mark.parametrize(
    "payload",
    [
        {},
        {"comment_ids": []},
        {"comment_ids": list(range(1, 502))},
        {"comment_ids": ["1"]},
        {"comment_ids": [0]},
        {"comment_ids": [9_007_199_254_740_992]},
        {"comment_ids": [1], "x": 1},
        {"comment_ids": None},
    ],
    ids=["empty", "empty-list", "501-ids", "string-id", "zero-id", "over-max", "extra-key", "null"],
)
async def test_a_malformed_read_body_is_a_request_validation_error(
    payload: dict[str, Any],
) -> None:
    """읽음 처리 본문 형식이 틀리면(누락·빈 배열·501개·문자열·범위 밖·모르는 키) 422이고 그대로다.

    테스트 코드: CM-052
    """
    # given: 읽지 않은 Comment
    use_cases = await seed(KIM_ID)
    async with clients(use_cases, USERS) as c:
        p1 = await post_comment(c["park"], "p1")
        # when: Owner가 형식이 틀린 본문으로 보낸다
        response = await c["kim"].post(READS, json=payload)
        unread = await _read_at(c["kim"], p1["id"])

    # then: 422 request-validation이고 p1은 읽지 않음 그대로다
    problem(response, 422, "request-validation")
    assert unread is None


async def test_exactly_500_ids_are_accepted_and_a_missing_deal_is_404_before_the_owner_check() -> (
    None
):
    """500개 배열은 204이고, 없는 Deal·형식이 틀린 code는 Owner가 아닌 사람에게도 404가 먼저다.

    테스트 코드: CM-052
    """
    # given: 읽지 않은 Comment
    use_cases = await seed(KIM_ID)
    async with clients(use_cases, USERS) as c:
        p1 = await post_comment(c["park"], "p1")
        # when: 500개 배열, 없는 code, 형식이 틀린 code(Owner가 아닌 PARK)로 보낸다
        limit = await c["kim"].post(
            READS, json={"comment_ids": list(range(p1["id"] + 1, p1["id"] + 501))}
        )
        missing = await c["park"].post(
            "/api/v1/deals/20991231-ZZZZ/comment-reads", json={"comment_ids": [p1["id"]]}
        )
        malformed = await c["park"].post(
            "/api/v1/deals/not-a-code/comment-reads", json={"comment_ids": [p1["id"]]}
        )
        unread = await _read_at(c["kim"], p1["id"])

    # then: 500개는 204, 나머지는 404 "Deal을 찾을 수 없습니다."이고 p1은 읽지 않음이다
    assert limit.status_code == 204
    assert problem(missing, 404, "not-found")["detail"] == DEAL_NOT_FOUND
    assert problem(malformed, 404, "not-found")["detail"] == DEAL_NOT_FOUND
    assert unread is None


async def test_marking_read_adds_no_history_and_changes_no_body_or_updated_at() -> None:
    """읽음 처리는 History를 남기지 않고 Comment의 본문·수정 시각을 바꾸지 않는다.

    테스트 코드: CM-054
    """
    # given: 읽지 않은 Comment와 현재 이력
    use_cases = await seed(KIM_ID)
    async with clients(use_cases, USERS) as c:
        p1 = await post_comment(c["park"], "자료 전달")
        history = (await c["kim"].get(f"/api/v1/deals/{CODE}/history")).json()
        # when: Owner가 읽음 처리한다
        await c["kim"].post(READS, json={"comment_ids": [p1["id"]]})
        after = (await c["kim"].get(f"{SINGLE}/{p1['id']}")).json()
        history_after = (await c["kim"].get(f"/api/v1/deals/{CODE}/history")).json()

    # then: 이력이 그대로이고 본문·수정 시각도 그대로다
    assert history_after == history
    assert (after["body"], after["updated_at"]) == (p1["body"], p1["updated_at"])


async def test_counts_returns_the_total_and_the_actions_with_unread_only() -> None:
    """읽지 않은 수 응답은 {unread, by_action}이고 Action별은 1 이상만이며 다른 Deal 것은 없다.

    테스트 코드: CM-055
    """
    # given: D에 읽지 않은 Deal Comment 1건, A의 읽지 않은 2건, B의 읽은 1건, E에 읽지 않은 1건
    use_cases = await seed(KIM_ID)
    async with clients(use_cases, USERS) as c:
        action_a = await post_action(c["kim"])
        action_b = await post_action(c["kim"])
        await post_comment(c["park"], "d")
        await post_comment(c["park"], "a1", action_id=action_a)
        await post_comment(c["boss"], "a2", action_id=action_a)
        await post_comment(c["kim"], "b", action_id=action_b)  # Owner가 썼으므로 읽음
        await c["park"].post(f"/api/v1/deals/{OTHER}/comments", json={"body": "e"})
        # when: user와 방문자가 센다
        viewer = await c["viewer"].get(COUNTS)
        anon = await c["anon"].get(COUNTS)

    # then: user도 200이고 전체 3, A만 2다. 방문자는 401이다
    assert viewer.status_code == 200, viewer.text
    assert viewer.json() == {"unread": 3, "by_action": [{"action_id": action_a, "unread": 2}]}
    problem(anon, 401, "unauthenticated")


@pytest.mark.parametrize("code", ["20991231-ZZZZ", "not-a-code"])
async def test_counts_of_a_missing_deal_is_404(code: str) -> None:
    """없는 Deal·형식이 틀린 code의 읽지 않은 수는 404다.

    테스트 코드: CM-055
    """
    # given: sales KIM
    use_cases = await seed(KIM_ID)
    async with clients(use_cases, USERS) as c:
        # when: 없는 Deal을 센다
        response = await c["kim"].get(f"/api/v1/deals/{code}/comment-counts")

    # then: 404 "Deal을 찾을 수 없습니다."다
    assert problem(response, 404, "not-found")["detail"] == DEAL_NOT_FOUND
