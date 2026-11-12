"""DealHistoryRepository 계약(R2): 순서대로 저장, 최신순 조회, 구분 필터, Deal별 분리.

Fake와 SQL(PostgreSQL)에 같은 기대값을 적용한다. id는 저장 순서대로 늘어난다(DB가 부여한다).
"""

from datetime import timedelta
from typing import TYPE_CHECKING

from app.domain.deal.history import DealHistoryEntry, HistoryCategory, HistoryDraft
from tests.factories import NOW, later, make_deal
from tests.support.user_ids import OWNER_ID, uid

if TYPE_CHECKING:
    from app.domain.deal.code import DealCode
    from tests.unit.repositories.deal_case import DealCase

FIRST = "20261016-A001"
SECOND = "20261016-A002"


def _entry(
    code: DealCode, at: int, *, category: str = "other", target: str = "Deal Name", **texts: str
) -> DealHistoryEntry:
    draft = HistoryDraft(
        HistoryCategory(category), target, texts.get("before", "A"), texts.get("after", "B")
    )
    return DealHistoryEntry(None, code, later(at), OWNER_ID, draft)


async def _deals(case: DealCase) -> tuple[DealCode, DealCode]:
    first, second = make_deal(code=FIRST), make_deal(code=SECOND)
    await case.add(first)
    await case.add(second)
    return first.id, second.id


async def test_a_new_deal_has_no_history(deal_case: DealCase) -> None:
    """이력을 쓰지 않은 Deal의 이력은 비어 있다."""
    # given: Deal 두 건
    first, _ = await _deals(deal_case)

    # when: 첫 Deal의 이력을 읽는다
    actual = list(await deal_case.history.list(first))
    # then: 빈 목록이다
    assert actual == []


async def test_saved_entries_get_increasing_ids_in_the_given_order(deal_case: DealCase) -> None:
    """저장한 이력은 준 순서대로 증가하는 id를 받는다."""
    # given: Deal 두 건
    first, _ = await _deals(deal_case)

    # when: 이력 세 건을 한 번에 저장한다
    await deal_case.history.add_many([_entry(first, 1), _entry(first, 2), _entry(first, 3)])

    # then: id가 정수이고 오름차순이며 서로 다르다
    ids = [e.id for e in reversed(list(await deal_case.history.list(first)))]
    assert all(isinstance(i, int) for i in ids)
    assert ids == sorted(ids)
    assert len(set(ids)) == 3


async def test_every_field_round_trips(deal_case: DealCase) -> None:
    """이력의 모든 필드가 저장 뒤 그대로 읽힌다."""
    # given: Expected Close 이력 한 건
    first, _ = await _deals(deal_case)
    entry = _entry(
        first,
        7,
        category="expectedClose",
        target="Expected Close",
        before="2026-12-01",
        after="2026-10-20",
    )

    # when: 저장하고 읽는다
    await deal_case.history.add_many([entry])

    # then: Deal code, 시각, 변경자, 구분·대상·전·후가 같다
    (stored,) = await deal_case.history.list(first)
    assert stored.id is not None
    assert (stored.deal_code, stored.changed_at, stored.changed_by) == (first, later(7), OWNER_ID)
    assert stored.draft == entry.draft


async def test_an_empty_before_text_is_kept_as_empty(deal_case: DealCase) -> None:
    """변경 전이 빈 문자열인 이력은 빈 문자열로 남는다."""
    # given: 등록 이력(변경 전 비어 있음)
    first, _ = await _deals(deal_case)
    created = HistoryDraft(HistoryCategory("created"), "Deal 등록", "", "Deal 등록")

    # when: 저장하고 읽는다
    await deal_case.history.add_many([DealHistoryEntry(None, first, NOW, OWNER_ID, created)])

    # then: 변경 전은 ''이고 변경 후는 'Deal 등록'이다
    (stored,) = await deal_case.history.list(first)
    assert (stored.draft.before, stored.draft.after) == ("", "Deal 등록")


async def test_entries_are_listed_newest_first(deal_case: DealCase) -> None:
    """이력은 변경 시각 최신순으로 읽힌다.

    테스트 코드: DD-035
    """
    # given: 시각이 다른 이력을 섞인 순서로 두 번에 나눠 저장했다
    first, _ = await _deals(deal_case)
    await deal_case.history.add_many(
        [_entry(first, 2, after="둘째"), _entry(first, 1, after="첫째")]
    )
    await deal_case.history.add_many([_entry(first, 3, after="셋째")])

    # when: 이력을 읽는다
    entries = await deal_case.history.list(first)

    # then: 셋째, 둘째, 첫째 순서다
    assert [e.draft.after for e in entries] == ["셋째", "둘째", "첫째"]


async def test_entries_of_the_same_moment_show_the_later_saved_one_first(
    deal_case: DealCase,
) -> None:
    """같은 시각의 이력은 나중에 저장한 것이 위에 나온다.

    테스트 코드: DD-035
    """
    # given: 같은 시각의 이력 두 건을 차례로 저장했다
    first, _ = await _deals(deal_case)
    await deal_case.history.add_many(
        [_entry(first, 5, after="먼저 저장"), _entry(first, 5, after="나중 저장")]
    )

    # when: 이력을 읽는다
    entries = await deal_case.history.list(first)

    # then: 나중 저장이 먼저 나온다
    assert [e.draft.after for e in entries] == ["나중 저장", "먼저 저장"]


async def test_the_category_filter_keeps_only_that_category(deal_case: DealCase) -> None:
    """구분으로 거르면 그 구분의 이력만 최신순으로 읽힌다.

    테스트 코드: DD-036
    """
    # given: created·status·other·status 이력 네 건
    first, _ = await _deals(deal_case)
    await deal_case.history.add_many(
        [
            _entry(first, 1, category="created", target="Deal 등록"),
            _entry(first, 2, category="status", target="Status"),
            _entry(first, 3, category="other"),
            _entry(first, 4, category="status", target="Status"),
        ]
    )

    # when: status와 partner 구분으로 읽는다
    status = await deal_case.history.list(first, category=HistoryCategory("status"))
    # then: status는 최신순 두 건, partner는 빈 목록이다
    partner = await deal_case.history.list(first, category=HistoryCategory("partner"))

    assert [e.changed_at for e in status] == [later(4), later(2)]
    assert list(partner) == []


async def test_entries_are_kept_per_deal(deal_case: DealCase) -> None:
    """이력은 Deal마다 따로 읽힌다."""
    # given: 두 Deal에 이력을 하나씩 저장했다
    first, second = await _deals(deal_case)
    await deal_case.history.add_many(
        [_entry(first, 1, after="첫째 딜"), _entry(second, 2, after="둘째 딜")]
    )

    # when: 각 Deal의 이력을 읽는다
    assert [e.draft.after for e in await deal_case.history.list(first)] == ["첫째 딜"]
    # then: 각각 자기 이력만 나온다
    assert [e.draft.after for e in await deal_case.history.list(second)] == ["둘째 딜"]


async def test_adding_nothing_is_allowed(deal_case: DealCase) -> None:
    """빈 목록을 저장해도 오류 없이 이력이 그대로다."""
    # given: Deal 두 건
    first, _ = await _deals(deal_case)

    # when: 빈 이력을 저장한다
    await deal_case.history.add_many([])

    # then: 이력은 비어 있다
    assert list(await deal_case.history.list(first)) == []


async def test_a_resigned_author_keeps_the_entry(deal_case: DealCase) -> None:
    """변경자가 퇴사해도 이력은 그대로 남고 변경자 id도 같다.

    테스트 코드: DD-037
    """
    # given: 사용자 leaver가 남긴 이력
    first, _ = await _deals(deal_case)
    await deal_case.ensure_owner(uid("leaver"))
    entry = DealHistoryEntry(
        None, first, NOW, uid("leaver"), HistoryDraft(HistoryCategory("other"), "x", "a", "b")
    )
    await deal_case.history.add_many([entry])

    # when: leaver를 퇴사 처리한다
    await deal_case.resign(uid("leaver"), NOW + timedelta(days=1))

    # then: 이력이 남고 변경자 id가 leaver다
    (stored,) = await deal_case.history.list(first)
    assert stored.changed_by == uid("leaver")
