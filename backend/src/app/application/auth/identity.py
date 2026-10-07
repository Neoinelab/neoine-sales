from dataclasses import dataclass


@dataclass(frozen=True, slots=True)
class Identity:
    """IdP가 검증해 준 사용자 정보. 역할은 앱이 groups를 보고 정한다."""

    subject: str
    email: str | None
    name: str
    groups: frozenset[str]
