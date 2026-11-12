import { describe, expect, it } from 'vitest'
import { designerReducer, type DesignerState } from '../designer/state/designerState'
import { emptyDesign, fieldOf, reduce, REPORT_CATALOG, uidAt, withColumns } from '../../../test/reportDesigner'
import type { ReportChartInput, ReportChartKind } from '../../../shared/model/reportTypes'
import { CHART_KINDS } from './chartKinds'
import { chartDraftIssues, defaultChart, fromChartInput, normalizeForKind, reconcileChart, toChartInput, type ChartDraft } from './chartDraft'

/**
 * 차트 초안(화면 상태, 컬럼은 uid로 가리킨다)의 순수 함수(명세 RC-R25~RC-R34).
 * 시그니처(테스트가 정한 계약):
 *   defaultChart(columns, headerOf: (uid) => string): ChartDraft | null   그룹핑 1~2개가 아니면 null
 *   normalizeForKind(draft, kind, columns): ChartDraft
 *   reconcileChart(draft | null, columns): ChartDraft | null
 *   toChartInput(draft, columns): 요청 모양(참조가 없으면 null, 숫자 칸이 잘못되면 글자 그대로)
 *   fromChartInput(input | null, columns): ChartDraft | null   index → uid, 범위 밖 index는 참조 없음
 *   chartDraftIssues(draft, columns): { part, message }[]
 */

/** key 목록으로 컬럼을 추가하고, group에 든 index의 컬럼을 그룹핑한다(집계는 카탈로그 기본값이 채워진다). */
function design(keys: string[], groups: number[]): DesignerState {
  let state = withColumns(...keys)
  for (const i of groups) state = reduce(state, { type: 'updateColumn', uid: uidAt(state, i), patch: { group: true } })
  return state
}

const HEADERS: Record<number, string> = { 1: 'Vendor', 2: 'Status', 3: '금액 합계 (원)', 4: 'Users count 합계' }
const headerOf = (uid: number): string => HEADERS[uid] ?? ''
/** ONE_GROUP 설계의 uid 기준 머리글(Vendor 1, 금액 2, Users count 3, Status 체류 4). */
const ONE_GROUP_HEADERS: Record<number, string> = { 1: 'Vendor', 2: '금액 합계 (원)', 3: 'Users count 합계', 4: 'Status 체류 합계' }
const oneGroupHeaderOf = (uid: number): string => ONE_GROUP_HEADERS[uid] ?? ''

/** Vendor(그룹, uid 1), 금액(2), Users(3), Status 체류(4)로 이루어진 1그룹 설계. */
const ONE_GROUP = (): DesignerState => design(['deal.vendor', 'deal.amount', 'deal.users', 'deal.status_days'], [0])
/** Vendor(1), Status(2) 그룹 + 금액(3), Users(4). */
const TWO_GROUPS = (): DesignerState => design(['deal.vendor', 'deal.status', 'deal.amount', 'deal.users'], [0, 1])

function draft(over: Partial<ChartDraft> = {}): ChartDraft {
  return {
    kind: 'bar',
    categoryUid: 1,
    seriesUid: null,
    valueUids: [2],
    swap: false,
    title: '',
    legend: 'top',
    dataLabels: false,
    categoryAxisTitle: '',
    valueAxisTitle: '',
    valueMin: '',
    valueMax: '',
    secondaryAxis: false,
    histogram: { mode: 'auto', count: '', width: '', overflow: '', underflow: '' },
    showTotal: false,
    comboTypes: {},
    ...over,
  }
}

describe('기본 차트(defaultChart)', () => {
  // 테스트 코드: RC-051
  it('그룹 1개의 기본 차트는 묶은 세로 막대이고 축 제목은 컬럼 머리글이다', () => {
    // when: 그룹 컬럼 1개 설계로 기본 차트를 만든다
    const created = defaultChart(ONE_GROUP().columns, oneGroupHeaderOf)

    // then: 묶은 세로 막대, 범주는 그 그룹, 값은 첫 값 컬럼이고 가로축·세로축 제목이 머리글이며 나머지는 기본값이다
    expect(created).toEqual({
      kind: 'bar',
      categoryUid: 1,
      seriesUid: null,
      valueUids: [2],
      swap: false,
      title: '',
      legend: 'top',
      dataLabels: false,
      categoryAxisTitle: 'Vendor',
      valueAxisTitle: '금액 합계 (원)',
      valueMin: '',
      valueMax: '',
      secondaryAxis: false,
      histogram: { mode: 'auto', count: '', width: '', overflow: '', underflow: '' },
      showTotal: false,
      comboTypes: {},
    })
  })

  // 테스트 코드: RC-051
  it('그룹 2개의 기본 차트는 누적 세로 막대이고 둘째 그룹이 계열이다', () => {
    // when: 그룹 컬럼 2개 설계로 기본 차트를 만든다
    const created = defaultChart(TWO_GROUPS().columns, headerOf)

    // then: 누적 세로 막대이고 범주는 첫 그룹, 계열은 둘째 그룹이며 축 제목이 머리글이다
    expect(created).toMatchObject({ kind: 'stacked_bar', categoryUid: 1, seriesUid: 2, valueUids: [3], categoryAxisTitle: 'Vendor', valueAxisTitle: '금액 합계 (원)' })
  })

  // 테스트 코드: RC-051
  it('그룹이 3개 이상이면 기본 차트를 만들지 않는다 (그룹 0개의 히스토그램은 RC-052)', () => {
    // given: 그룹 컬럼이 없는 설계와 3개인 설계
    const none = withColumns('deal.code', 'deal.name')
    const three = design(['deal.vendor', 'deal.status', 'deal.forecast', 'deal.amount'], [0, 1, 2])

    // when: 각 설계로 기본 차트를 만든다
    const withoutGroups = defaultChart(none.columns, headerOf)
    const withThreeGroups = defaultChart(three.columns, headerOf)

    // then: 둘 다 만들지 않는다(null)
    expect(withoutGroups).toBeNull()
    expect(withThreeGroups).toBeNull()
  })

  // 테스트 코드: RC-051
  it('집계 컬럼이 없으면 기본 차트의 값이 비어 있다', () => {
    // given: 그룹 컬럼만 있는 설계
    const onlyGroup = design(['deal.vendor'], [0])

    // when: 기본 차트를 만든다
    const actual = defaultChart(onlyGroup.columns, headerOf)

    // then: 막대이고 범주는 그 그룹이며 값은 비어 있다
    expect(actual).toMatchObject({ kind: 'bar', categoryUid: 1, valueUids: [] })
  })
})

describe('종류 변경 정리(normalizeForKind)', () => {
  const rich = () => draft({ kind: 'bar', valueUids: [2, 3, 4], swap: true, secondaryAxis: true, valueMin: '1', valueMax: '9', title: '제목' })

  // 테스트 코드: RC-057
  it.each<ReportChartKind>(['pie', 'doughnut'])('원형·도넛형으로 바꾸면 값 하나만 남기고 계열·전환·보조 축·범위를 정리한다 (%s)', (kind) => {
    // when: 원형 또는 도넛형으로 종류를 바꾼다 (전제: 값 3개·전환·보조 축·범위·제목을 가진 막대 초안)
    const next = normalizeForKind(rich(), kind, ONE_GROUP().columns)

    // then: 값 1개이고 계열·전환·보조 축·범위가 없으며 제목과 범주는 그대로다
    expect(next).toMatchObject({ kind, seriesUid: null, valueUids: [2], swap: false, secondaryAxis: false, valueMin: '', valueMax: '', title: '제목', categoryUid: 1 })
  })

  // 테스트 코드: RC-057
  it('분산형으로 바꾸면 값 10개까지와 범위는 두고 전환·보조 축만 끈다', () => {
    // when: 분산형으로 종류를 바꾼다 (전제: 값 3개·전환·보조 축·범위를 가진 막대 초안)
    const next = normalizeForKind(rich(), 'scatter', ONE_GROUP().columns)

    // then: 값 3개와 범위는 그대로이고 전환·보조 축은 꺼진다
    expect(next).toMatchObject({ kind: 'scatter', valueUids: [2, 3, 4], swap: false, secondaryAxis: false, valueMin: '1', valueMax: '9' })
  })

  // 테스트 코드: RC-057
  it('콤보로 바꾸면 값 전부와 보조 축은 두고 전환만 끈다', () => {
    // when: 콤보로 종류를 바꾼다 (전제: 값 3개·전환·보조 축·범위를 가진 막대 초안)
    const next = normalizeForKind(rich(), 'combo', ONE_GROUP().columns)

    // then: 값 3개와 보조 축·범위는 그대로이고 전환은 꺼진다
    expect(next).toMatchObject({ kind: 'combo', valueUids: [2, 3, 4], swap: false, secondaryAxis: true, valueMin: '1', valueMax: '9' })
  })

  // 테스트 코드: RC-057
  it.each<ReportChartKind>(['bar', 'horizontal_bar', 'stacked_bar', 'stacked_100_bar', 'line', 'area'])('막대·꺾은선·영역으로 바꾸면 전환·값·범위는 두고 보조 축만 끈다 (%s)', (kind) => {
    // when: 막대형 종류로 바꾼다 (전제: 값 2개·전환·보조 축·범위를 가진 원형 초안)
    const next = normalizeForKind(draft({ kind: 'pie', valueUids: [2, 3], swap: true, secondaryAxis: true, valueMin: '1', valueMax: '9' }), kind, ONE_GROUP().columns)

    // then: 값 2개·전환·범위는 그대로이고 보조 축만 꺼진다
    expect(next).toMatchObject({ kind, valueUids: [2, 3], swap: true, secondaryAxis: false, valueMin: '1', valueMax: '9' })
  })

  // 테스트 코드: RC-057
  it('원형에서 누적 막대로 바꾸면 남는 그룹 컬럼이 계열로 채워진다', () => {
    // given: 계열 없는 원형 초안
    const pie = draft({ kind: 'pie', categoryUid: 1, seriesUid: null, valueUids: [3] })

    // when: 그룹 2개 설계에서 누적 막대로 바꾼다
    const actual = normalizeForKind(pie, 'stacked_bar', TWO_GROUPS().columns)

    // then: 범주는 그대로이고 둘째 그룹이 계열이 된다
    expect(actual).toMatchObject({ kind: 'stacked_bar', categoryUid: 1, seriesUid: 2 })
  })

  // 테스트 코드: RC-057
  it('계열을 쓰지 않는 종류로 바꾸면 계열을 비운다', () => {
    // given: 계열이 있는 누적 막대 초안
    const stacked = draft({ kind: 'stacked_bar', seriesUid: 2, valueUids: [3] })

    // when: 콤보로 바꾼다
    const actual = normalizeForKind(stacked, 'combo', TWO_GROUPS().columns).seriesUid

    // then: 계열이 없다
    expect(actual).toBeNull()
  })

  // 테스트 코드: RC-057
  it.each(CHART_KINDS.map((k) => k.key))('모든 종류의 정리 결과가 그 종류의 규칙표를 따른다 (%s)', (kind) => {
    // given: 그 종류의 규칙표 행
    const rule = CHART_KINDS.find((k) => k.key === kind)
    if (!rule) throw new Error('rule')

    // when: 값 3개·전환·보조 축·범위가 있는 초안을 그 종류로 바꾼다
    const next = normalizeForKind(rich(), kind, ONE_GROUP().columns)

    // then: 값 개수 한도와 전환·보조 축·범위·계열 허용이 규칙표를 따른다
    expect(next.kind).toBe(kind)
    expect(next.valueUids.length).toBeLessThanOrEqual(rule.valuesMax)
    if (!rule.allowsSwap) expect(next.swap).toBe(false)
    if (!rule.allowsSecondary) expect(next.secondaryAxis).toBe(false)
    if (!rule.allowsValueRange) expect([next.valueMin, next.valueMax]).toEqual(['', ''])
    if (!rule.allowsSeries) expect(next.seriesUid).toBeNull()
  })
})

describe('컬럼 변경 뒤 참조 정리(reconcileChart)', () => {
  // 테스트 코드: RC-070
  it('값 컬럼을 지우면 그 값만 빠지고 나머지 설정은 그대로다', () => {
    // given: 값 컬럼 2개를 쓰는 차트 초안과 설계
    const before = ONE_GROUP()
    const chart = draft({ valueUids: [2, 3], title: '제목' })
    // when: 값 컬럼 하나를 설계에서 지운다
    const after = designerReducer(before, { type: 'removeColumn', uid: 3 }, REPORT_CATALOG)

    // then: 정리한 초안은 값에서만 빠지고 나머지는 같다
    expect(reconcileChart(chart, after.columns)).toEqual({ ...chart, valueUids: [2] })
  })

  // 테스트 코드: RC-070
  it('범주 컬럼의 그룹핑을 끄면 범주가 비워지고 나머지 설정은 그대로다', () => {
    // when: 범주 컬럼의 그룹핑을 끈다
    const after = designerReducer(ONE_GROUP(), { type: 'updateColumn', uid: 1, patch: { group: false } }, REPORT_CATALOG)

    // then: 범주는 null이고 제목은 남는다
    expect(reconcileChart(draft({ title: '남는 제목' }), after.columns)).toMatchObject({ categoryUid: null, title: '남는 제목' })
  })

  // 테스트 코드: RC-070
  it('계열 컬럼의 그룹핑을 끄면 계열만 비워지고 범주는 남는다', () => {
    // given: 그룹 2개 설계
    const before = TWO_GROUPS()
    // when: 계열 컬럼의 그룹핑을 끈다
    const after = designerReducer(before, { type: 'updateColumn', uid: 2, patch: { group: false } }, REPORT_CATALOG)

    // then: 범주는 그대로이고 계열은 null이다
    expect(reconcileChart(draft({ kind: 'stacked_bar', seriesUid: 2, valueUids: [3] }), after.columns)).toMatchObject({ categoryUid: 1, seriesUid: null })
  })

  // 테스트 코드: RC-070
  it('값 컬럼이 그룹이 되면 값에서 빠진다', () => {
    // when: 값 컬럼을 그룹핑한다
    const after = designerReducer(ONE_GROUP(), { type: 'updateColumn', uid: 3, patch: { group: true } }, REPORT_CATALOG)

    // then: 값 목록에서 그 컬럼이 빠진다
    expect(reconcileChart(draft({ valueUids: [2, 3] }), after.columns)?.valueUids).toEqual([2])
  })

  // 테스트 코드: RC-070
  it('범주 컬럼을 지우면 범주가 비워진다', () => {
    // when: 범주 컬럼을 설계에서 지운다
    const after = designerReducer(ONE_GROUP(), { type: 'removeColumn', uid: 1 }, REPORT_CATALOG)

    // then: 범주는 null이다
    expect(reconcileChart(draft(), after.columns)?.categoryUid).toBeNull()
  })

  // 테스트 코드: RC-070
  it('컬럼을 옮기면 uid로 따라가서 요청 index만 바뀐다', () => {
    // given: 값 컬럼 하나를 쓰는 차트 초안과 설계
    const before = ONE_GROUP()
    const chart = draft({ valueUids: [3] })
    // when: 그 값 컬럼을 맨 앞으로 옮긴다
    const moved = designerReducer(before, { type: 'moveColumn', uid: 3, to: 0 }, REPORT_CATALOG)

    // then: 정리한 초안은 그대로이고 요청 index만 옮기기 전후로 달라진다
    expect(reconcileChart(chart, moved.columns)).toEqual(chart)
    expect(toChartInput(chart, before.columns)).toMatchObject({ category: 0, values: [2] })
    expect(toChartInput(chart, moved.columns)).toMatchObject({ category: 1, values: [0] })
  })

  // 테스트 코드: RC-070
  it('초안이 없으면 정리해도 없다', () => {
    // when: null 초안을 정리한다
    const actual = reconcileChart(null, ONE_GROUP().columns)
    // then: null이다
    expect(actual).toBeNull()
  })
})

describe('요청 차트와 초안 변환', () => {
  const INPUT: ReportChartInput = {
    kind: 'stacked_bar',
    category: 0,
    series: 1,
    values: [2],
    swap: true,
    title: '분기 Pipeline',
    legend: 'right',
    dataLabels: true,
    categoryAxisTitle: 'Vendor',
    valueAxisTitle: '금액',
    valueMin: 0,
    valueMax: 12.5,
    secondaryAxis: false,
    histogram: null,
    showTotal: false,
    comboSeries: null,
  }

  // 테스트 코드: RC-072
  it('요청 차트를 초안으로 바꿨다가 다시 요청으로 바꾸면 같은 값이다', () => {
    // given: 그룹 2개 설계
    const columns = TWO_GROUPS().columns

    // when: 저장 차트 입력을 초안으로 바꾼다
    const restored = fromChartInput(INPUT, columns)

    // then: 초안의 참조가 uid이고 다시 요청으로 바꾸면 원래 입력과 같다
    expect(restored).toMatchObject({ categoryUid: 1, seriesUid: 2, valueUids: [3], valueMin: '0', valueMax: '12.5' })
    expect(restored && toChartInput(restored, columns)).toEqual(INPUT)
  })

  // 테스트 코드: RC-072
  it('범위가 없거나 음수 최소값인 차트도 왕복해서 같다', () => {
    // given: 음수 최소·최대 없음 범위의 입력
    const columns = ONE_GROUP().columns
    const input: ReportChartInput = { ...INPUT, kind: 'bar', series: null, valueMin: -3, valueMax: null }

    // when: 초안으로 바꾼다
    const restored = fromChartInput(input, columns)

    // then: 다시 요청으로 바꾸면 같은 입력이다
    expect(restored && toChartInput(restored, columns)).toEqual(input)
  })

  // 테스트 코드: RC-072
  it('입력이 없으면 초안도 없다', () => {
    // when: null 입력을 초안으로 바꾼다
    const actual = fromChartInput(null, ONE_GROUP().columns)
    // then: null이다
    expect(actual).toBeNull()
  })

  // 테스트 코드: RC-072
  it('열 밖 index를 가리키는 참조는 참조 없음으로 둔다', () => {
    // when: 범위 밖 index의 입력을 초안으로 바꾼다
    const restored = fromChartInput({ ...INPUT, category: 9, series: 8, values: [1, 7] }, TWO_GROUPS().columns)

    // then: 범주·계열은 null이고 값은 있는 것만 남는다
    expect(restored).toMatchObject({ categoryUid: null, seriesUid: null, valueUids: [2] })
  })
})

describe('미완성 초안의 요청 변환(toChartInput)', () => {
  // 테스트 코드: RC-071
  it('참조가 없으면 범위 밖 index 대신 null을 보낸다', () => {
    // when: 범주 없음·없는 계열 uid의 초안을 요청으로 바꾼다
    const input = toChartInput(draft({ categoryUid: null, seriesUid: 99, valueUids: [2] }), ONE_GROUP().columns)

    // then: 범주·계열은 null이고 값은 index로 바뀐다
    expect(input).toMatchObject({ category: null, series: null, values: [1] })
  })

  // 테스트 코드: RC-071
  it('숫자 글자는 숫자로, 빈칸은 null로, 잘못된 글자는 그대로 보낸다', () => {
    // given: 그룹 1개 설계
    const columns = ONE_GROUP().columns

    // when: 범위 글자가 숫자·빈칸·잘못된 글자인 초안을 요청으로 바꾼다
    const actual = toChartInput(draft({ valueMin: '12.5', valueMax: '' }), columns)
    const actual2 = toChartInput(draft({ valueMin: 'abc', valueMax: 'Infinity' }), columns)
    // then: 각각 숫자·null·글자 그대로다
    expect(actual).toMatchObject({ valueMin: 12.5, valueMax: null })
    expect(actual2).toMatchObject({ valueMin: 'abc', valueMax: 'Infinity' })
  })

  // 테스트 코드: RC-071
  it('글자와 켜기·끄기 값은 그대로 보낸다', () => {
    // when: 글자와 켜기·끄기를 채운 초안을 요청으로 바꾼다
    const input = toChartInput(draft({ title: ' 제목 ', legend: 'none', dataLabels: true, categoryAxisTitle: 'x', valueAxisTitle: 'y' }), ONE_GROUP().columns)

    // then: 제목(공백 포함)·범례·데이터 레이블·축 제목이 그대로다
    expect(input).toMatchObject({ kind: 'bar', swap: false, title: ' 제목 ', legend: 'none', dataLabels: true, categoryAxisTitle: 'x', valueAxisTitle: 'y', secondaryAxis: false })
  })
})

describe('화면 안내(chartDraftIssues)', () => {
  const messages = (d: ChartDraft, state: DesignerState) => chartDraftIssues(d, state.columns).map((i) => i.message)

  // 테스트 코드: RC-067
  it('완성된 초안에는 화면 안내가 없다', () => {
    // when: 기본 초안의 문제 항목을 구한다
    const actual = chartDraftIssues(draft(), ONE_GROUP().columns)
    // then: 안내가 없다
    expect(actual).toEqual([])
  })

  // 테스트 코드: RC-067
  it('범주가 없으면 범주 열을 고르라고 안내한다', () => {
    // when: 범주를 비운 초안의 안내 문구를 만든다
    const actual = messages(draft({ categoryUid: null }), ONE_GROUP())
    // then: 범주 열을 고르라는 안내가 있다
    expect(actual).toContain('범주 열을 고르세요')
  })

  // 테스트 코드: RC-067
  it('그룹이 2개인데 계열이 없으면 계열을 고르라고 안내한다', () => {
    // when: 계열 없이 값 1개인 누적 막대 초안의 안내 문구를 만든다
    const actual = messages(draft({ kind: 'stacked_bar', seriesUid: null, valueUids: [3] }), TWO_GROUPS())
    // then: 나머지 하나를 계열로 고르라는 안내가 있다
    expect(actual).toContain('그룹핑 컬럼이 2개면 나머지 하나를 계열로 고르세요')
  })

  // 테스트 코드: RC-067
  it('값이 없거나 종류의 값 개수와 다르면 안내한다', () => {
    // when: 값이 없는 초안과 값 1개인 분산형 초안의 안내 문구를 만든다
    const actual = messages(draft({ valueUids: [] }), ONE_GROUP())
    const actual2 = messages(draft({ kind: 'scatter', valueUids: [2] }), ONE_GROUP())
    // then: 값 열을 고르라는 안내와 값 열 2~10개를 고르라는 안내가 있다
    expect(actual).toContain('값 열을 고르세요')
    expect(actual2).toContain('이 차트는 값 열을 2~10개 골라야 합니다')
  })

  // 테스트 코드: RC-067
  it('범위 글자가 숫자가 아니거나 최대가 최소보다 작으면 안내한다', () => {
    // when: 세로축 최소가 숫자가 아닌 초안과 최소가 최대보다 큰 초안의 안내 문구를 만든다
    const actual = messages(draft({ valueMin: 'abc' }), ONE_GROUP())
    const actual2 = messages(draft({ valueMin: '10', valueMax: '5' }), ONE_GROUP())
    // then: 숫자를 입력하라는 안내와 최대가 최소보다 커야 한다는 안내가 있다
    expect(actual).toContain('숫자를 입력하세요')
    expect(actual2).toContain('최대는 최소보다 커야 합니다')
  })

  // 테스트 코드: RC-067
  it('안내는 어느 칸에 속하는지 알려 준다', () => {
    // when: 범주가 없고 최소 글자가 잘못된 초안의 안내를 구한다
    const parts = chartDraftIssues(draft({ categoryUid: null, valueMin: 'abc' }), ONE_GROUP().columns).map((i) => i.part)

    // then: 안내 칸이 category와 value_min을 포함한다
    expect(parts).toEqual(expect.arrayContaining(['category', 'value_min']))
  })
})

// 사용 확인: 빈 설계에서 만든 초안은 없다.
describe('빈 설계', () => {
  it('빈 설계에서는 기본 차트가 없다', () => {
    // when: 컬럼이 없는 설계로 기본 차트를 만든다
    const actual = defaultChart(emptyDesign().columns, headerOf)
    const actual2 = fieldOf('deal.vendor').groupable
    // then: null이다
    expect(actual).toBeNull()
    expect(actual2).toBe(true)
  })
})
