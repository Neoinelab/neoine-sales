import { describe, expect, it } from 'vitest'
import { ACTION_TYPES } from '../../../shared/model/constants'
import type { ActionInput } from '../../../shared/model/types'
import { serverAction } from '../../../test/fixtures/serverAction'
import { serverUserRef } from '../../../test/fixtures/serverDeal'
import { fromApiActionType, toActionCreateBody, toActionUpdateBody, toApiActionType, toDealAction } from './action'

const PAIRS = [
  ['통화', 'call'],
  ['미팅', 'meeting'],
  ['이메일', 'email'],
  ['데모', 'demo'],
  ['제안', 'proposal'],
  ['협상', 'negotiation'],
  ['계약', 'contract'],
  ['기타', 'other'],
] as const

const input = (over: Partial<ActionInput> = {}): ActionInput => ({
  type: '미팅',
  progress: '고객사 방문',
  nextAction: '견적 재전달',
  dueDate: '2026-10-22',
  memo: '',
  ...over,
})

describe('action type mapping (R-13)', () => {
  it('covers every action type of the screen exactly once', () => {
    expect(PAIRS.map(([label]) => label)).toEqual([...ACTION_TYPES])
  })

  it.each(PAIRS)('maps %s to %s and back', (label, api) => {
    expect(toApiActionType(label)).toBe(api)
    expect(fromApiActionType(api)).toBe(label)
  })
})

describe('toDealAction', () => {
  it('maps the server action to the screen action (action becomes progress)', () => {
    const mapped = toDealAction(
      serverAction({
        action_type: 'negotiation',
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
      progress: '최종 가격 협의',
      nextAction: '계약서 초안 검토',
      dueDate: '2026-10-18',
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
    const body = toActionCreateBody(input({ type: '통화', memo: '메모' }))

    expect(body).toEqual({
      action_type: 'call',
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

  it('maps a status change with its resolution to status_change', () => {
    const body = toActionCreateBody(
      input({
        statusChange: {
          change: { field: 'statusKey', value: 'contract_completed' },
          resolution: { revenueAmount: 1_800_000_000, revenueDate: '2026-10-15' },
        },
      }),
    )

    expect(body.status_change).toEqual({
      change: { field: 'status_key', value: 'contract_completed' },
      resolution: { revenue_amount: 1_800_000_000, revenue_date: '2026-10-15' },
    })
  })

  it('maps a forecast change and a reopen choice (status_key / forecast_key resolution)', () => {
    const body = toActionCreateBody(
      input({
        statusChange: {
          change: { field: 'forecastKey', value: 'pipeline' },
          resolution: { statusKey: 'price_negotiation' },
        },
      }),
    )

    expect(body.status_change).toEqual({
      change: { field: 'forecast_key', value: 'pipeline' },
      resolution: { status_key: 'price_negotiation' },
    })
  })

  it('omits status_change and resolution when there is none', () => {
    const plain = toActionCreateBody(input())
    const noResolution = toActionCreateBody(input({ statusChange: { change: { field: 'statusKey', value: 'qualified' } } }))

    expect(plain).not.toHaveProperty('status_change')
    expect(noResolution.status_change).toEqual({ change: { field: 'status_key', value: 'qualified' } })
  })
})

describe('toActionUpdateBody', () => {
  it('has the content fields only', () => {
    const body = toActionUpdateBody({ type: '기타', progress: '수정', nextAction: '다음', dueDate: '2026-11-01', memo: '' })

    expect(body).toEqual({ action_type: 'other', action: '수정', next_action: '다음', due_date: '2026-11-01', memo: '' })
  })

  it('sends an empty due date as null', () => {
    const body = toActionUpdateBody({ type: '기타', progress: 'x', nextAction: 'y', dueDate: '', memo: '' })

    expect(body.due_date).toBeNull()
  })
})
