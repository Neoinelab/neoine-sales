"""저장 리포트 라우터의 결과 배치 (AC22~29): FakeUseCases 위의 HTTP 계약.

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


# ---- 만들기·수정·복제 (AC24, 25, 28, 29) ----


async def test_create_with_layout_returns_and_rereads_it() -> None:
    async with clients(FakeUseCases(), {"alice": Role.SALES}) as c:
        response = await c["alice"].post(URL, json=create_body(layout=SIDE_CHART_FIRST))
        reread = await c["alice"].get(f"{URL}/{response.json()['id']}")

    assert response.status_code == 201, response.text
    assert response.json()["layout"] == SIDE_CHART_FIRST
    assert reread.json()["layout"] == SIDE_CHART_FIRST


@pytest.mark.parametrize("omit", [True, False], ids=["key-omitted", "null"])
async def test_create_without_layout_returns_the_default(omit: bool) -> None:
    body = create_body()
    if not omit:
        body["layout"] = None
    async with clients(FakeUseCases(), {"alice": Role.SALES}) as c:
        response = await c["alice"].post(URL, json=body)

    assert response.status_code == 201, response.text
    assert response.json()["layout"] == DEFAULT


@pytest.mark.parametrize("omit", [True, False], ids=["key-omitted", "null"])
async def test_update_without_layout_keeps_the_stored_one(omit: bool) -> None:
    body = update_body(1, "새 이름")
    if not omit:
        body["layout"] = None
    async with clients(FakeUseCases(), {"alice": Role.SALES}) as c:
        made = await create(c["alice"], layout=SIDE_CHART_FIRST)
        response = await c["alice"].put(f"{URL}/{made['id']}", json=body)

    assert response.status_code == 200, response.text
    assert response.json()["layout"] == SIDE_CHART_FIRST
    assert response.json()["revision"] == 2


async def test_update_with_layout_replaces_it() -> None:
    async with clients(FakeUseCases(), {"alice": Role.SALES}) as c:
        made = await create(c["alice"], layout=SIDE_CHART_FIRST)
        response = await c["alice"].put(
            f"{URL}/{made['id']}", json=update_body(1, "그대로", layout=TABLE_ONLY)
        )
        reread = await c["alice"].get(f"{URL}/{made['id']}")

    assert response.status_code == 200, response.text
    assert response.json()["layout"] == TABLE_ONLY
    assert reread.json()["layout"] == TABLE_ONLY


async def test_copy_keeps_the_source_layout() -> None:
    async with clients(FakeUseCases(), {"alice": Role.SALES}) as c:
        made = await create(c["alice"], layout=SIDE_CHART_FIRST)
        response = await c["alice"].post(
            f"{URL}/{made['id']}/copy", json={"name": "복사", "visibility": "public"}
        )

    assert response.status_code == 201, response.text
    assert response.json()["layout"] == SIDE_CHART_FIRST


async def test_list_items_do_not_include_the_layout() -> None:
    async with clients(FakeUseCases(), {"alice": Role.SALES}) as c:
        await create(c["alice"], layout=SIDE_CHART_FIRST)
        listed = await c["alice"].get(URL)

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
    async with clients(FakeUseCases(), {"alice": Role.SALES}) as c:
        response = await c["alice"].post(URL, json=create_body(layout=layout))
        listed = await c["alice"].get(URL)

    body = problem(response, 422, "invalid-report")
    assert _locations(body) == [(location, "invalid-value")]
    assert listed.json() == []


async def test_update_with_invalid_layout_value_is_invalid_report_and_changes_nothing() -> None:
    async with clients(FakeUseCases(), {"alice": Role.SALES}) as c:
        made = await create(c["alice"], layout=SIDE_CHART_FIRST)
        response = await c["alice"].put(
            f"{URL}/{made['id']}", json=update_body(1, "바뀜", layout=layout_json(arrange="row"))
        )
        reread = await c["alice"].get(f"{URL}/{made['id']}")

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
    async with clients(FakeUseCases(), {"alice": Role.SALES}) as c:
        created = await c["alice"].post(URL, json=create_body(layout=layout))

    problem(created, 422, "request-validation")


# ---- 배치만 바꾸기 (AC22, 26, 27) ----


async def test_put_layout_changes_only_the_layout_and_bumps_the_revision() -> None:
    async with clients(FakeUseCases(), {"alice": Role.SALES}) as c:
        made = await create(c["alice"])
        response = await c["alice"].put(
            f"{URL}/{made['id']}/layout", json=_layout_body(SIDE_CHART_FIRST)
        )
        reread = await c["alice"].get(f"{URL}/{made['id']}")

    assert response.status_code == 200, response.text
    body = response.json()
    assert body["layout"] == SIDE_CHART_FIRST
    assert body["revision"] == 2
    assert reread.json() == body
    for key in ("name", "description", "visibility", "definition", "generated_sql", "chart"):
        assert body[key] == made[key], key


async def test_put_layout_by_another_user_records_the_editor() -> None:
    async with clients(FakeUseCases(), {"alice": Role.SALES, "bob": Role.USER}) as c:
        made = await create(c["alice"])
        response = await c["bob"].put(f"{URL}/{made['id']}/layout", json=_layout_body(TABLE_ONLY))

    assert response.status_code == 200, response.text
    assert response.json()["owner"] == made["owner"]
    assert response.json()["updated_by"]["id"] != made["owner"]["id"]


async def test_consecutive_layout_saves_with_the_returned_revision_succeed() -> None:
    async with clients(FakeUseCases(), {"alice": Role.SALES}) as c:
        made = await create(c["alice"])
        first = await c["alice"].put(
            f"{URL}/{made['id']}/layout", json=_layout_body(SIDE_CHART_FIRST, 1)
        )
        second = await c["alice"].put(
            f"{URL}/{made['id']}/layout",
            json=_layout_body(TABLE_ONLY, first.json()["revision"]),
        )

    assert (first.status_code, second.status_code) == (200, 200)
    assert second.json()["revision"] == 3
    assert second.json()["layout"] == TABLE_ONLY


async def test_put_layout_with_a_stale_revision_is_409_invalid_state() -> None:
    async with clients(FakeUseCases(), {"alice": Role.SALES}) as c:
        made = await create(c["alice"])
        await c["alice"].put(f"{URL}/{made['id']}/layout", json=_layout_body(SIDE_CHART_FIRST, 1))
        stale = await c["alice"].put(f"{URL}/{made['id']}/layout", json=_layout_body(TABLE_ONLY, 1))
        reread = await c["alice"].get(f"{URL}/{made['id']}")

    problem(stale, 409, "invalid-state")
    assert (reread.json()["layout"], reread.json()["revision"]) == (SIDE_CHART_FIRST, 2)


async def test_put_layout_of_others_private_report_is_404_like_a_missing_one() -> None:
    async with clients(FakeUseCases(), {"alice": Role.SALES, "bob": Role.SALES}) as c:
        private = await create(c["alice"], visibility="private")
        hidden = await c["bob"].put(f"{URL}/{private['id']}/layout", json=_layout_body(TABLE_ONLY))
        missing = await c["bob"].put(f"{URL}/999999/layout", json=_layout_body(TABLE_ONLY))

    hidden_body = problem(hidden, 404, "not-found")
    missing_body = problem(missing, 404, "not-found")
    assert hidden_body["detail"] == missing_body["detail"] == "리포트를 찾을 수 없습니다."


async def test_put_layout_checks_not_found_before_an_invalid_layout() -> None:
    async with clients(FakeUseCases(), {"alice": Role.SALES, "bob": Role.SALES}) as c:
        private = await create(c["alice"], visibility="private")
        response = await c["bob"].put(
            f"{URL}/{private['id']}/layout", json=_layout_body(layout_json("grid"))
        )

    problem(response, 404, "not-found")


async def test_put_layout_checks_the_layout_value_before_the_revision() -> None:
    async with clients(FakeUseCases(), {"alice": Role.SALES}) as c:
        made = await create(c["alice"])
        response = await c["alice"].put(
            f"{URL}/{made['id']}/layout", json=_layout_body(layout_json("grid"), 9)
        )

    body = problem(response, 422, "invalid-report")
    assert _locations(body) == [(["layout", "view"], "invalid-value")]


async def test_put_layout_with_invalid_values_collects_every_location() -> None:
    bad = {"view": "x", "order": ["a"], "arrange": "y"}
    async with clients(FakeUseCases(), {"alice": Role.SALES}) as c:
        made = await create(c["alice"], layout=SIDE_CHART_FIRST)
        response = await c["alice"].put(f"{URL}/{made['id']}/layout", json=_layout_body(bad))
        reread = await c["alice"].get(f"{URL}/{made['id']}")

    body = problem(response, 422, "invalid-report")
    assert [loc for loc, _ in _locations(body)] == [
        ["layout", "view"],
        ["layout", "order"],
        ["layout", "arrange"],
    ]
    assert (reread.json()["layout"], reread.json()["revision"]) == (SIDE_CHART_FIRST, 1)


async def test_layout_request_unknown_key_returns_request_validation() -> None:
    async with clients(FakeUseCases(), {"alice": Role.SALES}) as c:
        made = await create(c["alice"])
        body = {**_layout_body(TABLE_ONLY), "name": "끼어든 키"}
        top = await c["alice"].put(f"{URL}/{made['id']}/layout", json=body)
        inner = await c["alice"].put(
            f"{URL}/{made['id']}/layout", json=_layout_body({**TABLE_ONLY, "extra": 1})
        )

    problem(top, 422, "request-validation")
    problem(inner, 422, "request-validation")


async def test_layout_request_missing_revision_returns_request_validation() -> None:
    async with clients(FakeUseCases(), {"alice": Role.SALES}) as c:
        made = await create(c["alice"])
        response = await c["alice"].put(f"{URL}/{made['id']}/layout", json={"layout": TABLE_ONLY})

    problem(response, 422, "request-validation")


async def test_layout_request_missing_layout_returns_request_validation() -> None:
    async with clients(FakeUseCases(), {"alice": Role.SALES}) as c:
        made = await create(c["alice"])
        response = await c["alice"].put(f"{URL}/{made['id']}/layout", json={"revision": 1})

    problem(response, 422, "request-validation")


@pytest.mark.parametrize("revision", [0, -1, "1", 1.5, None, True])
async def test_layout_request_bad_revision_returns_request_validation(revision: Any) -> None:  # noqa: ANN401
    async with clients(FakeUseCases(), {"alice": Role.SALES}) as c:
        made = await create(c["alice"])
        response = await c["alice"].put(
            f"{URL}/{made['id']}/layout", json=_layout_body(TABLE_ONLY, revision)
        )

    problem(response, 422, "request-validation")


async def test_put_layout_requires_a_login() -> None:
    async with clients(FakeUseCases(), {"alice": Role.SALES, "anon": Role.SALES}) as c:
        made = await create(c["alice"])
        response = await c["anon"].put(f"{URL}/{made['id']}/layout", json=_layout_body(TABLE_ONLY))

    assert response.status_code == 401


async def test_put_layout_keeps_a_broken_stored_chart_untouched() -> None:
    use_cases = FakeUseCases()
    async with clients(use_cases, {"alice": Role.SALES}) as c:
        report = make_report(owner=await use_cases.user_id_of("alice"), chart_unreadable=True)
        async with use_cases.uow as uow:
            await uow.saved_reports.add(report)
            await uow.commit()
        response = await c["alice"].put(f"{URL}/{report.id}/layout", json=_layout_body(TABLE_ONLY))
        reread = await c["alice"].get(f"{URL}/{report.id}")

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
    use_cases = FakeUseCases()
    async with clients(use_cases, {"alice": Role.SALES}) as c:
        broken_id = await _store_broken(use_cases, "alice")
        response = await c["alice"].put(f"{URL}/{broken_id}/layout", json=_layout_body(layout))
        async with use_cases.uow as uow:
            saved = await uow.saved_reports.get(ReportId(broken_id))

    body = problem(response, 422, "invalid-report")
    assert _locations(body) == [(["definition"], "stored-invalid")]
    assert (saved.layout.view, saved.revision) == ("both", 1)


async def test_put_layout_of_others_private_broken_report_is_404() -> None:
    use_cases = FakeUseCases()
    async with clients(use_cases, {"alice": Role.SALES, "bob": Role.SALES}) as c:
        broken_id = await _store_broken(use_cases, "alice", visibility="private")
        response = await c["bob"].put(f"{URL}/{broken_id}/layout", json=_layout_body(TABLE_ONLY))

    problem(response, 404, "not-found")
