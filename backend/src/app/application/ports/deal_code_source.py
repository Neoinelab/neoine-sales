from typing import Protocol


class DealCodeSuffixSource(Protocol):
    """Deal code 끝 4자리를 내는 Port. 무작위 구현은 infra, 테스트는 고정 열을 쓴다."""

    def next_suffix(self) -> str:
        """`DEAL_CODE_ALPHABET`(영문 대문자·숫자)에서 균등하게 뽑은 4자."""
        ...
