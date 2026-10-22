import type { DashboardSummary } from '../../shared/model/types'

/**
 * 화면 테스트용 Dashboard 요약. 숫자는 한눈에 보이도록 정했고 항목 사이 관계(합계 = 항목 합, Open 합 = Open 셀 합,
 * 분기 합 = 연 합)를 모두 지킨다. 금액은 원 단위(화면은 천원).
 *
 * Forecast(Lost 제외): pipeline 18/320M, best 6/150M, most_likely 4/90M, commit 3/70M, won 2/40M, open 31/630M
 * Status(Lost 제외, = Open 31/630M + Won 2/40M): prospecting 14/250M … contract_completed 2/40M, 합계 33/670M
 * 분기(Open 합 / Won): Q1 4/100M·1/10M, Q2 6/120M·0, Q3 9/200M·1/30M, Q4 12/210M·0
 */
const cell = (count: number, amount: number) => ({ count, amount })

export function dashboardSummaryFixture(over: Partial<DashboardSummary> = {}): DashboardSummary {
  return {
    asOf: '2026-10-15T09:00:00+09:00',
    today: '2026-10-15',
    period: { year: 2026, quarter: null, from: '2026-01-01', to: '2026-12-31' },
    forecast: {
      columns: [
        { key: 'pipeline', name: 'Pipeline', outcome: 'open', order: 1 },
        { key: 'best', name: 'Best', outcome: 'open', order: 2 },
        { key: 'most_likely', name: 'Most Likely', outcome: 'open', order: 3 },
        { key: 'commit', name: 'Commit', outcome: 'open', order: 4 },
        { key: 'won', name: 'Won', outcome: 'won', order: 5 },
      ],
      cells: {
        pipeline: cell(18, 320_000_000),
        best: cell(6, 150_000_000),
        most_likely: cell(4, 90_000_000),
        commit: cell(3, 70_000_000),
        won: cell(2, 40_000_000),
      },
      openTotal: cell(31, 630_000_000),
    },
    statuses: {
      items: [
        { key: 'prospecting', name: '기회발굴', order: 1, ...cell(14, 250_000_000) },
        { key: 'introduction', name: '제품소개', order: 2, ...cell(6, 110_000_000) },
        { key: 'poc_preparation', name: 'POC준비', order: 3, ...cell(4, 80_000_000) },
        { key: 'poc_completed', name: 'POC완료', order: 4, ...cell(3, 70_000_000) },
        { key: 'technical_evaluation', name: '기술평가', order: 5, ...cell(2, 60_000_000) },
        { key: 'price_negotiation', name: '가격협상', order: 6, ...cell(2, 60_000_000) },
        { key: 'contract_completed', name: '계약완료', order: 7, ...cell(2, 40_000_000) },
      ],
      total: cell(33, 670_000_000),
    },
    quarters: [
      quarter(1, '2026-01-01', '2026-03-31', { pipeline: cell(2, 40_000_000), best: cell(1, 20_000_000), most_likely: cell(0, 0), commit: cell(1, 40_000_000), won: cell(1, 10_000_000) }),
      quarter(2, '2026-04-01', '2026-06-30', { pipeline: cell(4, 60_000_000), best: cell(1, 30_000_000), most_likely: cell(1, 30_000_000), commit: cell(0, 0), won: cell(0, 0) }),
      quarter(3, '2026-07-01', '2026-09-30', { pipeline: cell(5, 100_000_000), best: cell(2, 50_000_000), most_likely: cell(1, 30_000_000), commit: cell(1, 20_000_000), won: cell(1, 30_000_000) }),
      quarter(4, '2026-10-01', '2026-12-31', { pipeline: cell(7, 120_000_000), best: cell(2, 50_000_000), most_likely: cell(2, 30_000_000), commit: cell(1, 10_000_000), won: cell(0, 0) }),
    ],
    attention: {
      staleDays: 14,
      overdue: 4,
      stale: 5,
      closingThisMonth: { year: 2026, month: 10, count: 4 },
      closingThisQuarter: { year: 2026, quarter: 4, count: 7 },
    },
    ...over,
  }
}

function quarter(
  number: 1 | 2 | 3 | 4,
  from: string,
  to: string,
  cells: Record<string, { count: number; amount: number }>,
) {
  const open = ['pipeline', 'best', 'most_likely', 'commit'].map((key) => cells[key] ?? cell(0, 0))
  const openTotal = open.reduce((sum, c) => cell(sum.count + c.count, sum.amount + c.amount), cell(0, 0))
  const won = cells.won ?? cell(0, 0)
  return { quarter: number, from, to, cells, openTotal, total: cell(openTotal.count + won.count, openTotal.amount + won.amount) }
}

/** 조건에 맞는 Deal이 하나도 없을 때의 요약(모든 숫자 0). */
export function emptyDashboardSummary(): DashboardSummary {
  const base = dashboardSummaryFixture()
  const zero = cell(0, 0)
  return {
    ...base,
    forecast: { ...base.forecast, cells: Object.fromEntries(base.forecast.columns.map((c) => [c.key, zero])), openTotal: zero },
    statuses: { items: base.statuses.items.map((i) => ({ ...i, ...zero })), total: zero },
    quarters: base.quarters.map((q) => ({
      ...q,
      cells: Object.fromEntries(base.forecast.columns.map((c) => [c.key, zero])),
      openTotal: zero,
      total: zero,
    })),
    attention: { ...base.attention, overdue: 0, stale: 0, closingThisMonth: { ...base.attention.closingThisMonth, count: 0 }, closingThisQuarter: { ...base.attention.closingThisQuarter, count: 0 } },
  }
}
