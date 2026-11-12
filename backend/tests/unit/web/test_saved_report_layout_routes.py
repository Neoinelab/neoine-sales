"""저장 리포트 라우터의 결과 배치: FakeUseCases 위의 HTTP 계약.

만들기·수정의 선택 필드 `layout`, 상세 응답의 항상 있는 `layout`, 배치만 바꾸는
`PUT /api/v1/reports/{id}/layout`. DB 없이 라우터·스키마·오류 매핑을 확인한다.
"""

from typing import TYPE_CHECKING, Any

import pytest

from app.domain.auth.principal import Role
from app.domain.saved_report.values import ReportId
from tests.factories_report import make_broken_report, make_report
from tests.fakes.use_cases import FakeUseCases
from tests.support.layout_defs import SIDE_CHART_FIRST, layout_json
from tests.unit.web.saved_report_http import (
    URL,
    clients,
    create,
    create_body,
    problem,
    update_body,
)

if TYPE_CHECKING:
    from collections.abc import Callable

DEFAULT = layout_json()
TABLE_ONLY = layout_json("table", ("table", "chart"), "stacked")


@pytest.fixture(autouse=True)
def _seoul(local_tz: Callable[[str], None]) -> None:
    local_tz("Asia/Seoul")


def _layout_body(layout: Any, revision: Any = 1) -> dict[str, Any]:  # noqa: ANN401
    return {"layout": layout, "revision": revision}


def _locations(body: dict[str, Any]) -> list[tuple[list[Any], str]]:
    return [(e["location"], e["code"]) for e in body["errors"]]


# ---- 만들기·수정·복제 ----


async def test_create_with_layout_returns_and_rereads_it() -> None:
    """배치를 정해 만들면 응답과 다시 연 상세의 배치가 같다.

    테스트 코드: RS-038
    """
    # given: 로그인한 sales 사용자
    async with clients(FakeUseCases(), {"alice": Role.SALES}) as c:
        # when: CHART_SIDE 배치로 만들고 다시 연다
        response = await c["alice"].post(URL, json=create_body(layout=SIDE_CHART_FIRST))
        reread = await c["alice"].get(f"{URL}/{response.json()['id']}")
    # then: 응답과 상세의 배치가 보낸 배치이고 revision 1이다
    assert response.status_code == 201, response.text
    assert response.json()["layout"] == SIDE_CHART_FIRST
    assert response.json()["revision"] == 1
    assert reread.json()["layout"] == SIDE_CHART_FIRST


@pytest.mark.parametrize("omit", [True, False], ids=["key-omitted", "null"])
async def test_create_without_layout_returns_the_default(omit: bool) -> None:
    """배치를 생략하거나 null로 만들면 기본 배치다.

    테스트 코드: RS-038
    """
    # given: layout 키를 생략하거나 null로 둔 본문
    body = create_body()
    if not omit:
        body["layout"] = None
    async with clients(FakeUseCases(), {"alice": Role.SALES}) as c:
        # when: 만든다
        response = await c["alice"].post(URL, json=body)
    # then: 응답의 배치가 기본 배치다
    assert response.status_code == 201, response.text
    assert response.json()["layout"] == DEFAULT


@pytest.mark.parametrize("omit", [True, False], ids=["key-omitted", "null"])
async def test_update_without_layout_keeps_the_stored_one(omit: bool) -> None:
    """배치를 생략하거나 null로 덮어쓰면 저장된 배치가 그대로 남는다.

    테스트 코드: RS-040
    """
    # given: 배치 CHART_SIDE인 리포트와 layout을 생략하거나 null로 둔 덮어쓰기 본문
    body = update_body(1, "새 이름")
    if not omit:
        body["layout"] = None
    async with clients(FakeUseCases(), {"alice": Role.SALES}) as c:
        made = await create(c["alice"], layout=SIDE_CHART_FIRST)
        # when: 이름만 바꿔 덮어쓴다
        response = await c["alice"].put(f"{URL}/{made['id']}", json=body)
    # then: 배치는 CHART_SIDE 그대로, revision 2다
    assert response.status_code == 200, response.text
    assert response.json()["layout"] == SIDE_CHART_FIRST
    assert response.json()["revision"] == 2


async def test_update_with_layout_replaces_it() -> None:
    """배치를 보내 덮어쓰면 배치가 바뀌고 다시 열어도 같다.

    테스트 코드: RS-040
    """
    # given: 배치 CHART_SIDE인 리포트
    async with clients(FakeUseCases(), {"alice": Role.SALES}) as c:
        made = await create(c["alice"], layout=SIDE_CHART_FIRST)
        # when: TABLE_ONLY를 보내 덮어쓰고 다시 연다
        response = await c["alice"].put(
            f"{URL}/{made['id']}", json=update_body(1, "그대로", layout=TABLE_ONLY)
        )
        reread = await c["alice"].get(f"{URL}/{made['id']}")
    # then: 응답과 상세의 배치가 TABLE_ONLY이고 revision 2다
    assert response.status_code == 200, response.text
    assert response.json()["layout"] == TABLE_ONLY
    assert response.json()["revision"] == 2
    assert reread.json()["layout"] == TABLE_ONLY


async def test_copy_keeps_the_source_layout() -> None:
    """복제 요청에 배치가 없어도 복제본은 원본의 배치를 가진다.

    테스트 코드: RS-028
    """
    # given: 배치 CHART_SIDE인 리포트
    async with clients(FakeUseCases(), {"alice": Role.SALES}) as c:
        made = await create(c["alice"], layout=SIDE_CHART_FIRST)
        # when: 메타만 보내 복제한다
        response = await c["alice"].post(
            f"{URL}/{made['id']}/copy", json={"name": "복사", "visibility": "public"}
        )
    # then: 복제본의 배치가 원본과 같다
    assert response.status_code == 201, response.text
    assert response.json()["layout"] == SIDE_CHART_FIRST


async def test_list_items_do_not_include_the_layout() -> None:
    """목록 항목에는 배치가 없다.

    테스트 코드: RS-010
    """
    # given: 배치가 있는 리포트
    async with clients(FakeUseCases(), {"alice": Role.SALES}) as c:
        await create(c["alice"], layout=SIDE_CHART_FIRST)
        # when: 목록을 읽는다
        listed = await c["alice"].get(URL)
    # then: 항목에 layout 키가 없다
    assert listed.json()
    assert all("layout" not in item for item in listed.json())


@pytest.mark.parametrize(
    ("layout", "location"),
    [
        (layout_json("grid"), ["layout", "view"]),
        ({**DEFAULT, "view": 1}, ["layout", "view"]),
        ({**DEFAULT, "order": ["table", "table"]}, ["layout", "order"]),
        ({**DEFAULT, "order": "table,chart"}, ["layout", "order"]),
        ({**DEFAULT, "arrange": "row"}, ["layout", "arrange"]),
    ],
)
async def test_create_with_invalid_layout_value_is_invalid_report(
    layout: dict[str, Any], location: list[str]
) -> None:
    """배치 값이 틀리면 만들기는 422 invalid-report(layout 위치)이고 저장되지 않는다.

    테스트 코드: RS-044
    """
    # given: 로그인한 sales 사용자
    async with clients(FakeUseCases(), {"alice": Role.SALES}) as c:
        # when: 틀린 배치 값으로 만든다
        response = await c["alice"].post(URL, json=create_body(layout=layout))
        listed = await c["alice"].get(URL)
    # then: 틀린 위치 하나가 invalid-value 위반이고 목록은 비어 있다
    body = problem(response, 422, "invalid-report")
    assert _locations(body) == [(location, "invalid-value")]
    assert listed.json() == []


async def test_update_with_invalid_layout_value_is_invalid_report_and_changes_nothing() -> None:
    """배치 값이 틀린 덮어쓰기는 422 invalid-report이고 리포트는 그대로다.

    테스트 코드: RS-044
    """
    # given: 배치 CHART_SIDE인 리포트
    async with clients(FakeUseCases(), {"alice": Role.SALES}) as c:
        made = await create(c["alice"], layout=SIDE_CHART_FIRST)
        # when: arrange가 "row"인 배치로 덮어쓴다
        response = await c["alice"].put(
            f"{URL}/{made['id']}", json=update_body(1, "바뀜", layout=layout_json(arrange="row"))
        )
        reread = await c["alice"].get(f"{URL}/{made['id']}")
    # then: ["layout","arrange"] 위반이고 이름·revision·배치가 그대로다
    body = problem(response, 422, "invalid-report")
    assert _locations(body) == [(["layout", "arrange"], "invalid-value")]
    assert (reread.json()["name"], reread.json()["revision"]) == ("분기 Pipeline", 1)
    assert reread.json()["layout"] == SIDE_CHART_FIRST


@pytest.mark.parametrize(
    "layout",
    [
        {**DEFAULT, "unknown": 1},
        {"view": "both", "order": ["table", "chart"]},
        {"order": ["table", "chart"], "arrange": "stacked"},
        {},
        [],
        "both",
        5,
    ],
    ids=["unknown-key", "no-arrange", "no-view", "empty-object", "list", "string", "number"],
)
async def test_layout_with_a_wrong_shape_is_request_validation(layout: Any) -> None:  # noqa: ANN401
    """만들기 요청의 배치 모양 오류(모르는 키·누락·타입)는 422 request-validation이다.

    테스트 코드: RS-045
    """
    # given: 로그인한 sales 사용자
    async with clients(FakeUseCases(), {"alice": Role.SALES}) as c:
        # when: 모양이 틀린 배치로 만든다
        created = await c["alice"].post(URL, json=create_body(layout=layout))
    # then: 422 request-validation이다
    problem(created, 422, "request-validation")


# ---- 배치만 바꾸기 ----


async def test_put_layout_changes_only_the_layout_and_bumps_the_revision() -> None:
    """배치만 저장하면 배치·revision만 바뀌고 이름·정의·SQL·차트는 그대로다.

    테스트 코드: RS-041
    """
    # given: alice의 리포트
    async with clients(FakeUseCases(), {"alice": Role.SALES}) as c:
        made = await create(c["alice"])
        # when: 배치만 저장하고 다시 연다
        response = await c["alice"].put(
            f"{URL}/{made['id']}/layout", json=_layout_body(SIDE_CHART_FIRST)
        )
        reread = await c["alice"].get(f"{URL}/{made['id']}")
    # then: 배치가 바뀌고 revision 2이며 나머지 필드는 만들 때와 같다
    assert response.status_code == 200, response.text
    body = response.json()
    assert body["layout"] == SIDE_CHART_FIRST
    assert body["revision"] == 2
    assert reread.json() == body
    for key in ("name", "description", "visibility", "definition", "generated_sql", "chart"):
        assert body[key] == made[key], key


async def test_put_layout_by_another_user_records_the_editor() -> None:
    """남의 공개 리포트의 배치를 저장하면 최종 수정자가 기록되고 만든 사람은 그대로다.

    테스트 코드: RS-043
    """
    # given: alice의 공개 리포트
    async with clients(FakeUseCases(), {"alice": Role.SALES, "bob": Role.USER}) as c:
        made = await create(c["alice"])
        # when: user bob이 배치를 저장한다
        response = await c["bob"].put(f"{URL}/{made['id']}/layout", json=_layout_body(TABLE_ONLY))
    # then: 200이고 만든 사람은 그대로, 최종 수정자는 bob이다
    assert response.status_code == 200, response.text
    assert response.json()["owner"] == made["owner"]
    assert response.json()["updated_by"]["id"] != made["owner"]["id"]


async def test_consecutive_layout_saves_with_the_returned_revision_succeed() -> None:
    """응답 revision으로 배치를 이어 저장하면 모두 된다.

    테스트 코드: RS-042
    """
    # given: alice의 리포트
    async with clients(FakeUseCases(), {"alice": Role.SALES}) as c:
        made = await create(c["alice"])
        # when: 직전 응답의 revision으로 두 번 저장한다
        first = await c["alice"].put(
            f"{URL}/{made['id']}/layout", json=_layout_body(SIDE_CHART_FIRST, 1)
        )
        second = await c["alice"].put(
            f"{URL}/{made['id']}/layout",
            json=_layout_body(TABLE_ONLY, first.json()["revision"]),
        )
    # then: 둘 다 200이고 revision 3, 마지막 배치다
    assert (first.status_code, second.status_code) == (200, 200)
    assert second.json()["revision"] == 3
    assert second.json()["layout"] == TABLE_ONLY


async def test_put_layout_with_a_stale_revision_is_409_invalid_state() -> None:
    """낡은 revision으로 배치를 저장하면 409 invalid-state이고 배치는 그대로다.

    테스트 코드: RS-042
    """
    # given: 배치를 한 번 저장해 revision 2가 된 리포트
    async with clients(FakeUseCases(), {"alice": Role.SALES}) as c:
        made = await create(c["alice"])
        await c["alice"].put(f"{URL}/{made['id']}/layout", json=_layout_body(SIDE_CHART_FIRST, 1))
        # when: revision 1로 다시 저장한다
        stale = await c["alice"].put(f"{URL}/{made['id']}/layout", json=_layout_body(TABLE_ONLY, 1))
        reread = await c["alice"].get(f"{URL}/{made['id']}")
    # then: 409 invalid-state이고 배치·revision이 그대로다
    problem(stale, 409, "invalid-state")
    assert (reread.json()["layout"], reread.json()["revision"]) == (SIDE_CHART_FIRST, 2)


async def test_put_layout_of_others_private_report_is_404_like_a_missing_one() -> None:
    """남의 비공개 리포트의 배치 저장은 없는 id와 같은 404이고 문구가 같다.

    테스트 코드: RS-014
    """
    # given: alice의 비공개 리포트
    async with clients(FakeUseCases(), {"alice": Role.SALES, "bob": Role.SALES}) as c:
        private = await create(c["alice"], visibility="private")
        # when: bob이 비공개 리포트와 없는 id에 배치를 저장한다
        hidden = await c["bob"].put(f"{URL}/{private['id']}/layout", json=_layout_body(TABLE_ONLY))
        missing = await c["bob"].put(f"{URL}/999999/layout", json=_layout_body(TABLE_ONLY))
    # then: 둘 다 404이고 문구가 같다
    hidden_body = problem(hidden, 404, "not-found")
    missing_body = problem(missing, 404, "not-found")
    assert hidden_body["detail"] == missing_body["detail"] == "리포트를 찾을 수 없습니다."


async def test_put_layout_checks_not_found_before_an_invalid_layout() -> None:
    """남의 비공개 리포트에 틀린 배치를 보내도 404가 먼저다.

    테스트 코드: RS-046
    """
    # given: alice의 비공개 리포트
    async with clients(FakeUseCases(), {"alice": Role.SALES, "bob": Role.SALES}) as c:
        private = await create(c["alice"], visibility="private")
        # when: bob이 틀린 배치를 저장한다
        response = await c["bob"].put(
            f"{URL}/{private['id']}/layout", json=_layout_body(layout_json("grid"))
        )
    # then: 404 not-found다
    problem(response, 404, "not-found")


async def test_put_layout_checks_the_layout_value_before_the_revision() -> None:
    """틀린 배치 값(422)이 낡은 revision(409)보다 먼저 판정된다.

    테스트 코드: RS-046
    """
    # given: alice의 리포트(revision 1)
    async with clients(FakeUseCases(), {"alice": Role.SALES}) as c:
        made = await create(c["alice"])
        # when: 틀린 배치를 틀린 revision 9로 저장한다
        response = await c["alice"].put(
            f"{URL}/{made['id']}/layout", json=_layout_body(layout_json("grid"), 9)
        )
    # then: 409가 아니라 ["layout","view"] 위반의 422다
    body = problem(response, 422, "invalid-report")
    assert _locations(body) == [(["layout", "view"], "invalid-value")]


async def test_put_layout_with_invalid_values_collects_every_location() -> None:
    """배치 값이 모두 틀리면 세 위치를 모두 알리고 배치는 바뀌지 않는다.

    테스트 코드: RS-044
    """
    # given: 배치 CHART_SIDE인 리포트와 세 값이 모두 틀린 배치
    bad = {"view": "x", "order": ["a"], "arrange": "y"}
    async with clients(FakeUseCases(), {"alice": Role.SALES}) as c:
        made = await create(c["alice"], layout=SIDE_CHART_FIRST)
        # when: 그 배치를 저장한다
        response = await c["alice"].put(f"{URL}/{made['id']}/layout", json=_layout_body(bad))
        reread = await c["alice"].get(f"{URL}/{made['id']}")
    # then: view·order·arrange 위치 위반이 모두 있고 배치·revision이 그대로다
    body = problem(response, 422, "invalid-report")
    assert [loc for loc, _ in _locations(body)] == [
        ["layout", "view"],
        ["layout", "order"],
        ["layout", "arrange"],
    ]
    assert (reread.json()["layout"], reread.json()["revision"]) == (SIDE_CHART_FIRST, 1)


async def test_layout_request_unknown_key_returns_request_validation() -> None:
    """배치 저장 요청의 바깥·안쪽 모르는 키는 422 request-validation이다.

    테스트 코드: RS-045
    """
    # given: alice의 리포트
    async with clients(FakeUseCases(), {"alice": Role.SALES}) as c:
        made = await create(c["alice"])
        body = {**_layout_body(TABLE_ONLY), "name": "끼어든 키"}
        # when: 바깥에 모르는 키를 더해 저장하고, 배치 안에 모르는 키를 더해 저장한다
        top = await c["alice"].put(f"{URL}/{made['id']}/layout", json=body)
        inner = await c["alice"].put(
            f"{URL}/{made['id']}/layout", json=_layout_body({**TABLE_ONLY, "extra": 1})
        )
    # then: 둘 다 422 request-validation이다
    problem(top, 422, "request-validation")
    problem(inner, 422, "request-validation")


async def test_layout_request_missing_revision_returns_request_validation() -> None:
    """revision이 없는 배치 저장 요청은 422 request-validation이다.

    테스트 코드: RS-045
    """
    # given: alice의 리포트
    async with clients(FakeUseCases(), {"alice": Role.SALES}) as c:
        made = await create(c["alice"])
        # when: revision 없이 저장한다
        response = await c["alice"].put(f"{URL}/{made['id']}/layout", json={"layout": TABLE_ONLY})
    # then: 422 request-validation이다
    problem(response, 422, "request-validation")


async def test_layout_request_missing_layout_returns_request_validation() -> None:
    """layout이 없는 배치 저장 요청은 422 request-validation이다.

    테스트 코드: RS-045
    """
    # given: alice의 리포트
    async with clients(FakeUseCases(), {"alice": Role.SALES}) as c:
        made = await create(c["alice"])
        # when: layout 없이 저장한다
        response = await c["alice"].put(f"{URL}/{made['id']}/layout", json={"revision": 1})
    # then: 422 request-validation이다
    problem(response, 422, "request-validation")


@pytest.mark.parametrize("revision", [0, -1, "1", 1.5, None, True])
async def test_layout_request_bad_revision_returns_request_validation(revision: Any) -> None:  # noqa: ANN401
    """revision이 0·음수·문자열·실수·null·불리언이면 422 request-validation이다.

    테스트 코드: RS-045
    """
    # given: alice의 리포트
    async with clients(FakeUseCases(), {"alice": Role.SALES}) as c:
        made = await create(c["alice"])
        # when: 잘못된 revision으로 저장한다
        response = await c["alice"].put(
            f"{URL}/{made['id']}/layout", json=_layout_body(TABLE_ONLY, revision)
        )
    # then: 422 request-validation이다
    problem(response, 422, "request-validation")


async def test_put_layout_requires_a_login() -> None:
    """로그인하지 않은 배치 저장은 401이다.

    테스트 코드: RS-050
    """
    # given: alice의 리포트와 로그인하지 않은 클라이언트
    async with clients(FakeUseCases(), {"alice": Role.SALES, "anon": Role.SALES}) as c:
        made = await create(c["alice"])
        # when: 로그인 없이 배치를 저장한다
        response = await c["anon"].put(f"{URL}/{made['id']}/layout", json=_layout_body(TABLE_ONLY))
    # then: 401이다
    assert response.status_code == 401


async def test_put_layout_keeps_a_broken_stored_chart_untouched() -> None:
    """읽을 수 없는 저장 차트가 있는 리포트의 배치 저장은 차트 안내를 그대로 둔다.

    테스트 코드: RS-041
    """
    # given: 저장 차트를 읽을 수 없는 alice의 리포트
    use_cases = FakeUseCases()
    async with clients(use_cases, {"alice": Role.SALES}) as c:
        report = make_report(owner=await use_cases.user_id_of("alice"), chart_unreadable=True)
        async with use_cases.uow as uow:
            await uow.saved_reports.add(report)
            await uow.commit()
        # when: 배치를 저장하고 다시 연다
        response = await c["alice"].put(f"{URL}/{report.id}/layout", json=_layout_body(TABLE_ONLY))
        reread = await c["alice"].get(f"{URL}/{report.id}")
    # then: 200이고 차트는 없는 채 chart_problem이 남고 배치만 바뀐다
    assert response.status_code == 200, response.text
    assert reread.json()["chart"] is None
    assert reread.json()["chart_problem"] is not None
    assert reread.json()["layout"] == TABLE_ONLY


async def _store_broken(use_cases: FakeUseCases, owner: str, **overrides: Any) -> int:  # noqa: ANN401
    report = make_broken_report(owner=await use_cases.user_id_of(owner), **overrides)
    async with use_cases.uow as uow:
        await uow.saved_reports.add(report)
        await uow.commit()
    return int(report.id)


@pytest.mark.parametrize("layout", [TABLE_ONLY, layout_json("grid")], ids=["valid", "invalid"])
async def test_put_layout_of_a_broken_definition_is_422_stored_invalid_and_changes_nothing(
    layout: dict[str, Any],
) -> None:
    """깨진 저장 정의 리포트의 배치 저장은 배치 값과 무관하게 422 stored-invalid이고 그대로다.

    테스트 코드: RS-046
    """
    # given: alice의 깨진 정의 리포트
    use_cases = FakeUseCases()
    async with clients(use_cases, {"alice": Role.SALES}) as c:
        broken_id = await _store_broken(use_cases, "alice")
        # when: 맞는 배치 또는 틀린 배치를 저장한다
        response = await c["alice"].put(f"{URL}/{broken_id}/layout", json=_layout_body(layout))
        async with use_cases.uow as uow:
            saved = await uow.saved_reports.get(ReportId(broken_id))
    # then: stored-invalid 위반이고 배치·revision이 그대로다
    body = problem(response, 422, "invalid-report")
    assert _locations(body) == [(["definition"], "stored-invalid")]
    assert (saved.layout.view, saved.revision) == ("both", 1)


async def test_put_layout_of_others_private_broken_report_is_404() -> None:
    """남의 비공개 깨진 리포트의 배치 저장은 404가 먼저다.

    테스트 코드: RS-046
    """
    # given: alice의 비공개 깨진 리포트
    use_cases = FakeUseCases()
    async with clients(use_cases, {"alice": Role.SALES, "bob": Role.SALES}) as c:
        broken_id = await _store_broken(use_cases, "alice", visibility="private")
        # when: bob이 배치를 저장한다
        response = await c["bob"].put(f"{URL}/{broken_id}/layout", json=_layout_body(TABLE_ONLY))
    # then: 404 not-found다
    problem(response, 404, "not-found")
