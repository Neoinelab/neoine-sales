"""저장된 AD 설정의 바인드 비밀번호 복호화와 후보 설정 완성. 값은 로그·예외에 남기지 않는다."""

import logging
from typing import TYPE_CHECKING

from app.application.directory.errors import DirectoryCredentialUnreadableError
from app.application.ports.secret_cipher import SecretDecryptionError
from app.domain.auth.credentials import Password
from app.domain.common.errors import InvalidValueError
from app.domain.directory.settings import DirectorySettings

if TYPE_CHECKING:
    from app.application.ports.secret_cipher import SecretCipher
    from app.domain.directory.settings import DirectorySettingsDraft, StoredDirectorySettings

logger = logging.getLogger(__name__)


def try_unseal(cipher: SecretCipher, stored: StoredDirectorySettings) -> Password | None:
    """바인드 비밀번호를 풀어 돌려준다. 풀 수 없으면 None(조회 화면·후보 완성용)."""
    try:
        return Password(cipher.unseal(stored.sealed_bind_password))
    except SecretDecryptionError, InvalidValueError:
        return None


def unseal_settings(cipher: SecretCipher, stored: StoredDirectorySettings) -> DirectorySettings:
    """AD 접속에 쓸 설정을 만든다. 풀 수 없으면 경고 로그 후 DirectoryCredentialUnreadableError."""
    password = try_unseal(cipher, stored)
    if password is None:
        logger.warning("AD 바인드 비밀번호를 복호화하지 못했습니다(암호화 키 변경 여부 확인)")
        raise DirectoryCredentialUnreadableError
    return DirectorySettings(stored.connection, password)


def resolve_draft(
    draft: DirectorySettingsDraft, stored: StoredDirectorySettings | None, cipher: SecretCipher
) -> DirectorySettings:
    """후보와 저장 값으로 접속 설정을 완성한다(비밀번호 유지 규칙은 도메인이 지킨다)."""
    if stored is None:
        return draft.complete(None, None)
    return draft.complete(stored.connection, try_unseal(cipher, stored))
