import { useMemo } from 'react'
import { useToday } from '../../../data/today'
import type { ReportChartInput, ReportResult } from '../../../shared/model/reportTypes'
import { buildChart } from './buildChart'
import { ReportChart } from './ReportChart'

const TRUNCATED = '최대 행 수 제한으로 표시된 행만 차트에 그렸습니다'

/** 데이터셋 모양(종류·보조 축·콤보 계열 종류)이 바뀌면 차트를 새로 만들기 위한 키. */
const shapeKeyOf = (input: ReportChartInput): string =>
  `${input.kind}:${input.secondaryAxis}:${(input.comboSeries ?? []).map((s) => `${s.type}${s.secondary ? '*' : ''}`).join(',')}`

/** 설정(결과 열 index)과 결과로 차트를 그린다. 결과와 맞지 않거나 점이 너무 많으면 이유만 보인다. */
export function ChartPreview({ input, result }: { input: ReportChartInput; result: ReportResult }) {
  const { now, today } = useToday()
  const built = useMemo(() => buildChart(input, result, { now, today }), [input, result, now, today])
  if ('problem' in built) return <p className="hint">{built.problem}</p>
  return (
    <>
      <ReportChart built={built} title={input.title} shapeKey={shapeKeyOf(input)} />
      {built.notes.map((note) => (
        <p key={note} className="field-hint">
          {note}
        </p>
      ))}
      {result.truncated && <p className="field-hint">{TRUNCATED}</p>}
    </>
  )
}
