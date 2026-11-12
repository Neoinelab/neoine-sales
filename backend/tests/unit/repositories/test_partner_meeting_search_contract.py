"""PartnerMeetingRepository.search·count 조건 계약: Fake와 SQL 구현에 같은 기대값.

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
    """조건이 없으면 전부 찾고 센다."""
    # given: 두 건
    await _put(meeting_case, "하나")
    await _put(meeting_case, "둘")
    # when: 조건 없이 읽고 센다
    found = await meeting_case.contents()
    total = await meeting_case.total()
    # then: 둘 다 나오고 건수는 2다
    assert sorted(found) == ["둘", "하나"]
    assert total == 2


async def test_the_content_filter_is_a_case_insensitive_substring(
    meeting_case: MeetingCase,
) -> None:
    """내용 조건은 대소문자 무시 부분 일치다.

    테스트 코드: PA-022
    """
    # given: 내용이 다른 두 건
    await _put(meeting_case, "Quote 전달 완료", day=1)
    await _put(meeting_case, "계약 논의", day=2)
    # when: "QUOTE"와 "논"으로 읽는다
    upper = await meeting_case.contents(content="QUOTE")
    korean = await meeting_case.contents(content="논")
    # then: 각각 해당 기록만 나오고 건수도 같다
    assert upper == ["Quote 전달 완료"]
    assert korean == ["계약 논의"]
    assert await meeting_case.total(content="quote") == 1


async def test_the_partner_filter_matches_the_stored_company_text(
    meeting_case: MeetingCase,
) -> None:
    """파트너 조건은 저장된 회사명에 대한 대소문자 무시 부분 일치다.

    테스트 코드: PA-022
    """
    # given: 회사가 다른 두 건
    await _put(meeting_case, "한빛 기록", company="한빛파트너스", day=1)
    await _put(meeting_case, "Acme 기록", company="AcmeCorp", day=2)
    # when: "빛파트", "ACMEc", "없는"으로 읽는다
    korean = await meeting_case.contents(partner="빛파트")
    upper = await meeting_case.contents(partner="ACMEc")
    # then: 각각 해당 회사만 나오고 없는 글자는 0건이다
    assert korean == ["한빛 기록"]
    assert upper == ["Acme 기록"]
    assert await meeting_case.total(partner="없는") == 0


@pytest.mark.parametrize("special", ["%", "_", "\\"])
async def test_like_special_characters_in_the_content_filter_are_literal(
    meeting_case: MeetingCase, special: str
) -> None:
    """내용 조건의 %·_·\\ 는 글자 그대로 찾는다.

    테스트 코드: PA-023
    """
    # given: 특수 문자가 든 기록과 비슷하지만 다른 기록 둘
    await _put(meeting_case, f"할인 10{special}", day=1)
    await _put(meeting_case, "할인 100", day=2)
    await _put(meeting_case, "할인 10X", day=3)
    # when: 그 특수 문자를 포함한 조건으로 읽는다
    found = await meeting_case.contents(content=f"10{special}")
    # then: 그 글자가 든 기록 하나만 나온다
    assert found == [f"할인 10{special}"]
    assert await meeting_case.total(content=f"10{special}") == 1


@pytest.mark.parametrize("special", ["%", "_"])
async def test_like_special_characters_in_the_partner_filter_are_literal(
    meeting_case: MeetingCase, special: str
) -> None:
    """파트너 조건의 %·_ 도 글자 그대로 찾는다.

    테스트 코드: PA-023
    """
    # given: 특수 문자가 든 회사와 비슷한 회사
    await _put(meeting_case, "특수 문자 회사", company=f"A{special}B", day=1)
    await _put(meeting_case, "일반 회사", company="AxxB", day=2)
    # when: 특수 문자가 든 회사명으로 읽는다
    found = await meeting_case.contents(partner=f"A{special}B")
    # then: 그 회사 기록만 나온다
    assert found == ["특수 문자 회사"]


async def test_the_date_range_is_inclusive_on_both_ends(meeting_case: MeetingCase) -> None:
    """날짜 범위는 양끝을 포함하고 한쪽만 줘도 된다.

    테스트 코드: PA-024
    """
    # given: 10/1~10/5 다섯 건
    for day in (1, 2, 3, 4, 5):
        await _put(meeting_case, f"d{day}", day=day)
    # when: 양끝, 시작만, 끝만, 하루로 읽는다
    both = await meeting_case.contents(date_from=date(2026, 10, 2), date_to=date(2026, 10, 4))
    only_from = await meeting_case.contents(date_from=date(2026, 10, 4))
    only_to = await meeting_case.contents(date_to=date(2026, 10, 2))
    one_day = await meeting_case.contents(date_from=date(2026, 10, 3), date_to=date(2026, 10, 3))
    # then: 양끝이 포함되고 건수도 조건을 따른다
    assert both == ["d4", "d3", "d2"]
    assert only_from == ["d5", "d4"]
    assert only_to == ["d2", "d1"]
    assert one_day == ["d3"]
    assert await meeting_case.total(date_from=date(2026, 10, 2), date_to=date(2026, 10, 4)) == 3


async def test_the_author_filter_matches_exactly_one_user(meeting_case: MeetingCase) -> None:
    """작성자 조건은 그 사용자의 기록만 찾는다.

    테스트 코드: PA-025
    """
    # given: 두 작성자의 기록
    kim = await meeting_case.author(uid("search-kim"))
    park = await meeting_case.author(uid("search-park"))
    await _put(meeting_case, "김 기록", day=1, author=kim)
    await _put(meeting_case, "박 기록", day=2, author=park)
    # when: 김으로 읽고 박으로 센다
    found = await meeting_case.contents(author_user_id=kim)
    park_total = await meeting_case.total(author_user_id=park)
    # then: 김의 기록만 나오고 박은 1건이다
    assert found == ["김 기록"]
    assert park_total == 1


async def test_the_author_filter_includes_a_resigned_author(meeting_case: MeetingCase) -> None:
    """작성자 조건은 퇴사한 작성자의 기록도 찾는다.

    테스트 코드: PA-025
    """
    # given: 퇴사 처리된 작성자의 기록
    gone = await meeting_case.author(uid("search-gone"))
    await _put(meeting_case, "퇴사자 기록", author=gone)
    await meeting_case.resign(gone)
    # when: 그 작성자로 읽는다
    found = await meeting_case.contents(author_user_id=gone)
    # then: 기록이 나온다
    assert found == ["퇴사자 기록"]


async def test_filters_are_anded(meeting_case: MeetingCase) -> None:
    """여러 조건은 AND로 합쳐지고 건수도 같은 조건을 따른다.

    테스트 코드: PA-026
    """
    # given: 내용·회사·작성자·날짜가 조금씩 다른 네 건
    kim = await meeting_case.author(uid("and-kim"))
    park = await meeting_case.author(uid("and-park"))
    await _put(meeting_case, "견적 김 한빛", day=1, author=kim)
    await _put(meeting_case, "견적 박 한빛", day=2, author=park)
    await _put(meeting_case, "견적 김 Acme", day=3, author=kim, company="AcmeCorp")
    await _put(meeting_case, "계약 김 한빛", day=4, author=kim)
    # when: 내용·파트너·작성자·시작 날짜를 모두 줘서 읽는다
    found = await meeting_case.contents(
        content="견적", partner="한빛", author_user_id=kim, date_from=date(2026, 10, 1)
    )
    # then: 모든 조건에 맞는 한 건만 나오고 건수도 1이다
    assert found == ["견적 김 한빛"]
    assert await meeting_case.total(content="견적", partner="한빛", author_user_id=kim) == 1


async def test_offset_and_limit_cut_the_page_but_count_ignores_them(
    meeting_case: MeetingCase,
) -> None:
    """offset·limit은 쪽만 자르고 건수는 영향받지 않는다.

    테스트 코드: PA-014, PA-026
    """
    # given: 날짜가 다른 일곱 건
    for day in range(1, 8):
        await _put(meeting_case, f"d{day}", day=day)
    # when: 쪽을 나눠 읽는다
    first = await meeting_case.contents(limit=3)
    second = await meeting_case.contents(offset=3, limit=3)
    last = await meeting_case.contents(offset=6, limit=3)
    beyond = await meeting_case.contents(offset=7, limit=3)
    # then: 쪽이 겹침 없이 이어지고 끝 너머는 비며 건수는 7이다
    assert first == ["d7", "d6", "d5"]
    assert second == ["d4", "d3", "d2"]
    assert last == ["d1"]
    assert beyond == []
    assert await meeting_case.total(offset=6, limit=3) == 7


async def test_an_empty_store_has_no_results_and_a_zero_count(meeting_case: MeetingCase) -> None:
    """기록이 없으면 결과가 없고 건수는 0이다.

    테스트 코드: PA-020
    """
    # when: 비어 있는 저장소를 읽고 센다
    found = await meeting_case.contents()
    total = await meeting_case.total()
    # then: 빈 목록과 0이다
    assert found == []
    assert total == 0
