import { useMemo } from 'react'
import { useToday } from '../../../data/today'
import type { ReportChartInput, ReportResult } from '../../../shared/model/reportTypes'
import { buildChart } from './buildChart'
import { ReportChart } from './ReportChart'

const TRUNCATED = '최대 행 수 제한으로 표시된 행만 차트에 그렸습니다'

/** 설정(결과 열 index)과 결과로 차트를 그린다. 결과와 맞지 않거나 점이 너무 많으면 이유만 보인다. */
export function ChartPreview({ input, result }: { input: ReportChartInput; result: ReportResult }) {
  const { now, today } = useToday()
  const built = useMemo(() => buildChart(input, result, { now, today, totals: result.totals }), [input, result, now, today])
  if ('problem' in built) return <p className="hint">{built.problem}</p>
  return (
    <>
      <ReportChart built={built} title={input.title} shapeKey={`${input.kind}:${input.secondaryAxis}`} />
      {result.truncated && <p className="field-hint">{TRUNCATED}</p>}
    </>
  )
}
