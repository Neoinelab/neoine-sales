import { render, screen } from '@testing-library/react'
import { describe, expect, it } from 'vitest'
import { lastChart, renderedCharts } from '../../../test/chartMock'
import { resultColumn, resultOf } from '../../../test/reportDesigner'
import type { ReportChartInput } from '../../../shared/model/reportTypes'
import { ChartPreview } from './ChartPreview'

/**
 * `ChartPreview`(Excel 확장 "제외 항목 안내", "shapeKey"). 계약(테스트가 정한 부분)
 * - 그릴 때 빌더가 돌려준 `notes`를 차트 아래에 `field-hint` 글자로 보인다(0 이하·빈 값 제외 개수 등).
 * - 종류·콤보 계열 종류·보조 축이 바뀌면 차트를 새로 만든다(`key`가 바뀐다): 그리기 요소는 새로 마운트된다.
 */

const VENDOR = resultColumn({ index: 0, field: 'deal.vendor', label: 'Vendor', type: 'code', valueType: 'text', format: null, group: true })
const SIZE = resultColumn({ index: 1, field: 'deal.users', label: '규모', type: 'number', valueType: 'integer', format: null, unit: null, aggregate: 'sum' })
const RESULT = resultOf({
  columns: [VENDOR, SIZE],
  rows: [
    ['A', 10],
    ['B', 0],
    ['C', null],
  ],
})

const input = (over: Partial<ReportChartInput> = {}): ReportChartInput => ({
  kind: 'funnel',
  category: 0,
  series: null,
  values: [1],
  swap: false,
  title: '',
  legend: 'top',
  dataLabels: false,
  categoryAxisTitle: '',
  valueAxisTitle: '',
  valueMin: null,
  valueMax: null,
  secondaryAxis: false,
  histogram: null,
  showTotal: false,
  comboSeries: null,
  ...over,
})

describe('ChartPreview notes', () => {
  it('shows what was left out under the chart', () => {
    render(<ChartPreview input={input()} result={RESULT} />)

    expect(screen.getByRole('img')).toBeVisible()
    const note = screen.getByText(/2개/)
    expect(note).toBeVisible()
    expect(note).toHaveClass('field-hint')
  })

  it('shows no note when every item is drawn', () => {
    const full = resultOf({ columns: [VENDOR, SIZE], rows: [['A', 10], ['B', 5]] })

    render(<ChartPreview input={input()} result={full} />)

    expect(lastChart().options).toMatchObject({ indexAxis: 'y' }) // 깔때기로 그려졌다
    expect(document.querySelector('.field-hint')).toBeNull()
  })

  it('draws the type that the kind needs through the generic chart', () => {
    render(<ChartPreview input={input({ kind: 'sunburst' })} result={RESULT} />)

    expect(renderedCharts().length).toBeGreaterThan(0)
    expect(lastChart().type).toBe('doughnut')
  })
})
