"""ldap3 MOCK_SYNC 기반 가짜 디렉터리. 실제 AD·네트워크·TLS 없이 어댑터의 LDAP 흐름만 검증한다.

한계: 모의 서버는 DN으로 하는 simple bind만 지원하고 TLS·StartTLS 협상·장애 조치를 흉내 내지 않는다.
RootDSE(빈 DN) 항목도 지원하지 않으므로, `RecordingConnection.search`가 "search_base가 빈 문자열인
BASE 검색"을 가로채 `MockDirectory.root_dse` 속성으로 응답한다(ldap3 응답과 같은 모양의
`searchResEntry`). 어댑터는 `connection.search("", "(objectClass=*)", BASE, attributes=[...])` 뒤
`connection.response`/`connection.result`를 읽기만 하면 된다.
연결 팩토리 시그니처는 `(settings, bind_user, password) -> ldap3.Connection`(열지 않은 연결)이다.
서비스 계정은 MockDirectory가 기본으로 만든다(`BIND_ACCOUNT`/`BIND_PASSWORD`).
"""

import threading
import time
import uuid
from typing import TYPE_CHECKING

from ldap3 import BASE, MOCK_SYNC, Connection, Server

from tests.factories_auth import BASE_DN, BIND_ACCOUNT, BIND_PASSWORD

if TYPE_CHECKING:
    from app.domain.directory.settings import DirectorySettings


class RecordingConnection(Connection):  # type: ignore[misc]
    """MOCK_SYNC 연결. 호출한 메서드·스레드를 기록하고, 메서드별로 예외나 결과 코드를 주입한다."""

    def __init__(
        self, server: Server, user: str | None, password: str | None, owner: MockDirectory
    ) -> None:
        super().__init__(
            server,
            user=user,
            password=password,
            client_strategy=MOCK_SYNC,
            raise_exceptions=False,
            read_only=True,
            auto_bind=False,
        )
        self._owner = owner
        # ldap3은 인스턴스 속성으로 strategy.open을 덮어쓰므로, open은 인스턴스에서 감싼다.
        self._strategy_open = self.open  # type: ignore[has-type]
        self.open = self._recording_open
        self.search_args: list[dict[str, object]] = []

    def _enter(self, name: str) -> None:
        self._owner.log.append((name, threading.get_ident()))
        if name in self._owner.faults:
            raise self._owner.faults[name]

    def _recording_open(self, *args: object, **kwargs: object) -> None:
        self._enter("open")
        self._strategy_open(*args, **kwargs)

    def start_tls(self, *args: object, **kwargs: object) -> bool:
        self._enter("start_tls")
        return bool(super().start_tls(*args, **kwargs))

    def bind(self, *args: object, **kwargs: object) -> bool:
        self._enter("bind")
        if self._owner.delay:
            time.sleep(self._owner.delay)
        code = self._owner.bind_codes_by_user.get(str(self.user), self._owner.bind_code)
        if code is not None:
            self.result = {"result": code, "description": "injected", "message": ""}
            return False
        return bool(super().bind(*args, **kwargs))

    def search(self, *args: object, **kwargs: object) -> bool:
        self._enter("search")
        names = (
            "search_base",
            "search_filter",
            "search_scope",
            "dereference_aliases",
            "attributes",
        )
        recorded = {**dict(zip(names, args, strict=False)), **kwargs}
        self.search_args.append(recorded)
        if recorded.get("search_base") == "" and recorded.get("search_scope") == BASE:
            return self._root_dse_search()
        code = self._owner.user_search_code
        if (
            code is not None
        ):  # 실제 AD는 결과 코드 4(sizeLimitExceeded)와 함께 항목을 돌려줄 수 있다
            super().search(*args, **kwargs)
            self.result = {"result": code, "description": "injected", "message": ""}
            return False
        return bool(super().search(*args, **kwargs))

    def _root_dse_search(self) -> bool:
        """RootDSE 읽기. 모의 서버가 빈 DN을 못 다루므로 root_dse 속성으로 직접 응답한다."""
        root = self._owner.root_dse
        if root is None:  # RootDSE를 읽을 권한이 없거나 서버가 거부하는 상황
            self.result = {"result": 50, "description": "insufficientAccessRights", "message": ""}
            self.response = []
            return False
        self.result = {"result": 0, "description": "success", "message": ""}
        self.response = [
            {"type": "searchResEntry", "dn": "", "attributes": dict(root), "raw_attributes": {}}
        ]
        return True

    def unbind(self, *args: object, **kwargs: object) -> bool:
        self._owner.log.append(("unbind", threading.get_ident()))
        return bool(super().unbind(*args, **kwargs))


def user_attributes(sam: str, password: str, **extra: str) -> dict[str, str | list[str]]:
    """AD 사용자 항목의 기본 속성. extra로 displayName, mail 같은 속성을 더한다."""
    return {"objectClass": ["user"], "userPassword": password, "sAMAccountName": sam, **extra}


class MockDirectory:
    """사용자 항목을 가진 가짜 디렉터리와, 어댑터에 주입할 연결 팩토리."""

    def __init__(self) -> None:
        self.server = Server(f"mock-{uuid.uuid4().hex}")
        self._seed = Connection(self.server, client_strategy=MOCK_SYNC)
        self.faults: dict[str, BaseException] = {}  # 메서드 이름 -> 그 호출에서 던질 예외
        self.bind_code: int | None = None  # 설정하면 모든 bind가 이 LDAP 결과 코드로 실패한다
        # 바인드 계정(DN)별 결과 코드. bind_code보다 우선한다(서비스 계정만/사용자만 실패시킬 때)
        self.bind_codes_by_user: dict[str, int] = {}
        # 설정하면 사용자 검색이 이 결과 코드로 끝난다(항목은 그대로 응답에 남는다)
        self.user_search_code: int | None = None
        # RootDSE 속성. None이면 RootDSE 읽기가 거부된다
        self.root_dse: dict[str, str | list[str]] | None = {"defaultNamingContext": BASE_DN}
        self.delay = 0.0  # bind에서 기다릴 시간(초). 이벤트 루프 차단 검사용
        self.log: list[tuple[str, int]] = []  # (호출한 메서드, 스레드 id)
        self.connections: list[RecordingConnection] = []
        self.factory_calls: list[tuple[DirectorySettings, str | None, str | None]] = []
        self.factory_threads: list[int] = []
        self.add_entry(
            BIND_ACCOUNT, user_attributes("svc-sales", BIND_PASSWORD, displayName="서비스 계정")
        )

    def add_entry(self, dn: str, attributes: dict[str, str | list[str]]) -> None:
        self._seed.strategy.add_entry(dn, attributes)

    def add_user(
        self,
        login_id: str,
        password: str,
        *,
        display_name: str | None = None,
        mail: str | None = None,
    ) -> str:
        """`cn=<login_id>,ou=users,<BASE_DN>` 항목을 만들고 DN을 돌려준다."""
        extra: dict[str, str] = {}
        if display_name is not None:
            extra["displayName"] = display_name
        if mail is not None:
            extra["mail"] = mail
        dn = f"cn={login_id},ou=users,{BASE_DN}"
        self.add_entry(dn, user_attributes(login_id, password, **extra))
        return dn

    def factory(
        self, settings: DirectorySettings, user: str | None, password: str | None
    ) -> RecordingConnection:
        self.factory_calls.append((settings, user, password))
        self.factory_threads.append(threading.get_ident())
        connection = RecordingConnection(self.server, user, password, self)
        self.connections.append(connection)
        return connection

    @property
    def calls(self) -> list[str]:
        return [name for name, _ in self.log]
