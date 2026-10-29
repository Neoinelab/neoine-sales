from dataclasses import dataclass


@dataclass(frozen=True, slots=True, repr=False)
class SealedSecret:
    """암호화된 비밀(불투명 토큰). repr/str에 토큰이 나오지 않는다."""

    token: str

    def __repr__(self) -> str:
        return "SealedSecret(***)"
