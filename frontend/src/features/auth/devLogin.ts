/** 개발용 로그인이 쓰는 예약 login_id(users의 실제 행). 백엔드 DEV_LOGIN_IDS와 같다. */
const DEV_LOGIN_IDS: readonly string[] = ['dev-admin', 'dev-sales', 'dev-user']

/** 개발용 로그인으로 들어온 사용자인지(AD 비밀번호가 없다). */
export function isDevSubject(subject: string): boolean {
  return DEV_LOGIN_IDS.includes(subject)
}
