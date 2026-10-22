import { PAST_PERIOD_LABELS, UPCOMING_PERIOD_LABELS, type DuePeriodChoice } from '../../../shared/model/periodChoice'
import type { UpcomingPeriodKey, UpdatedPeriodKey, UpdatedPeriods } from '../../../shared/model/types'

interface ActionPeriodFieldProps {
  /** 선택 상자 라벨이자 직접 지정 날짜 라벨의 접두어(예: '수행일' -> '수행일 시작'). */
  label: string
  value: DuePeriodChoice
  onChange: (value: DuePeriodChoice) => void
  /** 서버 프리셋. 아직 없으면(로딩·오류) 프리셋 옵션은 비활성이다. */
  presets: UpdatedPeriods | undefined
  /** 향후 N개월 옵션을 보일지(기한만). */
  withUpcoming?: boolean
  from: string
  to: string
  onFromChange: (value: string) => void
  onToChange: (value: string) => void
}

const PAST_KEYS = Object.keys(PAST_PERIOD_LABELS) as UpdatedPeriodKey[]
const UPCOMING_KEYS = Object.keys(UPCOMING_PERIOD_LABELS) as UpcomingPeriodKey[]

/** 기간 조건 한 칸: 전체 / 프리셋 / 직접 지정(선택하면 시작·끝 날짜 입력이 나타난다). */
export function ActionPeriodField({ label, value, onChange, presets, withUpcoming = false, from, to, onFromChange, onToChange }: ActionPeriodFieldProps) {
  return (
    <>
      <label className="field">
        <span>{label}</span>
        <select value={value} onChange={(e) => onChange(e.target.value as DuePeriodChoice)}>
          <option value="">전체</option>
          {PAST_KEYS.map((key) => (
            <option key={key} value={key} disabled={!presets?.periods.some((p) => p.key === key)}>
              {PAST_PERIOD_LABELS[key]}
            </option>
          ))}
          {withUpcoming &&
            UPCOMING_KEYS.map((key) => (
              <option key={key} value={`next${key}`} disabled={!presets?.upcoming.some((p) => p.key === key)}>
                {UPCOMING_PERIOD_LABELS[key]}
              </option>
            ))}
          <option value="custom">직접 지정</option>
        </select>
      </label>
      {value === 'custom' && (
        <>
          <label className="field">
            <span>{label} 시작</span>
            <input type="date" value={from} onChange={(e) => onFromChange(e.target.value)} />
          </label>
          <label className="field">
            <span>{label} 끝</span>
            <input type="date" value={to} onChange={(e) => onToChange(e.target.value)} />
          </label>
        </>
      )}
    </>
  )
}
