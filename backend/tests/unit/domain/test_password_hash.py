"""PasswordHash: 대체 로그인용 해시의 인코딩 문자열 값 객체. 형식 해석은 infra가 한다."""

import dataclasses

import pytest

from app.domain.auth.password_hash import PASSWORD_HASH_MAX, PasswordHash
from app.domain.common.errors import InvalidValueError

ENCODED = "scrypt$ln=14,r=8,p=1$c2FsdHNhbHRzYWx0c2FsdA$aGFzaGhhc2hoYXNoaGFzaGhhc2hoYXNoaGFzaGhhc2g"


def test_valid_encoded_value_is_kept() -> None:
    """올바른 인코딩 문자열은 그대로 보관한다."""
    # when: 해시 값 객체를 만든다
    hashed = PasswordHash(ENCODED)

    # then: 인코딩 문자열이 그대로다
    assert hashed.encoded == ENCODED


def test_hash_of_the_maximum_length_is_accepted() -> None:
    """512자 해시는 허용한다."""
    # when: 최대 길이 해시를 만든다
    hashed = PasswordHash("x" * 512)

    # then: 상한은 512이고 길이가 보존된다
    assert PASSWORD_HASH_MAX == 512
    assert len(hashed.encoded) == 512


@pytest.mark.parametrize("value", ["", "a" * 513, "scrypt$a\x00b"])
def test_empty_nul_or_too_long_hash_is_rejected(value: str) -> None:
    """빈 값·NUL 포함·513자 해시는 거부한다."""
    # when·then: 잘못된 값으로 만들면 InvalidValueError가 난다
    with pytest.raises(InvalidValueError):
        PasswordHash(value)


def test_repr_hides_encoded_value() -> None:
    """repr·str에는 인코딩된 해시가 드러나지 않는다."""
    # given: 해시 값 객체
    hashed = PasswordHash(ENCODED)

    # when: repr·str로 문자열을 만든다
    shown_repr = repr(hashed)
    shown_str = str(hashed)
    # then: 두 문자열에 원문이 없고 repr은 가림 표기를 쓴다
    assert ENCODED not in shown_repr
    assert ENCODED not in shown_str
    assert "PasswordHash(***)" in shown_repr


def test_password_hash_is_frozen_and_compares_by_value() -> None:
    """해시 값 객체는 불변이고 값으로 비교한다."""
    # given: 해시 값 객체
    hashed = PasswordHash(ENCODED)

    # when: 같은 값으로 다른 해시 객체를 만든다
    same = PasswordHash(ENCODED)
    # then: 같은 값이면 같다
    assert hashed == same
    # when·then: 값을 바꾸려 하면 FrozenInstanceError가 난다
    with pytest.raises(dataclasses.FrozenInstanceError):
        hashed.encoded = "x"  # type: ignore[misc]
