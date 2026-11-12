import { describe, expect, it } from 'vitest'
import type { DesignerState } from '../designer/state/designerState'
import { reduce, uidAt, withColumns } from '../../../test/reportDesigner'
import type { ReportChartInput } from '../../../shared/model/reportTypes'
import { chartDraftIssues, defaultChart, fromChartInput, normalizeForKind, toChartInput, type ChartDraft } from './chartDraft'

/**
 * 차트 초안의 새 종류·옵션(명세 RC-R25, RC-R28~RC-R34). 기존 동작은 `chartDraft.test.ts`가 고정한다.
 * 계약(테스트가 정한 부분)
 * - `ChartDraft`에 `histogram: { mode: 'auto' | 'count' | 'width', count, width, overflow, underflow }`(입력 칸 문자열),
 *   `showTotal: boolean`, `comboTypes: Record<uid, { type, secondary }>`(값 열 uid 기준)가 있다.
 * - `defaultChart(columns, headerOf, isNumberField?)`: 그룹핑이 없고 숫자 필드(`isNumberField(field)`)가 있으면 히스토그램 초안,
 *   숫자 필드가 없거나 3개 이상 그룹이면 null. `isNumberField`를 생략하면 숫자 필드가 없는 것으로 본다.
 * - `toChartInput`: 종류가 쓰지 않는 옵션은 `histogram: null`·`showTotal: false`·`comboSeries: null`로 보낸다.
 *   구간 방식이 쓰지 않는 칸은 null로 보낸다(서버가 "비워 두세요"로 거절하지 않게). 잘못된 숫자 글자는 그대로 보낸다.
 * - `chartDraftIssues`의 `part`는 서버 위치를 '.'로 이은 것이다(`histogram.bin_count`, `combo_series`).
 */

function design(keys: string[], groups: number[]): DesignerState {
  let state = withColumns(...keys)
  for (const i of groups) state = reduce(state, { type: 'updateColumn', uid: uidAt(state, i), patch: { group: true } })
  return state
}

const headerOf = (uid: number): string => `H${uid}`
const isNumber = (field: string): boolean => ['deal.amount', 'deal.users'].includes(field)
/** Vendor(그룹, uid 1), 금액(2), Users(3), Status 체류(4). */
const ONE_GROUP = (): DesignerState => design(['deal.vendor', 'deal.amount', 'deal.users', 'deal.status_days'], [0])
/** Deal code(uid 1, 텍스트), 금액(2), Users(3): 그룹핑 없음. */
const UNGROUPED = (): DesignerState => withColumns('deal.code', 'deal.amount', 'deal.users')

const AUTO = { mode: 'auto', count: '', width: '', overflow: '', underflow: '' } as const

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
    histogram: { ...AUTO },
    showTotal: false,
    comboTypes: {},
    ...over,
  }
}

describe('defaultChart: 그룹핑 없는 리포트', () => {
  // 테스트 코드: RC-052
  it('그룹핑이 없으면 첫 숫자 컬럼의 히스토그램으로 시작한다', () => {
    // when: 그룹핑 없는 설계로 기본 차트를 만든다
    const created = defaultChart(UNGROUPED().columns, headerOf, isNumber)

    // then: 히스토그램이고 범주·계열이 없으며 값은 첫 숫자 컬럼, 구간은 자동이다
    expect(created).toMatchObject({ kind: 'histogram', categoryUid: null, seriesUid: null, valueUids: [2], histogram: AUTO })
  })

  // 테스트 코드: RC-052
  it('숫자 컬럼이 하나도 없으면 기본 차트를 만들지 않는다', () => {
    // given: 텍스트 컬럼만 있는 설계
    const text = withColumns('deal.code', 'deal.name')

    // when: 기본 차트를 만든다
    const actual = defaultChart(text.columns, headerOf, isNumber)

    // then: 만들지 않는다(null)
    expect(actual).toBeNull()
  })

  // 테스트 코드: RC-052
  it('숫자 필드 판정 함수가 없으면 그룹핑 없는 기본 차트를 만들지 않는다', () => {
    // when: 판정 함수 없이 그룹핑 없는 설계로 기본 차트를 만든다
    const actual = defaultChart(UNGROUPED().columns, headerOf)

    // then: 만들지 않는다(null)
    expect(actual).toBeNull()
  })

  // 테스트 코드: RC-051
  it('그룹 컬럼 1개는 여전히 묶은 세로 막대로 시작한다', () => {
    // when: 판정 함수를 준 채 그룹 1개 설계로 기본 차트를 만든다
    const actual = defaultChart(ONE_GROUP().columns, headerOf, isNumber)

    // then: 막대이고 범주는 그 그룹이다
    expect(actual).toMatchObject({ kind: 'bar', categoryUid: 1 })
  })
})

describe('normalizeForKind: 새 종류', () => {
  // 테스트 코드: RC-058
  it('히스토그램으로 바꾸면 범주·계열을 비우고 값 하나만 남긴다', () => {
    // when: 값 2개 막대 초안을 히스토그램으로 바꾼다
    const next = normalizeForKind(draft({ valueUids: [2, 3] }), 'histogram', ONE_GROUP().columns)

    // then: 범주·계열이 null이고 값은 1개다
    expect(next).toMatchObject({ kind: 'histogram', categoryUid: null, seriesUid: null, valueUids: [2] })
  })

  // 테스트 코드: RC-058
  it('히스토그램에서 나오면 첫 그룹 컬럼이 범주로 돌아온다', () => {
    // given: 범주 없는 히스토그램 초안
    const hist = draft({ kind: 'histogram', categoryUid: null })

    // when: 막대로 바꾼다
    const actual = normalizeForKind(hist, 'bar', ONE_GROUP().columns)

    // then: 범주가 첫 그룹이다
    expect(actual).toMatchObject({ kind: 'bar', categoryUid: 1 })
  })

  // 테스트 코드: RC-058
  it('범주를 쓰는 종류끼리 바꾸면 범주를 유지한다', () => {
    // when: 범주가 있는 막대 초안을 방사형으로 바꾼다
    const actual = normalizeForKind(draft({ categoryUid: 1 }), 'radar', ONE_GROUP().columns)

    // then: 범주가 그대로다
    expect(actual).toMatchObject({ categoryUid: 1 })
  })

  // 테스트 코드: RC-058
  it('콤보로 바꾸면 첫 값은 막대, 나머지는 꺾은선으로 시작한다', () => {
    // when: 값 3개 막대 초안을 콤보로 바꾼다
    const next = normalizeForKind(draft({ valueUids: [2, 3, 4] }), 'combo', ONE_GROUP().columns)

    // then: 첫 값 컬럼은 묶은 세로 막대, 나머지는 기본 축 꺾은선이다
    expect(next.comboTypes).toEqual({
      2: { type: 'column', secondary: false },
      3: { type: 'line', secondary: false },
      4: { type: 'line', secondary: false },
    })
  })

  // 테스트 코드: RC-058
  it('콤보에서 콤보로 바꿔도 고른 계열 설정을 값 컬럼 uid로 유지한다', () => {
    // given: 값마다 종류를 고른 콤보 초안
    const chosen = { 2: { type: 'area', secondary: false }, 3: { type: 'line', secondary: true } } as const
    // when: 콤보로 다시 바꾼다
    const next = normalizeForKind(draft({ kind: 'combo', valueUids: [2, 3], comboTypes: { ...chosen } }), 'combo', ONE_GROUP().columns)

    // then: 고른 계열 설정이 그대로다
    expect(next.comboTypes).toEqual(chosen)
  })

  // 테스트 코드: RC-058
  it('폭포가 아닌 종류로 바꾸면 합계 막대를 끈다', () => {
    // when: 합계 막대를 켠 폭포 초안을 막대로 바꾼다
    const actual = normalizeForKind(draft({ kind: 'waterfall', showTotal: true }), 'bar', ONE_GROUP().columns).showTotal

    // then: 합계 막대가 꺼진다
    expect(actual).toBe(false)
  })

  // 테스트 코드: RC-058
  it('폭포로 바꿔도 합계 막대는 유지한다', () => {
    // when: 합계 막대를 켠 폭포 초안을 폭포로 바꾼다
    const actual = normalizeForKind(draft({ kind: 'waterfall', showTotal: true }), 'waterfall', ONE_GROUP().columns).showTotal

    // then: 합계 막대가 켜진 채다
    expect(actual).toBe(true)
  })

  // 테스트 코드: RC-058
  it('거품형은 값 3개까지, 파레토는 1개까지 남긴다', () => {
    // given: 값 3개를 쓰는 초안
    const many = draft({ valueUids: [2, 3, 4] })

    // when: 거품형으로 바꾼다
    const actual = normalizeForKind(many, 'bubble', ONE_GROUP().columns).valueUids
    const actual2 = normalizeForKind(many, 'pareto', ONE_GROUP().columns).valueUids
    // then: 값 3개, 파레토로 바꾸면 값 1개가 남는다
    expect(actual).toEqual([2, 3, 4])
    expect(actual2).toEqual([2])
  })
})

describe('toChartInput·fromChartInput: 새 키', () => {
  const columns = () => ONE_GROUP().columns

  // 테스트 코드: RC-071
  it('종류가 쓰지 않는 옵션은 요청에 담지 않는다', () => {
    // when: 막대 초안에 구간·합계·콤보 설정이 남아 있는 채로 요청으로 바꾼다
    const input = toChartInput(draft({ histogram: { ...AUTO, mode: 'count', count: '5' }, showTotal: true, comboTypes: { 2: { type: 'area', secondary: true } } }), columns())

    // then: 구간 null, 합계 false, 계열 설정 null이다
    expect(input).toMatchObject({ histogram: null, showTotal: false, comboSeries: null })
  })

  // 테스트 코드: RC-071
  it('히스토그램 구간 설정은 숫자로 바꿔 보낸다', () => {
    // given: 구간 수 방식에 구간 수 8·오버플로 100.5를 입력한 히스토그램 초안
    const hist = draft({ kind: 'histogram', categoryUid: null, histogram: { mode: 'count', count: '8', width: '', overflow: '100.5', underflow: '' } })

    // when: 요청으로 바꾼다
    const actual = toChartInput(hist, columns())

    // then: 범주는 null이고 구간 방식·수·오버플로가 숫자로, 쓰지 않는 칸은 null이다
    expect(actual).toMatchObject({
      category: null,
      histogram: { binMode: 'count', binCount: 8, binWidth: null, overflow: 100.5, underflow: null },
    })
  })

  // 테스트 코드: RC-071
  it('구간 방식이 쓰는 칸만 보낸다', () => {
    // given: 너비 방식에 구간 수 글자도 남아 있는 히스토그램 초안
    const hist = draft({ kind: 'histogram', categoryUid: null, histogram: { mode: 'width', count: '8', width: '2.5', overflow: '', underflow: '' } })

    // when: 요청으로 바꾼다
    const actual = toChartInput(hist, columns()).histogram

    // then: 구간 너비만 숫자이고 나머지 칸은 null이다
    expect(actual).toEqual({ binMode: 'width', binCount: null, binWidth: 2.5, overflow: null, underflow: null })
  })

  // 테스트 코드: RC-071
  it('잘못된 숫자 글자는 그대로 보내 서버가 위치와 함께 거절하게 한다', () => {
    // given: 구간 수에 abc를 입력한 히스토그램 초안
    const hist = draft({ kind: 'histogram', categoryUid: null, histogram: { mode: 'count', count: 'abc', width: '', overflow: '', underflow: '' } })

    // when: 요청으로 바꾼다
    const actual = toChartInput(hist, columns()).histogram

    // then: 구간 수가 글자 그대로다
    expect(actual).toMatchObject({ binCount: 'abc' })
  })

  // 테스트 코드: RC-071
  it('합계 막대는 폭포일 때만 보낸다', () => {
    // when: 합계 막대를 켠 폭포 초안을 요청으로 바꾼다
    const actual = toChartInput(draft({ kind: 'waterfall', showTotal: true }), columns())

    // then: showTotal이 true다
    expect(actual).toMatchObject({ showTotal: true })
  })

  // 테스트 코드: RC-071
  it('콤보 계열은 값 컬럼 순서대로 보내고 보조 축은 계열에서 계산한다', () => {
    // given: 값 순서가 바뀐 콤보 초안(보조 축 계열 포함)
    const combo = draft({
      kind: 'combo',
      valueUids: [3, 2],
      comboTypes: { 2: { type: 'line', secondary: true }, 3: { type: 'stacked_column', secondary: false } },
    })

    // when: 요청으로 바꾼다
    const input = toChartInput(combo, columns())

    // then: 값 index와 계열 설정이 값 순서를 따르고 보조 축이 켜진다
    expect(input.values).toEqual([2, 1])
    expect(input.comboSeries).toEqual([
      { type: 'stacked_column', secondary: false },
      { type: 'line', secondary: true },
    ])
    expect(input.secondaryAxis).toBe(true)
  })

  // 테스트 코드: RC-071
  it('콤보 계열 설정이 빠져 있으면 첫 값 막대, 나머지 꺾은선으로 채워 보낸다', () => {
    // when: 계열 설정이 비어 있는 콤보 초안을 요청으로 바꾼다
    const input = toChartInput(draft({ kind: 'combo', valueUids: [2, 3], comboTypes: {} }), columns())

    // then: 막대 + 꺾은선으로 채워지고 보조 축은 꺼져 있다
    expect(input.comboSeries).toEqual([
      { type: 'column', secondary: false },
      { type: 'line', secondary: false },
    ])
    expect(input.secondaryAxis).toBe(false)
  })

  // 테스트 코드: RC-072
  it('히스토그램 요청을 초안으로 바꿨다가 다시 요청으로 바꾸면 같은 값이다', () => {
    // given: 구간 너비 방식의 히스토그램 요청
    const input: ReportChartInput = {
      kind: 'histogram',
      category: null,
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
      histogram: { binMode: 'width', binCount: null, binWidth: 2.5, overflow: 100, underflow: -5 },
      showTotal: false,
      comboSeries: null,
    }

    // when: 초안으로 바꾼다
    const restored = fromChartInput(input, columns())

    // then: 구간 글자가 채워진 초안이고 다시 요청으로 바꾸면 같은 값이다
    expect(restored).toMatchObject({ categoryUid: null, histogram: { mode: 'width', width: '2.5', overflow: '100', underflow: '-5', count: '' } })
    expect(restored && toChartInput(restored, columns())).toEqual(input)
  })

  // 테스트 코드: RC-072
  it('콤보 요청의 계열 설정은 값 컬럼 uid 키로 옮겨졌다가 그대로 돌아온다', () => {
    // given: 계열 설정이 있는 콤보 요청
    const input: ReportChartInput = {
      kind: 'combo',
      category: 0,
      series: null,
      values: [1, 2],
      swap: false,
      title: '',
      legend: 'top',
      dataLabels: false,
      categoryAxisTitle: '',
      valueAxisTitle: '',
      valueMin: null,
      valueMax: null,
      secondaryAxis: true,
      histogram: null,
      showTotal: false,
      comboSeries: [
        { type: 'stacked_area', secondary: false },
        { type: 'line_markers', secondary: true },
      ],
    }

    // when: 초안으로 바꾼다
    const restored = fromChartInput(input, columns())

    // then: 계열 설정이 값 컬럼 uid 키이고 다시 요청으로 바꾸면 같은 값이다
    expect(restored?.comboTypes).toEqual({ 2: { type: 'stacked_area', secondary: false }, 3: { type: 'line_markers', secondary: true } })
    expect(restored && toChartInput(restored, columns())).toEqual(input)
  })

  // 테스트 코드: RC-072
  it('폭포의 합계 막대 켜기도 왕복한다', () => {
    // when: 합계 막대를 켠 폭포 초안을 요청으로 바꿨다가 다시 초안으로 바꾼다
    const input = toChartInput(draft({ kind: 'waterfall', showTotal: true }), columns())

    const restored = fromChartInput(input, columns())

    // then: 합계 막대가 켜져 있다
    expect(restored?.showTotal).toBe(true)
  })
})

describe('chartDraftIssues: 새 종류', () => {
  const messages = (d: ChartDraft, state: DesignerState): string[] => chartDraftIssues(d, state.columns).map((i) => i.message)
  const issueAt = (d: ChartDraft, state: DesignerState, part: string): string | undefined => chartDraftIssues(d, state.columns).find((i) => i.part === part)?.message

  // 테스트 코드: RC-067
  it('히스토그램은 범주를 고르라고 안내하지 않는다', () => {
    // given: 범주 없는 히스토그램 초안
    const hist = draft({ kind: 'histogram', categoryUid: null, valueUids: [2] })

    // when: 안내를 구한다
    const actual = chartDraftIssues(hist, UNGROUPED().columns).map((i) => i.part)

    // then: 안내 칸에 category가 없다
    expect(actual).not.toContain('category')
  })

  // 테스트 코드: RC-067
  it('완성된 그룹핑 없는 히스토그램에는 안내가 없다', () => {
    // when: 완성된 히스토그램 초안의 안내를 구한다
    const actual = chartDraftIssues(draft({ kind: 'histogram', categoryUid: null, valueUids: [2] }), UNGROUPED().columns)

    // then: 안내가 없다
    expect(actual).toEqual([])
  })

  // 테스트 코드: RC-068
  it.each([
    ['0', '구간 수는 1~100의 정수입니다'],
    ['101', '구간 수는 1~100의 정수입니다'],
    ['2.5', '구간 수는 1~100의 정수입니다'],
    ['', '구간 수는 1~100의 정수입니다'],
  ])('구간 수 방식에서 잘못된 구간 수를 안내한다 (%j)', (count, message) => {
    // given: 구간 수 방식에 잘못된 구간 수를 입력한 히스토그램 초안
    const hist = draft({ kind: 'histogram', categoryUid: null, histogram: { ...AUTO, mode: 'count', count } })

    // when: 안내를 구한다
    const actual = issueAt(hist, UNGROUPED(), 'histogram.bin_count')

    // then: `histogram.bin_count` 칸에 "구간 수는 1~100의 정수입니다"가 나온다
    expect(actual).toBe(message)
  })

  // 테스트 코드: RC-068
  it.each(['1', '100'])('구간 수 방식의 경계값 1·100은 안내가 없다 (%s)', (count) => {
    // given: 구간 수 경계값을 입력한 히스토그램 초안
    const hist = draft({ kind: 'histogram', categoryUid: null, histogram: { ...AUTO, mode: 'count', count } })

    // when: 안내를 구한다
    const actual = issueAt(hist, UNGROUPED(), 'histogram.bin_count')

    // then: `histogram.bin_count` 안내가 없다
    expect(actual).toBeUndefined()
  })

  // 테스트 코드: RC-068
  it.each(['0', '-1', ''])('너비 방식에서 0 이하·빈 구간 너비를 안내한다 (%j)', (width) => {
    // given: 구간 너비 방식에 잘못된 너비를 입력한 히스토그램 초안
    const hist = draft({ kind: 'histogram', categoryUid: null, histogram: { ...AUTO, mode: 'width', width } })

    // when: 안내를 구한다
    const actual = issueAt(hist, UNGROUPED(), 'histogram.bin_width')

    // then: `histogram.bin_width` 칸에 "구간 너비는 0보다 큰 숫자입니다"가 나온다
    expect(actual).toBe('구간 너비는 0보다 큰 숫자입니다')
  })

  // 테스트 코드: RC-068
  it('자동·너비 방식에서는 구간 수를 검사하지 않는다', () => {
    // given: 너비 방식에 구간 수 0 글자가 남아 있는 히스토그램 초안
    const hist = draft({ kind: 'histogram', categoryUid: null, histogram: { ...AUTO, mode: 'width', width: '2', count: '0' } })

    // when: 안내를 구한다
    const actual = issueAt(hist, UNGROUPED(), 'histogram.bin_count')

    // then: `histogram.bin_count` 안내가 없다
    expect(actual).toBeUndefined()
  })

  // 테스트 코드: RC-068
  it('오버플로는 언더플로보다 커야 한다', () => {
    // given: 오버플로·언더플로가 같은 초안과 오버플로가 큰 초안
    const hist = draft({ kind: 'histogram', categoryUid: null, histogram: { ...AUTO, overflow: '10', underflow: '10' } })
    const ok = draft({ kind: 'histogram', categoryUid: null, histogram: { ...AUTO, overflow: '10', underflow: '9' } })

    // when: 같은 값인다
    const actual = issueAt(hist, UNGROUPED(), 'histogram.overflow')
    const actual2 = issueAt(ok, UNGROUPED(), 'histogram.overflow')
    // then: 오버플로 칸에 "오버플로 구간은 언더플로 구간보다 커야 합니다"가 나오고 올바른 값이면 안내가 없다
    expect(actual).toBe('오버플로 구간은 언더플로 구간보다 커야 합니다')
    expect(actual2).toBeUndefined()
  })

  // 테스트 코드: RC-068
  it('모든 계열을 보조 축에 둔 콤보를 안내한다', () => {
    // given: 모든 계열이 보조 축인 콤보 초안
    const combo = draft({
      kind: 'combo',
      valueUids: [2, 3],
      comboTypes: { 2: { type: 'column', secondary: true }, 3: { type: 'line', secondary: true } },
    })

    // when: 안내를 구한다
    const actual = issueAt(combo, ONE_GROUP(), 'combo_series')

    // then: `combo_series` 칸에 "모든 계열을 보조 축에 둘 수 없습니다"가 나온다
    expect(actual).toBe('모든 계열을 보조 축에 둘 수 없습니다')
  })

  // 테스트 코드: RC-067
  it('새 종류의 값 개수를 서버와 같은 문구로 안내한다', () => {
    // when: 거품형·선 있는 분산형 초안의 안내 문구를 만든다
    const actual = messages(draft({ kind: 'bubble', valueUids: [2, 3] }), ONE_GROUP())
    const actual2 = messages(draft({ kind: 'scatter_line', valueUids: [2] }), ONE_GROUP())
    // then: 값 2개인 거품형과 값 1개인 직선 분산형의 안내에 개수 문구가 있다
    expect(actual).toContain('이 차트는 값 열을 3개 골라야 합니다')
    expect(actual2).toContain('이 차트는 값 열을 2~10개 골라야 합니다')
  })
})

/** 그룹핑 컬럼 수가 종류의 최대를 넘으면 서버 `chart-kind-groups`와 같은 뜻의 안내를 낸다. */
describe('chartDraftIssues: 그룹핑 컬럼 수', () => {
  const messages = (d: ChartDraft, state: DesignerState): string[] => chartDraftIssues(d, state.columns).map((i) => i.message)
  const TWO_GROUPS = (): DesignerState => design(['deal.vendor', 'deal.status', 'deal.amount'], [0, 1])
  const THREE_GROUPS = (): DesignerState => design(['deal.vendor', 'deal.status', 'deal.forecast', 'deal.amount'], [0, 1, 2])

  // 테스트 코드: RC-068
  it('원형은 그룹 컬럼 2개를 쓸 수 없다고 안내한다', () => {
    // given: 원형 초안
    const pie = draft({ kind: 'pie', categoryUid: 1, valueUids: [3] })

    // when: 그룹 컬럼 2개 설계로 안내를 구한다
    const actual = messages(pie, TWO_GROUPS())

    // then: "이 차트는 그룹핑 컬럼이 1개 이하일 때 만들 수 있습니다"가 나온다
    expect(actual).toContain('이 차트는 그룹핑 컬럼이 1개 이하일 때 만들 수 있습니다')
  })

  // 테스트 코드: RC-068
  it('막대는 그룹 컬럼 3개를 쓸 수 없다고 안내한다', () => {
    // given: 막대 초안
    const bar = draft({ kind: 'bar', categoryUid: 1, seriesUid: 2, valueUids: [4] })

    // when: 그룹 컬럼 3개 설계로 안내를 구한다
    const actual = messages(bar, THREE_GROUPS())

    // then: "이 차트는 그룹핑 컬럼이 2개 이하일 때 만들 수 있습니다"가 나온다
    expect(actual).toContain('이 차트는 그룹핑 컬럼이 2개 이하일 때 만들 수 있습니다')
  })

  // 테스트 코드: RC-068
  it('그룹 수가 종류에 맞으면 그룹 수 안내가 없다', () => {
    // given: 원형 초안
    const pie = draft({ kind: 'pie', categoryUid: 1, valueUids: [2] })

    // when: 그룹 컬럼 1개 설계로 안내를 구한다
    const actual = messages(pie, ONE_GROUP()).filter((m) => m.includes('그룹핑 컬럼이'))

    // then: 그룹핑 컬럼 수 안내가 없다
    expect(actual).toEqual([])
  })
})

/** 그룹핑 없는 히스토그램의 값은 숫자 컬럼만. `chartDraftIssues(draft, columns, isNumberField?)`의 셋째 인자가 숫자 필드 판정이다. */
describe('chartDraftIssues: 히스토그램 값 열', () => {
  // 테스트 코드: RC-068
  it('그룹핑 없는 히스토그램의 값이 텍스트 컬럼이면 숫자 컬럼이어야 한다고 안내한다', () => {
    // given: 텍스트 컬럼을 값으로 고른 히스토그램 초안
    const hist = draft({ kind: 'histogram', categoryUid: null, valueUids: [1] })

    // when: 숫자 필드 판정과 함께 안내를 구한다
    const actual = chartDraftIssues(hist, UNGROUPED().columns, isNumber).map((i) => i.message)

    // then: "값 열은 숫자 컬럼이어야 합니다"가 나온다
    expect(actual).toContain('값 열은 숫자 컬럼이어야 합니다')
  })

  // 테스트 코드: RC-068
  it('숫자 컬럼을 고르면 숫자 컬럼 안내가 없다', () => {
    // given: 숫자 컬럼을 값으로 고른 히스토그램 초안
    const hist = draft({ kind: 'histogram', categoryUid: null, valueUids: [2] })

    // when: 숫자 필드 판정과 함께 안내를 구한다
    const actual = chartDraftIssues(hist, UNGROUPED().columns, isNumber).map((i) => i.message)

    // then: "값 열은 숫자 컬럼이어야 합니다" 안내가 없다
    expect(actual).not.toContain('값 열은 숫자 컬럼이어야 합니다')
  })
})
