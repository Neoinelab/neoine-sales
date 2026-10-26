import { periodOf } from '../shared/model/period'

/**
 * 조건 없이 목록에 들어올 때 붙는 기본 조건 주소(올해만, Quarter 전체). now는 앱 시계 값('YYYY-MM-DDT…+09:00')이고 날짜 부분을 그대로 쓴다.
 * extra는 기본 조건 뒤에 붙는 쿼리(예: 'sort=owner&order=asc').
 */
export function defaultDealsUrl(now: string, extra = ''): string {
  const { year } = periodOf(now.slice(0, 10))
  return `/deals?year=${year}${extra ? `&${extra}` : ''}`
}

/** 시계를 고정하지 않은 테스트용: 기본 조건 주소의 모양. */
export const DEFAULT_DEALS_URL_PATTERN = /^\/deals\?year=\d{4}$/
