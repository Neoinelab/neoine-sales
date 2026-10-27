import { describe, expect, it } from 'vitest'
import { columnAt, conditionUidAt, emptyDesign, fieldOf, reduce, REPORT_CATALOG, uidAt, withColumns } from '../../../../test/reportDesigner'
import { designerReducer, initialDesignerState, isDirty } from './designerState'
import { toReportRequest } from './toRequest'

const LIMITS = REPORT_CATALOG.limits

describe('initialDesignerState', () => {
  it('starts without columns or conditions, with AND, no sort and the default row limit', () => {
    expect(initialDesignerState(LIMITS)).toMatchObject({
      columns: [],
      conditions: [],
      combine: 'and',
      sort: null,
      rowLimit: 1000,
      selectedUid: null,
    })
  })
})

describe('designerReducer columns (AC4)', () => {
  it('adds the same field twice as two columns with default format', () => {
    const state = withColumns('deal.amount', 'deal.amount')

    expect(state.columns).toHaveLength(2)
    expect(uidAt(state, 0)).not.toBe(uidAt(state, 1))
    for (const column of state.columns) {
      expect(column).toMatchObject({ field: 'deal.amount', format: 'krw_thousand', label: '', group: false, aggregate: null, prefixLength: null })
    }
  })

  it('selects the column it just added', () => {
    const state = withColumns('deal.code', 'deal.name')

    expect(state.selectedUid).toBe(uidAt(state, 1))
  })

  it('removes the column by uid', () => {
    const state = withColumns('deal.code', 'deal.name', 'deal.solution')

    const next = reduce(state, { type: 'removeColumn', uid: uidAt(state, 1) })

    expect(next.columns.map((c) => c.field)).toEqual(['deal.code', 'deal.solution'])
    expect(next.selectedUid).not.toBe(uidAt(state, 1))
  })

  it('does not add a column beyond the limit and keeps the same state object', () => {
    const state = withColumns(...Array.from({ length: LIMITS.columnsMax }, () => 'deal.code'))

    const next = reduce(state, { type: 'addColumn', field: fieldOf('deal.name') })

    expect(state.columns).toHaveLength(30)
    expect(next).toBe(state)
  })

  it('selects a column by uid and clears the selection with null', () => {
    const state = withColumns('deal.code', 'deal.name')

    const first = reduce(state, { type: 'selectColumn', uid: uidAt(state, 0) })
    const none = reduce(first, { type: 'selectColumn', uid: null })

    expect(first.selectedUid).toBe(uidAt(state, 0))
    expect(none.selectedUid).toBeNull()
  })

  it('updates the label of one column only', () => {
    const state = withColumns('deal.code', 'deal.name')

    const next = reduce(state, { type: 'updateColumn', uid: uidAt(state, 1), patch: { label: '이름' } })

    expect(next.columns.map((c) => c.label)).toEqual(['', '이름'])
  })
})

describe('designerReducer moving (AC5)', () => {
  it('moves a column to the target index', () => {
    const state = withColumns('deal.code', 'deal.name', 'deal.solution')

    const next = reduce(state, { type: 'moveColumn', uid: uidAt(state, 0), to: 2 })

    expect(next.columns.map((c) => c.field)).toEqual(['deal.name', 'deal.solution', 'deal.code'])
  })

  it('clamps a target past the end to the last place', () => {
    const state = withColumns('deal.code', 'deal.name', 'deal.solution')

    const next = reduce(state, { type: 'moveColumn', uid: uidAt(state, 0), to: 99 })

    expect(next.columns.map((c) => c.field)).toEqual(['deal.name', 'deal.solution', 'deal.code'])
  })

  it('keeps the same state object when the column is already there', () => {
    const state = withColumns('deal.code', 'deal.name')

    expect(reduce(state, { type: 'moveColumn', uid: uidAt(state, 1), to: 1 })).toBe(state)
  })

  it('moves a column and keeps the sort on the same column', () => {
    const base = withColumns('deal.code', 'deal.name', 'deal.solution')
    const sorted = reduce(base, { type: 'setSort', sort: { uid: uidAt(base, 0), direction: 'desc' } })

    const next = reduce(sorted, { type: 'moveColumn', uid: uidAt(sorted, 0), to: 2 })
    const request = toReportRequest(next, REPORT_CATALOG)

    expect(next.sort).toEqual({ uid: uidAt(sorted, 0), direction: 'desc' })
    expect('request' in request && request.request.sort).toEqual({ column: 2, direction: 'desc' })
  })
})

describe('designerReducer sort (AC10)', () => {
  it('removing the sorted column clears the sort', () => {
    const state = withColumns('deal.code', 'deal.name')
    const sorted = reduce(state, { type: 'setSort', sort: { uid: uidAt(state, 1), direction: 'asc' } })

    const next = reduce(sorted, { type: 'removeColumn', uid: uidAt(sorted, 1) })

    expect(next.sort).toBeNull()
  })

  it('keeps the sort when another column is removed', () => {
    const state = withColumns('deal.code', 'deal.name')
    const sorted = reduce(state, { type: 'setSort', sort: { uid: uidAt(state, 1), direction: 'asc' } })

    const next = reduce(sorted, { type: 'removeColumn', uid: uidAt(sorted, 0) })

    expect(next.sort).toEqual({ uid: uidAt(sorted, 1), direction: 'asc' })
  })

  it('sets and clears the row limit', () => {
    const state = reduce(emptyDesign(), { type: 'setRowLimit', rowLimit: 10000 })

    expect(state.rowLimit).toBe(10000)
  })
})

describe('designerReducer conditions (AC7, AC8)', () => {
  it('adds a condition with the first operator and an empty value', () => {
    const state = reduce(emptyDesign(), { type: 'addCondition', field: fieldOf('deal.name') })

    expect(state.conditions).toHaveLength(1)
    expect(state.conditions[0]).toMatchObject({ field: 'deal.name', operator: 'contains', draft: { shape: 'text', text: '' } })
  })

  it('does not add a condition beyond the limit and keeps the same state object', () => {
    const many = Array.from({ length: LIMITS.conditionsMax }, () => ({ type: 'addCondition' as const, field: fieldOf('deal.name') }))
    const state = reduce(emptyDesign(), ...many)

    expect(reduce(state, { type: 'addCondition', field: fieldOf('deal.name') })).toBe(state)
  })

  it('removes a condition by uid', () => {
    const state = reduce(emptyDesign(), { type: 'addCondition', field: fieldOf('deal.name') }, { type: 'addCondition', field: fieldOf('deal.code') })

    const next = reduce(state, { type: 'removeCondition', uid: conditionUidAt(state, 0) })

    expect(next.conditions.map((c) => c.field)).toEqual(['deal.code'])
  })

  it('switches the combine', () => {
    expect(reduce(emptyDesign(), { type: 'setCombine', combine: 'or' }).combine).toBe('or')
  })

  it('stores the typed draft', () => {
    const state = reduce(emptyDesign(), { type: 'addCondition', field: fieldOf('deal.name') })

    const next = reduce(state, { type: 'changeDraft', uid: conditionUidAt(state, 0), draft: { shape: 'text', text: '은행' } })

    expect(next.conditions[0]?.draft).toEqual({ shape: 'text', text: '은행' })
  })
})

describe('reset and isDirty (AC15, AC16)', () => {
  it('is dirty only after a change from the initial state', () => {
    const initial = emptyDesign()

    expect(isDirty(initial, LIMITS)).toBe(false)
    expect(isDirty(reduce(initial, { type: 'addColumn', field: fieldOf('deal.code') }), LIMITS)).toBe(true)
    expect(isDirty(reduce(initial, { type: 'addCondition', field: fieldOf('deal.name') }), LIMITS)).toBe(true)
    expect(isDirty(reduce(initial, { type: 'setCombine', combine: 'or' }), LIMITS)).toBe(true)
    expect(isDirty(reduce(initial, { type: 'setRowLimit', rowLimit: 100 }), LIMITS)).toBe(true)
  })

  it('is not dirty again after the added column is removed', () => {
    const added = withColumns('deal.code')

    const removed = reduce(added, { type: 'removeColumn', uid: uidAt(added, 0) })

    expect(isDirty(removed, LIMITS)).toBe(false)
  })

  it('goes back to the initial design on reset', () => {
    const state = reduce(withColumns('deal.code'), { type: 'setCombine', combine: 'or' }, { type: 'reset' })

    expect(state).toMatchObject({ columns: [], conditions: [], combine: 'and', sort: null, rowLimit: 1000, selectedUid: null })
    expect(isDirty(state, LIMITS)).toBe(false)
  })

  it('never reuses the uid of a removed column', () => {
    const first = withColumns('deal.code')
    const removed = reduce(first, { type: 'removeColumn', uid: uidAt(first, 0) })

    const second = reduce(removed, { type: 'addColumn', field: fieldOf('deal.code') })

    expect(uidAt(second, 0)).not.toBe(uidAt(first, 0))
  })

  it('returns the reducer unchanged for an unknown uid', () => {
    const state = withColumns('deal.code')

    expect(designerReducer(state, { type: 'removeColumn', uid: 9999 }, REPORT_CATALOG)).toBe(state)
    expect(columnAt(state, 0).field).toBe('deal.code')
  })
})
