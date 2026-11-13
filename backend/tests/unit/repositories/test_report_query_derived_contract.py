"""ReportQueryRunner(SQL) 계약: 계산 필드가 Deals 목록과 같은 값을 낸다.

기대값은 Deal 저장소 `search`(목록)의 최종 업데이트·Next Action 기준 행과 도메인 함수
(`compute_risk`, `status_days`)로 계산하고, 리포트의 경고·체류 일수·최종 업데이트일과 비교한다.
오늘 2026-10-27, 경고 기준 14일이다.
"""

from datetime import timedelta
from typing import TYPE_CHECKING

from app.application.ports.deal_repository import DealQuery
from app.domain.deal.risk import RiskBasis, compute_risk, status_days
from tests.support.report_defs import TODAY, col, cond
from tests.unit.repositories.report_case import kst

if TYPE_CHECKING:
    from tests.unit.repositories.report_case import ReportCase

BASIS = RiskBasis(today=TODAY, stale_days=14)


async def _seed(case: ReportCase) -> None:
    overdue = await case.add_deal(name="overdue", created=kst(2026, 10, 20, 9))
    await case.deals.add_action(
        overdue, kst(2026, 10, 25), next_action="계획", due_date=TODAY - timedelta(days=7)
    )
    await case.add_deal(name="stale", created=kst(2026, 8, 1, 9))
    both = await case.add_deal(name="both", created=kst(2026, 8, 1, 9))
    await case.deals.add_action(
        both, kst(2026, 9, 1), next_action="계획", due_date=kst(2026, 9, 10).date()
    )
    closed = await case.add_deal(name="closed", forecast="lost", created=kst(2026, 8, 1, 9))
    await case.deals.add_action(
        closed, kst(2026, 9, 1), next_action="계획", due_date=kst(2026, 9, 10).date()
    )
    await case.add_deal(name="fresh", created=kst(2026, 10, 26, 9))
    done = await case.add_deal(name="done", created=kst(2026, 10, 20, 9))
    await case.deals.add_action(
        done, kst(2026, 10, 26), next_action="계획", due_date=TODAY - timedelta(days=1)
    )
    await case.deals.add_action(done, kst(2026, 10, 26, 13), action="진행만", next_action="")


async def _list_codes(case: ReportCase, **criteria: object) -> list[str]:
    query = DealQuery(risk_basis=BASIS, limit=200, **criteria)  # type: ignore[arg-type]
    return sorted(item.deal.id.value for item in await case.deals.deals.search(query))


_RISK_NAMES = {"overdue": "기한초과", "stale": "미업데이트", "overdue_stale": "기한초과·미업데이트"}


async def _report_codes(case: ReportCase, operator: str, value: object) -> list[str]:
    rows = await case.rows([col("deal.code")], [cond("deal.risk", operator, value)])
    return sorted(row[0] for row in rows)


async def test_risk_status_days_and_last_updated_match_the_deal_list(
    report_case: ReportCase,
) -> None:
    """경고·체류 일수·최종 업데이트일 값은 Deals 목록과 같다.

    테스트 코드: RQ-040
    """
    # given: 기한초과·미업데이트·둘 다·종료·정상 Deal 시드
    await _seed(report_case)

    # when: Deal code·경고·체류 일수·최종 업데이트로 조회한다
    rows = await report_case.rows(
        [
            col("deal.code"),
            col("deal.risk"),
            col("deal.status_days"),
            col("deal.last_updated_at"),
        ]
    )

    # then: Deal마다 목록 기준 계산값과 같고 네 가지 경고 표기가 모두 나온다
    listed = await report_case.deals.deals.search(DealQuery(risk_basis=BASIS, limit=200))
    expected = {}
    for item in listed:
        risk = compute_risk(
            forecast_key=item.deal.sync.forecast_key,
            due_date=item.next_action.due_date if item.next_action else None,
            last_updated_on=item.last_updated_on,
            today=TODAY,
            stale_days=14,
        )
        expected[item.deal.id.value] = (
            _RISK_NAMES[risk.value] if risk else None,
            status_days(item.deal.status_changed_on, TODAY),
            item.last_updated_on,
        )
    assert {row[0]: tuple(row[1:]) for row in rows} == expected
    assert {e[0] for e in expected.values()} == {
        "기한초과",
        "미업데이트",
        "기한초과·미업데이트",
        None,
    }


async def test_risk_in_overdue_equals_the_list_overdue_filter(report_case: ReportCase) -> None:
    """경고 기한초과 조건은 목록의 기한초과 필터와 같은 Deal을 고른다.

    테스트 코드: RQ-039
    """
    # given: 경고 시드
    await _seed(report_case)

    # when: 리포트의 기한초과 조건과 목록의 기한초과 필터로 조회한다
    report_codes = await _report_codes(report_case, "in", ["overdue"])
    list_codes = await _list_codes(report_case, overdue=True)
    # then: 두 결과가 같다
    assert report_codes == list_codes


async def test_risk_in_stale_equals_the_list_stale_filter(report_case: ReportCase) -> None:
    """경고 미업데이트 조건은 목록의 미업데이트 필터와 같은 Deal을 고른다.

    테스트 코드: RQ-039
    """
    # given: 경고 시드
    await _seed(report_case)

    # when: 리포트의 미업데이트 조건과 목록의 미업데이트 필터로 조회한다
    report_codes = await _report_codes(report_case, "in", ["stale"])
    list_codes = await _list_codes(report_case, stale=True)
    # then: 두 결과가 같다
    assert report_codes == list_codes


async def test_risk_in_overdue_and_stale_equals_the_list_with_both_filters(
    report_case: ReportCase,
) -> None:
    """두 경고를 함께 고르면 목록의 두 필터를 함께 건 결과와 같다.

    테스트 코드: RQ-039
    """
    # given: 경고 시드
    await _seed(report_case)

    # when: 리포트의 두 경고 조건과 목록의 두 필터로 조회한다
    report_codes = await _report_codes(report_case, "in", ["overdue", "stale"])
    list_codes = await _list_codes(report_case, overdue=True, stale=True)
    # then: 두 결과가 같다
    assert report_codes == list_codes


async def test_risk_not_in_and_is_empty_are_the_complements(report_case: ReportCase) -> None:
    """경고 not_in·is_empty는 경고가 아닌 Deal을 고른다.

    테스트 코드: RQ-039
    """
    # given: 경고 시드
    await _seed(report_case)
    everyone = await _list_codes(report_case)
    flagged = await _list_codes(report_case, overdue=True, stale=True)

    # when: 경고 not_in과 is_empty 조건으로 조회한다
    not_in = await _report_codes(report_case, "not_in", ["overdue", "stale"])
    empty = await _report_codes(report_case, "is_empty", None)

    # then: 둘 다 전체에서 경고 Deal을 뺀 것과 같고 비어 있지 않다
    assert not_in == sorted(set(everyone) - set(flagged))
    assert empty == sorted(set(everyone) - set(flagged))
    assert not_in  # closed(lost)와 fresh가 남는다


async def test_a_closed_deal_never_has_a_risk(report_case: ReportCase) -> None:
    """종료(Lost)된 Deal은 경고가 없다.

    테스트 코드: RQ-040
    """
    # given: 경고 시드(Lost Deal 포함)
    await _seed(report_case)

    # when: Lost Deal의 이름과 경고를 조회한다
    rows = await report_case.rows(
        [col("deal.name"), col("deal.risk")],
        [cond("deal.name", "equals", "closed")],
    )

    # then: 경고가 None이다
    assert rows == [("closed", None)]
