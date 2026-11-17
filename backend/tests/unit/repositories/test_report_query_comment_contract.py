"""ReportQueryRunner(SQL) 계약: Comment 필드 `action.comment`·`deal.comment`.

둘 다 `deal_comments` 본문을 작성 순(created_at, id)으로 줄바꿈("\\n")으로 이은 값이고 없으면
null이다. action.comment는 그 Action에 연결된 Comment만, deal.comment는 그 Deal 소속 Comment 전부
(Action 연결 여부 무관)다. deal.comment는 Deal 필드라 Deal당 한 번 규칙을 따른다.
"""

from typing import TYPE_CHECKING

from tests.support.report_defs import col, cond
from tests.unit.repositories.report_case import kst

if TYPE_CHECKING:
    from tests.unit.repositories.report_case import ReportCase


async def test_action_comment_joins_the_comments_of_that_action_in_writing_order(
    report_case: ReportCase,
) -> None:
    """action.comment는 그 Action의 Comment를 작성 순 줄바꿈으로 이어 붙이고 없으면 비어 있다.

    테스트 코드: RQ-118
    """
    # given: Action A에 Comment "첫째"·"둘째"(작성 순), Action B는 Comment 없음, Deal Comment 하나
    deal = await report_case.add_deal(name="D")
    action_a = await report_case.deals.add_action(deal, kst(2026, 10, 5, 9), action="a")
    await report_case.deals.add_action(deal, kst(2026, 10, 5, 10), action="b")
    await report_case.deals.add_comment(deal.id, "둘째", kst(2026, 10, 6, 10), action=action_a)
    await report_case.deals.add_comment(deal.id, "첫째", kst(2026, 10, 6, 9), action=action_a)
    await report_case.deals.add_comment(deal.id, "딜 글", kst(2026, 10, 6, 8))

    # when: 진행사항과 action.comment로 조회한다
    rows = await report_case.rows([col("action.action"), col("action.comment")])

    # then: A의 값은 "첫째\n둘째"(작성 순, Deal Comment는 섞이지 않는다)이고 B는 null이다
    assert dict(rows) == {"a": "첫째\n둘째", "b": None}


async def test_action_comment_is_empty_condition_picks_only_actions_without_comments(
    report_case: ReportCase,
) -> None:
    """action.comment 비어 있음 조건은 Comment가 없는 Action이 있는 Deal만 고른다.

    테스트 코드: RQ-118
    """
    # given: Comment가 있는 Action만 가진 Deal X와 Comment 없는 Action을 가진 Deal Y
    with_comment = await report_case.add_deal(name="X")
    action = await report_case.deals.add_action(with_comment, kst(2026, 10, 5, 9))
    await report_case.deals.add_comment(with_comment.id, "내용", kst(2026, 10, 6), action=action)
    without = await report_case.add_deal(name="Y")
    await report_case.deals.add_action(without, kst(2026, 10, 5, 10))

    # when: Deal 이름과 비어 있음 조건으로 조회한다
    empty = await report_case.rows([col("deal.name")], [cond("action.comment", "is_empty")])
    filled = await report_case.rows([col("deal.name")], [cond("action.comment", "is_not_empty")])

    # then: 비어 있음은 Y만, 비어 있지 않음은 X만 고른다
    assert empty == [("Y",)]
    assert filled == [("X",)]


async def test_deal_comment_joins_every_comment_of_the_deal_and_not_other_deals(
    report_case: ReportCase,
) -> None:
    """deal.comment는 Action 연결 여부와 무관하게 그 Deal의 모든 Comment를 작성 순으로 잇고
    다른 Deal 것은 섞이지 않으며 Comment 없는 Deal은 null이다.

    테스트 코드: RQ-121
    """
    # given: Deal D에 Deal Comment "예산"과 Action Comment "견적", 다른 Deal E에 "남", Deal F는 없음
    deal = await report_case.add_deal(name="D")
    other = await report_case.add_deal(name="E")
    await report_case.add_deal(name="F")
    action = await report_case.deals.add_action(deal, kst(2026, 10, 5, 9))
    await report_case.deals.add_comment(deal.id, "견적", kst(2026, 10, 6, 10), action=action)
    await report_case.deals.add_comment(deal.id, "예산", kst(2026, 10, 6, 9))
    await report_case.deals.add_comment(other.id, "남", kst(2026, 10, 6, 11))

    # when: Deal 이름과 deal.comment로 조회한다
    rows = await report_case.rows([col("deal.name"), col("deal.comment")])

    # then: D는 "예산\n견적"(작성 순), E는 "남", F는 null이다
    assert dict(rows) == {"D": "예산\n견적", "E": "남", "F": None}


async def test_a_report_with_only_deal_comment_returns_one_row_per_deal(
    report_case: ReportCase,
) -> None:
    """deal.comment만 쓴 리포트는 Action이 여러 건이어도 Deal당 1행이다(Deal 범위).

    테스트 코드: RQ-122
    """
    # given: Action 3건과 Comment가 있는 Deal 하나
    deal = await report_case.add_deal(name="D")
    for hour in (9, 10, 11):
        await report_case.deals.add_action(deal, kst(2026, 10, 5, hour))
    await report_case.deals.add_comment(deal.id, "예산", kst(2026, 10, 6))

    # when: deal.comment만으로 조회한다
    result = await report_case.run([col("deal.comment")])

    # then: Deal당 1행이다
    assert [tuple(row) for row in result.rows] == [("예산",)]
    assert result.total_count == 1


async def test_deal_comment_count_counts_each_deal_once_in_action_row_groups(
    report_case: ReportCase,
) -> None:
    """Action 행 범위 그룹핑에서 deal.comment 건수는 Action 행 수가 아니라 Comment가 있는 Deal 수다.

    테스트 코드: RQ-123
    """
    # given: 같은 유형 Action 3건과 Comment 2건이 있는 Deal, Comment 없는 Deal
    deal = await report_case.add_deal(name="D")
    for hour in (9, 10, 11):
        await report_case.deals.add_action(deal, kst(2026, 10, 5, hour), action_type="미팅")
    await report_case.deals.add_comment(deal.id, "예산", kst(2026, 10, 6, 9))
    await report_case.deals.add_comment(deal.id, "일정", kst(2026, 10, 6, 10))
    plain = await report_case.add_deal(name="P")
    await report_case.deals.add_action(plain, kst(2026, 10, 5, 12), action_type="미팅")

    # when: Action 유형 그룹과 deal.comment 건수, Action 건수로 조회한다
    rows = await report_case.rows(
        [
            col("action.type", group=True),
            col("deal.comment", aggregate="count"),
            col("action.count"),
        ]
    )

    # then: 미팅 그룹의 deal.comment 건수는 1(Comment가 있는 Deal 하나)이고 Action 건수는 4다
    assert rows == [("미팅", 1, 4)]


async def test_deal_comment_contains_matches_a_deal_comment_or_an_action_comment(
    report_case: ReportCase,
) -> None:
    """deal.comment contains 조건은 Deal·Action Comment 어느 쪽 본문에 있어도 그 Deal을 고른다.

    테스트 코드: RQ-124
    """
    # given: X는 Deal Comment에만, Y는 Action Comment에만 "예산"이 있고 Z는 없다
    first = await report_case.add_deal(name="X")
    second = await report_case.add_deal(name="Y")
    third = await report_case.add_deal(name="Z")
    await report_case.deals.add_comment(first.id, "예산 회의", kst(2026, 10, 6, 9))
    action = await report_case.deals.add_action(second, kst(2026, 10, 5, 9))
    await report_case.deals.add_comment(
        second.id, "추가 예산 논의", kst(2026, 10, 6, 10), action=action
    )
    await report_case.deals.add_comment(third.id, "일정", kst(2026, 10, 6, 11))

    # when: deal.comment contains "예산"으로 조회한다
    rows = await report_case.rows([col("deal.name")], [cond("deal.comment", "contains", "예산")])

    # then: X와 Y가 나오고 Z는 나오지 않는다
    assert sorted(rows) == [("X",), ("Y",)]
