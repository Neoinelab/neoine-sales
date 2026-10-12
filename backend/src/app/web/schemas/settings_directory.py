from pydantic import BaseModel, Field, SecretStr, StrictInt

from app.application.directory.test_settings import TestResult
from app.domain.auth.credentials import Password
from app.web.schemas.auth_directory import DirectorySettingsRequest


def _to_password(secret: SecretStr | None) -> Password | None:
    """비밀번호 형식 오류(빈 값·NUL·길이)는 도메인이 invalid-value(422)로 거절한다."""
    return None if secret is None else Password(secret.get_secret_value())


class DirectorySettingsTestRequest(DirectorySettingsRequest):
    """연결 테스트 본문: 설정 + 현재 로그인한 admin의 비밀번호(dev 로그인 admin은 생략)."""

    password: SecretStr | None = None

    def to_password(self) -> Password | None:
        return _to_password(self.password)


class DirectorySettingsUpdateRequest(DirectorySettingsTestRequest):
    """저장 본문: 연결 테스트 본문 + 낙관적 잠금용 revision(1 이상)."""

    expected_revision: StrictInt = Field(ge=1)


class DirectoryTestResultResponse(BaseModel):
    success: bool
    stage: str | None
    message: str

    @classmethod
    def from_result(cls, result: TestResult) -> DirectoryTestResultResponse:
        stage = None if result.stage is None else str(result.stage)
        return cls(success=result.success, stage=stage, message=result.message)
