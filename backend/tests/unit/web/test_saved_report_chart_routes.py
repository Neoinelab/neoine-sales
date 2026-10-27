"""저장 리포트 라우터의 차트 (Reports 4단계 AC1·2·3·4·6·7·8·9): FakeUseCases 위의 HTTP 계약.

차트는 선택 필드 `chart`(객체 또는 null)로 받고, 응답에 정규화된 `chart`와 `chart_problem`을 싣는다.
목록 항목에는 `chart_kind`가 있다. DB 없이 라우터·스키마·오류 매핑을 확인한다.
"""

from typing import TYPE_CHECKING, Any

import pytest

from app.domain.auth.principal import Role
from tests.factories_report import make_report
from tests.fakes.use_cases import FakeUseCases
from tests.support.chart_defs import chart_body, chart_definition
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

# 0 = Vendor(그룹), 1 = Status(그룹), 2 = amount(집계), 3 = users(집계)
GROUPED: dict[str, Any] = {
    "columns": [
        {"field": "deal.vendor", "group": True},
        {"field": "deal.status", "group": True},
        {"field": "deal.amount"},
        {"field": "deal.users"},
    ]
}
# 0 = Vendor(그룹), 1 = amount(집계), 2 = users(집계)
ONE_GROUP: dict[str, Any] = {
    "columns": [
        {"field": "deal.vendor", "group": True},
        {"field": "deal.amount"},
        {"field": "deal.users"},
    ]
}
UNGROUPED: dict[str, Any] = {"columns": [{"field": "deal.code"}, {"field": "deal.amount"}]}
STACKED = chart_body("stacked_bar", 0, series=1, values=[2], title="Vendor별", legend="bottom")
PROBLEM = "저장된 차트 설정을 읽을 수 없어 차트 없이 열었습니다. 차트를 다시 만들어 저장하세요."
BAD_SHAPES: list[Any] = [
    {**chart_body(), "unknown": 1},
    [],
    [1],
    "bar",
    5,
    True,
    {k: v for k, v in chart_body().items() if k != "kind"},
    {k: v for k, v in chart_body().items() if k != "category"},
    {k: v for k, v in chart_body().items() if k != "values"},
]
BAD_SHAPE_IDS = [
    "unknown-key",
    "empty-list",
    "list",
    "string",
    "number",
    "bool",
    "no-kind",
    "no-category",
    "no-values",
]


@pytest.fixture(autouse=True)
def _seoul(local_tz: Callable[[str], None]) -> None:
    local_tz("Asia/Seoul")


def _locations(body: dict[str, Any]) -> list[tuple[list[Any], str]]:
    return [(e["location"], e["code"]) for e in body["errors"]]


async def _store_unreadable(use_cases: FakeUseCases, owner: str, **overrides: Any) -> int:  # noqa: ANN401
    """저장소에 "차트를 읽을 수 없는" 리포트를 직접 넣는다(API로는 만들 수 없는 상태)."""
    report = make_report(
        owner=await use_cases.user_id_of(owner),
        definition=chart_definition(2, 2),
        chart_unreadable=True,
        **overrides,
    )
    async with use_cases.uow as uow:
        await uow.saved_reports.add(report)
        await uow.commit()
    return int(report.id)


# ---- 만들기 (AC1) ----


async def test_create_returns_the_normalized_chart() -> None:
    chart = chart_body("stacked_bar", 0, series=1, values=[2], title="  Vendor별  ")
    async with clients(FakeUseCases(), {"alice": Role.SALES}) as c:
        response = await c["alice"].post(URL, json=create_body(definition=GROUPED, chart=chart))

    assert response.status_code == 201, response.text
    body = response.json()
    assert body["chart"] == {**chart, "title": "Vendor별"}
    assert body["chart_problem"] is None
    assert body["chart_kind"] == "stacked_bar"


async def test_omitted_optional_chart_keys_get_their_defaults() -> None:
    minimal = {"kind": "bar", "category": 0, "values": [2]}
    async with clients(FakeUseCases(), {"alice": Role.SALES}) as c:
        response = await c["alice"].post(URL, json=create_body(definition=ONE_GROUP, chart=minimal))
        reread = await c["alice"].get(f"{URL}/{response.json()['id']}")

    assert response.status_code == 201, response.text
    expected = chart_body("bar", 0, values=[2])
    assert response.json()["chart"] == expected
    assert reread.json()["chart"] == expected


@pytest.mark.parametrize("omit", [True, False], ids=["key-omitted", "null"])
async def test_create_without_a_chart_has_no_chart(omit: bool) -> None:
    body = create_body(definition=GROUPED)
    if not omit:
        body["chart"] = None
    async with clients(FakeUseCases(), {"alice": Role.SALES}) as c:
        response = await c["alice"].post(URL, json=body)

    assert response.status_code == 201, response.text
    assert response.json()["chart"] is None
    assert response.json()["chart_problem"] is None
    assert response.json()["chart_kind"] is None


async def test_get_returns_the_saved_chart_and_the_list_shows_its_kind() -> None:
    async with clients(FakeUseCases(), {"alice": Role.SALES}) as c:
        with_chart = await create(c["alice"], "차트", definition=GROUPED, chart=STACKED)
        without = await create(c["alice"], "차트 없음", definition=GROUPED)
        detail = await c["alice"].get(f"{URL}/{with_chart['id']}")
        listed = await c["alice"].get(URL)

    assert detail.json()["chart"] == {**STACKED, "title": "Vendor별"}
    assert detail.json()["chart_problem"] is None
    kinds = {item["id"]: item["chart_kind"] for item in listed.json()}
    assert kinds == {with_chart["id"]: "stacked_bar", without["id"]: None}
    assert all("chart" not in item and "chart_problem" not in item for item in listed.json())


# ---- 요청 모양 (AC3) ----


@pytest.mark.parametrize("chart", BAD_SHAPES, ids=BAD_SHAPE_IDS)
async def test_chart_shape_errors_are_request_validation(chart: Any) -> None:  # noqa: ANN401
    async with clients(FakeUseCases(), {"alice": Role.SALES}) as c:
        made = await create(c["alice"], definition=GROUPED)
        control = await c["alice"].post(
            URL, json=create_body("올바른 차트", definition=GROUPED, chart=STACKED)
        )
        created = await c["alice"].post(URL, json=create_body("다른 이름", chart=chart))
        updated = await c["alice"].put(
            f"{URL}/{made['id']}", json=update_body(1, definition=GROUPED, chart=chart)
        )
        reread = await c["alice"].get(f"{URL}/{made['id']}")

    assert control.status_code == 201, control.text  # 올바른 모양의 차트는 받는다
    problem(created, 422, "request-validation")
    problem(updated, 422, "request-validation")
    assert reread.json()["revision"] == 1


async def test_copy_request_still_rejects_a_chart_key() -> None:
    async with clients(FakeUseCases(), {"alice": Role.SALES}) as c:
        made = await create(c["alice"], definition=GROUPED, chart=STACKED)
        response = await c["alice"].post(
            f"{URL}/{made['id']}/copy",
            json={"name": "복사", "visibility": "public", "chart": STACKED},
        )

    problem(response, 422, "request-validation")


# ---- 값 검증 (AC2) ----


async def test_chart_issues_map_to_invalid_report_with_chart_location() -> None:
    chart = chart_body("bar", 0, values=[1, 0])  # 둘째 값이 그룹 컬럼
    async with clients(FakeUseCases(), {"alice": Role.SALES}) as c:
        response = await c["alice"].post(URL, json=create_body(definition=ONE_GROUP, chart=chart))
        listed = await c["alice"].get(URL)

    body = problem(response, 422, "invalid-report")
    assert _locations(body) == [(["chart", "values", 1], "chart-value-invalid")]
    assert body["errors"][0]["message"] == "값 열은 숫자(집계) 컬럼이어야 합니다"
    assert body["detail"] == body["errors"][0]["message"]
    assert listed.json() == []


async def test_a_string_index_is_a_value_error_not_a_shape_error() -> None:
    chart = chart_body("bar", "0", values=[1])
    async with clients(FakeUseCases(), {"alice": Role.SALES}) as c:
        response = await c["alice"].post(URL, json=create_body(definition=ONE_GROUP, chart=chart))

    body = problem(response, 422, "invalid-report")
    assert _locations(body) == [(["chart", "category"], "chart-category-invalid")]


@pytest.mark.parametrize("key", ["value_min", "value_max"])
@pytest.mark.parametrize("number", [10**400, -(10**400)])
async def test_a_huge_integer_range_is_invalid_report_not_a_server_error(
    key: str, number: int
) -> None:
    chart = chart_body("bar", 0, values=[1], **{key: number})
    async with clients(FakeUseCases(), {"alice": Role.SALES}) as c:
        response = await c["alice"].post(URL, json=create_body(definition=ONE_GROUP, chart=chart))

    body = problem(response, 422, "invalid-report")
    assert _locations(body) == [(["chart", key], "chart-range-invalid")]


async def test_a_huge_value_list_returns_one_violation() -> None:
    chart = chart_body("bar", 0, values=[0] * 100_000)
    async with clients(FakeUseCases(), {"alice": Role.SALES}) as c:
        response = await c["alice"].post(URL, json=create_body(definition=ONE_GROUP, chart=chart))

    body = problem(response, 422, "invalid-report")
    assert _locations(body) == [(["chart", "values"], "chart-values-count")]


async def test_all_chart_issues_are_returned_together() -> None:
    chart = chart_body("bar", 1, values=[0], legend="left")
    async with clients(FakeUseCases(), {"alice": Role.SALES}) as c:
        response = await c["alice"].post(URL, json=create_body(definition=ONE_GROUP, chart=chart))

    body = problem(response, 422, "invalid-report")
    assert {code for _, code in _locations(body)} == {
        "chart-category-invalid",
        "chart-value-invalid",
        "chart-legend-invalid",
    }


async def test_chart_for_an_ungrouped_definition_is_invalid_report() -> None:
    async with clients(FakeUseCases(), {"alice": Role.SALES}) as c:
        response = await c["alice"].post(
            URL, json=create_body(definition=UNGROUPED, chart=chart_body())
        )

    body = problem(response, 422, "invalid-report")
    assert _locations(body) == [(["chart"], "chart-needs-grouping")]


async def test_definition_issues_are_returned_without_chart_issues() -> None:
    bad_definition = {"columns": [{"field": "deal.password"}]}
    chart = chart_body("nope", 99, values="x")
    async with clients(FakeUseCases(), {"alice": Role.SALES}) as c:
        response = await c["alice"].post(
            URL, json=create_body(definition=bad_definition, chart=chart)
        )

    body = problem(response, 422, "invalid-report")
    assert _locations(body) == [(["columns", 0, "field"], "unknown-field")]


# ---- 덮어쓰기 (AC1·4·5) ----


async def test_put_changes_only_the_chart_and_bumps_the_revision() -> None:
    async with clients(FakeUseCases(), {"alice": Role.SALES}) as c:
        made = await create(
            c["alice"], definition=GROUPED, chart=chart_body("bar", 0, series=1, values=[2])
        )
        response = await c["alice"].put(
            f"{URL}/{made['id']}", json=update_body(1, "수정본", definition=GROUPED, chart=STACKED)
        )

    assert response.status_code == 200, response.text
    body = response.json()
    assert body["revision"] == 2
    assert body["chart"] == {**STACKED, "title": "Vendor별"}
    assert body["chart_kind"] == "stacked_bar"
    assert body["generated_sql"] == made["generated_sql"]  # 차트와 무관
    assert body["updated_at"] >= made["updated_at"]


@pytest.mark.parametrize("omit", [True, False], ids=["key-omitted", "null"])
async def test_put_without_a_chart_removes_the_saved_one(omit: bool) -> None:
    body = update_body(1, "수정본", definition=GROUPED)
    if not omit:
        body["chart"] = None
    async with clients(FakeUseCases(), {"alice": Role.SALES}) as c:
        made = await create(c["alice"], definition=GROUPED, chart=STACKED)
        response = await c["alice"].put(f"{URL}/{made['id']}", json=body)
        reread = await c["alice"].get(f"{URL}/{made['id']}")

    assert response.status_code == 200, response.text
    assert response.json()["chart"] is None
    assert reread.json()["chart"] is None
    assert reread.json()["chart_kind"] is None


async def test_put_with_a_chart_that_no_longer_fits_the_definition_is_rejected() -> None:
    async with clients(FakeUseCases(), {"alice": Role.SALES}) as c:
        made = await create(c["alice"], definition=GROUPED, chart=STACKED)
        response = await c["alice"].put(
            f"{URL}/{made['id']}",
            json=update_body(1, "수정본", definition=UNGROUPED, chart=STACKED),
        )
        reread = await c["alice"].get(f"{URL}/{made['id']}")

    body = problem(response, 422, "invalid-report")
    assert _locations(body) == [(["chart"], "chart-needs-grouping")]
    assert reread.json()["revision"] == 1
    assert reread.json()["definition"] == made["definition"]
    assert reread.json()["chart"] == made["chart"]


# ---- 복제 (AC6) ----


async def test_copy_carries_the_chart() -> None:
    async with clients(FakeUseCases(), {"alice": Role.SALES, "bob": Role.USER}) as c:
        made = await create(c["alice"], definition=GROUPED, chart=STACKED)
        response = await c["bob"].post(
            f"{URL}/{made['id']}/copy", json={"name": "복사본", "visibility": "private"}
        )

    assert response.status_code == 201, response.text
    assert response.json()["chart"] == made["chart"]
    assert response.json()["chart_kind"] == "stacked_bar"
    assert response.json()["chart_problem"] is None


# ---- 깨진 저장 차트 (AC7) ----


async def test_get_opens_a_report_with_an_unreadable_chart_without_a_chart() -> None:
    use_cases = FakeUseCases()
    async with clients(use_cases, {"alice": Role.SALES}) as c:
        report_id = await _store_unreadable(use_cases, "alice", name="깨진 차트")
        response = await c["alice"].get(f"{URL}/{report_id}")

    assert response.status_code == 200, response.text
    body = response.json()
    assert body["chart"] is None
    assert body["chart_problem"] == PROBLEM
    assert body["chart_kind"] is None
    assert body["name"] == "깨진 차트"


async def test_list_and_run_work_with_an_unreadable_chart() -> None:
    use_cases = FakeUseCases()
    async with clients(use_cases, {"alice": Role.SALES}) as c:
        report_id = await _store_unreadable(use_cases, "alice")
        listed = await c["alice"].get(URL)
        run = await c["alice"].post(f"{URL}/{report_id}/run")

    assert listed.status_code == 200, listed.text
    (item,) = listed.json()
    assert (item["id"], item["chart_kind"]) == (report_id, None)
    assert run.status_code == 200, run.text


async def test_copy_of_an_unreadable_chart_report_has_no_chart() -> None:
    use_cases = FakeUseCases()
    async with clients(use_cases, {"alice": Role.SALES}) as c:
        report_id = await _store_unreadable(use_cases, "alice")
        response = await c["alice"].post(
            f"{URL}/{report_id}/copy", json={"name": "복사본", "visibility": "public"}
        )

    assert response.status_code == 201, response.text
    assert response.json()["chart"] is None
    assert response.json()["chart_problem"] is None


@pytest.mark.parametrize("chart", [STACKED, None], ids=["new-chart", "no-chart"])
async def test_put_repairs_an_unreadable_chart(chart: dict[str, Any] | None) -> None:
    use_cases = FakeUseCases()
    async with clients(use_cases, {"alice": Role.SALES}) as c:
        report_id = await _store_unreadable(use_cases, "alice", name="복구")
        response = await c["alice"].put(
            f"{URL}/{report_id}", json=update_body(1, "복구", definition=GROUPED, chart=chart)
        )
        reread = await c["alice"].get(f"{URL}/{report_id}")

    assert response.status_code == 200, response.text
    assert response.json()["chart_problem"] is None
    assert reread.json()["chart_problem"] is None
    assert reread.json()["chart_kind"] == (None if chart is None else "stacked_bar")


async def test_permission_is_decided_before_the_chart_is_read() -> None:
    use_cases = FakeUseCases()
    async with clients(use_cases, {"alice": Role.SALES, "bob": Role.SALES}) as c:
        report_id = await _store_unreadable(use_cases, "alice", visibility="private")
        get = await c["bob"].get(f"{URL}/{report_id}")
        copy = await c["bob"].post(
            f"{URL}/{report_id}/copy", json={"name": "침입", "visibility": "public"}
        )

    problem(get, 404, "not-found")
    problem(copy, 404, "not-found")
