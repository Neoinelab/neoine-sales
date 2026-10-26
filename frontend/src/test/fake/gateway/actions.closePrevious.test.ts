import { describe, expect, it } from 'vitest'
import type { ActionInput } from '../../../shared/model/types'
import { dealCode, expectApiError, mockAs } from '../testing'

const CHANGED = '이전 Next Action이 바뀌었습니다. 창을 닫고 다시 열어 주세요.'
const STATUS_FORBIDDEN = '본인 Action 또는 admin만 Next Action 상태를 바꿀 수 있습니다.'

const input = (over: Partial<ActionInput> = {}): ActionInput => ({
  type: { name: '미팅' },
  progress: '고객사 방문',
  nextAction: '견적 재전달',
  dueDate: '2026-10-22',
  memo: '기존 메모',
  ...over,
})

type Mock = Awaited<ReturnType<typeof mockAs>>
const find = async (gw: Mock['gateway'], code: string, id: number) => (await gw.actions.list(code, {})).find((a) => a.id === id)

describe('actions.create with closePreviousNextActionId', () => {
  it('closes the basis row as done at the new actions time and keeps its memo', async () => {
    const { gateway } = await mockAs('kim')
    const code = dealCode(2)
    const previous = await gateway.actions.create(code, input())

    const created = await gateway.actions.create(code, input({ closePreviousNextActionId: previous.id }))

    expect(await find(gateway, code, previous.id)).toMatchObject({
      nextActionStatus: 'done',
      nextActionClosedAt: created.actedAt,
      memo: '기존 메모',
    })
  })

  it('writes the status line first and the registration line after it', async () => {
    const { gateway } = await mockAs('kim')
    const code = dealCode(2)
    const previous = await gateway.actions.create(code, input())
    const base = (await gateway.history.list(code, {})).length

    await gateway.actions.create(code, input({ closePreviousNextActionId: previous.id }))

    const history = await gateway.history.list(code, {})
    expect(history).toHaveLength(base + 2)
    expect(history[0]).toMatchObject({ category: 'action', target: 'Action' })
    expect(history[1]).toMatchObject({
      category: 'action',
      target: 'Next Action',
      before: '견적 재전달 (Due 2026-10-22) · Open',
      after: '종료(수행)',
    })
  })

  it('leaves the previous row open when the field is absent', async () => {
    const { gateway } = await mockAs('kim')
    const code = dealCode(2)
    const previous = await gateway.actions.create(code, input())

    await gateway.actions.create(code, input())

    expect(await find(gateway, code, previous.id)).toMatchObject({ nextActionStatus: 'open', nextActionClosedAt: null })
  })

  it('is a 409 and saves nothing when the id is not the basis row', async () => {
    const { gateway } = await mockAs('kim')
    const code = dealCode(2)
    const stale = await gateway.actions.create(code, input())
    await gateway.actions.create(code, input({ progress: '그 사이 추가' }))
    const count = (await gateway.actions.list(code, {})).length
    const history = (await gateway.history.list(code, {})).length

    await expectApiError(gateway.actions.create(code, input({ closePreviousNextActionId: stale.id })), 409, CHANGED)

    expect(await gateway.actions.list(code, {})).toHaveLength(count)
    expect(await gateway.history.list(code, {})).toHaveLength(history)
    expect(await find(gateway, code, stale.id)).toMatchObject({ nextActionStatus: 'open' })
  })

  it('is a 409 for an action of another deal and for an unknown id', async () => {
    const { gateway } = await mockAs('kim')
    const code = dealCode(2)
    await gateway.actions.create(code, input())
    const foreign = await gateway.actions.create(dealCode(1), input())

    await expectApiError(gateway.actions.create(code, input({ closePreviousNextActionId: foreign.id })), 409, CHANGED)
    await expectApiError(gateway.actions.create(code, input({ closePreviousNextActionId: Number.MAX_SAFE_INTEGER })), 409, CHANGED)
  })

  it('skips an already closed basis row and saves only the new action', async () => {
    const { gateway } = await mockAs('kim')
    const code = dealCode(2)
    const previous = await gateway.actions.create(code, input())
    const closed = await gateway.actions.changeNextActionStatus(previous.id, { status: 'notDone', memo: '' })
    const history = (await gateway.history.list(code, {})).length

    await gateway.actions.create(code, input({ closePreviousNextActionId: previous.id }))

    expect(await find(gateway, code, previous.id)).toMatchObject({
      nextActionStatus: 'notDone',
      nextActionClosedAt: closed.nextActionClosedAt,
    })
    expect(await gateway.history.list(code, {})).toHaveLength(history + 1)
  })

  it('is a 403 for another sales users row and saves nothing, but admin may close it', async () => {
    const kim = await mockAs('kim')
    const code = dealCode(2)
    const previous = await kim.gateway.actions.create(code, input())
    const count = (await kim.gateway.actions.list(code, {})).length

    await kim.gateway.auth.quickLogin(3) // park (sales)
    await expectApiError(kim.gateway.actions.create(code, input({ closePreviousNextActionId: previous.id })), 403, STATUS_FORBIDDEN)
    expect(await kim.gateway.actions.list(code, {})).toHaveLength(count)
    expect(await find(kim.gateway, code, previous.id)).toMatchObject({ nextActionStatus: 'open' })

    await kim.gateway.auth.quickLogin(1) // root (admin)
    await kim.gateway.actions.create(code, input({ closePreviousNextActionId: previous.id }))
    expect(await find(kim.gateway, code, previous.id)).toMatchObject({ nextActionStatus: 'done' })
  })

  it('keeps the previous row open when the new content is invalid', async () => {
    const { gateway } = await mockAs('kim')
    const code = dealCode(2)
    const previous = await gateway.actions.create(code, input())

    await expectApiError(
      gateway.actions.create(code, input({ progress: '', nextAction: '', dueDate: '', closePreviousNextActionId: previous.id })),
      422,
      '진행사항 또는 Next Action을 입력하세요.',
    )

    expect(await find(gateway, code, previous.id)).toMatchObject({ nextActionStatus: 'open' })
  })

  it('breaks ties of the same acted time by the higher id like the server', async () => {
    const { gateway } = await mockAs('kim')
    const code = dealCode(2)
    const first = await gateway.actions.create(code, input({ progress: '첫째' }))
    const second = await gateway.actions.create(code, input({ progress: '둘째' })) // 같은 Fake 시각, 더 큰 id

    await expectApiError(gateway.actions.create(code, input({ closePreviousNextActionId: first.id })), 409, CHANGED)
    await gateway.actions.create(code, input({ closePreviousNextActionId: second.id }))
    expect(await find(gateway, code, second.id)).toMatchObject({ nextActionStatus: 'done' })
  })
})
