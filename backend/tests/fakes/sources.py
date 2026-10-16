"""UploadSource 대역: 큰 본문을 메모리에 미리 만들지 않고 흘려 주는 원본과, 읽다가 실패하는 원본."""


class ClientGone(Exception):  # noqa: N818 - 업로드 중 연결이 끊긴 상황(Starlette ClientDisconnect 대역)
    """OSError가 아닌 읽기 실패. 저장소 구현은 이를 바꾸지 않고 그대로 올려야 한다."""


class ZeroSource:
    """`total` 바이트의 0을 요청한 크기(없으면 64KiB)씩 돌려준다."""

    def __init__(self, total: int) -> None:
        self._left = total

    async def read(self, size: int = -1) -> bytes:
        step = 64 * 1024 if size < 0 else size
        count = min(step, self._left)
        self._left -= count
        return bytes(count)


class FailingSource:
    """처음 `good_chunks`번은 데이터를 주고 그다음 읽기에서 `error`를 던진다(연결 끊김 등)."""

    def __init__(self, error: BaseException, *, good_chunks: int = 1, chunk: int = 1024) -> None:
        self._error = error
        self._left = good_chunks
        self._chunk = chunk

    async def read(self, size: int = -1) -> bytes:
        if self._left == 0:
            raise self._error
        self._left -= 1
        return b"x" * self._chunk
