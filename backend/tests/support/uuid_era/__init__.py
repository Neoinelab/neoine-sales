"""UUID 시절(`e8c2b4f6a1d9` 이하) 스키마에 원시 SQL로 행을 넣는 도우미.

BIGINT id 리비전(`bigint_ids_revision()`)은 모든 앱 테이블을 새로 만들므로, 그 이전 리비전을
검증하는 테스트(과거 리비전 target 고정 시나리오와 그 Given 행)는 이 UUID 도우미를 그대로 쓴다.
head 스키마(정수 id)용 도우미는 `tests/support/{head,attachment,vendor,alert}_rows.py`다.
"""
