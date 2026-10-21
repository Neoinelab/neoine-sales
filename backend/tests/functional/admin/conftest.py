"""admin feature(코드·BANT Label) 시나리오 공통 설명.

기본 코드(Status 7·Forecast 6)와 기본 Label 23개는 마이그레이션이 넣는 시드다. 시나리오가 끝날
때마다 시드 상태로 되돌리는 일은 모든 feature가 공유하는 `tests/functional/conftest.py`의 `api`
fixture가 맡는다(`restore_default_catalog`). 마이그레이션 시드 자체를 보는 시나리오는 같은 파일의
`fresh_api`(마이그레이션만 적용한 새 임시 DB)를 쓴다. `test_catalog_seed.py`가 방금 마이그레이션한
새 DB에서 시드를 같은 표와 대조한다.
"""
