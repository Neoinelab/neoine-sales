"""FernetSecretCipher: AD 바인드 비밀번호 암호화(AC3·AC10). 키가 다르거나 손상되면 풀 수 없다."""

import base64

import pytest
from app.application.ports.secret_cipher import SecretDecryptionError
from app.domain.common.secret import SealedSecret
from app.infra.crypto.fernet_cipher import FernetSecretCipher
from pydantic import SecretStr

from tests.support.crypto_keys import OTHER_FERNET_KEY, TEST_FERNET_KEY

PLAINTEXT = "Svc-Dummy-pw-1!"


def _cipher(key: str = TEST_FERNET_KEY) -> FernetSecretCipher:
    return FernetSecretCipher(SecretStr(key))


def test_seal_then_unseal_round_trips() -> None:
    cipher = _cipher()

    assert cipher.unseal(cipher.seal(PLAINTEXT)) == PLAINTEXT


@pytest.mark.parametrize(
    "text", ["한글 비밀번호!", "a" * 256, " spaces inside ", "p@ss:w/rd\\\\\"'"]
)
def test_unusual_passwords_round_trip(text: str) -> None:
    cipher = _cipher()

    assert cipher.unseal(cipher.seal(text)) == text


def test_token_does_not_contain_plaintext() -> None:
    sealed = _cipher().seal(PLAINTEXT)

    assert isinstance(sealed, SealedSecret)
    assert sealed.token.isascii()
    assert PLAINTEXT not in sealed.token
    assert base64.urlsafe_b64encode(PLAINTEXT.encode()).decode().rstrip("=") not in sealed.token
    assert PLAINTEXT not in repr(sealed)


def test_sealing_twice_gives_different_tokens() -> None:
    cipher = _cipher()

    assert cipher.seal(PLAINTEXT).token != cipher.seal(PLAINTEXT).token


def test_a_token_sealed_with_one_key_opens_with_the_same_key_in_a_new_instance() -> None:
    sealed = _cipher().seal(PLAINTEXT)

    assert _cipher().unseal(sealed) == PLAINTEXT


def test_unseal_with_other_key_raises_decryption_error() -> None:
    sealed = _cipher(TEST_FERNET_KEY).seal(PLAINTEXT)

    with pytest.raises(SecretDecryptionError):
        _cipher(OTHER_FERNET_KEY).unseal(sealed)


@pytest.mark.parametrize("token", ["garbage", "gAAAAA-not-a-token", "x" * 200, "한글"])
def test_unseal_garbage_raises_decryption_error(token: str) -> None:
    with pytest.raises(SecretDecryptionError):
        _cipher().unseal(SealedSecret(token))


def test_unseal_of_a_tampered_token_raises_decryption_error() -> None:
    token = _cipher().seal(PLAINTEXT).token
    flipped = token[:-4] + ("AAAA" if not token.endswith("AAAA") else "BBBB")

    with pytest.raises(SecretDecryptionError):
        _cipher().unseal(SealedSecret(flipped))


def test_error_message_has_no_token_key_or_plaintext() -> None:
    sealed = _cipher(TEST_FERNET_KEY).seal(PLAINTEXT)

    with pytest.raises(SecretDecryptionError) as caught:
        _cipher(OTHER_FERNET_KEY).unseal(sealed)

    text = f"{caught.value!s}|{caught.value!r}|{caught.value.args!r}"
    for secret in (sealed.token, TEST_FERNET_KEY, OTHER_FERNET_KEY, PLAINTEXT):
        assert secret not in text
