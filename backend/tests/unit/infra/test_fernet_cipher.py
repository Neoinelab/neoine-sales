"""FernetSecretCipher: AD 바인드 비밀번호 암호화. 키가 다르거나 손상되면 풀 수 없다."""

import base64

import pytest
from pydantic import SecretStr

from app.application.ports.secret_cipher import SecretDecryptionError
from app.domain.common.secret import SealedSecret
from app.infra.crypto.fernet_cipher import FernetSecretCipher
from tests.support.crypto_keys import OTHER_FERNET_KEY, TEST_FERNET_KEY

PLAINTEXT = "Svc-Dummy-pw-1!"


def _cipher(key: str = TEST_FERNET_KEY) -> FernetSecretCipher:
    return FernetSecretCipher(SecretStr(key))


def test_seal_then_unseal_round_trips() -> None:
    """봉인한 비밀번호를 풀면 원문이 나온다."""
    # given: 암호기
    cipher = _cipher()

    # when: 봉인한 뒤 푼다
    opened = cipher.unseal(cipher.seal(PLAINTEXT))

    # then: 원문과 같다
    assert opened == PLAINTEXT


@pytest.mark.parametrize(
    "text", ["한글 비밀번호!", "a" * 256, " spaces inside ", "p@ss:w/rd\\\\\"'"]
)
def test_unusual_passwords_round_trip(text: str) -> None:
    """한글·공백·특수문자 비밀번호도 봉인 후 풀면 원문이 나온다."""
    # given: 암호기
    cipher = _cipher()

    # when: 봉인한 뒤 푼다
    opened = cipher.unseal(cipher.seal(text))

    # then: 원문과 같다
    assert opened == text


def test_token_does_not_contain_plaintext() -> None:
    """토큰에는 원문이나 그 base64가 들어 있지 않다."""
    # when: 비밀번호를 봉인한다
    sealed = _cipher().seal(PLAINTEXT)

    # then: ASCII 토큰이고 원문·base64 원문·repr 어디에도 원문이 없다
    assert isinstance(sealed, SealedSecret)
    assert sealed.token.isascii()
    assert PLAINTEXT not in sealed.token
    assert base64.urlsafe_b64encode(PLAINTEXT.encode()).decode().rstrip("=") not in sealed.token
    assert PLAINTEXT not in repr(sealed)


def test_sealing_twice_gives_different_tokens() -> None:
    """같은 비밀번호를 두 번 봉인하면 토큰이 서로 다르다."""
    # given: 암호기
    cipher = _cipher()

    # when: 같은 원문을 두 번 봉인한다
    first = cipher.seal(PLAINTEXT).token
    second = cipher.seal(PLAINTEXT).token

    # then: 토큰이 다르다
    assert first != second


def test_a_token_sealed_with_one_key_opens_with_the_same_key_in_a_new_instance() -> None:
    """같은 키를 가진 새 인스턴스로도 토큰을 풀 수 있다."""
    # given: 한 인스턴스가 봉인한 토큰
    sealed = _cipher().seal(PLAINTEXT)

    # when: 같은 키의 새 인스턴스로 푼다
    opened = _cipher().unseal(sealed)

    # then: 원문과 같다
    assert opened == PLAINTEXT


def test_unseal_with_other_key_raises_decryption_error() -> None:
    """다른 키로는 풀 수 없고 복호화 오류가 난다."""
    # given: 한 키로 봉인한 토큰
    sealed = _cipher(TEST_FERNET_KEY).seal(PLAINTEXT)

    # when·then: 다른 키로 풀면 SecretDecryptionError가 난다
    with pytest.raises(SecretDecryptionError):
        _cipher(OTHER_FERNET_KEY).unseal(sealed)


@pytest.mark.parametrize("token", ["garbage", "gAAAAA-not-a-token", "x" * 200, "한글"])
def test_unseal_garbage_raises_decryption_error(token: str) -> None:
    """토큰이 아닌 문자열은 복호화 오류가 난다."""
    # when·then: 쓰레기 토큰을 풀면 SecretDecryptionError가 난다
    with pytest.raises(SecretDecryptionError):
        _cipher().unseal(SealedSecret(token))


def test_unseal_of_a_tampered_token_raises_decryption_error() -> None:
    """변조된 토큰은 복호화 오류가 난다."""
    # given: 끝부분을 바꾼 토큰
    token = _cipher().seal(PLAINTEXT).token
    flipped = token[:-4] + ("AAAA" if not token.endswith("AAAA") else "BBBB")

    # when·then: 변조 토큰을 풀면 SecretDecryptionError가 난다
    with pytest.raises(SecretDecryptionError):
        _cipher().unseal(SealedSecret(flipped))


def test_error_message_has_no_token_key_or_plaintext() -> None:
    """복호화 오류 메시지에는 토큰·키·원문이 들어 있지 않다."""
    # given: 한 키로 봉인한 토큰
    sealed = _cipher(TEST_FERNET_KEY).seal(PLAINTEXT)

    # when: 다른 키로 풀어 오류를 받는다
    with pytest.raises(SecretDecryptionError) as caught:
        _cipher(OTHER_FERNET_KEY).unseal(sealed)

    # then: 오류 문자열 어디에도 토큰·키·원문이 없다
    text = f"{caught.value!s}|{caught.value!r}|{caught.value.args!r}"
    for secret in (sealed.token, TEST_FERNET_KEY, OTHER_FERNET_KEY, PLAINTEXT):
        assert secret not in text
