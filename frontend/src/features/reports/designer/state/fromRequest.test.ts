import { describe, expect, it } from 'vitest'
import type { ReportQueryInput } from '../../../../shared/model/reportTypes'
import { REPORT_CATALOG } from '../../../../test/reportDesigner'
import { fromReportRequest, fromSavedReport } from './fromRequest'
import { toReportRequest } from './toRequest'

/** 저장된 요청 → 디자이너 상태(Reports 3단계 P1·P2, AC15). toReportRequest의 역변환이다. */

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
  it.each(SHAPES)('round trips %s through the designer state', (_name, input) => {
    expect(requestOf(input)).toEqual(input)
  })

  it('turns money back into thousand won text and ids into strings', () => {
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

    expect(state.conditions.map((c) => c.draft)).toEqual([
      { shape: 'number', text: '1500' },
      { shape: 'range', low: '1000', high: '2000' },
      { shape: 'list', values: ['6', '1'] },
    ])
  })

  it('reads date and relative drafts', () => {
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

    expect(state.conditions.map((c) => c.draft)).toEqual([
      { shape: 'date_range', first: '2026-01-01', last: '2026-03-31' },
      { shape: 'date', day: '2026-06-30' },
      { shape: 'relative', period: 'last_n_days', days: '30' },
      { shape: 'relative', period: 'this_quarter', days: '' },
    ])
  })

  it('restores the sort of each column and leaves selection empty', () => {
    const state = load({
      columns: [CODE, { field: 'deal.name', group: false, sort: 'desc' }, { field: 'deal.solution', group: false, sort: 'asc' }],
      conditions: [],
      combine: 'and',
      rowLimit: 1000,
    })

    expect(state.columns.map((c) => c.sort)).toEqual([null, 'desc', 'asc'])
    expect('sort' in state).toBe(false)
    expect(state.selectedUid).toBeNull()
  })

  it('treats a column without sort as no sort', () => {
    const state = load({ columns: [CODE], conditions: [], combine: 'and', rowLimit: 1000 })

    expect(state.columns[0]?.sort).toBeNull()
  })

  it('gives every column and condition its own uid and leaves nextUid above them', () => {
    const state = load({
      columns: [CODE, { field: 'deal.name', group: false }],
      conditions: [{ field: 'deal.name', operator: 'is_empty' }],
      combine: 'and',
      rowLimit: 100,
    })

    const uids = [...state.columns.map((c) => c.uid), ...state.conditions.map((c) => c.uid)]
    expect(new Set(uids).size).toBe(3)
    expect(state.nextUid).toBeGreaterThan(Math.max(...uids))
  })

  it('keeps a missing label empty and a given label as typed', () => {
    const state = load({
      columns: [CODE, { field: 'deal.amount', group: false, label: '금액 합계' }],
      conditions: [],
      combine: 'and',
      rowLimit: 100,
    })

    expect(state.columns.map((c) => c.label)).toEqual(['', '금액 합계'])
  })

  it('keeps the column settings: prefix length, group and aggregate, and a number column has no format', () => {
    const state = load({
      columns: [
        { field: 'deal.name', prefixLength: 7, group: true },
        { field: 'deal.amount', group: false, aggregate: 'avg' },
      ],
      conditions: [],
      combine: 'or',
      rowLimit: 10000,
    })

    expect(state.columns[0]).toMatchObject({ field: 'deal.name', format: null, prefixOn: true, prefixLength: 7, group: true, aggregate: null })
    expect(state.columns[1]).toMatchObject({ field: 'deal.amount', format: null, prefixOn: false, prefixLength: null, group: false, aggregate: 'avg' })
    expect(state).toMatchObject({ combine: 'or', rowLimit: 10000 })
  })
})

describe('fromReportRequest number columns (AC-10)', () => {
  it('opens a number column without a format and sends none when requested again', () => {
    const input: ReportQueryInput = {
      columns: [
        { field: 'deal.amount', group: false, aggregate: 'sum', prefixLength: 3 },
        { field: 'deal.users', group: false },
      ],
      conditions: [],
      combine: 'and',
      rowLimit: 100,
    }

    const state = load(input)

    expect(state.columns.map((c) => c.format)).toEqual([null, null])
    expect(requestOf(input).columns.some((c) => 'format' in c)).toBe(false)
  })
})

describe('fromReportRequest prefix option (AC19)', () => {
  it('turns a request prefix length into an enabled option with the same N', () => {
    const state = load({ columns: [{ field: 'deal.name', prefixLength: 5, group: false }], conditions: [], combine: 'and', rowLimit: 100 })

    expect(state.columns[0]).toMatchObject({ format: null, prefixOn: true, prefixLength: 5 })
  })

  it('leaves the option off and the format empty for a plain text column', () => {
    const state = load({ columns: [CODE], conditions: [], combine: 'and', rowLimit: 100 })

    expect(state.columns[0]).toMatchObject({ format: null, prefixOn: false, prefixLength: null })
  })

  it('never writes a legacy format when the loaded design is requested again', () => {
    const request = requestOf({ columns: [{ field: 'deal.name', prefixLength: 5, group: false }], conditions: [], combine: 'and', rowLimit: 100 })

    expect(request.columns[0]).toEqual({ field: 'deal.name', prefixLength: 5, group: false })
  })
})

describe('fromReportRequest with fields the catalog no longer has', () => {
  it('keeps unknown fields so the server can report them', () => {
    const input: ReportQueryInput = {
      columns: [CODE, { field: 'deal.nope', group: false, label: '없는 필드' }],
      conditions: [{ field: 'deal.nada', operator: 'contains', value: 'x' }],
      combine: 'and',
      rowLimit: 100,
    }

    const state = load(input)
    const request = requestOf(input)

    expect(state.columns.map((c) => c.field)).toEqual(['deal.code', 'deal.nope'])
    expect(state.conditions.map((c) => c.field)).toEqual(['deal.nada'])
    expect(request.columns).toEqual(input.columns)
    expect(request.conditions[0]).toMatchObject({ field: 'deal.nada', operator: 'contains' })
  })
})

describe('fromReportRequest money conditions (AC-9)', () => {
  it('divides only the amount by 1,000 for the input text', () => {
    const state = load(
      withConditions([
        { field: 'deal.amount', operator: 'gte', value: 1_500_000 },
        { field: 'deal.users', operator: 'gte', value: 5 },
      ]),
    )

    expect(state.conditions.map((c) => c.draft)).toEqual([
      { shape: 'number', text: '1500' },
      { shape: 'number', text: '5' },
    ])
  })
})

describe('fromSavedReport and the result layout (작성/결과 탭 분리 AC18)', () => {
  const definition: ReportQueryInput = { columns: [CODE], conditions: [], combine: 'and', rowLimit: 100 }

  it('takes the saved layout into the designer state', () => {
    const layout = { view: 'chart', order: ['chart', 'table'], arrange: 'side_by_side' } as const

    const state = fromSavedReport({ definition, chart: null, layout }, REPORT_CATALOG, REPORT_CATALOG.limits)

    expect(state.layout).toEqual(layout)
  })

  it('opens a plain definition with the default layout', () => {
    expect(load(definition).layout).toEqual({ view: 'both', order: ['table', 'chart'], arrange: 'stacked' })
  })
})
