import type { Schemas } from '../../../shared/api/client'
import {
  CHART_KIND_KEYS,
  type ReportBinMode,
  type ReportChartInput,
  type ReportChartKind,
  type ReportChartLegend,
  type ReportComboSeries,
  type ReportComboSeriesType,
  type ReportHistogramBins,
} from '../../../shared/model/reportTypes'
import { malformedResponse } from '../request'

const KINDS: readonly string[] = CHART_KIND_KEYS
const LEGENDS: readonly string[] = ['top', 'right', 'bottom', 'none']
const BIN_MODES: readonly string[] = ['auto', 'count', 'width']
const COMBO_TYPES: readonly string[] = ['column', 'stacked_column', 'line', 'line_markers', 'area', 'stacked_area']

/** 모르는 종류는 화면이 그릴 수 없으므로 계약 위반(malformed-response)이다. */
export function toChartKind(value: string): ReportChartKind {
  if (KINDS.includes(value)) return value as ReportChartKind
  throw malformedResponse()
}

function toLegend(value: string): ReportChartLegend {
  if (LEGENDS.includes(value)) return value as ReportChartLegend
  throw malformedResponse()
}

function toHistogram(body: Schemas['HistogramResponse'] | null): ReportHistogramBins | null {
  if (body === null) return null
  if (!BIN_MODES.includes(body.bin_mode)) throw malformedResponse()
  return { binMode: body.bin_mode as ReportBinMode, binCount: body.bin_count, binWidth: body.bin_width, overflow: body.overflow, underflow: body.underflow }
}

function toComboSeries(body: Schemas['ComboSeriesResponse'][] | null): ReportComboSeries[] | null {
  if (body === null) return null
  return body.map((item) => {
    if (!COMBO_TYPES.includes(item.type)) throw malformedResponse()
    return { type: item.type as ReportComboSeriesType, secondary: item.secondary }
  })
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
    histogram: toHistogram(body.histogram),
    showTotal: body.show_total,
    comboSeries: toComboSeries(body.combo_series),
  }
}

/** 요청 본문(snake_case, 16개 키 모두). 서버가 값 검증을 하므로 불완전한 값도 그대로 보낸다. */
export function toChartBody(input: ReportChartInput): Schemas['ReportChartRequest'] {
  const { histogram } = input
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
    histogram: histogram
      ? { bin_mode: histogram.binMode, bin_count: histogram.binCount, bin_width: histogram.binWidth, overflow: histogram.overflow, underflow: histogram.underflow }
      : null,
    show_total: input.showTotal,
    combo_series: input.comboSeries,
  }
}
