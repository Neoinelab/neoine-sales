/** 도메인 상수(A-0 계약). 값은 PRD 확정 결정(11.1)과 계획 4.2/6장 기준. */

/** Status 시스템 코드 key. 이름이 바뀌어도 key로 판단한다. */
export const STATUS_CONTRACT_COMPLETED = 'contract_completed'
/** Forecast 시스템 코드 key. */
export const FORECAST_WON = 'won'
export const FORECAST_LOST = 'lost'

/** 기본 Status key(신규 Deal 기본값, 시드 순서와 같다). */
export const STATUS_PROSPECTING = 'prospecting'
export const FORECAST_PIPELINE = 'pipeline'

/** Deal code 형식: 등록일(YYYYMMDD) + '-' + 대문자/숫자 4자리. 예: 20261015-A7K2 */
export const DEAL_CODE_PATTERN = /^\d{8}-[A-Z0-9]{4}$/

/** Action 유형 이름 최대 길이(서버와 같다). */
export const ACTION_TYPE_NAME_MAX_LENGTH = 50

/** Deal Solution 텍스트 최대 길이(서버와 같다). 목록 URL 필터도 이 길이를 넘으면 무시한다. */
export const SOLUTION_MAX_LENGTH = 200

export const BANT_CATEGORIES = ['budget', 'authority', 'need', 'timeline'] as const
export type BantCategory = (typeof BANT_CATEGORIES)[number]
export const BANT_CATEGORY_NAMES: Record<BantCategory, string> = {
  budget: 'Budget',
  authority: 'Authority',
  need: 'Need',
  timeline: 'Timeline',
}
export const BANT_LABEL_MAX_LENGTH = 50

/** 미업데이트 기준 기본값(일). 서버 기본값과 같고 Fake 기본값·화면 초기값에만 쓴다. 실제 기준은 경고 기준 설정. */
export const DEFAULT_STALE_DAYS = 14
/** 경고 기준 허용 범위(서버와 같은 1~365 정수). */
export const STALE_DAYS_MIN = 1
export const STALE_DAYS_MAX = 365
export const STALE_DAYS_RANGE_MESSAGE = '미업데이트 기준은 1~365일 사이의 정수로 입력하세요.'

/** 목록 페이지 크기. */
export const DEAL_PAGE_SIZE = 20

/** 첨부 파일 제한. */
export const MAX_FILE_BYTES = 100 * 1024 * 1024
export const MAX_FILE_DESCRIPTION = 100
/** 실행·설치 파일 확장자(소문자, 점 제외). 마지막 확장자 기준, 대소문자 무시. */
export const BLOCKED_EXTENSIONS: readonly string[] = [
  'exe',
  'msi',
  'bat',
  'cmd',
  'sh',
  'ps1',
  'jar',
  'com',
  'scr',
  'dmg',
  'pkg',
  'deb',
  'rpm',
  'vbs',
  'vbe',
  'wsf',
  'wsh',
  'hta',
  'cpl',
  'msp',
  'mst',
  'apk',
  'appimage',
  'run',
]

/**
 * 빠른 로그인 버튼과 개발용 사용자 id의 약속. 사용자 id는 Fake 시드의 사용자 id(정수)와 같다(root 1, kim 2, han 6).
 * `role`은 실제 서버의 dev 로그인(역할로 로그인)이 쓴다. 서버는 역할당 개발용 계정 하나로 로그인시킨다.
 */
export const QUICK_LOGIN_USERS: readonly { userId: number; label: string; role: 'admin' | 'sales' | 'user' }[] = [
  { userId: 1, label: '관리자', role: 'admin' },
  { userId: 2, label: '영업', role: 'sales' },
  { userId: 6, label: '조회자', role: 'user' },
]

/**
 * 삭제할 수 없는 시스템 연결 코드 key(서버와 같은 5개). 이름·순서는 바꿀 수 있다.
 * 서버가 정본이고 화면은 응답의 `locked`를 쓴다. 이 상수는 Fake 시드와 계약 테스트가 서버와 맞추는 데 쓴다.
 */
export const LOCKED_KEYS = {
  status: ['prospecting', 'contract_completed'],
  forecast: ['pipeline', 'won', 'lost'],
} as const
