from typing import TYPE_CHECKING

from app.application.directory.errors import DirectoryVerificationError
from app.application.directory.result import SUCCESS_MESSAGE, TestResult
from app.application.ports.directory import DirectoryUnavailableError, VerificationStage

if TYPE_CHECKING:
    from app.application.directory.connection_proof import DirectoryConnectionProof
    from app.application.ports.directory import DirectoryAuthenticator
    from app.domain.directory.settings import DirectorySettings


class VerifyDirectorySettings:
    def __init__(self, directory: DirectoryAuthenticator, proof: DirectoryConnectionProof) -> None:
        self._directory = directory
        self._proof = proof

    async def execute(self, settings: DirectorySettings, scope: str) -> TestResult:
        try:
            base_dn = await self._directory.discover_base_dn(settings)
        except DirectoryUnavailableError as error:
            stage = error.stage or VerificationStage.CONNECT
            return TestResult(False, stage, DirectoryVerificationError(stage).message)
        token = self._proof.issue(settings.connection, base_dn, scope)
        return TestResult(True, None, SUCCESS_MESSAGE, base_dn, token)
