import { render, screen } from '@testing-library/react'
import { describe, expect, it } from 'vitest'
import { lastChart, renderedCharts } from '../../../test/chartMock'
import { resultColumn, resultOf } from '../../../test/reportDesigner'
import type { ReportChartInput } from '../../../shared/model/reportTypes'
import { ChartPreview } from './ChartPreview'

/**
 * `ChartPreview`(제외 항목 안내, shapeKey). 계약(테스트가 정한 부분)
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

describe('ChartPreview: 제외 항목 안내', () => {
  // 테스트 코드: RC-073
  it('제외한 항목이 있으면 차트 아래에 개수를 안내한다', () => {
    // when: 0 이하·빈 값이 섞인 결과로 미리보기를 그린다
    render(<ChartPreview input={input()} result={RESULT} />)

    // then: 그림이 보이고 "2개" 안내가 field-hint 글자로 보인다
    expect(screen.getByRole('img')).toBeVisible()
    const note = screen.getByText(/2개/)
    expect(note).toBeVisible()
    expect(note).toHaveClass('field-hint')
  })

  // 테스트 코드: RC-073
  it('모두 그리면 안내가 없다', () => {
    // given: 모두 그릴 수 있는 결과
    const full = resultOf({ columns: [VENDOR, SIZE], rows: [['A', 10], ['B', 5]] })

    // when: 미리보기를 그린다
    render(<ChartPreview input={input()} result={full} />)

    // then: 깔때기로 그려지고 field-hint 안내가 없다
    expect(lastChart().options).toMatchObject({ indexAxis: 'y' }) // 깔때기로 그려졌다
    expect(document.querySelector('.field-hint')).toBeNull()
  })

  // 테스트 코드: RC-073
  it('종류에 필요한 Chart.js 종류로 그린다', () => {
    // when: 선버스트 미리보기를 그린다
    render(<ChartPreview input={input({ kind: 'sunburst' })} result={RESULT} />)

    // then: 그리기 요소가 만들어지고 종류가 doughnut이다
    expect(renderedCharts().length).toBeGreaterThan(0)
    expect(lastChart().type).toBe('doughnut')
  })
})
