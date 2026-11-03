import type { ReportBinMode, ReportChartInput, ReportChartKind, ReportChartLegend, ReportComboSeries, ReportHistogramBins } from '../../../shared/model/reportTypes'
import type { DesignerColumn } from '../designer/state/designerState'
import { kindRule } from './chartKinds'

/**
 * 디자이너 화면의 차트 초안. 컬럼은 index가 아니라 uid로 가리켜 컬럼을 옮겨도 같은 컬럼을 따른다.
 * 저장·요청 때만 `toChartInput`으로 index로 바꾼다. 숫자 칸은 입력 칸 문자열('' = 자동).
 */
export interface ChartDraft {
  kind: ReportChartKind
  categoryUid: number | null
  seriesUid: number | null
  valueUids: number[]
  swap: boolean
  title: string
  legend: ReportChartLegend
  dataLabels: boolean
  categoryAxisTitle: string
  valueAxisTitle: string
  valueMin: string
  valueMax: string
  secondaryAxis: boolean
  /** 히스토그램 구간 설정(입력 칸 문자열). 구간 방식이 쓰지 않는 칸의 글자는 방식을 되돌릴 때를 위해 남긴다. */
  histogram: HistogramDraft
  /** 폭포: 끝에 합계 막대. */
  showTotal: boolean
  /** 콤보 계열별 설정. 값 열 uid가 키라 컬럼 순서를 바꿔도 따라간다. */
  comboTypes: Record<number, ReportComboSeries>
}

export interface HistogramDraft {
  mode: ReportBinMode
  count: string
  width: string
  overflow: string
  underflow: string
}

export const AUTO_BINS: HistogramDraft = { mode: 'auto', count: '', width: '', overflow: '', underflow: '' }

export interface ChartDraftIssue {
  /** 서버 위치 키(`category`·`series`·`values`·`value_min`·`value_max`·`histogram.bin_count`·`combo_series` 등, 중첩은 '.'로 잇는다). */
  part: string
  message: string
}

const groupsOf = (columns: readonly DesignerColumn[]): DesignerColumn[] => columns.filter((c) => c.group)
const valuesOf = (columns: readonly DesignerColumn[]): DesignerColumn[] => columns.filter((c) => !c.group)

/** 콤보 계열의 기본값: 첫 값 열은 묶은 세로 막대, 나머지는 꺾은선(서버가 채우는 옛 규칙과 같다). */
export const comboDefault = (index: number): ReportComboSeries => ({ type: index === 0 ? 'column' : 'line', secondary: false })

/** 값 열 순서대로의 콤보 계열 설정(없는 칸은 기본값). */
export function comboSettings(draft: Pick<ChartDraft, 'valueUids' | 'comboTypes'>): ReportComboSeries[] {
  return draft.valueUids.map((uid, i) => draft.comboTypes[uid] ?? comboDefault(i))
}

/**
 * 그룹핑 컬럼 1개면 묶은 세로 막대, 2개면 둘째 그룹을 계열로 한 누적 세로 막대.
 * 그룹핑이 없으면 숫자 필드(`isNumberField`) 컬럼 하나를 표본으로 한 히스토그램이고, 숫자 필드가 없거나 3개 이상이면 만들 수 없다(null).
 */
export function defaultChart(columns: readonly DesignerColumn[], headerOf: (uid: number) => string, isNumberField?: (field: string) => boolean): ChartDraft | null {
  const groups = groupsOf(columns)
  const [category, second] = groups
  const common = { swap: false, title: '', legend: 'top', dataLabels: false, valueMin: '', valueMax: '', secondaryAxis: false, histogram: { ...AUTO_BINS }, showTotal: false, comboTypes: {} } as const
  if (groups.length === 0) {
    const sample = isNumberField ? valuesOf(columns).find((c) => isNumberField(c.field)) : undefined
    if (!sample) return null
    return { ...common, kind: 'histogram', categoryUid: null, seriesUid: null, valueUids: [sample.uid], categoryAxisTitle: headerOf(sample.uid), valueAxisTitle: '빈도' }
  }
  if (!category || groups.length > 2) return null
  const first = valuesOf(columns)[0]
  return {
    ...common,
    kind: second ? 'stacked_bar' : 'bar',
    categoryUid: category.uid,
    seriesUid: second?.uid ?? null,
    valueUids: first ? [first.uid] : [],
    categoryAxisTitle: headerOf(category.uid),
    valueAxisTitle: first ? headerOf(first.uid) : '',
  }
}

/** 종류 규칙에 맞게 설정을 정리한다(쓸 수 없는 칸은 비우고 값 개수는 자른다). 값이 모자란 것은 안내로 알린다. */
export function normalizeForKind(draft: ChartDraft, kind: ReportChartKind, columns: readonly DesignerColumn[]): ChartDraft {
  const rule = kindRule(kind)
  const groups = groupsOf(columns)
  const categoryUid = rule.usesCategory ? (draft.categoryUid ?? groups[0]?.uid ?? null) : null
  let seriesUid = rule.allowsSeries ? draft.seriesUid : null
  if (rule.allowsSeries && seriesUid === null && groups.length === 2 && categoryUid !== null) {
    seriesUid = groups.find((g) => g.uid !== categoryUid)?.uid ?? null
  }
  const valueMax = seriesUid === null ? rule.valuesMax : 1
  const valueUids = draft.valueUids.slice(0, valueMax)
  return {
    ...draft,
    kind,
    categoryUid,
    seriesUid,
    valueUids,
    swap: rule.allowsSwap ? draft.swap : false,
    secondaryAxis: rule.allowsSecondary ? draft.secondaryAxis : false,
    valueMin: rule.allowsValueRange ? draft.valueMin : '',
    valueMax: rule.allowsValueRange ? draft.valueMax : '',
    showTotal: kind === 'waterfall' ? draft.showTotal : false,
    comboTypes: kind === 'combo' ? Object.fromEntries(valueUids.map((uid, i) => [uid, draft.comboTypes[uid] ?? comboDefault(i)])) : draft.comboTypes,
  }
}

/** 컬럼 편집(지우기·그룹핑 변경) 뒤 없어지거나 역할이 바뀐 참조를 뺀다. 나머지 설정은 그대로 둔다. */
export function reconcileChart(draft: ChartDraft | null, columns: readonly DesignerColumn[]): ChartDraft | null {
  if (!draft) return null
  const groupUids = new Set(groupsOf(columns).map((c) => c.uid))
  const valueUids = new Set(valuesOf(columns).map((c) => c.uid))
  const categoryUid = draft.categoryUid !== null && groupUids.has(draft.categoryUid) ? draft.categoryUid : null
  const seriesUid = draft.seriesUid !== null && groupUids.has(draft.seriesUid) ? draft.seriesUid : null
  const kept = draft.valueUids.filter((uid) => valueUids.has(uid))
  const same = categoryUid === draft.categoryUid && seriesUid === draft.seriesUid && kept.length === draft.valueUids.length
  return same ? draft : { ...draft, categoryUid, seriesUid, valueUids: kept }
}

const NUMBER_TEXT = /^[+-]?(\d+\.?\d*|\.\d+)(e[+-]?\d+)?$/i

/** '' → null, 숫자 글자 → 숫자, 그 밖은 글자 그대로(서버가 위치와 함께 거절한다). */
function rangeValue(text: string): number | string | null {
  const trimmed = text.trim()
  if (trimmed === '') return null
  if (!NUMBER_TEXT.test(trimmed)) return text
  const value = Number(trimmed)
  return Number.isFinite(value) ? value : text
}

/** 구간 설정 → 요청 모양. 구간 방식이 쓰지 않는 칸은 null로 보낸다(서버가 "비워 두세요"로 거절하지 않게). */
function histogramInput(h: HistogramDraft): ReportHistogramBins {
  return {
    binMode: h.mode,
    binCount: h.mode === 'count' ? rangeValue(h.count) : null,
    binWidth: h.mode === 'width' ? rangeValue(h.width) : null,
    overflow: rangeValue(h.overflow),
    underflow: rangeValue(h.underflow),
  }
}

/** 초안 → 요청 모양. `uids[i]`는 결과(또는 정의) i번째 열의 uid다. 참조가 없으면 범위 밖 index 대신 null을 보낸다. 종류가 쓰지 않는 옵션은 비워 보낸다. */
export function chartInputFor(draft: ChartDraft, uids: readonly number[]): ReportChartInput {
  const rule = kindRule(draft.kind)
  const indexOf = (uid: number | null): number | null => {
    if (uid === null) return null
    const index = uids.indexOf(uid)
    return index < 0 ? null : index
  }
  const settings = comboSettings(draft)
  const present = draft.valueUids.map((uid, i) => ({ index: indexOf(uid), series: settings[i] ?? comboDefault(i) })).filter((v): v is { index: number; series: ReportComboSeries } => v.index !== null)
  const combo = rule.options.includes('combo_series')
  return {
    kind: draft.kind,
    category: rule.usesCategory ? indexOf(draft.categoryUid) : null,
    series: indexOf(draft.seriesUid),
    values: present.map((v) => v.index),
    swap: draft.swap,
    title: draft.title,
    legend: draft.legend,
    dataLabels: draft.dataLabels,
    categoryAxisTitle: draft.categoryAxisTitle,
    valueAxisTitle: draft.valueAxisTitle,
    valueMin: rangeValue(draft.valueMin),
    valueMax: rangeValue(draft.valueMax),
    secondaryAxis: combo ? present.some((v) => v.series.secondary) : draft.secondaryAxis,
    histogram: rule.options.includes('histogram') ? histogramInput(draft.histogram) : null,
    showTotal: rule.options.includes('show_total') ? draft.showTotal : false,
    comboSeries: combo ? present.map((v) => v.series) : null,
  }
}

export function toChartInput(draft: ChartDraft, columns: readonly DesignerColumn[]): ReportChartInput {
  return chartInputFor(
    draft,
    columns.map((c) => c.uid),
  )
}

/** 저장된 차트(index) → 초안(uid). 범위 밖 index는 참조 없음으로 둔다. */
export function fromChartInput(input: ReportChartInput | null, columns: readonly DesignerColumn[]): ChartDraft | null {
  if (!input) return null
  const uidAt = (index: number | null): number | null => (index === null ? null : (columns[index]?.uid ?? null))
  const text = (value: number | string | null): string => (value === null ? '' : String(value))
  return {
    kind: input.kind,
    categoryUid: uidAt(input.category),
    seriesUid: uidAt(input.series),
    valueUids: input.values.map(uidAt).filter((uid): uid is number => uid !== null),
    swap: input.swap,
    title: input.title,
    legend: input.legend,
    dataLabels: input.dataLabels,
    categoryAxisTitle: input.categoryAxisTitle,
    valueAxisTitle: input.valueAxisTitle,
    valueMin: text(input.valueMin),
    valueMax: text(input.valueMax),
    secondaryAxis: input.secondaryAxis,
    histogram: input.histogram
      ? { mode: input.histogram.binMode, count: text(input.histogram.binCount), width: text(input.histogram.binWidth), overflow: text(input.histogram.overflow), underflow: text(input.histogram.underflow) }
      : { ...AUTO_BINS },
    showTotal: input.showTotal,
    comboTypes: comboTypesOf(input, uidAt),
  }
}

/** 저장된 콤보 계열(값 열 순서) → 값 열 uid 키 설정. 참조가 없는 열은 건너뛴다. */
function comboTypesOf(input: ReportChartInput, uidAt: (index: number | null) => number | null): Record<number, ReportComboSeries> {
  const entries: [number, ReportComboSeries][] = []
  input.values.forEach((index, i) => {
    const uid = uidAt(index)
    const series = input.comboSeries?.[i]
    if (uid !== null && series) entries.push([uid, { ...series }])
  })
  return Object.fromEntries(entries)
}

function countMessage(min: number, max: number): string {
  return min === max ? `이 차트는 값 열을 ${min}개 골라야 합니다` : `이 차트는 값 열을 ${min}~${max}개 골라야 합니다`
}

/** 서버 규칙 중 화면에서 판정할 수 있는 것의 안내(문구는 서버와 같다). 저장을 막지는 않는다(서버가 정본). */
const BIN_COUNT_MAX = 100

function histogramIssues(h: HistogramDraft): ChartDraftIssue[] {
  const issues: ChartDraftIssue[] = []
  if (h.mode === 'count') {
    const count = rangeValue(h.count)
    if (typeof count !== 'number' || !Number.isInteger(count) || count < 1 || count > BIN_COUNT_MAX) {
      issues.push({ part: 'histogram.bin_count', message: '구간 수는 1~100의 정수입니다' })
    }
  }
  if (h.mode === 'width') {
    const width = rangeValue(h.width)
    if (typeof width !== 'number' || !(width > 0) || width > Number.MAX_SAFE_INTEGER) {
      issues.push({ part: 'histogram.bin_width', message: '구간 너비는 0보다 큰 숫자입니다' })
    }
  }
  const over = rangeValue(h.overflow)
  const under = rangeValue(h.underflow)
  if (typeof over === 'string') issues.push({ part: 'histogram.overflow', message: '숫자를 입력하세요' })
  if (typeof under === 'string') issues.push({ part: 'histogram.underflow', message: '숫자를 입력하세요' })
  if (typeof over === 'number' && typeof under === 'number' && under >= over) {
    issues.push({ part: 'histogram.overflow', message: '오버플로 구간은 언더플로 구간보다 커야 합니다' })
  }
  return issues
}

/** 서버 규칙 중 화면에서 판정할 수 있는 것의 안내(문구는 서버와 같다). 저장을 막지는 않는다(서버가 정본). */
export function chartDraftIssues(draft: ChartDraft, columns: readonly DesignerColumn[]): ChartDraftIssue[] {
  const rule = kindRule(draft.kind)
  const groupUids = groupsOf(columns).map((c) => c.uid)
  const issues: ChartDraftIssue[] = []
  if (rule.usesCategory && (draft.categoryUid === null || !groupUids.includes(draft.categoryUid))) issues.push({ part: 'category', message: '범주 열을 고르세요' })
  if (rule.allowsSeries && groupUids.length === 2 && draft.seriesUid === null) {
    issues.push({ part: 'series', message: '그룹핑 컬럼이 2개면 나머지 하나를 계열로 고르세요' })
  }
  const count = draft.valueUids.length
  const [min, max] = draft.seriesUid === null ? [rule.valuesMin, rule.valuesMax] : [1, 1]
  if (count === 0) issues.push({ part: 'values', message: '값 열을 고르세요' })
  else if (count < min || count > max) issues.push({ part: 'values', message: countMessage(min, max) })
  const low = rangeValue(draft.valueMin)
  const high = rangeValue(draft.valueMax)
  if (typeof low === 'string') issues.push({ part: 'value_min', message: '숫자를 입력하세요' })
  if (typeof high === 'string') issues.push({ part: 'value_max', message: '숫자를 입력하세요' })
  if (typeof low === 'number' && typeof high === 'number' && low >= high) issues.push({ part: 'value_max', message: '최대는 최소보다 커야 합니다' })
  if (rule.options.includes('histogram')) issues.push(...histogramIssues(draft.histogram))
  if (rule.options.includes('combo_series') && count > 0 && comboSettings(draft).every((s) => s.secondary)) {
    issues.push({ part: 'combo_series', message: '모든 계열을 보조 축에 둘 수 없습니다' })
  }
  return issues
}
