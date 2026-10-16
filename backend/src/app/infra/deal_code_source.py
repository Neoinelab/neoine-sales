import secrets

from app.domain.deal.code import DEAL_CODE_ALPHABET, SUFFIX_LENGTH


class RandomDealCodeSuffixSource:
    """DealCodeSuffixSource Port의 실제 구현: 영문 대문자·숫자에서 4자를 무작위로 뽑는다."""

    def next_suffix(self) -> str:
        return "".join(secrets.choice(DEAL_CODE_ALPHABET) for _ in range(SUFFIX_LENGTH))
