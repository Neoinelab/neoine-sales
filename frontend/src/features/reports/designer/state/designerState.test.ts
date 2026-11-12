import { describe, expect, it } from 'vitest'
import { columnAt, conditionUidAt, emptyDesign, fieldOf, reduce, REPORT_CATALOG, uidAt, withColumns } from '../../../../test/reportDesigner'
import type { ChartDraft } from '../../chart/chartDraft'
import { designKey } from './designKey'
import { designerReducer, initialDesignerState, isDirty, sameDesign, type DesignerState } from './designerState'
import { toReportRequest } from './toRequest'

const LIMITS = REPORT_CATALOG.limits

describe('initialDesignerState', () => {
  // 테스트 코드: RQ-067
  it('컬럼·조건 없이 AND와 기본 행 수 제한으로 시작한다', () => {
    // when: 초기 설계 상태를 만든다
    const actual = initialDesignerState(LIMITS)
    const actual2 = 'sort' in initialDesignerState(LIMITS)
    // then: 초기 설계는 컬럼·조건이 없고 결합 and, 행 수 1000, 선택 없음이며 최상위 sort가 없다
    expect(actual).toMatchObject({
      columns: [],
      conditions: [],
      combine: 'and',
      rowLimit: 1000,
      selectedUid: null,
    })
    expect(actual2).toBe(false)
  })
})

describe('designerReducer columns', () => {
  // 테스트 코드: RQ-071
  it('같은 필드를 두 번 넣으면 컬럼 둘이 되고 숫자 포맷이 없다', () => {
    // when: 금액을 두 번 넣는다
    const state = withColumns('deal.amount', 'deal.amount')

    // then: 컬럼이 둘이고 uid가 다르며 포맷·이름·집계·정렬이 기본값이다
    expect(state.columns).toHaveLength(2)
    expect(uidAt(state, 0)).not.toBe(uidAt(state, 1))
    for (const column of state.columns) {
      expect(column).toMatchObject({ field: 'deal.amount', format: null, label: '', group: false, aggregate: null, prefixOn: false, prefixLength: null, sort: null })
    }
  })

  // 테스트 코드: RQ-071
  it('방금 넣은 컬럼이 선택된다', () => {
    // when: 컬럼 둘을 넣는다
    const state = withColumns('deal.code', 'deal.name')

    // then: 마지막 컬럼이 선택된다
    expect(state.selectedUid).toBe(uidAt(state, 1))
  })

  // 테스트 코드: RQ-071
  it('uid로 컬럼을 뺀다', () => {
    // given: 컬럼 셋
    const state = withColumns('deal.code', 'deal.name', 'deal.solution')

    // when: 둘째 컬럼을 뺀다
    const next = reduce(state, { type: 'removeColumn', uid: uidAt(state, 1) })

    // then: 나머지 둘이 남고 선택은 뺀 컬럼이 아니다
    expect(next.columns.map((c) => c.field)).toEqual(['deal.code', 'deal.solution'])
    expect(next.selectedUid).not.toBe(uidAt(state, 1))
  })

  // 테스트 코드: RQ-071
  it('컬럼 한도를 넘으면 더 넣지 않고 같은 상태 객체를 돌려준다', () => {
    // given: 컬럼 30개
    const state = withColumns(...Array.from({ length: LIMITS.columnsMax }, () => 'deal.code'))

    // when: 컬럼을 하나 더 넣는다
    const next = reduce(state, { type: 'addColumn', field: fieldOf('deal.name') })

    // then: 30개 그대로이고 같은 상태 객체다
    expect(state.columns).toHaveLength(30)
    expect(next).toBe(state)
  })

  // 테스트 코드: RQ-074
  it('uid로 컬럼을 선택하고 null로 선택을 푼다', () => {
    // given: 컬럼 둘
    const state = withColumns('deal.code', 'deal.name')

    // when: 첫 컬럼을 선택하고 null로 선택을 푼다
    const first = reduce(state, { type: 'selectColumn', uid: uidAt(state, 0) })
    const none = reduce(first, { type: 'selectColumn', uid: null })

    // then: 선택이 첫 컬럼이었다가 null이 된다
    expect(first.selectedUid).toBe(uidAt(state, 0))
    expect(none.selectedUid).toBeNull()
  })

  // 테스트 코드: RQ-074
  it('한 컬럼의 표시 이름만 바꾼다', () => {
    // given: 컬럼 둘
    const state = withColumns('deal.code', 'deal.name')

    // when: 둘째 컬럼의 표시 이름을 바꾼다
    const next = reduce(state, { type: 'updateColumn', uid: uidAt(state, 1), patch: { label: '이름' } })

    // then: 둘째만 바뀐다
    expect(next.columns.map((c) => c.label)).toEqual(['', '이름'])
  })
})

describe('designerReducer moving', () => {
  // 테스트 코드: RQ-072
  it('컬럼을 목표 위치로 옮긴다', () => {
    // given: 컬럼 셋
    const state = withColumns('deal.code', 'deal.name', 'deal.solution')

    // when: 첫 컬럼을 셋째 자리로 옮긴다
    const next = reduce(state, { type: 'moveColumn', uid: uidAt(state, 0), to: 2 })

    // then: 순서가 이름, Solution, code다
    expect(next.columns.map((c) => c.field)).toEqual(['deal.name', 'deal.solution', 'deal.code'])
  })

  // 테스트 코드: RQ-072
  it('끝을 넘는 위치는 마지막 자리로 맞춘다', () => {
    // given: 컬럼 셋
    const state = withColumns('deal.code', 'deal.name', 'deal.solution')

    // when: 첫 컬럼을 99번째로 옮긴다
    const next = reduce(state, { type: 'moveColumn', uid: uidAt(state, 0), to: 99 })

    // then: 마지막 자리로 간다
    expect(next.columns.map((c) => c.field)).toEqual(['deal.name', 'deal.solution', 'deal.code'])
  })

  // 테스트 코드: RQ-072
  it('이미 그 자리면 같은 상태 객체를 돌려준다', () => {
    // given: 컬럼 둘
    const state = withColumns('deal.code', 'deal.name')

    // when: 둘째 컬럼을 둘째 자리로 옮긴다
    const actual = reduce(state, { type: 'moveColumn', uid: uidAt(state, 1), to: 1 })
    // then: 같은 상태 객체다
    expect(actual).toBe(state)
  })

  // 테스트 코드: RQ-072
  it('컬럼을 옮기면 그 정렬도 함께 간다', () => {
    // given: 첫 컬럼을 내림차순 정렬한 컬럼 셋
    const base = withColumns('deal.code', 'deal.name', 'deal.solution')
    const sorted = reduce(base, { type: 'updateColumn', uid: uidAt(base, 0), patch: { sort: 'desc' } })

    // when: 첫 컬럼을 셋째 자리로 옮긴다
    const next = reduce(sorted, { type: 'moveColumn', uid: uidAt(sorted, 0), to: 2 })
    // then: 정렬이 셋째 컬럼에 붙고 요청에도 컬럼 정렬만 있다
    const request = toReportRequest(next, REPORT_CATALOG)

    expect(next.columns.map((c) => c.sort)).toEqual([null, null, 'desc'])
    expect('request' in request && request.request.columns.map((c) => c.sort)).toEqual([undefined, undefined, 'desc'])
    expect('request' in request && 'sort' in request.request).toBe(false)
  })
})

describe('designerReducer sort', () => {
  // 테스트 코드: RQ-074
  it('한 컬럼의 정렬만 정하고 null로 지운다', () => {
    // given: 컬럼 둘
    const state = withColumns('deal.code', 'deal.name')

    // when: 둘째 컬럼을 오름차순으로 정했다가 null로 지운다
    const set = reduce(state, { type: 'updateColumn', uid: uidAt(state, 1), patch: { sort: 'asc' } })
    const cleared = reduce(set, { type: 'updateColumn', uid: uidAt(set, 1), patch: { sort: null } })

    // then: 둘째만 asc였다가 모두 없어진다
    expect(set.columns.map((c) => c.sort)).toEqual([null, 'asc'])
    expect(cleared.columns.map((c) => c.sort)).toEqual([null, null])
  })

  // 테스트 코드: RQ-086
  it('정렬한 컬럼을 빼면 요청에서 그 정렬도 없어진다', () => {
    // given: 둘째 컬럼을 정렬한 설계
    const state = withColumns('deal.code', 'deal.name')
    const sorted = reduce(state, { type: 'updateColumn', uid: uidAt(state, 1), patch: { sort: 'asc' } })

    // when: 둘째 컬럼을 뺀다
    const next = reduce(sorted, { type: 'removeColumn', uid: uidAt(sorted, 1) })
    // then: 설계에도 요청에도 정렬이 없다
    const request = toReportRequest(next, REPORT_CATALOG)

    expect(next.columns.map((c) => c.sort)).toEqual([null])
    expect('request' in request && request.request.columns.some((c) => c.sort !== undefined)).toBe(false)
  })

  // 테스트 코드: RQ-086
  it('다른 컬럼을 빼도 남은 컬럼의 정렬은 유지된다', () => {
    // given: 둘째 컬럼을 정렬한 설계
    const state = withColumns('deal.code', 'deal.name')
    const sorted = reduce(state, { type: 'updateColumn', uid: uidAt(state, 1), patch: { sort: 'asc' } })

    // when: 첫째 컬럼을 뺀다
    const next = reduce(sorted, { type: 'removeColumn', uid: uidAt(sorted, 0) })

    // then: 남은 컬럼이 asc 정렬 그대로다
    expect(next.columns.map((c) => c.sort)).toEqual(['asc'])
  })

  // 테스트 코드: RQ-099
  it('컬럼 정렬이 바뀌면 다른 설계이고 되돌리면 같은 설계다', () => {
    // given: 컬럼 둘의 기본 설계
    const base = withColumns('deal.code', 'deal.name')
    // when: 둘째 컬럼 정렬을 정했다가 지운다
    const sorted = reduce(base, { type: 'updateColumn', uid: uidAt(base, 1), patch: { sort: 'desc' } })
    const back = reduce(sorted, { type: 'updateColumn', uid: uidAt(sorted, 1), patch: { sort: null } })

    // then: 정렬했을 때는 다르고 되돌리면 같다
    expect(sameDesign(base, sorted)).toBe(false)
    expect(sameDesign(base, back)).toBe(true)
  })

  // 테스트 코드: RQ-087
  it('최대 행을 정한다', () => {
    // when: 최대 행을 10000으로 정한다
    const state = reduce(emptyDesign(), { type: 'setRowLimit', rowLimit: 10000 })

    // then: 행 수 제한이 10000이다
    expect(state.rowLimit).toBe(10000)
  })
})

describe('designerReducer conditions', () => {
  // 테스트 코드: RQ-078
  it('조건을 추가하면 첫 연산자와 빈 값으로 시작한다', () => {
    // when: Deal 이름 조건을 추가한다
    const state = reduce(emptyDesign(), { type: 'addCondition', field: fieldOf('deal.name') })

    // then: 조건 하나가 포함 연산자와 빈 텍스트 값으로 생긴다
    expect(state.conditions).toHaveLength(1)
    expect(state.conditions[0]).toMatchObject({ field: 'deal.name', operator: 'contains', draft: { shape: 'text', text: '' } })
  })

  // 테스트 코드: RQ-078
  it('조건 한도를 넘으면 더 넣지 않고 같은 상태 객체를 돌려준다', () => {
    // given: 조건 20개
    const many = Array.from({ length: LIMITS.conditionsMax }, () => ({ type: 'addCondition' as const, field: fieldOf('deal.name') }))
    const state = reduce(emptyDesign(), ...many)

    // when: 조건을 하나 더 넣는다
    const actual = reduce(state, { type: 'addCondition', field: fieldOf('deal.name') })
    // then: 같은 상태 객체다
    expect(actual).toBe(state)
  })

  // 테스트 코드: RQ-078
  it('uid로 조건을 지운다', () => {
    // given: 조건 둘
    const state = reduce(emptyDesign(), { type: 'addCondition', field: fieldOf('deal.name') }, { type: 'addCondition', field: fieldOf('deal.code') })

    // when: 첫 조건을 지운다
    const next = reduce(state, { type: 'removeCondition', uid: conditionUidAt(state, 0) })

    // then: 둘째 조건만 남는다
    expect(next.conditions.map((c) => c.field)).toEqual(['deal.code'])
  })

  // 테스트 코드: RQ-079
  it('결합을 바꾼다', () => {
    // when: 결합을 or로 바꾼다
    const actual = reduce(emptyDesign(), { type: 'setCombine', combine: 'or' }).combine
    // then: 설계의 결합이 or다
    expect(actual).toBe('or')
  })

  // 테스트 코드: RQ-081
  it('입력한 값 초안을 저장한다', () => {
    // given: Deal 이름 조건
    const state = reduce(emptyDesign(), { type: 'addCondition', field: fieldOf('deal.name') })

    // when: 값 은행을 입력한다
    const next = reduce(state, { type: 'changeDraft', uid: conditionUidAt(state, 0), draft: { shape: 'text', text: '은행' } })

    // then: 초안이 텍스트 은행이다
    expect(next.conditions[0]?.draft).toEqual({ shape: 'text', text: '은행' })
  })
})

describe('reset and isDirty', () => {
  // 테스트 코드: RQ-101
  it('초기 상태에서 바뀐 뒤에만 바뀐 설계로 본다', () => {
    // given: 초기 설계
    const initial = emptyDesign()

    // when: 초기에는 바뀌지 않았고 컬럼·조건·결합·행 수를 바꾼다
    const actual = isDirty(initial, LIMITS)
    const actual2 = isDirty(reduce(initial, { type: 'addColumn', field: fieldOf('deal.code') }), LIMITS)
    const actual3 = isDirty(reduce(initial, { type: 'addCondition', field: fieldOf('deal.name') }), LIMITS)
    const actual4 = isDirty(reduce(initial, { type: 'setCombine', combine: 'or' }), LIMITS)
    const actual5 = isDirty(reduce(initial, { type: 'setRowLimit', rowLimit: 100 }), LIMITS)
    // then: 바뀐 설계다
    expect(actual).toBe(false)
    expect(actual2).toBe(true)
    expect(actual3).toBe(true)
    expect(actual4).toBe(true)
    expect(actual5).toBe(true)
  })

  // 테스트 코드: RQ-101
  it('넣은 컬럼을 다시 빼면 바뀌지 않은 설계로 돌아온다', () => {
    // given: 컬럼을 하나 넣은 설계
    const added = withColumns('deal.code')

    // when: 그 컬럼을 뺀다
    const removed = reduce(added, { type: 'removeColumn', uid: uidAt(added, 0) })

    // then: 바뀌지 않은 설계다
    expect(isDirty(removed, LIMITS)).toBe(false)
  })

  // 테스트 코드: RQ-102
  it('초기화하면 초기 설계로 돌아간다', () => {
    // given: 컬럼과 or 결합이 있는 설계
    const state = reduce(withColumns('deal.code'), { type: 'setCombine', combine: 'or' }, { type: 'reset' })

    // when: 초기화한다
    const actual = 'sort' in state
    const actual2 = isDirty(state, LIMITS)
    // then: 컬럼·조건이 비고 and·1000·선택 없음이며 바뀐 설계가 아니다
    expect(state).toMatchObject({ columns: [], conditions: [], combine: 'and', rowLimit: 1000, selectedUid: null })
    expect(actual).toBe(false)
    expect(actual2).toBe(false)
  })

  // 테스트 코드: RQ-071
  it('뺀 컬럼의 uid를 다시 쓰지 않는다', () => {
    // given: 컬럼을 넣었다가 뺀 설계
    const first = withColumns('deal.code')
    const removed = reduce(first, { type: 'removeColumn', uid: uidAt(first, 0) })

    // when: 같은 필드를 다시 넣는다
    const second = reduce(removed, { type: 'addColumn', field: fieldOf('deal.code') })

    // then: 새 uid가 이전과 다르다
    expect(uidAt(second, 0)).not.toBe(uidAt(first, 0))
  })

  // 테스트 코드: RQ-071
  it('모르는 uid는 상태를 바꾸지 않는다', () => {
    // given: 컬럼 하나
    const state = withColumns('deal.code')

    // when: 없는 컬럼 번호 9999를 삭제하는 동작을 처리하고 첫 컬럼을 읽는다
    const actual = designerReducer(state, { type: 'removeColumn', uid: 9999 }, REPORT_CATALOG)
    const actual2 = columnAt(state, 0).field
    // then: 없는 uid의 컬럼을 빼도 같은 상태 객체이고 컬럼은 그대로다
    expect(actual).toBe(state)
    expect(actual2).toBe('deal.code')
  })
})

describe('설계 상태의 차트', () => {
  const CHART: ChartDraft = {
    kind: 'bar',
    categoryUid: 1,
    seriesUid: null,
    valueUids: [2],
    swap: false,
    title: '',
    legend: 'top',
    dataLabels: false,
    categoryAxisTitle: 'Vendor',
    valueAxisTitle: '금액',
    valueMin: '',
    valueMax: '',
    secondaryAxis: false,
    histogram: { mode: 'auto', count: '', width: '', overflow: '', underflow: '' },
    showTotal: false,
    comboTypes: {},
  }

  /** Vendor(그룹, uid 1) + 금액(합계, uid 2) + Users(합계, uid 3) 설계. 차트는 load로 직접 넣는다. */
  function grouped(chart: ChartDraft | null): DesignerState {
    let state = withColumns('deal.vendor', 'deal.amount', 'deal.users')
    state = reduce(state, { type: 'updateColumn', uid: 1, patch: { group: true } })
    return reduce(state, { type: 'load', state: { ...state, chart } })
  }

  it('처음에는 차트가 없다', () => {
    // when: 초기 상태를 만든다
    const actual = initialDesignerState(LIMITS).chart

    // then: 차트가 null이다
    expect(actual).toBeNull()
  })

  // 테스트 코드: RC-077
  it('차트를 바꾸면 설계 키와 변경 여부는 바뀌지만 조회 설계는 같다', () => {
    // given: 차트 없는 설계, 차트 있는 설계
    const plain = grouped(null)
    const charted = grouped(CHART)
    // when: 차트 제목을 바꾼다
    const edited = reduce(charted, { type: 'changeChart', patch: { title: '새 제목' } })

    // then: 조회 설계는 모두 같고 설계 키는 서로 다르다
    expect(sameDesign(plain, charted)).toBe(true)
    expect(sameDesign(charted, edited)).toBe(true)
    expect(designKey(plain, REPORT_CATALOG)).not.toBe(designKey(charted, REPORT_CATALOG))
    expect(designKey(charted, REPORT_CATALOG)).not.toBe(designKey(edited, REPORT_CATALOG))
  })

  // 테스트 코드: RC-077
  it('차트를 되돌리거나 지우면 설계 키가 원래대로다', () => {
    // given: 차트 없는 설계, 차트 있는 설계
    const plain = grouped(null)
    const charted = grouped(CHART)

    // when: 차트를 지우거나 제목을 바꿨다가 되돌린다
    const removed = reduce(charted, { type: 'removeChart' })
    const back = reduce(reduce(charted, { type: 'changeChart', patch: { title: 'x' } }), { type: 'changeChart', patch: { title: '' } })

    // then: 지운 키는 차트 없는 설계와, 되돌린 키는 차트 있는 설계와 같다
    expect(designKey(removed, REPORT_CATALOG)).toBe(designKey(plain, REPORT_CATALOG))
    expect(designKey(back, REPORT_CATALOG)).toBe(designKey(charted, REPORT_CATALOG))
  })

  // 테스트 코드: RC-077
  it('컬럼이 없어도 차트가 있으면 변경으로 센다', () => {
    // when: 차트만 넣은 설계와 빈 설계가 바뀌었는지 판정한다
    const actual = isDirty({ ...emptyDesign(), chart: CHART }, LIMITS)
    const actual2 = isDirty(emptyDesign(), LIMITS)
    // then: 차트만 있는 빈 설계는 변경이 있고 빈 설계는 변경이 없다
    expect(actual).toBe(true)
    expect(actual2).toBe(false)
  })

  // 테스트 코드: RC-057
  it('종류를 바꾸면 종류 규칙에 따라 정리한다', () => {
    // given: 값 2개·행/열 전환을 켠 막대 설계
    const wide = grouped({ ...CHART, valueUids: [2, 3], swap: true })

    // when: 원형으로 바꾼다
    const pie = reduce(wide, { type: 'setChartKind', kind: 'pie' })

    // then: 원형이고 값 1개이며 전환이 꺼진다
    expect(pie.chart).toMatchObject({ kind: 'pie', valueUids: [2], swap: false })
  })

  // 테스트 코드: RC-070
  it('컬럼을 빼면 차트의 그 참조만 빠지고 나머지 설정은 유지한다', () => {
    // given: 값 2개와 제목이 있는 차트 설계
    const state = grouped({ ...CHART, valueUids: [2, 3], title: '유지' })

    // when: 값 컬럼 하나를 뺀다
    const after = reduce(state, { type: 'removeColumn', uid: 3 })

    // then: 값에서 그 컬럼이 빠지고 제목은 그대로다
    expect(after.chart).toMatchObject({ valueUids: [2], title: '유지' })
  })

  // 테스트 코드: RC-070
  it('범주 컬럼의 그룹핑을 끄면 범주 참조를 비운다', () => {
    // when: 범주 컬럼의 그룹핑을 끈다
    const after = reduce(grouped(CHART), { type: 'updateColumn', uid: 1, patch: { group: false } })

    // then: 범주 uid가 null이다
    expect(after.chart?.categoryUid).toBeNull()
  })

  // 테스트 코드: RC-070
  it('차트가 없으면 컬럼을 빼도 차트는 그대로 없다', () => {
    // when: 차트 없는 설계에서 컬럼을 뺀다
    const actual = reduce(grouped(null), { type: 'removeColumn', uid: 3 }).chart

    // then: 차트가 null이다
    expect(actual).toBeNull()
  })

  // 테스트 코드: RC-053
  it('차트 지우기와 초기화는 차트를 없앤다', () => {
    // given: 차트 있는 설계
    const state = grouped(CHART)

    // when: 차트를 지우거나 초기화한다
    const actual = reduce(state, { type: 'removeChart' }).chart
    const actual2 = reduce(state, { type: 'reset' }).chart
    // then: 차트가 null이다
    expect(actual).toBeNull()
    expect(actual2).toBeNull()
  })

  // 테스트 코드: RC-070
  it('컬럼을 옮기기만 하면 차트를 건드리지 않는다', () => {
    // given: 차트 있는 설계
    const state = grouped(CHART)

    // when: 컬럼을 맨 앞으로 옮긴다
    const actual = reduce(state, { type: 'moveColumn', uid: 3, to: 0 }).chart

    // then: 차트가 그대로다
    expect(actual).toEqual(CHART)
  })
})

describe('설계 상태의 결과 배치', () => {
  const DEFAULT = { view: 'both', order: ['table', 'chart'], arrange: 'stacked' } as const

  it('처음 배치는 기본 배치다', () => {
    // when: 초기 설계 상태의 배치를 읽는다
    const actual = initialDesignerState(LIMITS).layout
    // then: 초기 상태의 배치가 기본 배치다
    expect(actual).toEqual(DEFAULT)
  })

  it('보기 방식을 바꿔도 순서와 배치는 유지한다', () => {
    // given: 표를 차트 오른쪽에 놓은 상태
    const state = reduce(emptyDesign(), { type: 'placeTile', dragged: 'table', target: 'chart', edge: 'right' })

    // when: 보기 방식을 차트만으로 바꾼다
    const next = reduce(state, { type: 'setResultView', view: 'chart' })

    // then: 보기만 바뀌고 순서·한 줄이 그대로다
    expect(next.layout).toEqual({ view: 'chart', order: ['chart', 'table'], arrange: 'side_by_side' })
  })

  it('이미 고른 보기 방식이면 같은 상태 객체를 돌려준다', () => {
    // given: 차트만이 선택된 상태
    const state = reduce(emptyDesign(), { type: 'setResultView', view: 'chart' })
    // when: 같은 보기를 다시 고른다
    const actual = state.layout.view
    // then: 같은 상태 객체다
    expect(actual).toBe('chart')

    expect(designerReducer(state, { type: 'setResultView', view: 'chart' }, REPORT_CATALOG)).toBe(state)
  })

  // 테스트 코드: RS-086
  it('타일 놓기: 표를 차트 오른쪽에 놓으면 차트 → 표 한 줄이다', () => {
    // when: 표를 차트 오른쪽에 놓는다
    const next = reduce(emptyDesign(), { type: 'placeTile', dragged: 'table', target: 'chart', edge: 'right' })

    // then: 차트 → 표, 한 줄이다
    expect(next.layout).toEqual({ view: 'both', order: ['chart', 'table'], arrange: 'side_by_side' })
  })

  // 테스트 코드: RS-086
  it('표를 차트 아래에 놓으면 차트 → 표 두 줄이다', () => {
    // when: 표를 차트 아래에 놓는다
    const next = reduce(emptyDesign(), { type: 'placeTile', dragged: 'table', target: 'chart', edge: 'bottom' })

    // then: 차트 → 표, 두 줄이다
    expect(next.layout).toEqual({ view: 'both', order: ['chart', 'table'], arrange: 'stacked' })
  })

  // 테스트 코드: RS-087
  it('자기 위에 놓으면 같은 상태 객체를 돌려준다', () => {
    // given: 한 줄 배치 상태
    const state = reduce(emptyDesign(), { type: 'placeTile', dragged: 'table', target: 'chart', edge: 'right' })
    // when: 차트를 차트 위에 놓는다
    const actual = state.layout.arrange
    // then: 같은 상태 객체다
    expect(actual).toBe('side_by_side')

    expect(designerReducer(state, { type: 'placeTile', dragged: 'chart', target: 'chart', edge: 'left' }, REPORT_CATALOG)).toBe(state)
  })

  // 테스트 코드: RS-089
  it('배치 변경은 컬럼·조건·차트를 건드리지 않는다', () => {
    // given: 컬럼이 있는 상태
    const state = withColumns('deal.code', 'deal.name')

    // when: 보기와 배치를 바꾼다
    const next = reduce(state, { type: 'setResultView', view: 'table' }, { type: 'placeTile', dragged: 'table', target: 'chart', edge: 'right' })

    // then: 배치만 바뀌고 컬럼·조건·차트 객체는 그대로다
    expect(next.layout).toEqual({ view: 'table', order: ['chart', 'table'], arrange: 'side_by_side' })
    expect(next.columns).toBe(state.columns)
    expect(next.conditions).toBe(state.conditions)
    expect(next.chart).toBe(state.chart)
  })

  // 테스트 코드: RS-089
  it('초기화하면 기본 배치로 돌아간다', () => {
    // given: 보기와 배치를 바꾼 상태
    const changed = reduce(emptyDesign(), { type: 'setResultView', view: 'table' }, { type: 'placeTile', dragged: 'table', target: 'chart', edge: 'right' })

    // when: 초기화한다
    const actual = reduce(changed, { type: 'reset' }).layout
    // then: 기본 배치다
    expect(actual).toEqual(DEFAULT)
  })

  it('불러온 상태의 배치를 가져온다', () => {
    // given: 배치가 다른 불러올 상태
    const loaded = { ...emptyDesign(), layout: { view: 'chart', order: ['chart', 'table'], arrange: 'side_by_side' } } as const

    // when: 불러온다
    const actual = reduce(emptyDesign(), { type: 'load', state: loaded }).layout
    // then: 그 배치가 된다
    expect(actual).toEqual(loaded.layout)
  })

  // 테스트 코드: RS-089
  it('새 리포트는 배치만 바꿔서는 바뀐 설계가 아니다', () => {
    // when: 새 리포트에서 보기와 배치만 바꾼다
    const changed = reduce(emptyDesign(), { type: 'setResultView', view: 'table' }, { type: 'placeTile', dragged: 'table', target: 'chart', edge: 'right' })

    // then: 바뀐 설계로 보지 않는다
    expect(changed.layout.view).toBe('table')
    expect(isDirty(changed, LIMITS)).toBe(false)
  })

  // 테스트 코드: RS-084
  it('배치만 바뀌면 조회 설계와 결과의 유효성은 그대로다', () => {
    // given: 컬럼이 있는 상태
    const state = withColumns('deal.code')

    // when: 타일을 옮긴다
    const next = reduce(state, { type: 'placeTile', dragged: 'table', target: 'chart', edge: 'right' })

    // then: 조회 설계는 같다
    expect(next.layout.order).toEqual(['chart', 'table'])
    expect(sameDesign(state, next)).toBe(true)
  })

  // 테스트 코드: RS-091
  it('다른 배치는 다른 설계 키이고 되돌리면 같은 키다', () => {
    // given: 컬럼이 있는 상태
    const state = withColumns('deal.code')
    // when: 타일을 옮겼다 되돌린다
    const moved = reduce(state, { type: 'placeTile', dragged: 'table', target: 'chart', edge: 'right' })
    const backToStacked = reduce(moved, { type: 'placeTile', dragged: 'chart', target: 'table', edge: 'bottom' })

    // then: 옮기면 키가 달라지고 되돌리면 같다
    expect(designKey(moved, REPORT_CATALOG)).not.toBe(designKey(state, REPORT_CATALOG))
    expect(designKey(reduce(state, { type: 'setResultView', view: 'chart' }), REPORT_CATALOG)).not.toBe(designKey(state, REPORT_CATALOG))
    expect(designKey(backToStacked, REPORT_CATALOG)).toBe(designKey(state, REPORT_CATALOG))
  })
})
