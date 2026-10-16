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
_PROBE_PREFIX = ".neoine-write-test-"


def validate_key(key: str) -> None:
    """저장 키는 uuid hex(32자 소문자 16진수)만 허용한다. 경로 구분자·`..`은 거절된다."""
    if _KEY_PATTERN.fullmatch(key) is None:
        raise ValueError("invalid storage key")


def deal_dir(root: str, deal_code: str) -> Path:
    return Path(root) / deal_code


def file_path(root: str, deal_code: str, key: str) -> Path:
    validate_key(key)
    return deal_dir(root, deal_code) / key


def make_deal_dir(directory: Path) -> None:
    if directory.is_symlink():  # 링크를 따라 저장 위치 밖에 쓰지 않는다
        raise NotADirectoryError(str(directory))
    directory.mkdir(parents=True, exist_ok=True, mode=DIR_MODE)
    if not directory.is_dir():
        raise NotADirectoryError(str(directory))
    with contextlib.suppress(OSError):  # 새로 만들지 않은 디렉터리의 소유가 달라도 쓰기는 계속된다
        directory.chmod(DIR_MODE)


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
