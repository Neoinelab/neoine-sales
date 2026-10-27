import { describe, expect, it } from 'vitest'
import type { ReportOperator } from '../../../../shared/model/reportTypes'
import { columnAt, conditionUidAt, emptyDesign, fieldOf, reduce, REPORT_CATALOG, uidAt, withColumns } from '../../../../test/reportDesigner'
import { aggregateChoices, filterableFields } from './columnRules'

describe('grouping transitions (AC6)', () => {
  it('turning on the first group fills number defaults and leaves text empty', () => {
    const state = withColumns('deal.vendor', 'deal.code', 'deal.amount', 'deal.status_days', 'action.count')

    const grouped = reduce(state, { type: 'updateColumn', uid: uidAt(state, 0), patch: { group: true } })

    expect(grouped.columns.map((c) => [c.field, c.group, c.aggregate])).toEqual([
      ['deal.vendor', true, null],
      ['deal.code', false, null],
      ['deal.amount', false, 'sum'],
      ['deal.status_days', false, 'avg'],
      ['action.count', false, 'count'],
    ])
  })

  it('turning off the last group clears every aggregate', () => {
    const state = withColumns('deal.vendor', 'deal.amount')
    const grouped = reduce(state, { type: 'updateColumn', uid: uidAt(state, 0), patch: { group: true } })

    const flat = reduce(grouped, { type: 'updateColumn', uid: uidAt(grouped, 0), patch: { group: false } })

    expect(flat.columns.map((c) => c.aggregate)).toEqual([null, null])
  })

  it('keeps the aggregates while another group remains', () => {
    const state = withColumns('deal.vendor', 'deal.status', 'deal.amount')
    const both = reduce(
      state,
      { type: 'updateColumn', uid: uidAt(state, 0), patch: { group: true } },
      { type: 'updateColumn', uid: uidAt(state, 1), patch: { group: true } },
    )

    const one = reduce(both, { type: 'updateColumn', uid: uidAt(both, 0), patch: { group: false } })

    expect(columnAt(one, 2).aggregate).toBe('sum')
  })

  it('clears the aggregate of a column that becomes a group', () => {
    const state = withColumns('deal.vendor', 'deal.amount')
    const grouped = reduce(state, { type: 'updateColumn', uid: uidAt(state, 0), patch: { group: true } })

    const regrouped = reduce(grouped, { type: 'updateColumn', uid: uidAt(grouped, 1), patch: { group: true } })

    expect(columnAt(regrouped, 1)).toMatchObject({ group: true, aggregate: null })
  })

  it('gives a column added later the default aggregate only when a group exists', () => {
    const flat = withColumns('deal.vendor')
    const grouped = reduce(flat, { type: 'updateColumn', uid: uidAt(flat, 0), patch: { group: true } })

    const withNumber = reduce(grouped, { type: 'addColumn', field: fieldOf('deal.amount') })
    const withText = reduce(grouped, { type: 'addColumn', field: fieldOf('deal.name') })
    const ungrouped = reduce(flat, { type: 'addColumn', field: fieldOf('deal.amount') })

    expect(columnAt(withNumber, 1).aggregate).toBe('sum')
    expect(columnAt(withText, 1).aggregate).toBeNull()
    expect(columnAt(ungrouped, 1).aggregate).toBeNull()
  })

  it('keeps an aggregate the user picked', () => {
    const state = withColumns('deal.vendor', 'deal.amount')
    const grouped = reduce(state, { type: 'updateColumn', uid: uidAt(state, 0), patch: { group: true } })

    const picked = reduce(grouped, { type: 'updateColumn', uid: uidAt(grouped, 1), patch: { aggregate: 'max' } })

    expect(columnAt(picked, 1).aggregate).toBe('max')
  })
})

describe('aggregate choices (AC6)', () => {
  it('aggregate choices follow the catalog', () => {
    expect(aggregateChoices(fieldOf('deal.code'))).toEqual(['count', 'count_distinct'])
    expect(aggregateChoices(fieldOf('deal.vendor'))).toEqual(['count', 'count_distinct'])
    expect(aggregateChoices(fieldOf('deal.amount'))).toEqual(['sum', 'avg', 'min', 'max'])
    expect(aggregateChoices(fieldOf('action.count'))).toEqual(['count'])
  })
})

describe('format change (AC6)', () => {
  it('format change to prefix sets length 20 and other formats clear it', () => {
    const state = withColumns('deal.name')
    const uid = uidAt(state, 0)

    const prefix = reduce(state, { type: 'updateColumn', uid, patch: { format: 'prefix' } })
    const longer = reduce(prefix, { type: 'updateColumn', uid, patch: { prefixLength: 5 } })
    const plain = reduce(longer, { type: 'updateColumn', uid, patch: { format: 'as_is' } })
    const again = reduce(plain, { type: 'updateColumn', uid, patch: { format: 'prefix' } })

    expect(columnAt(prefix, 0)).toMatchObject({ format: 'prefix', prefixLength: 20 })
    expect(columnAt(longer, 0).prefixLength).toBe(5)
    expect(columnAt(plain, 0)).toMatchObject({ format: 'as_is', prefixLength: null })
    expect(columnAt(again, 0).prefixLength).toBe(20)
  })
})

describe('condition rules (AC7)', () => {
  it('condition fields exclude the non filterable action count', () => {
    const fields = filterableFields(REPORT_CATALOG)

    expect(fields).toHaveLength(39)
    expect(fields.map((f) => f.key)).not.toContain('action.count')
    expect(fields.every((f) => f.filterable)).toBe(true)
  })

  it('changing the condition field resets operator and value', () => {
    const added = reduce(emptyDesign(), { type: 'addCondition', field: fieldOf('deal.name') })
    const uid = conditionUidAt(added, 0)
    const typed = reduce(added, { type: 'changeOperator', uid, operator: 'equals' }, { type: 'changeDraft', uid, draft: { shape: 'text', text: '은행' } })

    const changed = reduce(typed, { type: 'changeConditionField', uid, field: fieldOf('deal.amount') })

    expect(changed.conditions[0]).toMatchObject({ field: 'deal.amount', operator: 'eq', draft: { shape: 'number', text: '' } })
  })

  it('starts each operator shape with an empty draft of that shape', () => {
    const draftOf = (key: string, operator: ReportOperator) => {
      const added = reduce(emptyDesign(), { type: 'addCondition', field: fieldOf(key) })
      const uid = conditionUidAt(added, 0)
      return reduce(added, { type: 'changeOperator', uid, operator }).conditions[0]?.draft
    }

    expect(draftOf('deal.name', 'is_empty')).toEqual({ shape: 'none' })
    expect(draftOf('deal.vendor', 'in')).toEqual({ shape: 'list', values: [] })
    expect(draftOf('deal.amount', 'between')).toEqual({ shape: 'range', low: '', high: '' })
    expect(draftOf('deal.expected_close', 'before')).toEqual({ shape: 'date', day: '' })
    expect(draftOf('deal.expected_close', 'between')).toEqual({ shape: 'date_range', first: '', last: '' })
    expect(draftOf('deal.created_at', 'between')).toEqual({ shape: 'date_range', first: '', last: '' })
    expect(draftOf('deal.expected_close', 'relative')).toMatchObject({ shape: 'relative', period: 'this_year' })
  })

  it('keeps the typed value when the operator keeps its shape and drops it otherwise', () => {
    const added = reduce(emptyDesign(), { type: 'addCondition', field: fieldOf('deal.amount') })
    const uid = conditionUidAt(added, 0)
    const typed = reduce(added, { type: 'changeDraft', uid, draft: { shape: 'number', text: '1,500' } })

    const sameShape = reduce(typed, { type: 'changeOperator', uid, operator: 'gt' })
    const otherShape = reduce(typed, { type: 'changeOperator', uid, operator: 'between' })

    expect(sameShape.conditions[0]?.draft).toEqual({ shape: 'number', text: '1,500' })
    expect(otherShape.conditions[0]?.draft).toEqual({ shape: 'range', low: '', high: '' })
  })
})
