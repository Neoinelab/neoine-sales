"""PasswordHash: 대체 로그인용 해시의 인코딩 문자열 값 객체(AC13). 형식 해석은 infra가 한다."""

import dataclasses

import pytest
from app.domain.auth.password_hash import PASSWORD_HASH_MAX, PasswordHash

from app.domain.common.errors import InvalidValueError

ENCODED = "scrypt$ln=14,r=8,p=1$c2FsdHNhbHRzYWx0c2FsdA$aGFzaGhhc2hoYXNoaGFzaGhhc2hoYXNoaGFzaGhhc2g"


def test_valid_encoded_value_is_kept() -> None:
    assert PasswordHash(ENCODED).encoded == ENCODED


def test_hash_of_the_maximum_length_is_accepted() -> None:
    assert PASSWORD_HASH_MAX == 512
    assert len(PasswordHash("x" * 512).encoded) == 512


@pytest.mark.parametrize("value", ["", "a" * 513, "scrypt$a\x00b"])
def test_empty_nul_or_too_long_hash_is_rejected(value: str) -> None:
    with pytest.raises(InvalidValueError):
        PasswordHash(value)


def test_repr_hides_encoded_value() -> None:
    hashed = PasswordHash(ENCODED)

    assert ENCODED not in repr(hashed)
    assert ENCODED not in str(hashed)
    assert "PasswordHash(***)" in repr(hashed)


def test_password_hash_is_frozen_and_compares_by_value() -> None:
    hashed = PasswordHash(ENCODED)

    assert hashed == PasswordHash(ENCODED)
    with pytest.raises(dataclasses.FrozenInstanceError):
        hashed.encoded = "x"  # type: ignore[misc]
