"""RandomDealCodeSuffixSource(AC-03): 영문 대문자·숫자 4자, 매번 무작위(고정 값이 아니다)."""

import re

from app.domain.deal.code import DEAL_CODE_ALPHABET, SUFFIX_LENGTH
from app.infra.deal_code_source import RandomDealCodeSuffixSource

SAMPLES = 400


def test_every_suffix_is_four_characters_from_the_alphabet() -> None:
    source = RandomDealCodeSuffixSource()

    for _ in range(SAMPLES):
        suffix = source.next_suffix()
        assert len(suffix) == SUFFIX_LENGTH
        assert set(suffix) <= set(DEAL_CODE_ALPHABET)
        assert re.fullmatch(r"[A-Z0-9]{4}", suffix)


def test_suffixes_vary_between_calls() -> None:
    source = RandomDealCodeSuffixSource()

    suffixes = {source.next_suffix() for _ in range(SAMPLES)}

    assert len(suffixes) > SAMPLES // 2  # 36^4 = 1,679,616 가지라 충돌은 드물다


def test_every_alphabet_character_shows_up_eventually() -> None:
    source = RandomDealCodeSuffixSource()

    seen = {char for _ in range(2000) for char in source.next_suffix()}

    assert seen == set(DEAL_CODE_ALPHABET)  # 한쪽으로 치우친 분포(예: 숫자만)를 잡는다


def test_two_sources_do_not_share_a_fixed_sequence() -> None:
    first = [RandomDealCodeSuffixSource().next_suffix() for _ in range(20)]
    second = [RandomDealCodeSuffixSource().next_suffix() for _ in range(20)]

    assert first != second
