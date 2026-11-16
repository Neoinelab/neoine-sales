import { describe, expect, it } from 'vitest'
import type { ReportQueryInput } from '../../../../shared/model/reportTypes'
import { REPORT_CATALOG } from '../../../../test/reportDesigner'
import { fromReportRequest, fromSavedReport } from './fromRequest'
import { toReportRequest } from './toRequest'

/** 저장된 요청 → 디자이너 상태. toReportRequest의 역변환이다. */

const load = (input: ReportQueryInput) => fromReportRequest(input, REPORT_CATALOG, REPORT_CATALOG.limits)

function requestOf(input: ReportQueryInput): ReportQueryInput {
  const built = toReportRequest(load(input), REPORT_CATALOG)
  if (!('request' in built)) throw new Error(`요청을 만들지 못함: ${JSON.stringify(built)}`)
  return built.request
}

const CODE: ReportQueryInput['columns'][number] = { field: 'deal.code', group: false }
const withConditions = (conditions: ReportQueryInput['conditions']): ReportQueryInput => ({
  columns: [CODE],
  conditions,
  combine: 'and',
  rowLimit: 100,
})

const SHAPES: readonly (readonly [string, ReportQueryInput])[] = [
  [
    'a grouped vendor by quarter report with money, list, label and sort',
    {
      columns: [
        { field: 'deal.vendor', group: true },
        { field: 'deal.expected_close', format: 'quarter', group: true },
        { field: 'deal.amount', group: false, aggregate: 'sum', label: '금액 합계', sort: 'desc' },
      ],
      conditions: [
        { field: 'deal.vendor', operator: 'in', value: [6, 1] },
        { field: 'deal.amount', operator: 'gte', value: 1_500_000 },
      ],
      combine: 'and',
      rowLimit: 1000,
    },
  ],
  ['a prefix column with its length', { columns: [{ field: 'deal.name', prefixLength: 7, group: false }], conditions: [], combine: 'and', rowLimit: 100 }],
  ['a prefix length on a number column', { columns: [{ field: 'deal.amount', prefixLength: 3, group: false }], conditions: [], combine: 'and', rowLimit: 100 }],
  ['a money range', withConditions([{ field: 'deal.amount', operator: 'between', value: [1_000_000, 2_000_000] }])],
  ['a zero money value', withConditions([{ field: 'deal.amount', operator: 'eq', value: 0 }])],
  ['a text condition', withConditions([{ field: 'deal.name', operator: 'contains', value: 'ITDR' }])],
  ['a condition without a value', withConditions([{ field: 'deal.name', operator: 'is_empty' }])],
  ['a key list', withConditions([{ field: 'deal.risk', operator: 'in', value: ['overdue', 'stale'] }])],
  ['an id list', withConditions([{ field: 'deal.owner', operator: 'not_in', value: [2, 3] }])],
  ['a date range', withConditions([{ field: 'deal.expected_close', operator: 'between', value: ['2026-01-01', '2026-03-31'] }])],
  ['a single date', withConditions([{ field: 'deal.expected_close', operator: 'before', value: '2026-12-31' }])],
  ['a relative period without days', withConditions([{ field: 'deal.expected_close', operator: 'relative', value: { period: 'this_year' } }])],
  ['a relative period of the last 1 month', withConditions([{ field: 'deal.expected_close', operator: 'relative', value: { period: 'last_1_month' } }])],
  ['a relative period of the last 3 months', withConditions([{ field: 'deal.created_at', operator: 'relative', value: { period: 'last_3_months' } }])],
  ['a relative period of the last 6 months', withConditions([{ field: 'deal.expected_close', operator: 'relative', value: { period: 'last_6_months' } }])],
  ['a relative period with days', withConditions([{ field: 'deal.created_at', operator: 'relative', value: { period: 'last_n_days', days: 30 } }])],
  ['an OR combine with the largest row limit', { columns: [CODE], conditions: [], combine: 'or', rowLimit: 10000 }],
  [
    'an Action column grouped with a count',
    {
      columns: [
        { field: 'deal.vendor', group: true, sort: 'asc' },
        { field: 'action.count', group: false, aggregate: 'count' },
      ],
      conditions: [],
      combine: 'and',
      rowLimit: 100,
    },
  ],
]

describe('fromReportRequest', () => {
  it.each(SHAPES)('%s 요청은 디자이너 상태를 거쳐도 그대로 돌아온다', (_name, input) => {
    // when: 상태로 읽었다 다시 요청으로 바꾼다
    const actual = requestOf(input)
    // then: 같다
    expect(actual).toEqual(input)
  })

  it('금액은 콤마가 있는 원 문자열로, id는 문자열로 읽는다', () => {
    // when: 금액·id 조건이 있는 요청을 읽는다
    const state = load({
      columns: [CODE],
      conditions: [
        { field: 'deal.amount', operator: 'gte', value: 1_500_000 },
        { field: 'deal.amount', operator: 'between', value: [1_000_000, 2_000_000] },
        { field: 'deal.vendor', operator: 'in', value: [6, 1] },
      ],
      combine: 'and',
      rowLimit: 100,
    })

    // then: 초안이 원 문자열·id 문자열이다
    expect(state.conditions.map((c) => c.draft)).toEqual([
      { shape: 'number', text: '1,500,000' },
      { shape: 'range', low: '1,000,000', high: '2,000,000' },
      { shape: 'list', values: ['6', '1'] },
    ])
  })

  it('날짜와 상대 기간 초안을 읽는다', () => {
    // when: 날짜·상대 기간 조건을 읽는다
    const state = load({
      columns: [CODE],
      conditions: [
        { field: 'deal.expected_close', operator: 'between', value: ['2026-01-01', '2026-03-31'] },
        { field: 'deal.expected_close', operator: 'after', value: '2026-06-30' },
        { field: 'deal.created_at', operator: 'relative', value: { period: 'last_n_days', days: 30 } },
        { field: 'deal.expected_close', operator: 'relative', value: { period: 'this_quarter' } },
      ],
      combine: 'and',
      rowLimit: 100,
    })

    // then: 해당 초안으로 복원된다
    expect(state.conditions.map((c) => c.draft)).toEqual([
      { shape: 'date_range', first: '2026-01-01', last: '2026-03-31' },
      { shape: 'date', day: '2026-06-30' },
      { shape: 'relative', period: 'last_n_days', days: '30' },
      { shape: 'relative', period: 'this_quarter', days: '' },
    ])
  })

  it('개월 기준 상대 기간은 일 수 없이 복원한다', () => {
    // when: 최근 3개월 조건을 읽는다
    const state = load({
      columns: [CODE],
      conditions: [{ field: 'deal.expected_close', operator: 'relative', value: { period: 'last_3_months' } }],
      combine: 'and',
      rowLimit: 100,
    })

    // then: 일 수 없는 초안이다
    expect(state.conditions.map((c) => c.draft)).toEqual([{ shape: 'relative', period: 'last_3_months', days: '' }])
  })

  it('컬럼마다 정렬을 복원하고 선택은 비워 둔다', () => {
    // when: 컬럼별 정렬이 있는 요청을 읽는다
    const state = load({
      columns: [CODE, { field: 'deal.name', group: false, sort: 'desc' }, { field: 'deal.product', group: false, sort: 'asc' }],
      conditions: [],
      combine: 'and',
      rowLimit: 1000,
    })

    // then: 정렬이 복원되고 선택은 없다
    expect(state.columns.map((c) => c.sort)).toEqual([null, 'desc', 'asc'])
    expect('sort' in state).toBe(false)
    expect(state.selectedUid).toBeNull()
  })

  it('정렬이 없는 컬럼은 정렬 없음이다', () => {
    // when: 정렬 없는 컬럼을 읽는다
    const state = load({ columns: [CODE], conditions: [], combine: 'and', rowLimit: 1000 })

    // then: 정렬이 null이다
    expect(state.columns[0]?.sort).toBeNull()
  })

  it('컬럼·조건마다 고유 uid를 주고 nextUid는 그 위다', () => {
    // when: 컬럼과 조건을 읽는다
    const state = load({
      columns: [CODE, { field: 'deal.name', group: false }],
      conditions: [{ field: 'deal.name', operator: 'is_empty' }],
      combine: 'and',
      rowLimit: 100,
    })

    // then: uid가 모두 다르고 nextUid가 더 크다
    const uids = [...state.columns.map((c) => c.uid), ...state.conditions.map((c) => c.uid)]
    expect(new Set(uids).size).toBe(3)
    expect(state.nextUid).toBeGreaterThan(Math.max(...uids))
  })

  it('없는 표시 이름은 비워 두고 준 이름은 그대로 둔다', () => {
    // when: 표시 이름이 있는 컬럼과 없는 컬럼을 읽는다
    const state = load({
      columns: [CODE, { field: 'deal.amount', group: false, label: '금액 합계' }],
      conditions: [],
      combine: 'and',
      rowLimit: 100,
    })

    // then: 빈 이름과 준 이름 그대로다
    expect(state.columns.map((c) => c.label)).toEqual(['', '금액 합계'])
  })

  it('앞 N자·그룹핑·집계를 복원하고 숫자 컬럼에는 포맷이 없다', () => {
    // when: 컬럼 설정이 있는 요청을 읽는다
    const state = load({
      columns: [
        { field: 'deal.name', prefixLength: 7, group: true },
        { field: 'deal.amount', group: false, aggregate: 'avg' },
      ],
      conditions: [],
      combine: 'or',
      rowLimit: 10000,
    })

    // then: 설정이 복원되고 숫자 컬럼은 포맷이 없다
    expect(state.columns[0]).toMatchObject({ field: 'deal.name', format: null, prefixOn: true, prefixLength: 7, group: true, aggregate: null })
    expect(state.columns[1]).toMatchObject({ field: 'deal.amount', format: null, prefixOn: false, prefixLength: null, group: false, aggregate: 'avg' })
    expect(state).toMatchObject({ combine: 'or', rowLimit: 10000 })
  })
})

describe('fromReportRequest number columns', () => {
  it('숫자 컬럼은 포맷 없이 열고 다시 요청해도 보내지 않는다', () => {
    // given: 숫자 컬럼 요청
    const input: ReportQueryInput = {
      columns: [
        { field: 'deal.amount', group: false, aggregate: 'sum', prefixLength: 3 },
        { field: 'deal.users', group: false },
      ],
      conditions: [],
      combine: 'and',
      rowLimit: 100,
    }

    // when: 읽는다
    const state = load(input)

    // then: 포맷이 없고 다시 요청해도 format 키가 없다
    expect(state.columns.map((c) => c.format)).toEqual([null, null])
    expect(requestOf(input).columns.some((c) => 'format' in c)).toBe(false)
  })
})

describe('fromReportRequest prefix option', () => {
  it('요청의 앞 N자는 같은 N으로 켜진 옵션이 된다', () => {
    // when: 앞 5자 컬럼을 읽는다
    const state = load({ columns: [{ field: 'deal.name', prefixLength: 5, group: false }], conditions: [], combine: 'and', rowLimit: 100 })

    // then: 옵션이 켜지고 N이 5다
    expect(state.columns[0]).toMatchObject({ format: null, prefixOn: true, prefixLength: 5 })
  })

  it('일반 텍스트 컬럼은 옵션이 꺼지고 포맷이 비어 있다', () => {
    // when: 일반 텍스트 컬럼을 읽는다
    const state = load({ columns: [CODE], conditions: [], combine: 'and', rowLimit: 100 })

    // then: 옵션이 꺼져 있다
    expect(state.columns[0]).toMatchObject({ format: null, prefixOn: false, prefixLength: null })
  })

  it('불러온 설계를 다시 요청해도 예전 포맷을 쓰지 않는다', () => {
    // when: 불러온 설계를 다시 요청으로 바꾼다
    const request = requestOf({ columns: [{ field: 'deal.name', prefixLength: 5, group: false }], conditions: [], combine: 'and', rowLimit: 100 })

    // then: format 키가 없다
    expect(request.columns[0]).toEqual({ field: 'deal.name', prefixLength: 5, group: false })
  })
})

describe('fromReportRequest with fields the catalog no longer has', () => {
  it('카탈로그에 없는 필드도 그대로 두어 서버가 알리게 한다', () => {
    // given: 카탈로그에 없는 필드가 섞인 요청
    const input: ReportQueryInput = {
      columns: [CODE, { field: 'deal.nope', group: false, label: '없는 필드' }],
      conditions: [{ field: 'deal.nada', operator: 'contains', value: 'x' }],
      combine: 'and',
      rowLimit: 100,
    }

    // when: 읽고 다시 요청으로 바꾼다
    const state = load(input)
    const request = requestOf(input)

    // then: 모르는 필드가 그대로 남는다
    expect(state.columns.map((c) => c.field)).toEqual(['deal.code', 'deal.nope'])
    expect(state.conditions.map((c) => c.field)).toEqual(['deal.nada'])
    expect(request.columns).toEqual(input.columns)
    expect(request.conditions[0]).toMatchObject({ field: 'deal.nada', operator: 'contains' })
  })
})

describe('fromReportRequest money conditions', () => {
  it('금액만 콤마로 쓰고 다른 숫자는 그대로 둔다', () => {
    // when: 금액 조건과 다른 숫자 조건을 읽는다
    const state = load(
      withConditions([
        { field: 'deal.amount', operator: 'gte', value: 1_500_000 },
        { field: 'deal.users', operator: 'gte', value: 5 },
      ]),
    )

    // then: 금액만 콤마 문자열이다
    expect(state.conditions.map((c) => c.draft)).toEqual([
      { shape: 'number', text: '1,500,000' },
      { shape: 'number', text: '5' },
    ])
  })
})

describe('fromSavedReport와 결과 배치', () => {
  const definition: ReportQueryInput = { columns: [CODE], conditions: [], combine: 'and', rowLimit: 100 }

  // 테스트 코드: RS-091
  it('저장된 배치를 디자이너 상태에 가져온다', () => {
    // given: 저장된 리포트의 배치
    const layout = { view: 'chart', order: ['chart', 'table'], arrange: 'side_by_side' } as const

    // when: 저장 리포트를 상태로 읽는다
    const state = fromSavedReport({ definition, chart: null, layout }, REPORT_CATALOG, REPORT_CATALOG.limits)

    // then: 상태의 배치가 저장된 배치다
    expect(state.layout).toEqual(layout)
  })

  // 테스트 코드: RS-091
  it('배치가 없는 정의는 기본 배치로 연다', () => {
    // when: 정의만 읽는다
    const actual = load(definition).layout
    // then: 기본 배치다
    expect(actual).toEqual({ view: 'both', order: ['table', 'chart'], arrange: 'stacked' })
  })
})
