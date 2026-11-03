import { useId } from 'react'
import type { ReportBinMode } from '../../../shared/model/reportTypes'
import type { ChartDraft } from './chartDraft'

type Value = ChartDraft['histogram']
type Part = 'bin_mode' | 'bin_count' | 'bin_width' | 'overflow' | 'underflow'

interface HistogramOptionsProps {
  value: Value
  onChange: (next: Value) => void
  /** 칸 이름(서버 위치와 같다)별 안내. */
  issues?: Partial<Record<Part, string>>
}

const MODES: { value: ReportBinMode; label: string }[] = [
  { value: 'auto', label: '자동' },
  { value: 'count', label: '구간 수' },
  { value: 'width', label: '구간 너비' },
]

/** 히스토그램 구간 설정: 방식(자동·구간 수·구간 너비)과 오버플로·언더플로 구간. 방식이 쓰지 않는 칸은 이유와 함께 비활성이다. */
export function HistogramOptions({ value, onChange, issues = {} }: HistogramOptionsProps) {
  const id = useId()
  const set = (patch: Partial<Value>) => onChange({ ...value, ...patch })
  const aria = (part: Part) => (issues[part] ? { 'aria-invalid': true as const, 'aria-describedby': `${id}-${part}` } : {})
  const note = (part: Part) =>
    issues[part] ? (
      <p id={`${id}-${part}`} className="error">
        {issues[part]}
      </p>
    ) : null
  return (
    <>
      <div className="field">
        <label htmlFor={`${id}-mode`}>구간 방식</label>
        <select id={`${id}-mode`} value={value.mode} {...aria('bin_mode')} onChange={(e) => set({ mode: e.target.value as ReportBinMode })}>
          {MODES.map((m) => (
            <option key={m.value} value={m.value}>
              {m.label}
            </option>
          ))}
        </select>
        {note('bin_mode')}
      </div>
      <div className="field">
        <label htmlFor={`${id}-count`}>구간 수</label>
        <input
          id={`${id}-count`}
          type="text"
          inputMode="numeric"
          value={value.count}
          disabled={value.mode !== 'count'}
          title={value.mode === 'count' ? undefined : '구간 방식이 구간 수일 때 쓸 수 있습니다'}
          {...aria('bin_count')}
          onChange={(e) => set({ count: e.target.value })}
        />
        {note('bin_count')}
      </div>
      <div className="field">
        <label htmlFor={`${id}-width`}>구간 너비</label>
        <input
          id={`${id}-width`}
          type="text"
          inputMode="decimal"
          value={value.width}
          disabled={value.mode !== 'width'}
          title={value.mode === 'width' ? undefined : '구간 방식이 구간 너비일 때 쓸 수 있습니다'}
          {...aria('bin_width')}
          onChange={(e) => set({ width: e.target.value })}
        />
        {note('bin_width')}
      </div>
      <div className="field">
        <label htmlFor={`${id}-overflow`}>오버플로 구간</label>
        <input id={`${id}-overflow`} type="text" inputMode="decimal" value={value.overflow} {...aria('overflow')} onChange={(e) => set({ overflow: e.target.value })} />
        <p className="field-hint">이 값보다 큰 값을 한 구간으로 묶습니다</p>
        {note('overflow')}
      </div>
      <div className="field">
        <label htmlFor={`${id}-underflow`}>언더플로 구간</label>
        <input id={`${id}-underflow`} type="text" inputMode="decimal" value={value.underflow} {...aria('underflow')} onChange={(e) => set({ underflow: e.target.value })} />
        <p className="field-hint">이 값 이하의 값을 한 구간으로 묶습니다</p>
        {note('underflow')}
      </div>
    </>
  )
}
