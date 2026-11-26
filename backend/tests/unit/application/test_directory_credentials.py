"""연결 테스트 증명: 자격증명 없이 범위·설정·유효기간을 검증한다(IN-087)."""


import pytest

from app.application.directory.connection_proof import PROOF_TTL_SECONDS, DirectoryConnectionProof
from app.domain.common.errors import InvalidValueError
from app.domain.common.secret import SealedSecret
from app.domain.directory.settings import SecurityMode
from tests.factories import NOW
from tests.factories_directory import make_directory_connection
from tests.fakes.secret_cipher import FakeSecretCipher, foreign_secret
from tests.fakes.unit_of_work import FixedClock


def test_valid_proof_returns_base_dn_and_contains_no_credentials() -> None:
    # given: 연결 테스트에 성공한 접속 정보
    cipher, clock = FakeSecretCipher(), FixedClock(NOW)
    proof = DirectoryConnectionProof(cipher, clock)
    connection = make_directory_connection()
    # when: 성공 증명을 발급하고 검증한다
    token = SealedSecret(proof.issue(connection, "dc=corp,dc=test", "setup"))
    # then: Base DN만 복원하고 계정이나 비밀번호를 요구하지 않는다
    assert proof.verify(connection, token, "setup") == "dc=corp,dc=test"


@pytest.mark.parametrize(
    "change",
    [
        {"host": "other.corp.test"},
        {"port": 389},
        {"security": SecurityMode.STARTTLS},
        {"user_filter": "(uid={login_id})"},
        {"connect_timeout_seconds": 9},
    ],
)
def test_any_connection_change_requires_retesting(change: dict[str, object]) -> None:
    # given: 원래 접속 정보의 성공 증명
    proof = DirectoryConnectionProof(FakeSecretCipher(), FixedClock(NOW))
    connection = make_directory_connection()
    token = SealedSecret(proof.issue(connection, "dc=corp,dc=test", "setup"))
    # when·then: 어떤 접속 정보든 바뀌면 저장할 수 없다
    with pytest.raises(InvalidValueError):
        proof.verify(make_directory_connection(**change), token, "setup")


@pytest.mark.parametrize("scope", ["admin:1", "admin:2", ""])
def test_proof_cannot_cross_setup_or_admin_scope(scope: str) -> None:
    # given: 초기 설정에서 성공했다
    proof = DirectoryConnectionProof(FakeSecretCipher(), FixedClock(NOW))
    connection = make_directory_connection()
    token = SealedSecret(proof.issue(connection, "dc=corp,dc=test", "setup"))
    # when·then: 다른 권한 범위로 재사용할 수 없다
    with pytest.raises(InvalidValueError):
        proof.verify(connection, token, scope)


def test_expired_or_foreign_proof_is_rejected() -> None:
    # given: 성공 증명을 발급했다
    clock = FixedClock(NOW)
    proof = DirectoryConnectionProof(FakeSecretCipher(), clock)
    connection = make_directory_connection()
    token = SealedSecret(proof.issue(connection, "dc=corp,dc=test", "setup"))
    # when: 유효기간이 끝난다
    clock.advance(seconds=PROOF_TTL_SECONDS)
    # then: 만료되거나 다른 키로 만든 증명은 재테스트를 요구한다
    for candidate in (token, foreign_secret()):
        with pytest.raises(InvalidValueError):
            proof.verify(connection, candidate, "setup")
