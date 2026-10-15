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

export const ACTION_TYPES = ['통화', '미팅', '이메일', '데모', '제안', '협상', '계약', '기타'] as const
export type ActionType = (typeof ACTION_TYPES)[number]
export const DEFAULT_ACTION_TYPE: ActionType = '기타'

export const BANT_CATEGORIES = ['budget', 'authority', 'need', 'timeline'] as const
export type BantCategory = (typeof BANT_CATEGORIES)[number]
export const BANT_CATEGORY_NAMES: Record<BantCategory, string> = {
  budget: 'Budget',
  authority: 'Authority',
  need: 'Need',
  timeline: 'Timeline',
}
export const BANT_LABEL_MAX_LENGTH = 50

/** 마지막 갱신 후 이 일수 이상이면 '미업데이트'(Risk). 경고 기준 Admin 설정은 범위 밖이라 상수. */
export const STALE_DAYS = 14

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
]

/** 세션 사용자 id를 보관하는 sessionStorage 키(로그인 유지용, 읽기/쓰기는 try/catch). */
export const SESSION_STORAGE_KEY = 'neoine-mock-user-id'

/** 빠른 로그인 버튼과 시드 사용자 id의 약속. 시드의 사용자 id는 `u-<loginId>`다. */
export const QUICK_LOGIN_USERS: readonly { userId: string; label: string }[] = [
  { userId: 'u-root', label: '관리자 최관리' },
  { userId: 'u-kim', label: '영업 김영업' },
  { userId: 'u-park', label: '영업 박영업' },
  { userId: 'u-han', label: '조회자 한조회' },
]
