/** 인증·역할 테스트가 함께 쓰는 API 응답 예시(생성된 스키마의 필드 이름과 같다). */

export const ME_ADMIN = { subject: 'root', email: null, name: '최관리', role: 'admin' }
export const ME_SALES = { subject: 'kim', email: null, name: '김영업', role: 'sales' }
export const ME_USER = { subject: 'viewer', email: null, name: '조회자', role: 'user' }
/** 로컬 개발용 로그인으로 들어온 admin(subject가 dev:로 시작한다). */
export const ME_DEV_ADMIN = { subject: 'dev:admin', email: null, name: '개발 사용자(admin)', role: 'admin' }

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
  updated_by: 'root',
}

export interface UserRow {
  id: string
  login_id: string
  role: string
  display_name: string | null
  email: string | null
  created_at: string
  created_by: string
  last_login_at: string | null
}

export const USER_ROWS: UserRow[] = [
  {
    id: 'u-1',
    login_id: 'root',
    role: 'admin',
    display_name: '최관리',
    email: null,
    created_at: '2026-01-02T00:00:00Z',
    created_by: 'setup',
    last_login_at: '2026-02-03T04:05:00Z',
  },
  {
    id: 'u-2',
    login_id: 'kim',
    role: 'sales',
    display_name: '김영업',
    email: 'kim@corp.test',
    created_at: '2026-01-05T00:00:00Z',
    created_by: 'root',
    last_login_at: null,
  },
]
