"""DirectorySettingsDraft.complete: 바인드 비밀번호 입력·유지 규칙(AC4·AC10).

비밀번호를 비운 요청(None)은 '저장된 값 유지'다. 저장된 접속 정보(호스트·포트·보안 연결·
바인드 계정)가
하나라도 바뀌면 유지할 수 없다(저장된 비밀번호가 다른 서버로 전송되는 것을 막는다).
"""

import pytest

from app.domain.auth.credentials import Password
from app.domain.common.errors import InvalidValueError
from app.domain.directory.settings import DirectorySettings, DirectorySettingsDraft, SecurityMode
from tests.factories_directory import make_directory_connection

PREVIOUS = make_directory_connection()
STORED_PASSWORD = Password("Stored-pw-1!")
NEW_PASSWORD = Password("New-pw-2!")


def test_draft_with_new_password_uses_it() -> None:
    draft = DirectorySettingsDraft(connection=PREVIOUS, bind_password=NEW_PASSWORD)

    completed = draft.complete(PREVIOUS, STORED_PASSWORD)

    assert isinstance(completed, DirectorySettings)
    assert completed.connection == PREVIOUS
    assert completed.bind_password.reveal() == "New-pw-2!"


def test_draft_with_new_password_works_without_previous_settings() -> None:
    draft = DirectorySettingsDraft(connection=PREVIOUS, bind_password=NEW_PASSWORD)

    assert draft.complete(None, None).bind_password.reveal() == "New-pw-2!"


def test_draft_with_new_password_replaces_even_when_stored_one_is_unreadable() -> None:
    draft = DirectorySettingsDraft(connection=PREVIOUS, bind_password=NEW_PASSWORD)

    assert draft.complete(PREVIOUS, None).bind_password.reveal() == "New-pw-2!"


def test_draft_without_password_reuses_previous_when_endpoint_and_account_same() -> None:
    changed = make_directory_connection(user_filter="(uid={login_id})", connect_timeout_seconds=12)
    draft = DirectorySettingsDraft(connection=changed, bind_password=None)

    completed = draft.complete(PREVIOUS, STORED_PASSWORD)

    assert completed.connection == changed
    assert completed.bind_password.reveal() == "Stored-pw-1!"


@pytest.mark.parametrize(
    "change",
    [
        {"host": "dc2.corp.test"},
        {"port": 3269},
        {"security": SecurityMode.STARTTLS},
        {"bind_account": "cn=other,ou=services,dc=corp,dc=test"},
    ],
    ids=["host", "port", "security", "bind_account"],
)
def test_draft_without_password_is_rejected_when_any_of_host_port_security_account_changes(
    change: dict[str, object],
) -> None:
    draft = DirectorySettingsDraft(
        connection=make_directory_connection(**change), bind_password=None
    )

    with pytest.raises(InvalidValueError) as caught:
        draft.complete(PREVIOUS, STORED_PASSWORD)

    assert "bind_password" in str(caught.value)
    assert "다시 입력" in str(caught.value)


def test_draft_without_password_and_no_previous_is_rejected() -> None:
    draft = DirectorySettingsDraft(connection=PREVIOUS, bind_password=None)

    with pytest.raises(InvalidValueError) as caught:
        draft.complete(None, None)

    assert "bind_password" in str(caught.value)
    assert "바인드 비밀번호를 입력하세요" in str(caught.value)


def test_draft_without_password_and_unreadable_previous_is_rejected() -> None:
    draft = DirectorySettingsDraft(connection=PREVIOUS, bind_password=None)

    with pytest.raises(InvalidValueError) as caught:
        draft.complete(PREVIOUS, None)

    assert "bind_password" in str(caught.value)
    assert "읽을 수 없습니다" in str(caught.value)
