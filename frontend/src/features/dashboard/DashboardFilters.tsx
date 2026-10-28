import { useYearOptions } from '../../data/dealYears'
import { useId } from 'react'
import { useVendors } from '../../data/vendors'
import { parseId } from '../../shared/model/ids'
import { QUARTERS, toggleQuarter } from '../../shared/model/quarterSet'
import { ErrorBanner } from '../../shared/ui/ErrorBanner'
import { SelectField } from '../../shared/ui/fields'
import { UserSelect } from '../../shared/ui/UserSelect'
import type { TabFilters } from './dashboardParams'

interface Props {
  /** 활성 탭의 조건. */
  filters: TabFilters
  onChange: (patch: Partial<TabFilters>) => void
}

const textOf = (id: number | undefined): string => (id === undefined ? '' : String(id))

/** Dashboard 필터(활성 탭 조건): 연도 / Quarter(Q1~Q4 토글, 여러 개, 없음=넷 다=전체) / 담당자 / Vendor(기간은 Expected Close 기준). 값은 URL이 가진다(제어 컴포넌트). */
export function DashboardFilterBar({ filters, onChange }: Props) {
  const quarterLabelId = useId()
  const yearOptions = useYearOptions(filters.year)
  const vendorsQuery = useVendors()
  const vendors = vendorsQuery.data ?? []
  const loaded = vendorsQuery.data !== undefined
  // 목록이 로드된 뒤 목록에 없는 id는 '전체'로 보인다. 목록이 없는 동안(로딩·오류)에는 URL 값을 '선택한 Vendor'로 보인다.
  const vendorValue = !loaded ? textOf(filters.vendor) : vendors.some((v) => v.id === filters.vendor) ? textOf(filters.vendor) : ''

  return (
    <form className="filters db-filters" aria-label="Dashboard 필터" onSubmit={(e) => e.preventDefault()}>
      <SelectField label="연도" name="year" value={String(filters.year)} onChange={(v) => onChange({ year: Number(v) })}>
        {yearOptions.years.map((y) => (
          <option key={y} value={y}>
            {y}
          </option>
        ))}
      </SelectField>
      <div className="field">
        <span id={quarterLabelId}>Quarter</span>
        <div className="db-quarter-buttons" role="group" aria-labelledby={quarterLabelId}>
          {QUARTERS.map((q) => {
            const on = filters.quarters.includes(q)
            return (
              <button key={q} type="button" aria-pressed={on} onClick={() => onChange({ quarters: toggleQuarter(filters.quarters, q, !on) })}>
                {`Q${q}`}
              </button>
            )
          })}
        </div>
      </div>
      <UserSelect label="담당자" name="owner" value={textOf(filters.ownerId)} onChange={(v) => onChange({ ownerId: parseId(v) })} includeResigned />
      <SelectField label="Vendor" name="vendor" value={vendorValue} onChange={(v) => onChange({ vendor: parseId(v) })}>
        <option value="">전체</option>
        {!loaded && vendorValue && <option value={vendorValue}>선택한 Vendor</option>}
        {vendors.map((v) => (
          <option key={v.id} value={v.id}>
            {v.name}
          </option>
        ))}
      </SelectField>
      <ErrorBanner error={yearOptions.error} />
      <ErrorBanner error={vendorsQuery.error} />
    </form>
  )
}
