import { useId } from 'react'
import type { ReportComboSeries, ReportComboSeriesType } from '../../../shared/model/reportTypes'
import { COMBO_PRESETS, comboPresetOf } from './build/combo'
import { comboDefault, type ChartDraft } from './chartDraft'

type Value = ChartDraft['comboTypes']

interface ComboSeriesEditorProps {
  /** 고른 값 열(차트 순서대로). */
  columns: { uid: number; header: string }[]
  value: Value
  onChange: (next: Value) => void
  issue?: string
}

const TYPES: { value: ReportComboSeriesType; label: string }[] = [
  { value: 'column', label: '묶은 세로 막대' },
  { value: 'stacked_column', label: '누적 세로 막대' },
  { value: 'line', label: '꺾은선' },
  { value: 'line_markers', label: '표식이 있는 꺾은선' },
  { value: 'area', label: '영역' },
  { value: 'stacked_area', label: '누적 영역' },
]

const CUSTOM = 'custom'

/** 콤보 계열 설정: 프리셋 바로가기와 값 열마다 종류·보조 축. 프리셋은 저장하지 않고 현재 설정이 프리셋과 같은지만 보여 준다. */
export function ComboSeriesEditor({ columns, value, onChange, issue }: ComboSeriesEditorProps) {
  const id = useId()
  const current: ReportComboSeries[] = columns.map((c, i) => value[c.uid] ?? comboDefault(i))
  const fill = (settings: ReportComboSeries[]): Value => Object.fromEntries(columns.map((c, i) => [c.uid, settings[i] ?? comboDefault(i)]))
  const edit = (index: number, patch: Partial<ReportComboSeries>) =>
    onChange(fill(current.map((s, i) => (i === index ? { ...s, ...patch } : s))))
  const pickPreset = (key: string) => {
    const preset = COMBO_PRESETS.find((p) => p.key === key)
    if (preset) onChange(fill(preset.apply(columns.length)))
  }
  return (
    <>
      <div className="field">
        <label htmlFor={`${id}-preset`}>콤보 프리셋</label>
        <select id={`${id}-preset`} value={comboPresetOf(current)} onChange={(e) => pickPreset(e.target.value)}>
          {COMBO_PRESETS.map((p) => (
            <option key={p.key} value={p.key}>
              {p.label}
            </option>
          ))}
          <option value={CUSTOM}>사용자 지정 조합</option>
        </select>
      </div>
      <div className="report-combo-rows">
        {columns.map((c, i) => (
          <div key={c.uid} className="report-combo-row">
            <span className="report-combo-name" title={c.header}>
              {c.header}
            </span>
            <select aria-label={`${c.header} 종류`} value={current[i]?.type ?? 'line'} onChange={(e) => edit(i, { type: e.target.value as ReportComboSeriesType })}>
              {TYPES.map((t) => (
                <option key={t.value} value={t.value}>
                  {t.label}
                </option>
              ))}
            </select>
            <label className="report-check">
              <input type="checkbox" aria-label={`${c.header} 보조 축`} checked={current[i]?.secondary ?? false} onChange={(e) => edit(i, { secondary: e.target.checked })} />
              보조 축
            </label>
          </div>
        ))}
      </div>
      {issue && <p className="error">{issue}</p>}
    </>
  )
}
