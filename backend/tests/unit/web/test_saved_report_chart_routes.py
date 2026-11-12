"""저장 리포트 라우터의 차트: FakeUseCases 위의 HTTP 계약(RC-R4, RC-R5, RC-R18~RC-R21).

차트는 선택 필드 `chart`(객체 또는 null)로 받고, 응답에 정규화된 `chart`와 `chart_problem`을 싣는다.
목록 항목에는 `chart_kind`가 있다. DB 없이 라우터·스키마·오류 매핑을 확인한다.
"""

from typing import TYPE_CHECKING, Any

import pytest

from app.domain.auth.principal import Role
from tests.factories_report import make_report
from tests.fakes.use_cases import FakeUseCases
from tests.support.chart_defs import bins, chart_body, chart_definition, combo_item
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


async def test_create_returns_the_normalized_chart() -> None:
    """차트와 함께 POST하면 201과 정규화된 차트·종류가 돌아온다.

    테스트 코드: RC-033
    """
    # given: 공백이 붙은 제목을 가진 누적 막대 차트
    chart = chart_body("stacked_bar", 0, series=1, values=[2], title="  Vendor별  ")
    # when: 차트와 함께 리포트를 만든다
    async with clients(FakeUseCases(), {"alice": Role.SALES}) as c:
        response = await c["alice"].post(URL, json=create_body(definition=GROUPED, chart=chart))

    # then: 201이고 응답 차트는 제목 공백이 지워진 값이며 chart_problem은 null, 종류는 stacked_bar다
    assert response.status_code == 201, response.text
    body = response.json()
    assert body["chart"] == {**chart, "title": "Vendor별"}
    assert body["chart_problem"] is None
    assert body["chart_kind"] == "stacked_bar"


async def test_omitted_optional_chart_keys_get_their_defaults() -> None:
    """선택 키를 생략한 차트는 기본값이 채워져 저장되고 다시 읽어도 같다.

    테스트 코드: RC-033
    """
    # given: 필수 키 세 개만 가진 차트
    minimal = {"kind": "bar", "category": 0, "values": [2]}
    # when: 리포트를 만들고 다시 조회한다
    async with clients(FakeUseCases(), {"alice": Role.SALES}) as c:
        response = await c["alice"].post(URL, json=create_body(definition=ONE_GROUP, chart=minimal))
        reread = await c["alice"].get(f"{URL}/{response.json()['id']}")

    # then: 응답과 재조회의 차트가 기본값으로 채워져 있다
    assert response.status_code == 201, response.text
    expected = chart_body("bar", 0, values=[2])
    assert response.json()["chart"] == expected
    assert reread.json()["chart"] == expected


@pytest.mark.parametrize("omit", [True, False], ids=["key-omitted", "null"])
async def test_create_without_a_chart_has_no_chart(omit: bool) -> None:
    """chart를 생략하거나 null로 보내면 차트 없는 리포트가 만들어진다.

    테스트 코드: RC-033
    """
    # given: chart 키를 생략하거나 null로 둔 본문
    body = create_body(definition=GROUPED)
    if not omit:
        body["chart"] = None
    # when: 리포트를 만든다
    async with clients(FakeUseCases(), {"alice": Role.SALES}) as c:
        response = await c["alice"].post(URL, json=body)

    # then: 201이고 chart·chart_problem·chart_kind가 모두 null이다
    assert response.status_code == 201, response.text
    assert response.json()["chart"] is None
    assert response.json()["chart_problem"] is None
    assert response.json()["chart_kind"] is None


async def test_get_returns_the_saved_chart_and_the_list_shows_its_kind() -> None:
    """상세는 저장된 차트를 보이고 목록은 종류만 보인다.

    테스트 코드: RC-033, RC-037
    """
    # when: 차트 있는 리포트와 없는 리포트를 만들어 상세와 목록을 조회한다
    async with clients(FakeUseCases(), {"alice": Role.SALES}) as c:
        with_chart = await create(c["alice"], "차트", definition=GROUPED, chart=STACKED)
        without = await create(c["alice"], "차트 없음", definition=GROUPED)
        detail = await c["alice"].get(f"{URL}/{with_chart['id']}")
        listed = await c["alice"].get(URL)

    # then: 상세에는 차트가 있고 목록 항목에는 chart_kind만 있다
    assert detail.json()["chart"] == {**STACKED, "title": "Vendor별"}
    assert detail.json()["chart_problem"] is None
    kinds = {item["id"]: item["chart_kind"] for item in listed.json()}
    assert kinds == {with_chart["id"]: "stacked_bar", without["id"]: None}
    assert all("chart" not in item and "chart_problem" not in item for item in listed.json())


@pytest.mark.parametrize("chart", BAD_SHAPES, ids=BAD_SHAPE_IDS)
async def test_chart_shape_errors_are_request_validation(chart: Any) -> None:  # noqa: ANN401
    """차트 모양이 틀리면 만들기·덮어쓰기 모두 request-validation이고 저장은 그대로다.

    테스트 코드: RC-032
    """
    # when: 잘못된 모양의 차트로 만들고 덮어쓴다 (전제: 올바른 모양의 차트는 201로 받는다)
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

    # then: 둘 다 422 request-validation이고 기존 리포트 revision은 그대로다
    assert control.status_code == 201, control.text  # 올바른 모양의 차트는 받는다
    problem(created, 422, "request-validation")
    problem(updated, 422, "request-validation")
    assert reread.json()["revision"] == 1


async def test_copy_request_still_rejects_a_chart_key() -> None:
    """복제 요청에 chart 키를 보내면 request-validation이다.

    테스트 코드: RC-032
    """
    # when: chart 키를 함께 보내 복제한다
    async with clients(FakeUseCases(), {"alice": Role.SALES}) as c:
        made = await create(c["alice"], definition=GROUPED, chart=STACKED)
        response = await c["alice"].post(
            f"{URL}/{made['id']}/copy",
            json={"name": "복사", "visibility": "public", "chart": STACKED},
        )

    # then: 422 request-validation이다
    problem(response, 422, "request-validation")


async def test_chart_issues_map_to_invalid_report_with_chart_location() -> None:
    """차트 값 위반은 422 invalid-report와 차트 위치·한국어 문구로 돌아오고 저장되지 않는다.

    테스트 코드: RC-030
    """
    # given: 둘째 값이 그룹 컬럼인 차트
    chart = chart_body("bar", 0, values=[1, 0])  # 둘째 값이 그룹 컬럼
    # when: 리포트를 만든다
    async with clients(FakeUseCases(), {"alice": Role.SALES}) as c:
        response = await c["alice"].post(URL, json=create_body(definition=ONE_GROUP, chart=chart))
        listed = await c["alice"].get(URL)

    body = problem(response, 422, "invalid-report")
    # then: 위치 `["chart","values",1]`과 코드·문구가 나오고 detail은 첫 문구이며 목록은 비어 있다
    assert _locations(body) == [(["chart", "values", 1], "chart-value-invalid")]
    assert body["errors"][0]["message"] == "값 열은 숫자(집계) 컬럼이어야 합니다"
    assert body["detail"] == body["errors"][0]["message"]
    assert listed.json() == []


async def test_a_string_index_is_a_value_error_not_a_shape_error() -> None:
    """범주 index가 문자열이면 모양 오류가 아니라 값 오류(invalid-report)다.

    테스트 코드: RC-032
    """
    # given: 범주가 문자열 "0"인 차트
    chart = chart_body("bar", "0", values=[1])
    # when: 리포트를 만든다
    async with clients(FakeUseCases(), {"alice": Role.SALES}) as c:
        response = await c["alice"].post(URL, json=create_body(definition=ONE_GROUP, chart=chart))

    body = problem(response, 422, "invalid-report")
    # then: 422 invalid-report이고 `chart.category` chart-category-invalid다
    assert _locations(body) == [(["chart", "category"], "chart-category-invalid")]


@pytest.mark.parametrize("key", ["value_min", "value_max"])
@pytest.mark.parametrize("number", [10**400, -(10**400)])
async def test_a_huge_integer_range_is_invalid_report_not_a_server_error(
    key: str, number: int
) -> None:
    """매우 큰 정수 범위도 서버 오류 없이 invalid-report다.

    테스트 코드: RC-032
    """
    # given: 10^400 범위를 가진 차트
    chart = chart_body("bar", 0, values=[1], **{key: number})
    # when: 리포트를 만든다
    async with clients(FakeUseCases(), {"alice": Role.SALES}) as c:
        response = await c["alice"].post(URL, json=create_body(definition=ONE_GROUP, chart=chart))

    body = problem(response, 422, "invalid-report")
    # then: 422 invalid-report이고 해당 키 chart-range-invalid다
    assert _locations(body) == [(["chart", key], "chart-range-invalid")]


async def test_a_huge_value_list_returns_one_violation() -> None:
    """값 목록이 10만 개여도 위반은 하나뿐이다.

    테스트 코드: RC-013, RC-030
    """
    # given: 값 10만 개짜리 차트
    chart = chart_body("bar", 0, values=[0] * 100_000)
    # when: 리포트를 만든다
    async with clients(FakeUseCases(), {"alice": Role.SALES}) as c:
        response = await c["alice"].post(URL, json=create_body(definition=ONE_GROUP, chart=chart))

    body = problem(response, 422, "invalid-report")
    # then: 422 invalid-report이고 chart-values-count 하나뿐이다
    assert _locations(body) == [(["chart", "values"], "chart-values-count")]


async def test_all_chart_issues_are_returned_together() -> None:
    """차트 위반은 모두 모아서 한 응답으로 돌려준다.

    테스트 코드: RC-030
    """
    # given: 범주·값·범례가 함께 틀린 차트
    chart = chart_body("bar", 1, values=[0], legend="left")
    # when: 리포트를 만든다
    async with clients(FakeUseCases(), {"alice": Role.SALES}) as c:
        response = await c["alice"].post(URL, json=create_body(definition=ONE_GROUP, chart=chart))

    body = problem(response, 422, "invalid-report")
    # then: 422 invalid-report이고 세 위반 코드가 모두 있다
    assert {code for _, code in _locations(body)} == {
        "chart-category-invalid",
        "chart-value-invalid",
        "chart-legend-invalid",
    }


async def test_chart_for_an_ungrouped_definition_is_invalid_report() -> None:
    """그룹핑 없는 정의에 차트를 보내면 invalid-report다.

    테스트 코드: RC-003, RC-030
    """
    # when: 그룹핑 없는 정의와 막대 차트로 리포트를 만든다
    async with clients(FakeUseCases(), {"alice": Role.SALES}) as c:
        response = await c["alice"].post(
            URL, json=create_body(definition=UNGROUPED, chart=chart_body())
        )

    body = problem(response, 422, "invalid-report")
    # then: 422 invalid-report이고 `chart` chart-needs-grouping 하나뿐이다
    assert _locations(body) == [(["chart"], "chart-needs-grouping")]


async def test_definition_issues_are_returned_without_chart_issues() -> None:
    """정의 위반이 있으면 정의 위반만 돌려주고 차트 위반은 알리지 않는다.

    테스트 코드: RC-031
    """
    # given: 엉터리 차트와 허용되지 않는 필드를 가진 정의
    bad_definition = {"columns": [{"field": "deal.password"}]}
    # when: 리포트를 만든다
    chart = chart_body("nope", 99, values="x")
    async with clients(FakeUseCases(), {"alice": Role.SALES}) as c:
        response = await c["alice"].post(
            URL, json=create_body(definition=bad_definition, chart=chart)
        )

    body = problem(response, 422, "invalid-report")
    # then: 422 invalid-report이고 정의 위치 위반뿐이다
    assert _locations(body) == [(["columns", 0, "field"], "unknown-field")]


async def test_put_changes_only_the_chart_and_bumps_the_revision() -> None:
    """차트만 바꿔 덮어써도 revision이 오르고 SQL은 그대로다.

    테스트 코드: RC-035
    """
    # when: 막대 차트가 있는 리포트를 누적 막대 차트로 덮어쓴다
    async with clients(FakeUseCases(), {"alice": Role.SALES}) as c:
        made = await create(
            c["alice"], definition=GROUPED, chart=chart_body("bar", 0, series=1, values=[2])
        )
        response = await c["alice"].put(
            f"{URL}/{made['id']}", json=update_body(1, "수정본", definition=GROUPED, chart=STACKED)
        )

    # then: 200이고 revision 2, 새 차트·종류, 같은 generated_sql이다
    assert response.status_code == 200, response.text
    body = response.json()
    assert body["revision"] == 2
    assert body["chart"] == {**STACKED, "title": "Vendor별"}
    assert body["chart_kind"] == "stacked_bar"
    assert body["generated_sql"] == made["generated_sql"]  # 차트와 무관
    assert body["updated_at"] >= made["updated_at"]


@pytest.mark.parametrize("omit", [True, False], ids=["key-omitted", "null"])
async def test_put_without_a_chart_removes_the_saved_one(omit: bool) -> None:
    """덮어쓸 때 chart를 생략하거나 null로 보내면 저장된 차트가 지워진다.

    테스트 코드: RC-035
    """
    # given: chart 키를 생략하거나 null로 둔 덮어쓰기 본문
    body = update_body(1, "수정본", definition=GROUPED)
    if not omit:
        body["chart"] = None
    # when: 차트가 있는 리포트를 덮어쓴다
    async with clients(FakeUseCases(), {"alice": Role.SALES}) as c:
        made = await create(c["alice"], definition=GROUPED, chart=STACKED)
        response = await c["alice"].put(f"{URL}/{made['id']}", json=body)
        reread = await c["alice"].get(f"{URL}/{made['id']}")

    # then: 200이고 응답과 재조회의 chart·chart_kind가 null이다
    assert response.status_code == 200, response.text
    assert response.json()["chart"] is None
    assert reread.json()["chart"] is None
    assert reread.json()["chart_kind"] is None


async def test_put_with_a_chart_that_no_longer_fits_the_definition_is_rejected() -> None:
    """바뀐 정의에 맞지 않는 차트로 덮어쓰면 거절되고 저장 내용은 그대로다.

    테스트 코드: RC-036
    """
    # when: 그룹핑을 끈 정의와 이전 차트로 덮어쓴다
    async with clients(FakeUseCases(), {"alice": Role.SALES}) as c:
        made = await create(c["alice"], definition=GROUPED, chart=STACKED)
        response = await c["alice"].put(
            f"{URL}/{made['id']}",
            json=update_body(1, "수정본", definition=UNGROUPED, chart=STACKED),
        )
        reread = await c["alice"].get(f"{URL}/{made['id']}")

    body = problem(response, 422, "invalid-report")
    # then: 422 invalid-report이고 revision·정의·차트가 그대로다
    assert _locations(body) == [(["chart"], "chart-needs-grouping")]
    assert reread.json()["revision"] == 1
    assert reread.json()["definition"] == made["definition"]
    assert reread.json()["chart"] == made["chart"]


async def test_copy_carries_the_chart() -> None:
    """복제하면 원본 차트가 복사본에 그대로 담긴다.

    테스트 코드: RC-038
    """
    # when: 다른 사용자가 공개 리포트를 복제한다
    async with clients(FakeUseCases(), {"alice": Role.SALES, "bob": Role.USER}) as c:
        made = await create(c["alice"], definition=GROUPED, chart=STACKED)
        response = await c["bob"].post(
            f"{URL}/{made['id']}/copy", json={"name": "복사본", "visibility": "private"}
        )

    # then: 201이고 복사본 차트·종류가 원본과 같고 chart_problem은 null이다
    assert response.status_code == 201, response.text
    assert response.json()["chart"] == made["chart"]
    assert response.json()["chart_kind"] == "stacked_bar"
    assert response.json()["chart_problem"] is None


async def test_get_opens_a_report_with_an_unreadable_chart_without_a_chart() -> None:
    """저장 차트를 읽을 수 없는 리포트는 200으로 차트 없이 안내 문구와 함께 열린다.

    테스트 코드: RC-040
    """
    # when: 차트를 읽을 수 없는 리포트를 조회한다 (전제: 저장소에 직접 넣은 상태)
    use_cases = FakeUseCases()
    async with clients(use_cases, {"alice": Role.SALES}) as c:
        report_id = await _store_unreadable(use_cases, "alice", name="깨진 차트")
        response = await c["alice"].get(f"{URL}/{report_id}")

    # then: 200이고 chart·chart_kind는 null, chart_problem은 안내 문구다
    assert response.status_code == 200, response.text
    body = response.json()
    assert body["chart"] is None
    assert body["chart_problem"] == PROBLEM
    assert body["chart_kind"] is None
    assert body["name"] == "깨진 차트"


async def test_list_and_run_work_with_an_unreadable_chart() -> None:
    """차트를 읽을 수 없어도 목록과 실행은 된다.

    테스트 코드: RC-040
    """
    # when: 목록을 조회하고 실행한다 (전제: 차트를 읽을 수 없는 리포트)
    use_cases = FakeUseCases()
    async with clients(use_cases, {"alice": Role.SALES}) as c:
        report_id = await _store_unreadable(use_cases, "alice")
        listed = await c["alice"].get(URL)
        run = await c["alice"].post(f"{URL}/{report_id}/run")

    # then: 목록 200에 chart_kind null이고 실행도 200이다
    assert listed.status_code == 200, listed.text
    (item,) = listed.json()
    assert (item["id"], item["chart_kind"]) == (report_id, None)
    assert run.status_code == 200, run.text


async def test_copy_of_an_unreadable_chart_report_has_no_chart() -> None:
    """차트를 읽을 수 없는 리포트도 차트 없이 복제된다.

    테스트 코드: RC-038, RC-040
    """
    # when: 복제한다 (전제: 차트를 읽을 수 없는 리포트)
    use_cases = FakeUseCases()
    async with clients(use_cases, {"alice": Role.SALES}) as c:
        report_id = await _store_unreadable(use_cases, "alice")
        response = await c["alice"].post(
            f"{URL}/{report_id}/copy", json={"name": "복사본", "visibility": "public"}
        )

    # then: 201이고 복사본 chart·chart_problem이 null이다
    assert response.status_code == 201, response.text
    assert response.json()["chart"] is None
    assert response.json()["chart_problem"] is None


@pytest.mark.parametrize("chart", [STACKED, None], ids=["new-chart", "no-chart"])
async def test_put_repairs_an_unreadable_chart(chart: dict[str, Any] | None) -> None:
    """차트를 읽을 수 없는 리포트를 새 차트 또는 차트 없이 덮어쓰면 복구된다.

    테스트 코드: RC-041
    """
    # when: 새 차트 또는 차트 없이 덮어쓰고 다시 조회한다 (전제: 차트를 읽을 수 없는 리포트)
    use_cases = FakeUseCases()
    async with clients(use_cases, {"alice": Role.SALES}) as c:
        report_id = await _store_unreadable(use_cases, "alice", name="복구")
        response = await c["alice"].put(
            f"{URL}/{report_id}", json=update_body(1, "복구", definition=GROUPED, chart=chart)
        )
        reread = await c["alice"].get(f"{URL}/{report_id}")

    # then: 200이고 chart_problem이 null이며 종류는 새 차트의 종류(없으면 null)다
    assert response.status_code == 200, response.text
    assert response.json()["chart_problem"] is None
    assert reread.json()["chart_problem"] is None
    assert reread.json()["chart_kind"] == (None if chart is None else "stacked_bar")


async def test_permission_is_decided_before_the_chart_is_read() -> None:
    """볼 수 없는 리포트는 차트 상태와 상관없이 404로 숨긴다."""
    # when: 다른 사용자가 비공개 리포트를 조회하고 복제한다 (전제: 차트를 읽을 수 없는 비공개
    #   리포트)
    use_cases = FakeUseCases()
    async with clients(use_cases, {"alice": Role.SALES, "bob": Role.SALES}) as c:
        report_id = await _store_unreadable(use_cases, "alice", visibility="private")
        get = await c["bob"].get(f"{URL}/{report_id}")
        copy = await c["bob"].post(
            f"{URL}/{report_id}/copy", json={"name": "침입", "visibility": "public"}
        )

    problem(get, 404, "not-found")
    # then: 둘 다 404 not-found다
    problem(copy, 404, "not-found")


# 0 = Vendor(그룹), 1 = amount(집계), 2 = users(집계), 3 = code 건수(집계): 거품형은 값 열 3개
THREE_VALUES: dict[str, Any] = {
    "columns": [
        {"field": "deal.vendor", "group": True},
        {"field": "deal.amount"},
        {"field": "deal.users"},
        {"field": "deal.code", "aggregate": "count"},
    ]
}
NEW_KIND_BODIES: list[tuple[str, dict[str, Any], dict[str, Any]]] = [
    (
        "stacked_horizontal_bar",
        GROUPED,
        chart_body("stacked_horizontal_bar", 0, series=1, values=[2]),
    ),
    ("bubble", THREE_VALUES, chart_body("bubble", 0, values=[1, 2, 3])),
    ("treemap", GROUPED, chart_body("treemap", 0, series=1, values=[2])),
    ("waterfall", ONE_GROUP, chart_body("waterfall", 0, values=[1], show_total=True)),
    (
        "combo",
        ONE_GROUP,
        chart_body(
            "combo",
            0,
            values=[1, 2],
            secondary_axis=True,
            combo_series=[combo_item("stacked_area"), combo_item("line_markers", secondary=True)],
        ),
    ),
]


@pytest.mark.parametrize(
    ("kind", "definition", "chart"), NEW_KIND_BODIES, ids=[k for k, _, _ in NEW_KIND_BODIES]
)
async def test_new_chart_kinds_are_saved_and_read_back_unchanged(
    kind: str, definition: dict[str, Any], chart: dict[str, Any]
) -> None:
    """새 종류 차트는 저장한 설정 그대로 다시 읽히고 목록에 그 종류가 나온다.

    테스트 코드: RC-047
    """
    # when: 새 종류 차트로 리포트를 만들고 다시 조회·목록 조회한다
    async with clients(FakeUseCases(), {"alice": Role.SALES}) as c:
        response = await c["alice"].post(URL, json=create_body(definition=definition, chart=chart))
        reread = await c["alice"].get(f"{URL}/{response.json()['id']}")
        listed = await c["alice"].get(URL)

    # then: 응답과 재조회의 차트가 요청과 같고 목록 chart_kind가 그 종류다
    assert response.status_code == 201, response.text
    assert response.json()["chart"] == chart
    assert response.json()["chart_kind"] == kind
    assert reread.json()["chart"] == chart
    assert [item["chart_kind"] for item in listed.json()] == [kind]


async def test_ungrouped_histogram_is_saved_with_a_null_category() -> None:
    """그룹핑 없는 리포트의 히스토그램은 범주 null·자동 구간으로 저장된다.

    테스트 코드: RC-048
    """
    # when: 그룹핑 없는 정의의 히스토그램으로 리포트를 만들고 다시 조회한다
    chart = chart_body("histogram", None, values=[1])
    async with clients(FakeUseCases(), {"alice": Role.SALES}) as c:
        response = await c["alice"].post(URL, json=create_body(definition=UNGROUPED, chart=chart))
        reread = await c["alice"].get(f"{URL}/{response.json()['id']}")

    # then: 범주는 null, 구간은 auto로 정규화되고 재조회도 같으며 종류는 histogram이다
    assert response.status_code == 201, response.text
    saved = response.json()["chart"]
    assert saved["category"] is None
    assert saved["histogram"] == bins()  # 생략하면 auto로 정규화
    assert reread.json()["chart"] == saved
    assert response.json()["chart_kind"] == "histogram"


async def test_omitted_new_option_keys_get_their_defaults() -> None:
    """새 옵션 키를 생략하면 기본값(null·false·null)으로 채워진다.

    테스트 코드: RC-025
    """
    # when: 옵션 없는 폭포 차트로 리포트를 만든다
    minimal = {"kind": "waterfall", "category": 0, "values": [1]}
    async with clients(FakeUseCases(), {"alice": Role.SALES}) as c:
        response = await c["alice"].post(URL, json=create_body(definition=ONE_GROUP, chart=minimal))

    # then: 구간 null, 합계 false, 계열 설정 null이다
    assert response.status_code == 201, response.text
    saved = response.json()["chart"]
    assert (saved["histogram"], saved["show_total"], saved["combo_series"]) == (None, False, None)


async def test_a_legacy_combo_request_returns_the_filled_series_settings() -> None:
    """계열 설정 없는 콤보 요청은 채워진 계열 설정으로 돌아온다.

    테스트 코드: RC-026
    """
    # when: 계열 설정 없이 보조 축을 켠 콤보로 리포트를 만든다
    chart = chart_body("combo", 0, values=[1, 2], secondary_axis=True)
    async with clients(FakeUseCases(), {"alice": Role.SALES}) as c:
        response = await c["alice"].post(URL, json=create_body(definition=ONE_GROUP, chart=chart))

    # then: 막대 + 보조 축 꺾은선으로 채운 계열 설정이다
    assert response.status_code == 201, response.text
    assert response.json()["chart"]["combo_series"] == [
        combo_item("column"),
        combo_item("line", secondary=True),
    ]


async def test_invalid_histogram_option_returns_422_with_location() -> None:
    """잘못된 구간 설정은 위치와 함께 422이고 저장되지 않는다.

    테스트 코드: RC-021, RC-030
    """
    # given: 구간 수 0인 히스토그램
    chart = chart_body("histogram", None, values=[1], histogram=bins(bin_mode="count", bin_count=0))
    # when: 리포트를 만든다
    async with clients(FakeUseCases(), {"alice": Role.SALES}) as c:
        response = await c["alice"].post(URL, json=create_body(definition=UNGROUPED, chart=chart))
        listed = await c["alice"].get(URL)

    body = problem(response, 422, "invalid-report")
    # then: 422 invalid-report이고 `histogram.bin_count` 위반이며 목록은 비어 있다
    assert _locations(body) == [(["chart", "histogram", "bin_count"], "chart-histogram-invalid")]
    assert listed.json() == []


async def test_invalid_combo_series_returns_422_with_location() -> None:
    """잘못된 계열 종류는 그 항목 위치와 함께 422다.

    테스트 코드: RC-027, RC-030
    """
    # given: 둘째 계열 종류가 bar인 콤보
    chart = chart_body(
        "combo",
        0,
        values=[1, 2],
        combo_series=[combo_item("column"), combo_item("bar")],
    )
    # when: 리포트를 만든다
    async with clients(FakeUseCases(), {"alice": Role.SALES}) as c:
        response = await c["alice"].post(URL, json=create_body(definition=ONE_GROUP, chart=chart))

    body = problem(response, 422, "invalid-report")
    # then: 422 invalid-report이고 `["chart","combo_series",1]` 위반이다
    assert _locations(body) == [(["chart", "combo_series", 1], "chart-combo-invalid")]


async def test_all_secondary_combo_returns_422() -> None:
    """모든 계열이 보조 축이면 422다.

    테스트 코드: RC-028, RC-030
    """
    # given: 모든 계열이 보조 축인 콤보
    chart = chart_body(
        "combo",
        0,
        values=[1, 2],
        secondary_axis=True,
        combo_series=[combo_item("column", secondary=True), combo_item("line", secondary=True)],
    )
    # when: 리포트를 만든다
    async with clients(FakeUseCases(), {"alice": Role.SALES}) as c:
        response = await c["alice"].post(URL, json=create_body(definition=ONE_GROUP, chart=chart))

    body = problem(response, 422, "invalid-report")
    # then: 422 invalid-report이고 chart-combo-secondary-all이다
    assert _locations(body) == [(["chart", "combo_series"], "chart-combo-secondary-all")]


async def test_option_on_the_wrong_kind_returns_422() -> None:
    """종류가 쓰지 않는 옵션을 켜면 422다.

    테스트 코드: RC-025, RC-030
    """
    # given: 합계 막대를 켠 막대 차트
    chart = chart_body("bar", 0, values=[1], show_total=True)
    # when: 리포트를 만든다
    async with clients(FakeUseCases(), {"alice": Role.SALES}) as c:
        response = await c["alice"].post(URL, json=create_body(definition=ONE_GROUP, chart=chart))

    body = problem(response, 422, "invalid-report")
    # then: 422 invalid-report이고 `show_total` chart-option-invalid다
    assert _locations(body) == [(["chart", "show_total"], "chart-option-invalid")]


async def test_unknown_chart_key_still_returns_request_validation() -> None:
    """알 수 없는 차트 키는 request-validation이다.

    테스트 코드: RC-032
    """
    # given: 알 수 없는 키 bin_count가 붙은 차트
    chart = {**chart_body("bar", 0, values=[1]), "bin_count": 5}
    # when: 리포트를 만든다
    async with clients(FakeUseCases(), {"alice": Role.SALES}) as c:
        response = await c["alice"].post(URL, json=create_body(definition=ONE_GROUP, chart=chart))

    # then: 422 request-validation이다
    problem(response, 422, "request-validation")


async def test_stored_legacy_combo_chart_reads_with_the_filled_series_settings() -> None:
    """계열 설정 없이 저장한 콤보는 다시 읽어도 채워진 계열 설정이다.

    테스트 코드: RC-026
    """
    # when: 계열 설정 없는 콤보 리포트를 만들고 조회한다
    async with clients(FakeUseCases(), {"alice": Role.SALES}) as c:
        made = await create(
            c["alice"], definition=ONE_GROUP, chart=chart_body("combo", 0, values=[1, 2])
        )
        detail = await c["alice"].get(f"{URL}/{made['id']}")

    # then: 막대 + 꺾은선으로 채운 계열 설정이다
    assert detail.json()["chart"]["combo_series"] == [combo_item("column"), combo_item("line")]


UNKNOWN_ENUM_CHARTS: list[dict[str, Any]] = [
    {**chart_body("histogram", None, values=[1]), "histogram": bins(bin_mode="foo")},
    {
        **chart_body("combo", 0, values=[1, 2]),
        "combo_series": [combo_item("pie"), combo_item("line")],
    },
]


@pytest.mark.parametrize("stored", UNKNOWN_ENUM_CHARTS, ids=["bin-mode", "combo-type"])
async def test_get_opens_a_report_whose_stored_chart_has_an_unknown_enum_value(
    stored: dict[str, Any],
) -> None:
    """저장 차트에 모르는 구간 방식·계열 종류가 있으면 차트 없이 안내와 함께 열린다.

    테스트 코드: RC-039, RC-040
    """
    from app.domain.report.errors import ReportDefinitionError  # noqa: PLC0415
    from app.domain.report.stored_chart import chart_from_json  # noqa: PLC0415

    # given: 저장소가 읽는 방식 그대로 JSON을 읽은 결과(읽기 실패면 차트 없음·읽을 수 없음)
    # 저장소가 JSON을 읽는 방식 그대로: 읽기 실패면 (차트 없음, 읽기 불가)
    try:
        chart, unreadable = chart_from_json(stored), False
    except ReportDefinitionError:
        chart, unreadable = None, True
    use_cases = FakeUseCases()
    # when: 리포트를 조회한다
    async with clients(use_cases, {"alice": Role.SALES}) as c:
        report = make_report(
            owner=await use_cases.user_id_of("alice"),
            definition=chart_definition(1, 2),
            chart=chart,
            chart_unreadable=unreadable,
        )
        async with use_cases.uow as uow:
            await uow.saved_reports.add(report)
            await uow.commit()
        response = await c["alice"].get(f"{URL}/{int(report.id)}")

    # then: 200이고 chart는 null, chart_problem은 안내 문구다
    assert response.status_code == 200, response.text
    assert response.json()["chart"] is None
    assert response.json()["chart_problem"] == PROBLEM
