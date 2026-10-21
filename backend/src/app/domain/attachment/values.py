"""첨부 파일 값과 한도. R1의 FileStorage.save와 첨부 도메인이 같은 상수를 쓴다."""

import unicodedata
from dataclasses import dataclass
from enum import StrEnum
from typing import NewType, Self

from app.domain.common.errors import InvalidValueError
from app.domain.common.validation import reject_nul

AttachmentId = NewType("AttachmentId", int)

MAX_FILE_BYTES = 100 * 1024 * 1024  # 104,857,600 허용, +1 거부
DESCRIPTION_MAX = 100  # 코드 포인트
FILE_NAME_MAX = 255  # 코드 포인트(NFC 정규화 뒤)

# 프런트 constants.ts의 BLOCKED_EXTENSIONS와 같은 집합(PRD 13개 + 결정 11개).
BLOCKED_EXTENSIONS = frozenset(
    {"exe", "msi", "bat", "cmd", "sh", "ps1", "jar", "com", "scr", "dmg", "pkg", "deb", "rpm"}
    | {"vbs", "vbe", "wsf", "wsh", "hta", "cpl", "msp", "mst", "apk", "appimage", "run"}
)

NO_FILE = "업로드할 파일을 선택하세요."
DESCRIPTION_TOO_LONG = "설명은 100자 이내로 입력하세요."
FILE_TOO_LARGE = "파일 크기가 100MB를 초과합니다. (최대 100MB)"
INVALID_FILE_NAME = "사용할 수 없는 파일 이름입니다."


def blocked_message(ext: str) -> str:
    return f"실행·설치 파일(.{ext})은 업로드할 수 없습니다."


class OnExists(StrEnum):
    """같은 이름의 파일이 이미 있을 때의 선택."""

    ASK = "ask"
    REPLACE = "replace"
    SKIP = "skip"


def extension_of(name: str) -> str:
    """이름 끝의 공백·점을 걷어 낸 뒤 마지막 확장자(소문자). `setup.exe.`는 'exe'.

    `.bashrc`·`a.`·`.exe`처럼 확장자가 없는 이름은 ''.
    """
    end = len(name)
    while end > 0 and (name[end - 1].isspace() or name[end - 1] == "."):
        end -= 1
    trimmed = name[:end]
    dot = trimmed.rfind(".")
    if dot <= 0:
        return ""
    return trimmed[dot + 1 :].lower()


def _is_control(char: str) -> bool:
    return ord(char) < 0x20 or ord(char) == 0x7F  # noqa: PLR2004 - C0 제어 문자와 DEL


def _is_format(char: str) -> bool:
    """유니코드 서식 문자(Cf): 방향 제어·zero-width 등 이름을 위장할 수 있어 거부한다."""
    return unicodedata.category(char) == "Cf"


@dataclass(frozen=True, slots=True)
class FileName:
    """첨부 파일 이름. NFC로 정규화한 값을 저장하고 비교한다(앞뒤 공백은 자르지 않는다)."""

    value: str

    @classmethod
    def parse(cls, raw: str) -> Self:
        text = unicodedata.normalize("NFC", raw)
        if (
            not text
            or len(text) > FILE_NAME_MAX
            or text in {".", ".."}
            or "/" in text
            or "\\" in text
            or any(_is_control(char) or _is_format(char) for char in text)
        ):
            raise InvalidValueError(INVALID_FILE_NAME)
        return cls(text)

    @property
    def extension(self) -> str:
        return extension_of(self.value)


def parse_description(raw: str) -> str:
    reject_nul(raw, "설명")
    text = raw.strip()
    if len(text) > DESCRIPTION_MAX:
        raise InvalidValueError(DESCRIPTION_TOO_LONG)
    return text


def ensure_within_limit(size: int) -> None:
    if size > MAX_FILE_BYTES:
        raise InvalidValueError(FILE_TOO_LARGE)


@dataclass(frozen=True, slots=True)
class UploadCandidate:
    """업로드 요청이 규칙을 통과한 결과."""

    file_name: FileName
    description: str

    @classmethod
    def check(cls, *, file_name: str | None, description: str, size: int | None) -> Self:
        """검증 순서: 파일 없음, 설명, 크기, 차단 확장자(원본 이름), 파일 이름.

        size=None이면 크기 검사는 생략한다.
        """
        if file_name is None:
            raise InvalidValueError(NO_FILE)
        text = parse_description(description)
        if size is not None:
            ensure_within_limit(size)
        extension = extension_of(file_name)
        if extension in BLOCKED_EXTENSIONS:
            raise InvalidValueError(blocked_message(extension))
        return cls(file_name=FileName.parse(file_name), description=text)
