import { useRef, useState, type FormEvent } from 'react'
import { useFreshUpdatedPeriods, useUpdatedPeriods } from '../../data/deals'
import { useVendors } from '../../data/vendors'
import { dateValueError } from '../../shared/model/dateText'
import { resolvePeriodChoice, type DuePeriodChoice, type PastPeriodChoice } from '../../shared/model/periodChoice'
import type { UpdatedPeriods } from '../../shared/model/types'
import { ErrorBanner } from '../../shared/ui/ErrorBanner'
import { PeriodField } from '../../shared/ui/PeriodField'
import { SelectField, TextField } from '../../shared/ui/fields'
import { UserSelect } from '../../shared/ui/UserSelect'
import type { ContractStatus } from '../../shared/model/types'
import { NO_CONTRACT_CONDITIONS, type ContractConditions } from './contractFilter'
import { STATUS_LABELS } from './contractLabels'

interface ContractFilterBarProps {
  applied: ContractConditions
  onSearch: (next: ContractConditions) => void
  onReset: () => void
}

type DateRange = { from: string; to: string }
type DateErrors = { startFrom?: string; startTo?: string; endFrom?: string; endTo?: string }

const STATUSES = Object.keys(STATUS_LABELS) as ContractStatus[]
const REVERSED = (label: string) => `${label} 범위의 시작은 끝보다 늦을 수 없습니다.`

/** 한 날짜 조건의 입력값을 검색에 쓸 범위로 푼다. 프리셋은 새로 받은 서버 프리셋으로 풀고, 직접 지정은 입력 그대로. */
function resolveRange(choice: DuePeriodChoice, draft: DateRange, fresh: UpdatedPeriods | undefined): DateRange {
  if (choice === '') return { from: '', to: '' }
  if (choice === 'custom' || fresh === undefined) return draft
  const resolved = resolvePeriodChoice(choice, fresh)
  return { from: resolved?.from ?? '', to: resolved?.to ?? '' }
}

function rangeErrors(range: DateRange, label: string): { from?: string; to?: string } {
  const from = dateValueError(range.from) ?? undefined
  const to = dateValueError(range.to) ?? undefined
  if (from || to) return { from, to }
  if (range.from !== '' && range.to !== '' && range.from > range.to) return { from: REVERSED(label) }
  return {}
}

/** 계약 검색 조건. 텍스트 칸의 Enter 또는 검색 버튼으로 한 번에 적용한다. */
export function ContractFilterBar({ applied, onSearch, onReset }: ContractFilterBarProps) {
  const [draft, setDraft] = useState<ContractConditions>(applied)
  const [startChoice, setStartChoice] = useState<PastPeriodChoice>('')
  const [endChoice, setEndChoice] = useState<DuePeriodChoice>('')
  const [errors, setErrors] = useState<DateErrors>({})
  const [refreshError, setRefreshError] = useState<unknown>(null)
  const periodsQuery = useUpdatedPeriods()
  const vendors = useVendors()
  const fetchFresh = useFreshUpdatedPeriods()
  // 검색·초기화마다 올린다. 늦게 온 이전 프리셋 응답은 순번이 달라 버린다.
  const searchSeq = useRef(0)
  const set = (patch: Partial<ContractConditions>) => setDraft((prev) => ({ ...prev, ...patch }))

  async function submit(event: FormEvent) {
    event.preventDefault()
    const seq = ++searchSeq.current
    setRefreshError(null)
    let fresh: UpdatedPeriods | undefined
    const needsFresh = [startChoice, endChoice].some((c) => c !== '' && c !== 'custom')
    if (needsFresh) {
      try {
        fresh = await fetchFresh()
        if (seq !== searchSeq.current) return
      } catch (error) {
        if (seq === searchSeq.current) setRefreshError(error)
        return
      }
    }
    const start = resolveRange(startChoice, { from: draft.startFrom, to: draft.startTo }, fresh)
    const end = resolveRange(endChoice, { from: draft.endFrom, to: draft.endTo }, fresh)
    const startErrors = rangeErrors(start, '라이선스 시작일')
    const endErrors = rangeErrors(end, '라이선스 종료일')
    if (startErrors.from || startErrors.to || endErrors.from || endErrors.to) {
      setErrors({ startFrom: startErrors.from, startTo: startErrors.to, endFrom: endErrors.from, endTo: endErrors.to })
      return
    }
    setErrors({})
    onSearch({ ...draft, startFrom: start.from, startTo: start.to, endFrom: end.from, endTo: end.to })
  }

  function reset() {
    searchSeq.current += 1
    setRefreshError(null)
    setStartChoice('')
    setEndChoice('')
    setErrors({})
    setDraft(NO_CONTRACT_CONDITIONS)
    onReset()
  }

  function choose(which: 'start' | 'end', next: string) {
    const value = next as DuePeriodChoice
    setErrors({})
    if (which === 'start') {
      setStartChoice(value as PastPeriodChoice)
      if (value === '') set({ startFrom: '', startTo: '' })
    } else {
      setEndChoice(value)
      if (value === '') set({ endFrom: '', endTo: '' })
    }
  }

  return (
    <form className="contract-filters" role="search" aria-label="계약 검색" onSubmit={(e) => void submit(e)}>
      <TextField label="고객사명" name="customer" maxLength={200} value={draft.customer} onChange={(customer) => set({ customer })} />
      <SelectField label="Vendor" name="vendor" value={draft.vendor} onChange={(vendor) => set({ vendor })}>
        <option value="">전체</option>
        {(vendors.data ?? []).map((vendor) => (
          <option key={vendor.id} value={vendor.id}>
            {vendor.name}
          </option>
        ))}
      </SelectField>
      <TextField label="제품명" name="product" maxLength={200} value={draft.product} onChange={(product) => set({ product })} />
      <UserSelect label="담당영업" name="salesOwner" value={draft.salesOwner} onChange={(salesOwner) => set({ salesOwner })} includeResigned />
      <SelectField label="상태" name="status" value={draft.status} onChange={(status) => set({ status: status as ContractConditions['status'] })}>
        <option value="">전체</option>
        {STATUSES.map((status) => (
          <option key={status} value={status}>
            {STATUS_LABELS[status]}
          </option>
        ))}
      </SelectField>
      <PeriodField
        label="라이선스 시작일"
        value={startChoice}
        onChange={(v) => choose('start', v)}
        presets={periodsQuery.data}
        from={draft.startFrom}
        to={draft.startTo}
        onFromChange={(startFrom) => set({ startFrom })}
        onToChange={(startTo) => set({ startTo })}
        fromError={errors.startFrom}
        toError={errors.startTo}
      />
      <PeriodField
        label="라이선스 종료일"
        withUpcoming
        value={endChoice}
        onChange={(v) => choose('end', v)}
        presets={periodsQuery.data}
        from={draft.endFrom}
        to={draft.endTo}
        onFromChange={(endFrom) => set({ endFrom })}
        onToChange={(endTo) => set({ endTo })}
        fromError={errors.endFrom}
        toError={errors.endTo}
      />
      <div className="filter-buttons">
        <button type="submit" className="primary">
          검색
        </button>
        <button type="button" onClick={reset}>
          초기화
        </button>
      </div>
      {periodsQuery.data === undefined && <ErrorBanner error={periodsQuery.error} />}
      {vendors.data === undefined && <ErrorBanner error={vendors.error} />}
      <ErrorBanner error={refreshError} />
    </form>
  )
}
