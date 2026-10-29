"""인증 유스케이스가 쓰는 고정 문구. 계정 존재 여부를 드러내지 않도록 실패 문구는 하나다."""

from app.application.auth.warning_stage import DirectoryWarningStage

LOGIN_FAILED = "아이디 또는 비밀번호가 올바르지 않습니다"
LOGIN_REQUIRED = "로그인이 필요합니다"
DIRECTORY_NOT_CONFIGURED = "AD 서버가 아직 등록되지 않았습니다"
SETUP_CLOSED = "이미 관리자가 등록되어 최초 설정을 진행할 수 없습니다"
DIRECTORY_FIRST = "먼저 AD 서버를 등록하세요"
STORAGE_FIRST = "파일 저장 위치를 먼저 설정하세요."

_PREFIX = "이전에 로그인한 비밀번호로 로그인했습니다."

# admin이 대체 로그인으로 들어왔을 때 로그인 뒤 팝업에 그대로 보이는 문구
FALLBACK_MESSAGES: dict[DirectoryWarningStage, str] = {
    DirectoryWarningStage.NOT_CONFIGURED: (
        f"AD 설정이 없어 {_PREFIX} Admin > 외부연동에서 AD 설정을 등록하세요."
    ),
    DirectoryWarningStage.CONNECT: (
        f"AD 서버에 연결하지 못해 {_PREFIX} 호스트·포트·방화벽을 확인하세요."
    ),
    DirectoryWarningStage.TLS: (
        f"AD 보안 연결(SSL/StartTLS)을 맺지 못해 {_PREFIX} 보안 연결 방식과 포트를 확인하세요."
    ),
    DirectoryWarningStage.SERVICE_BIND: (
        f"바인드 계정으로 AD에 로그인하지 못해 {_PREFIX} 바인드 계정과 비밀번호를 확인하세요."
    ),
    DirectoryWarningStage.BASE_DN: (
        f"AD 검색 기준(Base DN)으로 사용자를 찾지 못해 {_PREFIX} AD 설정을 다시 저장하세요."
    ),
    DirectoryWarningStage.SEARCH: (
        f"사용자 필터에 맞는 AD 사용자가 둘 이상이라 {_PREFIX} 사용자 필터를 확인하세요."
    ),
    DirectoryWarningStage.CREDENTIAL_UNREADABLE: (
        "저장된 바인드 비밀번호를 읽을 수 없어(암호화 키 변경 여부 확인) "
        f"{_PREFIX} 외부연동에서 바인드 비밀번호를 다시 입력하세요."
    ),
    DirectoryWarningStage.UNKNOWN: (
        f"AD 서버와 통신하지 못해 {_PREFIX} AD 설정과 서버 상태를 확인하세요."
    ),
}
