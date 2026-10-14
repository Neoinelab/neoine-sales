/** 인증·역할 테스트가 함께 쓰는 API 응답 예시(생성된 스키마의 필드 이름과 같다). */

export const ME_ADMIN = { user_id: 'u-1', subject: 'root', email: null, name: '최관리', role: 'admin' }
export const ME_SALES = { user_id: 'u-2', subject: 'kim', email: null, name: '김영업', role: 'sales' }
export const ME_USER = { user_id: 'u-9', subject: 'viewer', email: null, name: '조회자', role: 'user' }
/** 로컬 개발용 로그인으로 들어온 admin(예약 login_id dev-admin의 users 행). */
export const ME_DEV_ADMIN = { user_id: 'u-dev', subject: 'dev-admin', email: null, name: '개발 사용자(admin)', role: 'admin' }

/** 서버가 내려주는 사용자 참조. label은 서버가 만든다(퇴사자는 '이름(퇴사)'). */
export const userRef = (id: string, name: string, resigned = false) => ({
  id,
  name,
  resigned,
  label: resigned ? `${name}(퇴사)` : name,
})

export const asMe = (role: 'admin' | 'sales' | 'user') =>
  ({ admin: ME_ADMIN, sales: ME_SALES, user: ME_USER })[role]

/** /auth/config 응답. 기본은 AD 설정과 관리자가 모두 있는 평상시 상태다. */
export const authConfig = (over: Record<string, boolean> = {}) => ({
  body: {
    dev_login: false,
    directory_login: true,
    needs_directory_setup: false,
    needs_admin_setup: false,
    ...over,
  },
})

/** PUT·POST 설정 계열이 돌려주는 AD 서버 설정 응답. */
export const DIRECTORY_SETTINGS = {
  server_urls: ['ldaps://dc1.corp.test', 'ldaps://dc2.corp.test'],
  use_starttls: false,
  ca_cert_pem: null,
  bind_template: 'CORP\\{login_id}',
  base_dn: 'dc=corp,dc=test',
  user_filter: '(&(objectClass=user)(sAMAccountName={login_id}))',
  display_name_attribute: 'displayName',
  email_attribute: 'mail',
  connect_timeout_seconds: 5,
  receive_timeout_seconds: 10,
  revision: 3,
  updated_at: '2026-05-01T03:00:00Z',
  updated_by: userRef('u-1', '최관리'),
}

export interface UserRow {
  id: string
  login_id: string
  role: string
  display_name: string | null
  email: string | null
  created_at: string
  created_by: ReturnType<typeof userRef>
  last_login_at: string | null
  status: 'active' | 'resigned'
  deleted_at: string | null
  delete_reason: 'resigned' | null
}

export const USER_ROWS: UserRow[] = [
  {
    id: 'u-1',
    login_id: 'root',
    role: 'admin',
    display_name: '최관리',
    email: null,
    created_at: '2026-01-02T00:00:00Z',
    created_by: userRef('u-0', '설정관리'),
    last_login_at: '2026-02-03T04:05:00Z',
    status: 'active',
    deleted_at: null,
    delete_reason: null,
  },
  {
    id: 'u-2',
    login_id: 'kim',
    role: 'sales',
    display_name: '김영업',
    email: 'kim@corp.test',
    created_at: '2026-01-05T00:00:00Z',
    created_by: userRef('u-1', '최관리'),
    last_login_at: null,
    status: 'active',
    deleted_at: null,
    delete_reason: null,
  },
]

/** 퇴사 처리된 사용자 행(status=resigned|all 목록에서만 나온다). */
export const RESIGNED_ROW: UserRow = {
  id: 'u-5',
  login_id: 'old',
  role: 'sales',
  display_name: '이퇴사',
  email: null,
  created_at: '2025-01-05T00:00:00Z',
  created_by: userRef('u-1', '최관리'),
  last_login_at: null,
  status: 'resigned',
  deleted_at: '2026-04-01T09:30:00Z',
  delete_reason: 'resigned',
}
