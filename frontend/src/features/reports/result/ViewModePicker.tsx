import { useId } from 'react'
import type { ReportResultView } from '../../../shared/model/reportTypes'

const OPTIONS: { value: ReportResultView; label: string; needsChart: boolean }[] = [
  { value: 'both', label: '표+차트', needsChart: true },
  { value: 'chart', label: '차트만', needsChart: true },
  { value: 'table', label: '표만', needsChart: false },
]

interface ViewModePickerProps {
  /** 지금 보이는 보기 방식(저장된 값이 아니라 화면에 실제로 적용된 값). */
  view: ReportResultView
  /** false면 차트가 들어가는 보기 방식은 고를 수 없다(보기 화면에서 저장된 차트가 없을 때). */
  chartAvailable: boolean
  onChange: (view: ReportResultView) => void
}

/** 보기 방식 선택: 표+차트 / 차트만 / 표만. */
export function ViewModePicker({ view, chartAvailable, onChange }: ViewModePickerProps) {
  const name = useId()
  return (
    <div role="radiogroup" aria-label="보기" className="report-view-choice">
      <span className="report-view-label" aria-hidden="true">
        보기
      </span>
      {OPTIONS.map(({ value, label, needsChart }) => {
        const blocked = needsChart && !chartAvailable
        return (
          <label key={value} className="report-check">
            <input type="radio" name={name} checked={view === value} disabled={blocked} title={blocked ? '저장된 차트가 없습니다' : undefined} onChange={() => onChange(value)} />
            {label}
          </label>
        )
      })}
    </div>
  )
}
