# SOLID 점검표

## 목차

1. 사용 방법
2. 원칙별 위반 신호와 수정
3. 코드 리뷰 질문

## 1. 사용 방법

변경분(diff)을 아래 표의 "위반 신호"와 대조한다. 신호가 있으면 "수정 방향"을 따른다. 애매하면 위반으로 단정하지 말고 근거(파일:줄)와 함께 "확인 필요"로 기록한다. 파이썬은 멀티 패러다임 언어이므로 상태 없는 변환·유틸까지 억지로 클래스로 만들지 않는다(모듈 수준 순수 함수가 더 파이썬답다).

## 2. 원칙별 위반 신호와 수정

### S: 단일 책임 (변경 이유가 하나)

| 위반 신호 | 수정 방향 |
| --- | --- |
| 클래스 이름에 `Manager`, `Helper`, `Util`, `And` | 책임 단위로 분리하고 역할을 드러내는 이름 사용 |
| 한 클래스가 규칙 + DB + 알림을 모두 처리 | 규칙은 도메인, 영속화는 Repository, 알림은 Notifier |
| 파일이 길어짐(`check_file_length.py`가 경고) | 책임별로 모듈 분리(압축 금지) |
| import가 DB·HTTP·메일 라이브러리에 걸쳐 있음 | 계층 분리, Port로 격리 |

### O: 개방-폐쇄 (확장에 열고 수정에 닫는다)

| 위반 신호 | 수정 방향 |
| --- | --- |
| 기능 추가 때마다 `if/elif` 체인이나 `isinstance` 분기를 수정 | 전략(Strategy)으로 교체: `Protocol` + 구현 클래스 목록 주입 |

```python
class DiscountPolicy(Protocol):
    def apply(self, order: Order) -> Money: ...

class PricingService:
    def __init__(self, policies: Sequence[DiscountPolicy]) -> None:
        self._policies = policies          # 새 정책 추가 시 이 코드는 불변
```

### L: 리스코프 치환 (하위 타입은 계약을 지킨다)

| 위반 신호 | 수정 방향 |
| --- | --- |
| 오버라이드가 `NotImplementedError`를 던진다 | 인터페이스를 쪼개거나(ISP) 상속을 합성으로 |
| 구현체마다 예외·반환 규약이 다르다 | Port 계약(예: 없으면 `NotFoundError`)을 문서화하고 **계약 테스트**를 Fake와 실제 구현 모두에 실행 |

### I: 인터페이스 분리 (쓰지 않는 메서드에 의존하지 않는다)

| 위반 신호 | 수정 방향 |
| --- | --- |
| 구현체의 절반 메서드가 `pass` | 역할별 Protocol로 분리(`Reader`, `Writer`) |
| 테스트 Fake 작성이 번거롭다 | Port가 너무 크다는 신호, 작게 분리 |

### D: 의존성 역전 (둘 다 추상화에 의존)

| 위반 신호 | 수정 방향 |
| --- | --- |
| 유스케이스 안에서 `SqlRepo()`, `requests.get()` 직접 생성/호출 | Port 정의 + 생성자 주입 |
| `domain`에서 `sqlalchemy`/`fastapi` import | domain 순수성 회복(`lint-imports` 계약 2) |
| `application`이 `infra`를 import | Port로 역전(`lint-imports` 계층 계약) |

## 3. 코드 리뷰 질문

- 이 클래스가 바뀌어야 하는 이유가 둘 이상인가?
- 새 변형(정책, 어댑터)을 추가할 때 기존 코드를 수정해야 하는가?
- 이 구현체를 Fake로 바꿔도 호출부가 그대로 동작하는가(치환 가능한가)?
- 호출부가 쓰지 않는 메서드까지 의존하는가?
- 의존 방향이 안쪽(domain)을 향하는가? 안쪽이 바깥 기술을 아는가?
- 규칙이 엔티티에 있는가, 서비스의 `if`에 흩어져 있는가?
