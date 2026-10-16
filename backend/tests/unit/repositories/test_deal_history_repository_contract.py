"""DealHistoryRepository 계약(R2, AC-06·25): 순서대로 저장, 최신순 조회, 구분 필터, Deal별 분리.

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
    first, _ = await _deals(deal_case)

    assert list(await deal_case.history.list(first)) == []


async def test_saved_entries_get_increasing_ids_in_the_given_order(deal_case: DealCase) -> None:
    first, _ = await _deals(deal_case)

    await deal_case.history.add_many([_entry(first, 1), _entry(first, 2), _entry(first, 3)])

    ids = [e.id for e in reversed(list(await deal_case.history.list(first)))]
    assert all(isinstance(i, int) for i in ids)
    assert ids == sorted(ids)
    assert len(set(ids)) == 3


async def test_every_field_round_trips(deal_case: DealCase) -> None:
    first, _ = await _deals(deal_case)
    entry = _entry(
        first,
        7,
        category="expectedClose",
        target="Expected Close",
        before="2026-12-01",
        after="2026-10-20",
    )

    await deal_case.history.add_many([entry])

    (stored,) = await deal_case.history.list(first)
    assert stored.id is not None
    assert (stored.deal_code, stored.changed_at, stored.changed_by) == (first, later(7), OWNER_ID)
    assert stored.draft == entry.draft


async def test_an_empty_before_text_is_kept_as_empty(deal_case: DealCase) -> None:
    first, _ = await _deals(deal_case)
    created = HistoryDraft(HistoryCategory("created"), "Deal 등록", "", "Deal 등록")

    await deal_case.history.add_many([DealHistoryEntry(None, first, NOW, OWNER_ID, created)])

    (stored,) = await deal_case.history.list(first)
    assert (stored.draft.before, stored.draft.after) == ("", "Deal 등록")


async def test_entries_are_listed_newest_first(deal_case: DealCase) -> None:
    first, _ = await _deals(deal_case)
    await deal_case.history.add_many(
        [_entry(first, 2, after="둘째"), _entry(first, 1, after="첫째")]
    )
    await deal_case.history.add_many([_entry(first, 3, after="셋째")])

    entries = await deal_case.history.list(first)

    assert [e.draft.after for e in entries] == ["셋째", "둘째", "첫째"]


async def test_entries_of_the_same_moment_show_the_later_saved_one_first(
    deal_case: DealCase,
) -> None:
    first, _ = await _deals(deal_case)
    await deal_case.history.add_many(
        [_entry(first, 5, after="먼저 저장"), _entry(first, 5, after="나중 저장")]
    )

    entries = await deal_case.history.list(first)

    assert [e.draft.after for e in entries] == ["나중 저장", "먼저 저장"]


async def test_the_category_filter_keeps_only_that_category(deal_case: DealCase) -> None:
    first, _ = await _deals(deal_case)
    await deal_case.history.add_many(
        [
            _entry(first, 1, category="created", target="Deal 등록"),
            _entry(first, 2, category="status", target="Status"),
            _entry(first, 3, category="other"),
            _entry(first, 4, category="status", target="Status"),
        ]
    )

    status = await deal_case.history.list(first, category=HistoryCategory("status"))
    partner = await deal_case.history.list(first, category=HistoryCategory("partner"))

    assert [e.changed_at for e in status] == [later(4), later(2)]
    assert list(partner) == []


async def test_entries_are_kept_per_deal(deal_case: DealCase) -> None:
    first, second = await _deals(deal_case)
    await deal_case.history.add_many(
        [_entry(first, 1, after="첫째 딜"), _entry(second, 2, after="둘째 딜")]
    )

    assert [e.draft.after for e in await deal_case.history.list(first)] == ["첫째 딜"]
    assert [e.draft.after for e in await deal_case.history.list(second)] == ["둘째 딜"]


async def test_adding_nothing_is_allowed(deal_case: DealCase) -> None:
    first, _ = await _deals(deal_case)

    await deal_case.history.add_many([])

    assert list(await deal_case.history.list(first)) == []


async def test_a_resigned_author_keeps_the_entry(deal_case: DealCase) -> None:
    first, _ = await _deals(deal_case)
    await deal_case.ensure_owner(uid("leaver"))
    entry = DealHistoryEntry(
        None, first, NOW, uid("leaver"), HistoryDraft(HistoryCategory("other"), "x", "a", "b")
    )
    await deal_case.history.add_many([entry])

    await deal_case.resign(uid("leaver"), NOW + timedelta(days=1))

    (stored,) = await deal_case.history.list(first)
    assert stored.changed_by == uid("leaver")
