import { useSearchParams } from 'react-router'
import { useDashboardSummary } from '../../data/dashboard'
import { useToday } from '../../data/today'
import { useVendors } from '../../data/vendors'
import type { DashboardSummary } from '../../shared/model/types'
import { effectiveVendorFilter } from '../../shared/model/vendorFilter'
import { ErrorBanner } from '../../shared/ui/ErrorBanner'
import { Tabs } from '../../shared/ui/Tabs'
import { DrillEnabledContext } from './DrillLink'
import { DashboardFilterBar } from './DashboardFilters'
import { filtersFromParams, paramsFromFilters, queryOf, selectedQuarterOf, type DashboardFilters, type DashboardTab } from './dashboardParams'
import type { DashboardScope } from './drillDown'
import { ForecastTab } from './ForecastTab'
import { StatusTab } from './StatusTab'
import './dashboard.css'

const TABS = [
  { id: 'status', label: 'Status' },
  { id: 'forecast', label: 'Forecast' },
] as const

const isTab = (id: string): id is DashboardTab => TABS.some((t) => t.id === id)

const sumCount = (cells: Record<string, { count: number }>): number => Object.values(cells).reduce((sum, c) => sum + c.count, 0)

/** 탭에 보일 Deal이 하나도 없는지. 주의 필요 Deal 타일은 기간과 무관해 판단에 넣지 않는다. */
function isEmpty(summary: DashboardSummary, tab: DashboardTab): boolean {
  const tilesEmpty = sumCount(summary.forecast.cells) === 0
  return tab === 'status'
    ? tilesEmpty && summary.statuses.total.count === 0
    : tilesEmpty && summary.quarters.every((q) => q.total.count === 0 && sumCount(q.cells) === 0)
}

/**
 * Dashboard `/dashboard`. 필터는 URL 쿼리가 가진다(탭 포함). Quarter는 Status 탭에만 적용되므로 Quarter를 고르면 두 탭의 요청이 다르다.
 * 숫자를 누르면 Deal 목록(`/deals?...`)으로 이동하고 목록 조건이 자동으로 채워진다. 모든 로그인 사용자가 조회하며 쓰기 동작은 없다.
 */
export function DashboardPage() {
  const [params, setParams] = useSearchParams()
  const { year: thisYear, today: clientToday } = useToday()
  const filters = filtersFromParams(params, thisYear)
  const vendors = useVendors().data
  // 표시와 조회 조건을 맞춘다: 목록에 없는 Vendor는 조회·이동 조건에서 제외한다.
  const vendor = effectiveVendorFilter(vendors, filters.vendor).vendorId
  const effective: DashboardFilters = { ...filters, vendor }
  const summary = useDashboardSummary(queryOf(effective))
  // Forecast 탭은 Quarter 필터를 쓰지 않는다(연간 범위). 선택 분기는 하단 영역과 강조에만 쓴다.
  const quarter = filters.tab === 'status' ? effective.quarter : undefined
  const scope: DashboardScope = { year: effective.year, quarter, ownerId: effective.ownerId, vendor }

  const update = (patch: Partial<DashboardFilters>) => setParams(paramsFromFilters({ ...filters, ...patch }))

  const data = summary.data
  // 새 조건의 응답이 오기 전에는 이전 응답(placeholder)이 남아 있으므로 불러오는 중으로 보고 Drill-down 링크를 내지 않는다.
  const loading = summary.isPending || summary.isPlaceholderData
  // Selected Quarter 기본값은 서버 업무 날짜(응답 today) 기준. 응답 전에는 클라이언트 날짜로 대체한다.
  const today = data?.today ?? clientToday
  return (
    <section className="db-page">
      <h1>Dashboard</h1>
      <DashboardFilterBar filters={filters} onChange={update} />
      <ErrorBanner error={summary.error} />
      {loading && (
        <p role="status" className="hint">
          불러오는 중…
        </p>
      )}
      {data && (
        <>
          <p className="hint">기간은 Expected Close 기준이며 금액 단위는 천원입니다. 기준일 {data.today}</p>
          {isEmpty(data, filters.tab) && <p className="db-empty">조건에 맞는 Deal이 없습니다.</p>}
        </>
      )}
      <DrillEnabledContext.Provider value={!loading}>
<Tabs label="Dashboard 보기" tabs={TABS} active={filters.tab} onChange={(id) => isTab(id) && update({ tab: id })}>
        {data && (filters.tab === 'status' ? <StatusTab summary={data} scope={scope} /> : <ForecastTab summary={data} scope={scope} selectedQuarter={selectedQuarterOf(filters, today)} onSelectQuarter={(sq) => update({ selectedQuarter: sq })} />)}
      </Tabs>
      </DrillEnabledContext.Provider>
    </section>
  )
}
