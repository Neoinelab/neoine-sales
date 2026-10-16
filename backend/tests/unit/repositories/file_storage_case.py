"""FileStorage 계약 테스트용 case: 같은 계약 테스트를 FakeFileStorage와 LocalFileStorage에 돌린다.

local은 `tmp_path` 아래 실제 디렉터리를 쓴다(DB가 필요 없어 integration 마커가 없다).
도메인·infra 모듈은 case를 열 때 가져온다(conftest가 이 모듈을 가져오므로 구현 전에도 수집된다).

`root`는 아직 없는 디렉터리, `other_root`는 다른 root, `blocked_root`는 쓸 수 없는 root다
(local은 일반 파일 아래의 경로 = 디렉터리를 만들 수 없음. 권한 비트에 기대지 않아 root 사용자로
돌려도 같은 결과다).
"""

from dataclasses import dataclass
from pathlib import Path
from typing import TYPE_CHECKING

import pytest

if TYPE_CHECKING:
    from app.application.ports.file_storage import FileStorage
    from app.domain.storage.path import StoragePath

    from tests.fakes.file_storage import FakeFileStorage

PARAMS = [pytest.param("fake", id="fake"), pytest.param("local", id="local")]


class LocalView:
    """실제 파일시스템을 들여다보는 도우미."""

    def dir_exists(self, path: str) -> bool:
        return Path(path).is_dir()

    def entries(self, path: str) -> list[str]:
        directory = Path(path)
        return sorted(child.name for child in directory.iterdir()) if directory.is_dir() else []


@dataclass(frozen=True, slots=True)
class FileStorageCase:
    storage: FileStorage
    view: FakeFileStorage | LocalView
    root: StoragePath
    other_root: StoragePath
    blocked_root: StoragePath

    def dir_exists(self, path: str) -> bool:
        return self.view.dir_exists(path)

    def entries(self, path: str) -> list[str]:
        return self.view.entries(path)


def open_fake_case() -> FileStorageCase:
    from app.domain.storage.path import StoragePath  # noqa: PLC0415

    from tests.fakes.file_storage import FakeFileStorage  # noqa: PLC0415

    fake = FakeFileStorage()
    fake.block("/blocked")
    return FileStorageCase(
        storage=fake,
        view=fake,
        root=StoragePath.parse("/data/files"),
        other_root=StoragePath.parse("/data/other"),
        blocked_root=StoragePath.parse("/blocked/files"),
    )


def open_local_case(tmp_path: Path) -> FileStorageCase:
    from app.domain.storage.path import StoragePath  # noqa: PLC0415
    from app.infra.storage.local_file_storage import LocalFileStorage  # noqa: PLC0415

    blocker = tmp_path / "blocker"
    blocker.write_bytes(b"i am a regular file")
    return FileStorageCase(
        storage=LocalFileStorage(),
        view=LocalView(),
        root=StoragePath.parse(str(tmp_path / "data" / "files")),
        other_root=StoragePath.parse(str(tmp_path / "data" / "other")),
        blocked_root=StoragePath.parse(str(blocker / "files")),
    )
