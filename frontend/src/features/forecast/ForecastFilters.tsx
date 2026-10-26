import { useVendors } from '../../data/vendors'
import { parseId } from '../../shared/model/ids'
import { ErrorBanner } from '../../shared/ui/ErrorBanner'
import { SelectField } from '../../shared/ui/fields'
import { UserSelect } from '../../shared/ui/UserSelect'
import { useForecastSnapshots } from '../../data/forecast'
import { useYearOptions } from '../../data/dealYears'
import type { ForecastFilters } from './forecastParams'

interface Props {
  filters: ForecastFilters
  onChange: (patch: Partial<ForecastFilters>) => void
}

const MONTHS = [1, 2, 3, 4, 5, 6, 7, 8, 9, 10, 11, 12] as const

const textOf = (id: number | undefined): string => (id === undefined ? '' : String(id))

/** Forecast 필터: 연도 / Quarter / 월 / 담당자 / Vendor. 값은 URL이 가진다(제어 컴포넌트). */
export function ForecastFilterBar({ filters, onChange }: Props) {
  const yearOptions = useYearOptions(filters.year)
  const vendorsQuery = useVendors()
  const snapshotsQuery = useForecastSnapshots()
  const snapshots = snapshotsQuery.data ?? []
  const snap = filters.snap
  const vendors = vendorsQuery.data ?? []
  const loaded = vendorsQuery.data !== undefined
  // 목록이 로드된 뒤 목록에 없는 id는 '전체'로 보인다. 목록이 없는 동안(로딩·오류)에는 URL 값을 '선택한 Vendor'로 보인다.
  const vendorValue = !loaded ? textOf(filters.vendor) : vendors.some((v) => v.id === filters.vendor) ? textOf(filters.vendor) : ''

  return (
    <form className="filters fc-filters" aria-label="Forecast 필터" onSubmit={(e) => e.preventDefault()}>
      <SelectField label="기준 시점" name="snap" value={snap ?? ''} onChange={(v) => onChange({ snap: v || undefined, selectedId: undefined })}>
        <option value="">지금</option>
        {snap && !snapshots.some((s) => s.period === snap) && <option value={snap}>{`${snap} 월말`}</option>}
        {snapshots.map((s) => (
          <option key={s.period} value={s.period}>{`${s.period} 월말`}</option>
        ))}
      </SelectField>
      <SelectField label="연도" name="year" value={String(filters.year)} onChange={(v) => onChange({ year: Number(v) })}>
        {yearOptions.years.map((y) => (
          <option key={y} value={y}>
            {y}
          </option>
        ))}
      </SelectField>
      <SelectField
        label="Quarter"
        name="quarter"
        value={filters.quarter ? String(filters.quarter) : ''}
        onChange={(v) => onChange({ quarter: v ? (Number(v) as 1 | 2 | 3 | 4) : undefined, month: undefined })}
      >
        <option value="">전체</option>
        {[1, 2, 3, 4].map((q) => (
          <option key={q} value={q}>{`Q${q}`}</option>
        ))}
      </SelectField>
      <SelectField
        label="월"
        name="month"
        value={filters.month ? String(filters.month) : ''}
        onChange={(v) => onChange({ month: v ? Number(v) : undefined, quarter: undefined })}
      >
        <option value="">전체</option>
        {MONTHS.map((m) => (
          <option key={m} value={m}>{`${m}월`}</option>
        ))}
      </SelectField>
      <UserSelect
        label="담당자"
        name="owner"
        value={textOf(filters.ownerId)}
        onChange={(v) => onChange({ ownerId: parseId(v) })}
        includeResigned
      />
      <SelectField label="Vendor" name="vendor" value={vendorValue} disabled={snap !== undefined} onChange={(v) => onChange({ vendor: parseId(v) })}>
        <option value="">전체</option>
        {!loaded && vendorValue && <option value={vendorValue}>선택한 Vendor</option>}
        {vendors.map((v) => (
          <option key={v.id} value={v.id}>
            {v.name}
          </option>
        ))}
      </SelectField>
      {snap !== undefined && <p className="hint">스냅숏에서는 Vendor 필터를 사용할 수 없습니다.</p>}
      <ErrorBanner error={yearOptions.error} />
      <ErrorBanner error={vendorsQuery.error} />
      <ErrorBanner error={snapshotsQuery.error} />
    </form>
  )
}
