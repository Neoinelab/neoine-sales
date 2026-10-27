import type { Schemas } from '../../../shared/api/client'
import type { ReportChartInput, ReportChartKind, ReportChartLegend } from '../../../shared/model/reportTypes'
import { malformedResponse } from '../request'

const KINDS: readonly string[] = ['bar', 'horizontal_bar', 'stacked_bar', 'stacked_100_bar', 'line', 'area', 'pie', 'doughnut', 'scatter', 'combo']
const LEGENDS: readonly string[] = ['top', 'right', 'bottom', 'none']

/** 모르는 종류는 화면이 그릴 수 없으므로 계약 위반(malformed-response)이다. */
export function toChartKind(value: string): ReportChartKind {
  if (KINDS.includes(value)) return value as ReportChartKind
  throw malformedResponse()
}

function toLegend(value: string): ReportChartLegend {
  if (LEGENDS.includes(value)) return value as ReportChartLegend
  throw malformedResponse()
}

export function toChart(body: Schemas['ReportChartResponse']): ReportChartInput {
  return {
    kind: toChartKind(body.kind),
    category: body.category,
    series: body.series,
    values: [...body.values],
    swap: body.swap,
    title: body.title,
    legend: toLegend(body.legend),
    dataLabels: body.data_labels,
    categoryAxisTitle: body.category_axis_title,
    valueAxisTitle: body.value_axis_title,
    valueMin: body.value_min,
    valueMax: body.value_max,
    secondaryAxis: body.secondary_axis,
  }
}

/** 요청 본문(snake_case, 13개 키 모두). 서버가 값 검증을 하므로 불완전한 값도 그대로 보낸다. */
export function toChartBody(input: ReportChartInput): Schemas['ReportChartRequest'] {
  return {
    kind: input.kind,
    category: input.category,
    series: input.series,
    values: input.values,
    swap: input.swap,
    title: input.title,
    legend: input.legend,
    data_labels: input.dataLabels,
    category_axis_title: input.categoryAxisTitle,
    value_axis_title: input.valueAxisTitle,
    value_min: input.valueMin,
    value_max: input.valueMax,
    secondary_axis: input.secondaryAxis,
  }
}
