"""저장 위치 경로 값 객체: 절대 POSIX 경로 하나를 검증하고 정규화한다."""

from dataclasses import dataclass
from typing import Self

from app.domain.common.errors import InvalidValueError
from app.domain.common.validation import reject_nul

STORAGE_PATH_MAX = 1024
PATH_NOT_ABSOLUTE = "절대 경로를 입력하세요."
PATH_TOO_LONG = "저장 경로는 1024자 이내로 입력하세요."
PATH_NOT_WRITABLE = "해당 위치에 쓸 수 없습니다."  # 쓰기 확인 실패 시 application이 던진다


@dataclass(frozen=True, slots=True)
class StoragePath:
    value: str  # 정규화된 절대 POSIX 경로

    @classmethod
    def parse(cls, raw: str) -> Self:
        reject_nul(raw, "저장 경로")
        text = raw.strip()
        if not text.startswith("/"):
            raise InvalidValueError(PATH_NOT_ABSOLUTE)
        segments = [part for part in text.split("/") if part not in ("", ".")]
        if ".." in segments:
            raise InvalidValueError(PATH_NOT_ABSOLUTE)
        normalized = "/" + "/".join(segments)
        if len(normalized) > STORAGE_PATH_MAX:
            raise InvalidValueError(PATH_TOO_LONG)
        return cls(normalized)
