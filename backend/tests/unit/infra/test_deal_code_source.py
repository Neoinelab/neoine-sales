"""RandomDealCodeSuffixSource: 영문 대문자·숫자 4자, 매번 무작위(고정 값이 아니다)."""

import re

from app.domain.deal.code import DEAL_CODE_ALPHABET, SUFFIX_LENGTH
from app.infra.deal_code_source import RandomDealCodeSuffixSource

SAMPLES = 400


def test_every_suffix_is_four_characters_from_the_alphabet() -> None:
    """무작위 끝 4자리는 항상 영문 대문자·숫자 4자다."""
    # when: 끝 4자리를 400번 뽑는다.
    source = RandomDealCodeSuffixSource()

    # then: 모두 길이 4이고 허용 문자만 쓴다.
    for _ in range(SAMPLES):
        suffix = source.next_suffix()
        assert len(suffix) == SUFFIX_LENGTH
        assert set(suffix) <= set(DEAL_CODE_ALPHABET)
        assert re.fullmatch(r"[A-Z0-9]{4}", suffix)


def test_suffixes_vary_between_calls() -> None:
    """끝 4자리는 매번 다른 값이 나온다."""
    # when: 400번 뽑는다.
    source = RandomDealCodeSuffixSource()

    suffixes = {source.next_suffix() for _ in range(SAMPLES)}

    # then: 서로 다른 값이 절반 넘게 나온다.
    assert len(suffixes) > SAMPLES // 2  # 36^4 = 1,679,616 가지라 충돌은 드물다


def test_every_alphabet_character_shows_up_eventually() -> None:
    """허용 문자가 모두 나온다(한쪽으로 치우친 분포가 아니다)."""
    # when: 2000번 뽑는다.
    source = RandomDealCodeSuffixSource()

    seen = {char for _ in range(2000) for char in source.next_suffix()}

    # then: 나온 문자 집합이 허용 문자 전체다.
    assert seen == set(DEAL_CODE_ALPHABET)  # 한쪽으로 치우친 분포(예: 숫자만)를 잡는다


def test_two_sources_do_not_share_a_fixed_sequence() -> None:
    """소스가 달라도 고정된 순서를 공유하지 않는다."""
    # when: 소스를 새로 만들어 20번씩 뽑는다.
    first = [RandomDealCodeSuffixSource().next_suffix() for _ in range(20)]
    second = [RandomDealCodeSuffixSource().next_suffix() for _ in range(20)]

    # then: 두 목록이 서로 다르다.
    assert first != second
