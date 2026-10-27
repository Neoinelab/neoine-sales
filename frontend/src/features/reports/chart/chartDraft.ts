import type { ReportChartInput, ReportChartKind, ReportChartLegend } from '../../../shared/model/reportTypes'
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
}

export interface ChartDraftIssue {
  /** 서버 위치 키(`category`·`series`·`values`·`value_min`·`value_max`). */
  part: string
  message: string
}

const groupsOf = (columns: readonly DesignerColumn[]): DesignerColumn[] => columns.filter((c) => c.group)
const valuesOf = (columns: readonly DesignerColumn[]): DesignerColumn[] => columns.filter((c) => !c.group)

/** 그룹핑 컬럼 1개면 세로 막대, 2개면 둘째 그룹을 계열로 한 누적 막대. 0개·3개 이상이면 만들 수 없다(null). */
export function defaultChart(columns: readonly DesignerColumn[], headerOf: (uid: number) => string): ChartDraft | null {
  const groups = groupsOf(columns)
  const [category, second] = groups
  if (!category || groups.length > 2) return null
  const first = valuesOf(columns)[0]
  return {
    kind: second ? 'stacked_bar' : 'bar',
    categoryUid: category.uid,
    seriesUid: second?.uid ?? null,
    valueUids: first ? [first.uid] : [],
    swap: false,
    title: '',
    legend: 'top',
    dataLabels: false,
    categoryAxisTitle: headerOf(category.uid),
    valueAxisTitle: first ? headerOf(first.uid) : '',
    valueMin: '',
    valueMax: '',
    secondaryAxis: false,
  }
}

/** 종류 규칙에 맞게 설정을 정리한다(쓸 수 없는 칸은 비우고 값 개수는 자른다). 값이 모자란 것은 안내로 알린다. */
export function normalizeForKind(draft: ChartDraft, kind: ReportChartKind, columns: readonly DesignerColumn[]): ChartDraft {
  const rule = kindRule(kind)
  const groups = groupsOf(columns)
  let seriesUid = rule.allowsSeries ? draft.seriesUid : null
  if (rule.allowsSeries && seriesUid === null && groups.length === 2 && draft.categoryUid !== null) {
    seriesUid = groups.find((g) => g.uid !== draft.categoryUid)?.uid ?? null
  }
  const valueMax = seriesUid === null ? rule.valuesMax : 1
  return {
    ...draft,
    kind,
    seriesUid,
    valueUids: draft.valueUids.slice(0, valueMax),
    swap: rule.allowsSwap ? draft.swap : false,
    secondaryAxis: rule.allowsSecondary ? draft.secondaryAxis : false,
    valueMin: rule.allowsValueRange ? draft.valueMin : '',
    valueMax: rule.allowsValueRange ? draft.valueMax : '',
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

/** 초안 → 요청 모양. `uids[i]`는 결과(또는 정의) i번째 열의 uid다. 참조가 없으면 범위 밖 index 대신 null을 보낸다. */
export function chartInputFor(draft: ChartDraft, uids: readonly number[]): ReportChartInput {
  const indexOf = (uid: number | null): number | null => {
    if (uid === null) return null
    const index = uids.indexOf(uid)
    return index < 0 ? null : index
  }
  return {
    kind: draft.kind,
    category: indexOf(draft.categoryUid),
    series: indexOf(draft.seriesUid),
    values: draft.valueUids.map(indexOf).filter((i): i is number => i !== null),
    swap: draft.swap,
    title: draft.title,
    legend: draft.legend,
    dataLabels: draft.dataLabels,
    categoryAxisTitle: draft.categoryAxisTitle,
    valueAxisTitle: draft.valueAxisTitle,
    valueMin: rangeValue(draft.valueMin),
    valueMax: rangeValue(draft.valueMax),
    secondaryAxis: draft.secondaryAxis,
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
  }
}

function countMessage(min: number, max: number): string {
  return min === max ? `이 차트는 값 열을 ${min}개 골라야 합니다` : `이 차트는 값 열을 ${min}~${max}개 골라야 합니다`
}

/** 서버 규칙 중 화면에서 판정할 수 있는 것의 안내(문구는 서버와 같다). 저장을 막지는 않는다(서버가 정본). */
export function chartDraftIssues(draft: ChartDraft, columns: readonly DesignerColumn[]): ChartDraftIssue[] {
  const rule = kindRule(draft.kind)
  const groupUids = groupsOf(columns).map((c) => c.uid)
  const issues: ChartDraftIssue[] = []
  if (draft.categoryUid === null || !groupUids.includes(draft.categoryUid)) issues.push({ part: 'category', message: '범주 열을 고르세요' })
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
  return issues
}
