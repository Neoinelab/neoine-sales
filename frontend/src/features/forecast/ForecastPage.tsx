import { useSearchParams } from 'react-router'
import { useForecastSnapshotSummary, useForecastSummary } from '../../data/forecast'
import { useUserOptions } from '../../data/users'
import { userLabel } from '../../shared/model/period'
import { useVendors } from '../../data/vendors'
import { useToday } from '../../data/today'
import { formatStamp } from '../../shared/format'
import { ErrorBanner } from '../../shared/ui/ErrorBanner'
import type { ForecastSummary } from '../../shared/model/types'
import { effectiveVendorFilter } from '../../shared/model/vendorFilter'
import { ForecastFilterBar } from './ForecastFilters'
import { filtersFromParams, paramsFromFilters, queryOf, type ForecastFilters } from './forecastParams'
import { OwnerDeals } from './OwnerDeals'
import { QuarterCards } from './QuarterCards'
import { SummaryTable } from './SummaryTable'
import './forecast.css'

/** 집계 기준 문구. 서버가 준 시각을 그 오프셋 그대로 보인다. */
function basisText(summary: ForecastSummary): string {
  const stamp = formatStamp(summary.asOf)
  return summary.basis === 'snapshot' ? `기준: ${summary.snapshotPeriod ?? ''} 월말(생성 ${stamp})` : `기준: 지금(${stamp})`
}

/**
 * Forecast `/forecast`. 6.6
 * 필터는 URL 쿼리가 가진다. 담당자 선택(`sel`)도 URL에 두어 Deal 상세에서 돌아와도 유지된다.
 * 모든 로그인 사용자가 조회하고 쓰기 동작은 없다.
 */
export function ForecastPage() {
  const [params, setParams] = useSearchParams()
  const { year: thisYear } = useToday()
  const filters = filtersFromParams(params, thisYear)
  const vendors = useVendors().data
  // 표시와 조회 조건을 맞춘다: 목록에 없는 Vendor는 조회에서 제외한다.
  const queryFilters = { ...filters, vendor: effectiveVendorFilter(vendors, filters.vendor).vendorId }
  const users = useUserOptions({ includeResigned: true }).data
  const live = useForecastSummary(queryOf(queryFilters), filters.snap === undefined)
  // 스냅숏에는 Vendor 조건이 없다(URL의 vendor는 보내지 않는다).
  const snapshotQuery = queryOf({ ...filters, vendor: undefined })
  const snapshot = useForecastSnapshotSummary(filters.snap, snapshotQuery)
  const summary = filters.snap === undefined ? live : snapshot

  const update = (patch: Partial<ForecastFilters>) => {
    setParams(paramsFromFilters({ ...filters, ...patch }))
  }

  const data = summary.data
  const isEmpty = data !== undefined && data.rows.length === 0
  // 조건에 Deal이 없어 요약 행이 없는 담당자도 이름으로 보인다(사용자 목록에서 찾는다).
  const selectedUser = users?.find((u) => u.id === filters.selectedId)
  const selectedName = data?.rows.find((r) => r.ownerId === filters.selectedId)?.ownerName ?? (selectedUser && userLabel(selectedUser))

  return (
    <section className="fc-page">
      <h1>Forecast</h1>
      <ForecastFilterBar filters={filters} onChange={update} />
      <ErrorBanner error={summary.error} />
      {summary.isPending && (
        <p role="status" className="hint">
          불러오는 중…
        </p>
      )}
      {data && <p className="hint">{basisText(data)}</p>}
      {data && !isEmpty && (
        <>
          <QuarterCards summary={data} filters={filters} />
          <SummaryTable
            summary={data}
            selectedId={filters.snap === undefined ? filters.selectedId : undefined}
            onSelect={filters.snap === undefined ? (selectedId) => update({ selectedId }) : undefined}
          />
        </>
      )}
      {isEmpty && <p className="fc-empty">조건에 맞는 Deal이 없습니다.</p>}
      {filters.snap === undefined && filters.selectedId && data && (
        <OwnerDeals
          ownerId={filters.selectedId}
          ownerName={selectedName ?? '선택한 담당자'}
          filters={queryFilters}
          columns={data.columns}
          openTotal={data.rows.find((r) => r.ownerId === filters.selectedId)?.total}
          onClear={() => update({ selectedId: undefined })}
        />
      )}
    </section>
  )
}
