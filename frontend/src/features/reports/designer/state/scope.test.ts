import { describe, expect, it } from 'vitest'
import type { DesignerAction, DesignerState } from './designerState'
import { emptyDesign, fieldOf, reduce, REPORT_CATALOG, uidAt, withColumns } from '../../../../test/reportDesigner'
import { describeScope, predictScope } from './scope'

/** 필드들을 컬럼으로 넣고, 지정한 인덱스를 그룹으로 만든 설계. */
function design(keys: string[], groupIndexes: number[] = [], extra: DesignerAction[] = []): DesignerState {
  const state = withColumns(...keys)
  return reduce(
    state,
    ...groupIndexes.map((i): DesignerAction => ({ type: 'updateColumn', uid: uidAt(state, i), patch: { group: true } })),
    ...extra,
  )
}

const actionCondition: DesignerAction = { type: 'addCondition', field: fieldOf('action.action') }

describe('predictScope (AC9)', () => {
  const cases: [string, DesignerState, { rowScope: string; actionFilter: string; dealNumbersOnce: boolean }][] = [
    ['Deal columns only', design(['deal.code']), { rowScope: 'deal', actionFilter: 'none', dealNumbersOnce: false }],
    ['an Action condition only', design(['deal.code'], [], [actionCondition]), { rowScope: 'deal', actionFilter: 'exists', dealNumbersOnce: false }],
    ['a Deal condition only', design(['deal.code'], [], [{ type: 'addCondition', field: fieldOf('deal.name') }]), { rowScope: 'deal', actionFilter: 'none', dealNumbersOnce: false }],
    ['an Action column', design(['deal.code', 'action.action']), { rowScope: 'action', actionFilter: 'join', dealNumbersOnce: false }],
    ['an Action column and an Action condition', design(['action.action'], [], [actionCondition]), { rowScope: 'action', actionFilter: 'join', dealNumbersOnce: false }],
    ['the Action count column', design(['deal.vendor', 'action.count'], [0]), { rowScope: 'action', actionFilter: 'join', dealNumbersOnce: false }],
    ['Deal numbers summed in Action rows with a group', design(['action.type', 'deal.amount'], [0]), { rowScope: 'action', actionFilter: 'join', dealNumbersOnce: true }],
    ['Deal numbers averaged in Action rows with a group', design(['action.type', 'deal.status_days'], [0]), { rowScope: 'action', actionFilter: 'join', dealNumbersOnce: true }],
    ['Deal numbers without a group in Action rows', design(['action.action', 'deal.amount']), { rowScope: 'action', actionFilter: 'join', dealNumbersOnce: false }],
    ['a Deal number summed in Deal rows with a group', design(['deal.vendor', 'deal.amount'], [0]), { rowScope: 'deal', actionFilter: 'none', dealNumbersOnce: false }],
    ['a non Deal number counted in Action rows with a group', design(['action.type', 'deal.name'], [0]), { rowScope: 'action', actionFilter: 'join', dealNumbersOnce: false }],
  ]

  it.each(cases)('predicts row scope action filter and deal numbers once like the server: %s', (_name, state, expected) => {
    expect(predictScope(state, REPORT_CATALOG)).toEqual(expected)
  })

  it('does not count a minimum or maximum as once-only', () => {
    const base = design(['action.type', 'deal.amount'], [0])
    const withMin = reduce(base, { type: 'updateColumn', uid: uidAt(base, 1), patch: { aggregate: 'min' } })
    const withMax = reduce(base, { type: 'updateColumn', uid: uidAt(base, 1), patch: { aggregate: 'max' } })

    expect(predictScope(withMin, REPORT_CATALOG).dealNumbersOnce).toBe(false)
    expect(predictScope(withMax, REPORT_CATALOG).dealNumbersOnce).toBe(false)
  })

  it('treats an empty design as Deal rows', () => {
    expect(predictScope(emptyDesign(), REPORT_CATALOG)).toEqual({ rowScope: 'deal', actionFilter: 'none', dealNumbersOnce: false })
  })
})

describe('describeScope (AC9)', () => {
  it('names the Deal row scope', () => {
    expect(describeScope({ rowScope: 'deal', actionFilter: 'none', dealNumbersOnce: false }, 'and')).toEqual({
      headline: '행 단위: Deal 1건',
      notes: [],
    })
  })

  it('names the Action row scope with its join', () => {
    expect(describeScope({ rowScope: 'action', actionFilter: 'join', dealNumbersOnce: false }, 'and')).toEqual({
      headline: '행 단위: Action 1건 · Deal과 Join(Action이 없는 Deal은 빠짐)',
      notes: [],
    })
  })

  it('scope messages for and or exists', () => {
    const exists = { rowScope: 'deal', actionFilter: 'exists', dealNumbersOnce: false } as const

    const and = describeScope(exists, 'and')
    const or = describeScope(exists, 'or')

    expect(and.headline).toBe('행 단위: Deal 1건 · 조건에 맞는 Action이 있는 Deal만')
    expect(or.headline).toBe('행 단위: Deal 1건 · 조건에 맞는 Action이 있는 Deal만')
    expect(and.notes).toEqual(['(같은 Action 하나가 모든 Action 조건을 만족)'])
    expect(or.notes).toEqual(['(Action 조건 중 하나를 만족하는 Action이 있는 Deal)'])
  })

  it('adds the once-per-Deal note for Deal numbers', () => {
    const scope = describeScope({ rowScope: 'action', actionFilter: 'join', dealNumbersOnce: true }, 'and')

    expect(scope.notes).toEqual(['Deal 숫자(금액 등)는 Deal마다 한 번만 더합니다'])
  })
})
