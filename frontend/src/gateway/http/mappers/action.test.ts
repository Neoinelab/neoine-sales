import { describe, expect, it } from 'vitest'
import type { ActionInput } from '../../../shared/model/types'
import { ACTION_TYPE_ID, serverAction } from '../../../test/fixtures/serverAction'
import { serverUserRef } from '../../../test/fixtures/serverDeal'
import { toActionCreateBody, toActionUpdateBody, toDealAction } from './action'

const input = (over: Partial<ActionInput> = {}): ActionInput => ({
  type: { id: ACTION_TYPE_ID },
  progress: '고객사 방문',
  nextAction: '견적 재전달',
  dueDate: '2026-10-22',
  memo: '',
  ...over,
})

describe('action type mapping (AC-7·14)', () => {
  it('has no enum mapping any more (the type is a catalog item, not a closed set)', async () => {
    const module = await import('./action')

    expect(module).not.toHaveProperty('toApiActionType')
    expect(module).not.toHaveProperty('fromApiActionType')
  })

  it('maps the {id, name} reference to type (current name) and typeId', () => {
    const mapped = toDealAction(serverAction({ action_type: { id: 'ty-9', name: '웨비나' } }))

    expect(mapped.type).toBe('웨비나')
    expect(mapped.typeId).toBe('ty-9')
  })

  it('sends the id object for a listed type and the name object for a new one', () => {
    expect(toActionCreateBody(input({ type: { id: 'ty-1' } })).action_type).toEqual({ id: 'ty-1' })
    expect(toActionUpdateBody({ ...input(), type: { name: '웨비나' } }).action_type).toEqual({ name: '웨비나' })
  })
})

describe('toDealAction', () => {
  it('maps the server action to the screen action (action becomes progress)', () => {
    const mapped = toDealAction(
      serverAction({
        action_type: { id: 'ty-neg', name: '협상' },
        action: '최종 가격 협의',
        next_action: '계약서 초안 검토',
        due_date: '2026-10-18',
        memo: '메모',
        status_key: 'price_negotiation',
        forecast_key: 'commit',
      }),
    )

    expect(mapped).toEqual({
      id: expect.any(String),
      dealCode: '20261016-AB12',
      actedAt: '2026-10-15T09:00:00+09:00',
      actor: { id: 'u-kim', name: '김영업', role: 'sales', status: 'active' },
      type: '협상',
      typeId: 'ty-neg',
      progress: '최종 가격 협의',
      nextAction: '계약서 초안 검토',
      dueDate: '2026-10-18',
      nextActionStatus: 'open',
      nextActionClosedAt: null,
      memo: '메모',
      statusKey: 'price_negotiation',
      forecastKey: 'commit',
    })
  })

  it('keeps the actor role and marks a resigned actor', () => {
    const mapped = toDealAction(serverAction({ actor: serverUserRef({ id: 'u-old', resigned: true, role: 'sales' }) }))

    expect(mapped.actor).toMatchObject({ id: 'u-old', role: 'sales', status: 'resigned' })
  })

  it('does not trim or cut a long text', () => {
    const long = '가'.repeat(5000)

    const mapped = toDealAction(serverAction({ action: long, next_action: long, memo: '나'.repeat(20000) }))

    expect(mapped.progress).toBe(long)
    expect(mapped.nextAction).toBe(long)
    expect(mapped.memo).toHaveLength(20000)
  })
})

describe('toActionCreateBody', () => {
  it('uses snake_case keys and has no acted_at or actor field', () => {
    const body = toActionCreateBody(input({ type: { name: '통화' }, memo: '메모' }))

    expect(body).toEqual({
      action_type: { name: '통화' },
      action: '고객사 방문',
      next_action: '견적 재전달',
      due_date: '2026-10-22',
      memo: '메모',
    })
  })

  it('sends an empty due date as null so the server answers with its own message', () => {
    expect(toActionCreateBody(input({ dueDate: '' })).due_date).toBeNull()
  })

  it('does not trim or cut the texts', () => {
    const body = toActionCreateBody(input({ progress: `  ${'가'.repeat(5000)}  `, memo: '나'.repeat(20000) }))

    expect(body.action).toBe(`  ${'가'.repeat(5000)}  `)
    expect(body.memo).toHaveLength(20000)
  })

  it('maps a status change with its resolution to status_changes', () => {
    const body = toActionCreateBody(
      input({
        statusChanges: [{
          change: { field: 'statusKey', value: 'contract_completed' },
          resolution: { revenueAmount: 1_800_000_000, revenueDate: '2026-10-15' },
        }],
      }),
    )

    expect(body.status_changes).toEqual([
      {
        change: { field: 'status_key', value: 'contract_completed' },
        resolution: { revenue_amount: 1_800_000_000, revenue_date: '2026-10-15' },
      },
    ])
    expect(body).not.toHaveProperty('status_change')
  })

  it('maps a forecast change and a reopen choice (status_key / forecast_key resolution)', () => {
    const body = toActionCreateBody(
      input({
        statusChanges: [{
          change: { field: 'forecastKey', value: 'pipeline' },
          resolution: { statusKey: 'price_negotiation' },
        }],
      }),
    )

    expect(body.status_changes).toEqual([
      {
        change: { field: 'forecast_key', value: 'pipeline' },
        resolution: { status_key: 'price_negotiation' },
      },
    ])
  })

  it('omits status_changes and resolution when there is none', () => {
    const plain = toActionCreateBody(input())
    const empty = toActionCreateBody(input({ statusChanges: [] }))
    const noResolution = toActionCreateBody(input({ statusChanges: [{ change: { field: 'statusKey', value: 'qualified' } }] }))

    expect(plain).not.toHaveProperty('status_changes')
    expect(plain).not.toHaveProperty('status_change')
    expect(empty).not.toHaveProperty('status_changes')
    expect(noResolution.status_changes).toEqual([{ change: { field: 'status_key', value: 'qualified' } }])
  })

  it('sends two changes in the order the user made them, each with its own resolution', () => {
    const body = toActionCreateBody(
      input({
        statusChanges: [
          { change: { field: 'forecastKey', value: 'commit' }, resolution: { statusKey: 'poc_completed' } },
          { change: { field: 'statusKey', value: 'contract_completed' }, resolution: { revenueAmount: 5_000_000, revenueDate: '2026-10-20' } },
        ],
      }),
    )

    expect(body.status_changes).toEqual([
      { change: { field: 'forecast_key', value: 'commit' }, resolution: { status_key: 'poc_completed' } },
      {
        change: { field: 'status_key', value: 'contract_completed' },
        resolution: { revenue_amount: 5_000_000, revenue_date: '2026-10-20' },
      },
    ])
    expect(body).not.toHaveProperty('status_change')
  })
})

describe('toActionUpdateBody', () => {
  it('has the content fields only', () => {
    const body = toActionUpdateBody({ type: { id: 'ty-other' }, progress: '수정', nextAction: '다음', dueDate: '2026-11-01', memo: '' })

    expect(body).toEqual({ action_type: { id: 'ty-other' }, action: '수정', next_action: '다음', due_date: '2026-11-01', memo: '' })
  })

  it('sends an empty due date as null', () => {
    const body = toActionUpdateBody({ type: { id: 'ty-other' }, progress: 'x', nextAction: 'y', dueDate: '', memo: '' })

    expect(body.due_date).toBeNull()
  })
})

describe('toDealAction nullable plan fields and Next Action status (AC-1·2·7·8)', () => {
  it('keeps null progress, Next Action, due date, status and closed time as null', () => {
    const mapped = toDealAction(
      serverAction({ action: null, next_action: null, due_date: null, next_action_status: null, next_action_closed_at: null }),
    )

    expect(mapped).toMatchObject({ progress: null, nextAction: null, dueDate: null, nextActionStatus: null, nextActionClosedAt: null })
  })

  it.each([
    ['open', 'open'],
    ['done', 'done'],
    ['not_done', 'notDone'],
  ] as const)('maps the server status %s to %s', (wire, status) => {
    const closed = wire === 'open' ? null : '2026-10-16T10:00:00+09:00'

    const mapped = toDealAction(serverAction({ next_action_status: wire, next_action_closed_at: closed }))

    expect(mapped.nextActionStatus).toBe(status)
    expect(mapped.nextActionClosedAt).toBe(closed)
  })
})

describe('request bodies of a partial input (AC-1·2)', () => {
  it('sends a progress-only content with an empty Next Action and a null due date', () => {
    const body = toActionCreateBody(input({ nextAction: '', dueDate: '' }))

    expect(body).toMatchObject({ action: '고객사 방문', next_action: '', due_date: null })
  })

  it('sends a Next-Action-only content with an empty progress', () => {
    const body = toActionUpdateBody({ type: { id: 'ty-1' }, progress: '', nextAction: '견적', dueDate: '2026-11-01', memo: '' })

    expect(body).toMatchObject({ action: '', next_action: '견적', due_date: '2026-11-01' })
  })
})
