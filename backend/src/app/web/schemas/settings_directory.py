from typing import Annotated

from pydantic import BaseModel, Field, SecretStr, StrictInt

from app.application.directory.test_settings import TestResult
from app.domain.auth.credentials import Password
from app.domain.directory.settings import DirectorySettingsDraft, bind_password_of
from app.web.schemas.auth_directory import DirectoryConnectionRequest


def _to_password(secret: SecretStr | None) -> Password | None:
    """비밀번호 형식 오류(빈 값·NUL·길이)는 도메인이 invalid-value(422)로 거절한다."""
    return None if secret is None else Password(secret.get_secret_value())


class DirectorySettingsTestRequest(DirectoryConnectionRequest):
    """연결 테스트 본문: 접속 정보 + 바인드 비밀번호(생략·null이면 저장된 값 유지) +
    현재 로그인한 admin의 비밀번호(dev 로그인 admin은 생략)."""

    bind_password: SecretStr | None = None
    password: SecretStr | None = None

    def to_draft(self) -> DirectorySettingsDraft:
        raw = self.bind_password
        bind = None if raw is None else bind_password_of(raw.get_secret_value())
        return DirectorySettingsDraft(self.to_connection(), bind)

    def to_password(self) -> Password | None:
        return _to_password(self.password)


class DirectorySettingsUpdateRequest(DirectorySettingsTestRequest):
    """저장 본문: 테스트 본문 + 낙관적 잠금용 revision(키 필수, null이면 설정 없을 때 생성)."""

    expected_revision: Annotated[StrictInt, Field(ge=1)] | None


class DirectoryTestResultResponse(BaseModel):
    success: bool
    stage: str | None
    message: str
    base_dn: str | None

    @classmethod
    def from_result(cls, result: TestResult) -> DirectoryTestResultResponse:
        stage = None if result.stage is None else str(result.stage)
        return cls(
            success=result.success, stage=stage, message=result.message, base_dn=result.base_dn
        )
