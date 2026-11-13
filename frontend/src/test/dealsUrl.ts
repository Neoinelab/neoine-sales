import { periodOf } from '../shared/model/period'
import type { Role } from '../shared/model/types'

/**
 * 조건 없이 목록에 들어올 때 붙는 기본 조건 주소. now는 앱 시계 값('YYYY-MM-DDT…+09:00')이고 날짜 부분을 그대로 쓴다.
 * 올해(Quarter 전체)에 sales만 '내 딜만'(`mine=1`)이 더해진다. 화면 테스트의 기본 로그인 역할이 sales라 role 기본값도 sales다.
 * extra는 기본 조건 뒤에 붙는 쿼리(예: 'sort=owner&order=asc').
 */
export function defaultDealsUrl(now: string, extra = '', role: Role = 'sales'): string {
  const { year } = periodOf(now.slice(0, 10))
  const mine = role === 'sales' ? '&mine=1' : ''
  return `/deals?year=${year}${mine}${extra ? `&${extra}` : ''}`
}

/** 시계를 고정하지 않은 테스트용: 기본 조건 주소의 정확한 모양. sales는 `&mine=1`이 필수이고 그 외 역할은 `mine`이 없어야 한다. */
export function defaultDealsUrlPattern(role: Role): RegExp {
  return role === 'sales' ? /^\/deals\?year=\d{4}&mine=1$/ : /^\/deals\?year=\d{4}$/
}
