import { describe, expect, it } from 'vitest'
import type { ReportQueryInput } from '../../../../shared/model/reportTypes'
import { fieldOf, reduce, REPORT_CATALOG, uidAt } from '../../../../test/reportDesigner'
import { designKey } from './designKey'
import { fromReportRequest } from './fromRequest'

/** 편집 화면의 "저장 안 됨" 판정 기준(Reports 3단계 P3, AC15): 설계 내용이 같으면 같은 문자열. */

const SAVED: ReportQueryInput = {
  columns: [
    { field: 'deal.vendor', group: true },
    { field: 'deal.amount', format: 'krw_thousand', group: false, aggregate: 'sum', sort: 'desc' },
  ],
  conditions: [{ field: 'deal.amount', operator: 'gte', value: 1_500_000 }],
  combine: 'and',
  rowLimit: 1000,
}

const load = () => fromReportRequest(SAVED, REPORT_CATALOG, REPORT_CATALOG.limits)
const keyOf = (state: ReturnType<typeof load>) => designKey(state, REPORT_CATALOG)

describe('designKey', () => {
  it('is equal for the loaded state and changes after an edit and back', () => {
    const loaded = load()
    const baseline = keyOf(loaded)

    const edited = reduce(loaded, { type: 'addColumn', field: fieldOf('deal.code') })
    const editedKey = keyOf(edited)
    const undone = reduce(edited, { type: 'removeColumn', uid: edited.columns[2]?.uid ?? -1 })

    expect(typeof baseline).toBe('string')
    expect(keyOf(load())).toBe(baseline)
    expect(editedKey).not.toBe(baseline)
    expect(keyOf(undone)).toBe(baseline)
  })

  it('does not depend on uids or on the selected column', () => {
    const loaded = load()
    const shifted = reduce(loaded, { type: 'addColumn', field: fieldOf('deal.code') })
    const removed = reduce(shifted, { type: 'removeColumn', uid: shifted.columns[2]?.uid ?? -1 })

    expect(removed.nextUid).not.toBe(loaded.nextUid)
    expect(keyOf(reduce(removed, { type: 'selectColumn', uid: uidAt(removed, 0) }))).toBe(keyOf(loaded))
  })

  it.each([
    ['a label', (s: ReturnType<typeof load>) => reduce(s, { type: 'updateColumn', uid: uidAt(s, 1), patch: { label: '합계' } })],
    ['the prefix option', (s: ReturnType<typeof load>) => reduce(s, { type: 'updateColumn', uid: uidAt(s, 0), patch: { prefixOn: true, prefixLength: 4 } })],
    ['the combine', (s: ReturnType<typeof load>) => reduce(s, { type: 'setCombine', combine: 'or' })],
    ['the row limit', (s: ReturnType<typeof load>) => reduce(s, { type: 'setRowLimit', rowLimit: 100 })],
    ['a column sort direction', (s: ReturnType<typeof load>) => reduce(s, { type: 'updateColumn', uid: uidAt(s, 1), patch: { sort: 'asc' } })],
    ['a column sort off', (s: ReturnType<typeof load>) => reduce(s, { type: 'updateColumn', uid: uidAt(s, 1), patch: { sort: null } })],
    ['a sort on another column', (s: ReturnType<typeof load>) => reduce(s, { type: 'updateColumn', uid: uidAt(s, 0), patch: { sort: 'asc' } })],
    ['the column order', (s: ReturnType<typeof load>) => reduce(s, { type: 'moveColumn', uid: uidAt(s, 1), to: 0 })],
    ['a condition value', (s: ReturnType<typeof load>) => reduce(s, { type: 'changeDraft', uid: s.conditions[0]?.uid ?? -1, draft: { shape: 'number', text: '2000' } })],
  ])('changes when %s changes', (_name, edit) => {
    expect(keyOf(edit(load()))).not.toBe(keyOf(load()))
  })

  it('still gives a key when a condition value cannot be read and tells it from another draft', () => {
    const loaded = load()
    const uid = loaded.conditions[0]?.uid ?? -1
    const unreadable = reduce(loaded, { type: 'changeDraft', uid, draft: { shape: 'number', text: 'abc' } })
    const other = reduce(loaded, { type: 'changeDraft', uid, draft: { shape: 'number', text: 'abd' } })

    expect(keyOf(unreadable)).not.toBe(keyOf(loaded))
    expect(keyOf(unreadable)).not.toBe(keyOf(other))
    expect(keyOf(unreadable)).toBe(keyOf(reduce(loaded, { type: 'changeDraft', uid, draft: { shape: 'number', text: 'abc' } })))
  })

  it('gets the same key again when a column sort is changed back', () => {
    const loaded = load()
    const flipped = reduce(loaded, { type: 'updateColumn', uid: uidAt(loaded, 1), patch: { sort: 'asc' } })
    const back = reduce(flipped, { type: 'updateColumn', uid: uidAt(flipped, 1), patch: { sort: 'desc' } })

    expect(keyOf(back)).toBe(keyOf(loaded))
  })

  it('tells which column carries the sort', () => {
    const loaded = load()
    const moved = reduce(
      loaded,
      { type: 'updateColumn', uid: uidAt(loaded, 1), patch: { sort: null } },
      { type: 'updateColumn', uid: uidAt(loaded, 0), patch: { sort: 'desc' } },
    )

    expect(keyOf(moved)).not.toBe(keyOf(loaded))
  })
})
