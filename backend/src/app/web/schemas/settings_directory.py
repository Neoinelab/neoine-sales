from typing import Annotated

from pydantic import BaseModel, Field, StrictInt

from app.application.directory.result import TestResult
from app.web.schemas.auth_directory import DirectorySettingsRequest, DirectorySettingsSaveRequest


class DirectorySettingsTestRequest(DirectorySettingsRequest):
    pass


class DirectorySettingsUpdateRequest(DirectorySettingsSaveRequest):
    expected_revision: Annotated[StrictInt, Field(ge=1)] | None


class DirectoryTestResultResponse(BaseModel):
    success: bool
    stage: str | None
    message: str
    base_dn: str | None
    test_token: str | None

    @classmethod
    def from_result(cls, result: TestResult) -> DirectoryTestResultResponse:
        return cls(
            success=result.success,
            stage=None if result.stage is None else str(result.stage),
            message=result.message,
            base_dn=result.base_dn,
            test_token=result.test_token,
        )
