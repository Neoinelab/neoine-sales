"""LocalFileStorage가 스레드에서 실행하는 동기 파일시스템 헬퍼. 경로 조합과 권한을 한 곳에 둔다."""

import contextlib
import os
import re
import shutil
import uuid
from pathlib import Path

CHUNK_SIZE = 1024 * 1024
DIR_MODE = 0o750
FILE_MODE = 0o640
_KEY_PATTERN = re.compile(r"[0-9a-f]{32}")
_PART_PATTERN = re.compile(r"[A-Za-z0-9-]{1,64}")
_PROBE_PREFIX = ".neoine-write-test-"


def validate_key(key: str) -> None:
    """저장 키는 uuid hex(32자 소문자 16진수)만 허용한다. 경로 구분자·`..`은 거절된다."""
    if _KEY_PATTERN.fullmatch(key) is None:
        raise ValueError("invalid storage key")


def validate_folder(parts: tuple[str, ...]) -> None:
    """폴더 조각은 영숫자와 '-'만(1~64자). '.'으로 시작하거나 구분자가 있으면 거절한다."""
    if not parts:
        raise ValueError("invalid storage folder")
    for part in parts:
        if _PART_PATTERN.fullmatch(part) is None:
            raise ValueError("invalid storage folder")


def folder_dir(root: str, parts: tuple[str, ...]) -> Path:
    validate_folder(parts)
    return Path(root).joinpath(*parts)


def file_path(root: str, parts: tuple[str, ...], key: str) -> Path:
    validate_key(key)
    return folder_dir(root, parts) / key


def reject_linked_folders(root: str, parts: tuple[str, ...]) -> None:
    """root 아래 폴더 조각 중 심볼릭 링크가 있으면 NotADirectoryError."""
    current = Path(root)
    for part in parts:
        current = current / part
        if current.is_symlink():
            raise NotADirectoryError(str(current))


def make_folders(root: str, parts: tuple[str, ...]) -> None:
    """root 아래 폴더를 조각마다 만든다(링크는 따라가지 않는다). 새 디렉터리 모드는 0o750."""
    Path(root).mkdir(parents=True, exist_ok=True, mode=DIR_MODE)
    current = Path(root)
    for part in parts:
        current = current / part
        if current.is_symlink():  # 링크를 따라 저장 위치 밖에 쓰지 않는다
            raise NotADirectoryError(str(current))
        current.mkdir(exist_ok=True, mode=DIR_MODE)
        if not current.is_dir():
            raise NotADirectoryError(str(current))
        with contextlib.suppress(OSError):  # 새로 만들지 않은 디렉터리의 소유가 달라도 계속한다
            current.chmod(DIR_MODE)


def create_exclusive(path: Path) -> int:
    """같은 이름이 있으면 FileExistsError. 파일 모드는 other 권한이 없다."""
    return os.open(path, os.O_WRONLY | os.O_CREAT | os.O_EXCL, FILE_MODE)


def write_all(descriptor: int, data: bytes) -> None:
    view = memoryview(data)
    while view:
        written = os.write(descriptor, view)
        view = view[written:]


def close_quietly(descriptor: int) -> None:
    with contextlib.suppress(OSError):
        os.close(descriptor)


def remove_quietly(path: Path) -> None:
    with contextlib.suppress(OSError):
        path.unlink()


def probe_writable(root: Path) -> None:
    """root(상위 포함)를 만들고 확인용 파일을 쓴 뒤 지운다. 디렉터리 외에는 흔적이 없다."""
    root.mkdir(parents=True, exist_ok=True, mode=DIR_MODE)
    if not root.is_dir():
        raise NotADirectoryError(str(root))
    probe = root / f"{_PROBE_PREFIX}{uuid.uuid4().hex}"
    descriptor = os.open(probe, os.O_WRONLY | os.O_CREAT | os.O_EXCL, FILE_MODE)
    try:
        os.write(descriptor, b"ok")
    finally:
        close_quietly(descriptor)
        remove_quietly(probe)


def stat_regular_file(path: Path) -> int | None:
    """일반 파일이면 크기, 없거나 파일이 아니면 None. 그 밖의 OSError(권한 등)는 그대로 낸다."""
    try:
        info = path.stat()
    except FileNotFoundError, NotADirectoryError:
        return None
    return info.st_size if path.is_file() else None


def delete_file(path: Path) -> None:
    with contextlib.suppress(FileNotFoundError, NotADirectoryError):
        path.unlink()


def delete_folder(root: str, parts: tuple[str, ...]) -> None:
    """폴더를 통째로 지운다. 중간 조각이 링크면 그대로 두고, 마지막이 링크면 링크만 지운다."""
    current = Path(root)
    for part in parts[:-1]:
        current = current / part
        if current.is_symlink():
            return
    delete_directory(current / parts[-1])


def delete_directory(directory: Path) -> None:
    """디렉터리를 통째로 지운다. 심볼릭 링크면 링크만 지우고 바깥은 건드리지 않는다."""
    if directory.is_symlink():
        directory.unlink()
        return
    with contextlib.suppress(FileNotFoundError, NotADirectoryError):
        shutil.rmtree(directory)


def open_for_read(path: Path) -> int:
    return os.open(path, os.O_RDONLY)


def check_readable(path: Path) -> None:
    """읽기용으로 열 수 있는지 확인하고 곧바로 닫는다(열린 채로 남기지 않는다)."""
    close_quietly(open_for_read(path))


def read_chunk(descriptor: int) -> bytes:
    return os.read(descriptor, CHUNK_SIZE)
