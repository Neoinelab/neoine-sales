import type { Role } from '../shared/model/types'

export const OPEN_FORECAST_SEARCH = 'forecast=best%2Ccommit%2Cmost_likely%2Cpipeline'

/**
 * 조건 없이 목록에 들어올 때 붙는 기본 조건 주소(DL-R19). 연도 전체(`year=all`)이고 Quarter는 없다.
 * sales만 '내 딜만'(`mine=1`)이 더해진다. 화면 테스트의 기본 로그인 역할이 sales라 role 기본값도 sales다.
 * now는 호출부 호환용으로 받지만 기본 조건이 날짜와 무관해져 쓰지 않는다.
 * extra는 기본 조건 뒤에 붙는 쿼리(예: 'sort=owner&order=asc').
 */
export function defaultDealsUrl(_now?: string, extra = '', role: Role = 'sales'): string {
  const mine = role === 'sales' ? '&mine=1' : ''
  return `/deals?year=all${mine}&${OPEN_FORECAST_SEARCH}${extra ? `&${extra}` : ''}`
}

/** 시계를 고정하지 않은 테스트용: 기본 조건 주소의 정확한 모양. sales는 `&mine=1`이 필수이고 그 외 역할은 `mine`이 없어야 한다. */
export function defaultDealsUrlPattern(role: Role): RegExp {
  return new RegExp(`^${defaultDealsUrl(undefined, '', role).replace('?', '\\?')}$`)
}
