"""DealCodeSuffixSource Port의 테스트용 구현.

- 인자가 없으면 호출할 때마다 겹치지 않는 4자리 suffix(`0001`, `0002`, ...)를 낸다.
- suffix를 주면 그 열을 순서대로 내고, 열이 끝나면 마지막 값을 계속 반복한다(충돌 시나리오용).
  결과(저장된 code)를 보고 검증하며 호출 횟수는 단언하지 않는다.
"""


class FakeDealCodeSuffixSource:
    def __init__(self, *suffixes: str) -> None:
        self._suffixes = list(suffixes)
        self._index = 0
        self._counter = 0

    def next_suffix(self) -> str:
        if not self._suffixes:
            self._counter += 1
            return f"{self._counter:04d}"
        suffix = self._suffixes[min(self._index, len(self._suffixes) - 1)]
        self._index += 1
        return suffix
