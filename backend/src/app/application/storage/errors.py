UPLOAD_UNAVAILABLE = "파일 저장 위치를 사용할 수 없어 업로드할 수 없습니다. 관리자에게 문의하세요."
DOWNLOAD_UNAVAILABLE = "파일 저장 위치를 사용할 수 없습니다. 관리자에게 문의하세요."


class StorageUnavailableError(Exception):
    """저장 위치가 없거나 쓸 수 없다. DomainError가 아니라 web이 별도로 503으로 매핑한다."""

    def __init__(self, message: str) -> None:
        super().__init__(message)
        self.message = message
