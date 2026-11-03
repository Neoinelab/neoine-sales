"""PartnerMeetingRepository.search·count 조건 계약(AC4): Fake와 SQL 구현에 같은 기대값.

조건은 AND, 텍스트는 대소문자 무시 부분 일치이고 `%`·`_`·`\\`는 글자 그대로다.
"""

from datetime import date
from typing import TYPE_CHECKING

import pytest

from tests.factories_partner_meeting import make_meeting
from tests.support.user_ids import uid

if TYPE_CHECKING:
    from tests.unit.repositories.partner_meeting_case import MeetingCase


async def _put(
    case: MeetingCase,
    content: str,
    *,
    company: str = "한빛파트너스",
    day: int = 1,
    author: object = None,
) -> None:
    kwargs = {} if author is None else {"author": author}
    await case.add(
        make_meeting(
            company=company,
            content=content,
            meeting_date=date(2026, 10, day),
            **kwargs,  # type: ignore[arg-type]
        )
    )


async def test_without_conditions_everything_is_found_and_counted(
    meeting_case: MeetingCase,
) -> None:
    await _put(meeting_case, "하나")
    await _put(meeting_case, "둘")

    assert sorted(await meeting_case.contents()) == ["둘", "하나"]
    assert await meeting_case.total() == 2


async def test_the_content_filter_is_a_case_insensitive_substring(
    meeting_case: MeetingCase,
) -> None:
    await _put(meeting_case, "Quote 전달 완료", day=1)
    await _put(meeting_case, "계약 논의", day=2)

    assert await meeting_case.contents(content="QUOTE") == ["Quote 전달 완료"]
    assert await meeting_case.contents(content="논") == ["계약 논의"]
    assert await meeting_case.total(content="quote") == 1


async def test_the_partner_filter_matches_the_stored_company_text(
    meeting_case: MeetingCase,
) -> None:
    await _put(meeting_case, "한빛 기록", company="한빛파트너스", day=1)
    await _put(meeting_case, "Acme 기록", company="AcmeCorp", day=2)

    assert await meeting_case.contents(partner="빛파트") == ["한빛 기록"]
    assert await meeting_case.contents(partner="ACMEc") == ["Acme 기록"]
    assert await meeting_case.total(partner="없는") == 0


@pytest.mark.parametrize("special", ["%", "_", "\\"])
async def test_like_special_characters_in_the_content_filter_are_literal(
    meeting_case: MeetingCase, special: str
) -> None:
    await _put(meeting_case, f"할인 10{special}", day=1)
    await _put(meeting_case, "할인 100", day=2)
    await _put(meeting_case, "할인 10X", day=3)

    found = await meeting_case.contents(content=f"10{special}")

    assert found == [f"할인 10{special}"]
    assert await meeting_case.total(content=f"10{special}") == 1


@pytest.mark.parametrize("special", ["%", "_"])
async def test_like_special_characters_in_the_partner_filter_are_literal(
    meeting_case: MeetingCase, special: str
) -> None:
    await _put(meeting_case, "특수 문자 회사", company=f"A{special}B", day=1)
    await _put(meeting_case, "일반 회사", company="AxxB", day=2)

    assert await meeting_case.contents(partner=f"A{special}B") == ["특수 문자 회사"]


async def test_the_date_range_is_inclusive_on_both_ends(meeting_case: MeetingCase) -> None:
    for day in (1, 2, 3, 4, 5):
        await _put(meeting_case, f"d{day}", day=day)

    both = await meeting_case.contents(date_from=date(2026, 10, 2), date_to=date(2026, 10, 4))
    only_from = await meeting_case.contents(date_from=date(2026, 10, 4))
    only_to = await meeting_case.contents(date_to=date(2026, 10, 2))
    one_day = await meeting_case.contents(date_from=date(2026, 10, 3), date_to=date(2026, 10, 3))

    assert both == ["d4", "d3", "d2"]
    assert only_from == ["d5", "d4"]
    assert only_to == ["d2", "d1"]
    assert one_day == ["d3"]
    assert await meeting_case.total(date_from=date(2026, 10, 2), date_to=date(2026, 10, 4)) == 3


async def test_the_author_filter_matches_exactly_one_user(meeting_case: MeetingCase) -> None:
    kim = await meeting_case.author(uid("search-kim"))
    park = await meeting_case.author(uid("search-park"))
    await _put(meeting_case, "김 기록", day=1, author=kim)
    await _put(meeting_case, "박 기록", day=2, author=park)

    assert await meeting_case.contents(author_user_id=kim) == ["김 기록"]
    assert await meeting_case.total(author_user_id=park) == 1


async def test_the_author_filter_includes_a_resigned_author(meeting_case: MeetingCase) -> None:
    gone = await meeting_case.author(uid("search-gone"))
    await _put(meeting_case, "퇴사자 기록", author=gone)
    await meeting_case.resign(gone)

    assert await meeting_case.contents(author_user_id=gone) == ["퇴사자 기록"]


async def test_filters_are_anded(meeting_case: MeetingCase) -> None:
    kim = await meeting_case.author(uid("and-kim"))
    park = await meeting_case.author(uid("and-park"))
    await _put(meeting_case, "견적 김 한빛", day=1, author=kim)
    await _put(meeting_case, "견적 박 한빛", day=2, author=park)
    await _put(meeting_case, "견적 김 Acme", day=3, author=kim, company="AcmeCorp")
    await _put(meeting_case, "계약 김 한빛", day=4, author=kim)

    found = await meeting_case.contents(
        content="견적", partner="한빛", author_user_id=kim, date_from=date(2026, 10, 1)
    )

    assert found == ["견적 김 한빛"]
    assert await meeting_case.total(content="견적", partner="한빛", author_user_id=kim) == 1


async def test_offset_and_limit_cut_the_page_but_count_ignores_them(
    meeting_case: MeetingCase,
) -> None:
    for day in range(1, 8):
        await _put(meeting_case, f"d{day}", day=day)

    first = await meeting_case.contents(limit=3)
    second = await meeting_case.contents(offset=3, limit=3)
    last = await meeting_case.contents(offset=6, limit=3)
    beyond = await meeting_case.contents(offset=7, limit=3)

    assert first == ["d7", "d6", "d5"]
    assert second == ["d4", "d3", "d2"]
    assert last == ["d1"]
    assert beyond == []
    assert await meeting_case.total(offset=6, limit=3) == 7


async def test_an_empty_store_has_no_results_and_a_zero_count(meeting_case: MeetingCase) -> None:
    assert await meeting_case.contents() == []
    assert await meeting_case.total() == 0
