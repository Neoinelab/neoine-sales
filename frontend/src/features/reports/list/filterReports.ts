import type { SavedReportSummary } from '../../../shared/model/reportTypes'

/** 이름·설명 부분 일치(대소문자 무시, 앞뒤 공백 제외)와 "내가 만든 리포트" 거르기. 서버 순서를 그대로 둔다. */
export function filterReports(items: readonly SavedReportSummary[], filter: { q: string; mine: boolean }, viewerId: number): SavedReportSummary[] {
  const needle = filter.q.trim().toLowerCase()
  return items.filter((item) => {
    if (filter.mine && item.owner.id !== viewerId) return false
    return needle === '' || item.name.toLowerCase().includes(needle) || item.description.toLowerCase().includes(needle)
  })
}
