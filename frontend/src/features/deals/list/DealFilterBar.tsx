import { useId, useRef, useState } from 'react'
import { useFreshUpdatedPeriods, useUpdatedPeriods } from '../../../data/deals'
import { useCodeSet } from '../../../data/codes'
import { useToday } from '../../../data/today'
import { useVendors } from '../../../data/vendors'
import { NEXT_ACTION_STATUS_FILTER_OPTIONS, nextActionStatusFromParam, nextActionStatusToParam } from '../../../shared/model/nextActionStatus'
import { parseMonth } from '../../../shared/model/month'
import { PAST_PERIOD_LABELS } from '../../../shared/model/periodChoice'
import { selectedUpdatedPeriod } from '../../../shared/model/updatedPeriod'
import { ErrorBanner } from '../../../shared/ui/ErrorBanner'
import { CheckboxField, SelectField, TextField } from '../../../shared/ui/fields'
import { UserSelect } from '../../../shared/ui/UserSelect'
import { outcomeFromParam } from './listQuery'

interface DealFilterBarProps {
  params: URLSearchParams
  /** URL 쿼리 일부를 바꾼다(빈 문자열은 삭제). */
  onChange: (patch: Record<string, string | undefined>) => void
  onReset: () => void
}

const QUARTERS = [1, 2, 3, 4] as const
const MONTHS = [1, 2, 3, 4, 5, 6, 7, 8, 9, 10, 11, 12] as const

/** 올해-1~+2에, URL로 들어온 유효한 연도(Dashboard Drill-down 등)가 범위 밖이면 그 값을 더한다. */
function yearOptions(year: number, urlYear: string): number[] {
  const years = [year - 1, year, year + 1, year + 2]
  const current = /^\d+$/.test(urlYear) ? Number(urlYear) : 0
  return current >= 1 && !years.includes(current) ? [...years, current].sort((a, b) => a - b) : years
}

/** Deal 목록 필터(DL-04, LB-06). 키워드는 검색 버튼, 나머지는 바꾸는 즉시 URL에 반영한다. */
export function DealFilterBar({ params, onChange, onReset }: DealFilterBarProps) {
  const { year: thisYear } = useToday()
  const codes = useCodeSet().data
  const vendorsQuery = useVendors()
  const vendors = vendorsQuery.data ?? []
  const loaded = vendorsQuery.data !== undefined
  const value = (key: string) => params.get(key) ?? ''
  const hintId = useId()
  const monthHintId = useId()
  const periodsQuery = useUpdatedPeriods()
  const periods = periodsQuery.data?.periods
  const fetchFresh = useFreshUpdatedPeriods()
  // 기간 선택(프리셋·전체·직접 지정·날짜 입력·초기화)마다 올린다. 늦게 온 이전 프리셋 응답은 순번이 달라 버린다.
  const periodSeq = useRef(0)
  const [refreshError, setRefreshError] = useState<unknown>(null)
  const updatedFrom = value('updated_from')
  const updatedTo = value('updated_to')
  // '직접 지정' 표시는 그것을 연 시점(또는 이 화면에서 날짜를 바꾼 시점)의 URL 날짜에만 묶인다.
  // 뒤로 가기 등으로 URL 날짜가 바깥에서 바뀌면 키가 달라져 닫히고, 표시는 selectedUpdatedPeriod 규칙을 따른다.
  const [customKey, setCustomKey] = useState<string | null>(null)
  const customOpen = customKey === `${updatedFrom}|${updatedTo}`
  const period = customOpen ? 'custom' : selectedUpdatedPeriod(updatedFrom || undefined, updatedTo || undefined, periods)
  const q = params.get('q') ?? ''
  const [keyword, setKeyword] = useState(q)
  const [seenQ, setSeenQ] = useState(q)
  if (q !== seenQ) {
    setSeenQ(q)
    setKeyword(q)
  }
  // Solution도 키워드처럼 검색(버튼·Enter)으로 URL에 반영한다. URL이 바깥에서 바뀌면(초기화·뒤로 가기) 입력란도 따라간다.
  const urlSolution = params.get('solution') ?? ''
  const [solution, setSolution] = useState(urlSolution)
  const [seenSolution, setSeenSolution] = useState(urlSolution)
  if (urlSolution !== seenSolution) {
    setSeenSolution(urlSolution)
    setSolution(urlSolution)
  }
  // 모르는 값은 '전체'로 보이고 조회에도 쓰이지 않는다(listQueryFromParams와 같은 판정).
  const nextStatus = nextActionStatusFromParam(params.get('next_status'))
  const hasQuarter = value('quarter') !== ''
  const hasYear = value('year') !== ''
  const showMonthHint = !hasQuarter && !hasYear && parseMonth(params.get('month')) !== undefined
  // 목록이 로드된 뒤 목록에 없는 Vendor id(예전 이름 값 등)는 '전체'로 보인다.
  // 조건 형식은 listQueryFromParams가, 목록 없는 id 판정은 DealsPage의 effectiveVendorFilter가 한다.
  // 목록이 없는 동안(로딩·오류)에는 URL 값이 조회에 쓰이므로 '선택한 Vendor' 옵션 하나로 선택 상태를 보인다.
  const vendorId = !loaded ? value('vendor') : vendors.some((v) => String(v.id) === value('vendor')) ? value('vendor') : ''

  /** 프리셋은 서버가 준 날짜를 그대로 URL에 쓰고, 전체는 두 키를 지운다. 직접 지정은 URL을 바꾸지 않는다. */
  async function changePeriod(next: string) {
    const seq = ++periodSeq.current
    setRefreshError(null)
    if (next === 'custom') {
      setCustomKey(`${updatedFrom}|${updatedTo}`)
      return
    }
    setCustomKey(null)
    if (next === '') {
      onChange({ updated_from: undefined, updated_to: undefined })
      return
    }
    // 자정이 지났을 수 있어 캐시를 쓰지 않고 서버에 다시 묻는다. 실패하면 URL은 그대로 두고 오류를 보인다.
    try {
      const fresh = await fetchFresh()
      if (seq !== periodSeq.current) return
      const chosen = fresh.periods.find((p) => p.key === next)
      onChange({ updated_from: chosen?.from, updated_to: chosen?.to })
    } catch (error) {
      if (seq === periodSeq.current) setRefreshError(error)
    }
  }

  function changeCustomDate(patch: { updated_from?: string; updated_to?: string }) {
    periodSeq.current += 1
    setCustomKey(`${patch.updated_from ?? updatedFrom}|${patch.updated_to ?? updatedTo}`)
    onChange(patch)
  }

  return (
    <form
      className="deal-filters"
      role="search"
      aria-label="Deal 필터"
      onSubmit={(event) => {
        event.preventDefault()
        onChange({ q: keyword.trim(), solution: solution.trim() })
      }}
    >
      <TextField label="키워드" name="keyword" value={keyword} onChange={setKeyword} />
      <UserSelect label="담당자" name="owner" value={value('owner')} onChange={(owner) => onChange({ owner })} includeResigned />
      <SelectField label="Vendor" name="vendor" value={vendorId} onChange={(vendor) => onChange({ vendor })}>
        <option value="">전체</option>
        {!loaded && vendorId && <option value={vendorId}>선택한 Vendor</option>}
        {vendors.map((v) => (
          <option key={v.id} value={v.id}>
            {v.name}
          </option>
        ))}
      </SelectField>
      <TextField label="Solution" name="solution" value={solution} onChange={setSolution} />
      <SelectField label="Status" name="status" value={value('status')} onChange={(status) => onChange({ status })}>
        <option value="">전체</option>
        {codes?.statuses.map((c) => (
          <option key={c.key} value={c.key}>
            {c.name}
          </option>
        ))}
      </SelectField>
      <SelectField label="Forecast" name="forecast" value={value('forecast')} onChange={(forecast) => onChange({ forecast })}>
        <option value="">전체</option>
        {codes?.forecasts.map((c) => (
          <option key={c.key} value={c.key}>
            {c.name}
          </option>
        ))}
      </SelectField>
      <SelectField label="Forecast 구분" name="outcome" value={outcomeFromParam(params.get('outcome')) ?? ''} onChange={(outcome) => onChange({ outcome })}>
        <option value="">전체</option>
        <option value="open">Open</option>
        <option value="won">Won</option>
        <option value="lost">Lost</option>
        <option value="not_lost">Lost 제외</option>
      </SelectField>
      <SelectField
        label="Next Action 상태"
        name="next_status"
        value={nextStatus ? nextActionStatusToParam(nextStatus) : ''}
        onChange={(next_status) => onChange({ next_status })}
      >
        {NEXT_ACTION_STATUS_FILTER_OPTIONS.map((o) => (
          <option key={o.value} value={o.value === '' ? '' : nextActionStatusToParam(o.value)}>
            {o.label}
          </option>
        ))}
      </SelectField>
      <SelectField
        label="연도"
        name="year"
        value={value('year')}
        onChange={(year) => onChange({ year })}
      >
        <option value="">전체</option>
        {yearOptions(thisYear, value('year')).map((y) => (
          <option key={y} value={String(y)}>
            {y}
          </option>
        ))}
      </SelectField>
      <label className="field">
        <span>Quarter</span>
        <select
          name="quarter"
          aria-label="Quarter"
          aria-describedby={hasQuarter && !hasYear ? hintId : undefined}
          value={value('quarter')}
          onChange={(e) => onChange({ quarter: e.target.value, month: '' })}
        >
          <option value="">전체</option>
          {QUARTERS.map((n) => (
            <option key={n} value={String(n)}>
              Q{n}
            </option>
          ))}
        </select>
        {hasQuarter && !hasYear && (
          <small id={hintId} className="field-hint">
            연도를 고르지 않으면 올해({thisYear}) 기준입니다.
          </small>
        )}
      </label>
      <label className="field">
        <span>월</span>
        <select
          name="month"
          aria-label="월"
          aria-describedby={showMonthHint ? monthHintId : undefined}
          value={hasQuarter ? '' : value('month')}
          onChange={(e) => onChange(e.target.value ? { month: e.target.value, quarter: '' } : { month: '' })}
        >
          <option value="">전체</option>
          {MONTHS.map((n) => (
            <option key={n} value={String(n)}>{`${n}월`}</option>
          ))}
        </select>
        {showMonthHint && (
          <small id={monthHintId} className="field-hint">
            연도를 고르지 않으면 올해({thisYear}) 기준입니다.
          </small>
        )}
      </label>
      <SelectField label="최종 업데이트" name="updated_period" value={period} onChange={changePeriod}>
        <option value="">전체</option>
        {(Object.keys(PAST_PERIOD_LABELS) as (keyof typeof PAST_PERIOD_LABELS)[]).map((key) => (
          <option key={key} value={key} disabled={!periods?.some((p) => p.key === key)}>
            {PAST_PERIOD_LABELS[key]}
          </option>
        ))}
        <option value="custom">직접 지정</option>
      </SelectField>
      {period === 'custom' && (
        <>
          <TextField label="시작일" name="updated_from" type="date" value={updatedFrom} onChange={(updated_from) => changeCustomDate({ updated_from })} />
          <TextField label="종료일" name="updated_to" type="date" value={updatedTo} onChange={(updated_to) => changeCustomDate({ updated_to })} />
        </>
      )}
      <CheckboxField label="내 딜만" name="mine" checked={value('mine') === '1'} onChange={(on) => onChange({ mine: on ? '1' : '' })} />
      <CheckboxField label="기한초과" name="overdue" checked={value('overdue') === '1'} onChange={(on) => onChange({ overdue: on ? '1' : '' })} />
      <CheckboxField label="미업데이트" name="stale" checked={value('stale') === '1'} onChange={(on) => onChange({ stale: on ? '1' : '' })} />
      <ErrorBanner error={vendorsQuery.error} />
      <ErrorBanner error={periodsQuery.error} />
      <ErrorBanner error={refreshError} />
      <div className="filter-buttons">
        <button type="submit" className="primary">
          검색
        </button>
        <button
          type="button"
          onClick={() => {
            periodSeq.current += 1
            setCustomKey(null)
            setRefreshError(null)
            onReset()
          }}
        >
          초기화
        </button>
      </div>
    </form>
  )
}
