import { describe, expect, it } from 'vitest'
import { resultColumn, resultOf } from '../../../../test/reportDesigner'
import type { ReportChartInput, ReportComboSeries, ReportComboSeriesType } from '../../../../shared/model/reportTypes'
import { buildChart } from '../buildChart'

/**
 * 리뷰 후속(Major 2, 계획 "설계 6"): 콤보에서 누적 계열이 하나라도 있으면 축이 `stacked: true`가 된다.
 * Chart.js는 묶음 키를 `meta.stack || type`으로 정하므로, 누적이 아닌 꺾은선·영역에 `stack`이 없으면 같은 키를 공유해 서로 쌓인다.
 * 계약: 누적이 아닌 모든 계열(column·line·line_markers·area)은 계열마다 고유한 `stack` id를 갖고,
 * 같은 종류의 누적 계열(stacked_column끼리, stacked_area끼리)은 공통 `stack` id를 쓴다.
 */

const CTX = { now: '2026-10-27T09:00:00+09:00', today: '2026-10-27' }
const VENDOR = resultColumn({ index: 0, field: 'deal.vendor', label: 'Vendor', type: 'code', valueType: 'text', format: null, group: true })
const sum = (index: number) => resultColumn({ index, field: 'deal.users', label: `합계 ${index}`, type: 'number', valueType: 'integer', format: null, unit: null, aggregate: 'sum' })
const RESULT = resultOf({
  columns: [VENDOR, sum(1), sum(2), sum(3), sum(4)],
  rows: [
    ['Silverfort', 3, 5, 7, 9],
    ['Okta', 4, 6, 8, 10],
  ],
})

const series = (type: ReportComboSeriesType, secondary = false): ReportComboSeries => ({ type, secondary })

function stacksOf(types: ReportComboSeriesType[]): (string | undefined)[] {
  const input: ReportChartInput = {
    kind: 'combo',
    category: 0,
    series: null,
    values: types.map((_, i) => i + 1),
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
    comboSeries: types.map((t) => series(t)),
  }
  const built = buildChart(input, RESULT, CTX) as unknown as { data: { datasets: { stack?: string }[] } }
  return built.data.datasets.map((d) => d.stack)
}

const plain = ['column', 'line', 'line_markers', 'area'] as const
const isPlain = (t: ReportComboSeriesType): boolean => (plain as readonly string[]).includes(t)

describe('buildChart: 콤보의 누적 묶음 (리뷰 후속 Major 2)', () => {
  it.each<ReportComboSeriesType[]>([
    ['stacked_column', 'line', 'line'],
    ['stacked_area', 'area', 'line'],
    ['stacked_area', 'line', 'column'],
    ['stacked_column', 'line_markers', 'area', 'line'],
  ])('gives every unstacked series its own stack id in %j', (...types) => {
    const stacks = stacksOf(types)
    const own = stacks.filter((_, i) => isPlain(types[i] as ReportComboSeriesType))

    expect(own.every((id) => typeof id === 'string' && id !== '')).toBe(true)
    expect(new Set(own).size).toBe(own.length) // 서로 다르다
    const stackedIds = stacks.filter((_, i) => !isPlain(types[i] as ReportComboSeriesType))
    expect(own.filter((id) => stackedIds.includes(id))).toEqual([]) // 누적 계열의 묶음과도 겹치지 않는다
  })

  it('shares one stack id among the stacked columns and one among the stacked areas', () => {
    const stacks = stacksOf(['stacked_column', 'stacked_area', 'stacked_column', 'stacked_area'])

    expect(stacks[0]).toBeTruthy()
    expect(stacks[2]).toBe(stacks[0])
    expect(stacks[1]).toBeTruthy()
    expect(stacks[3]).toBe(stacks[1])
  })
})
