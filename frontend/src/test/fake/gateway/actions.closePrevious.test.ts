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
  // 기준 행은 새 Action 시각으로 종료(수행)가 되고 Memo는 그대로다.
  // 테스트 코드: AC-090
  it('closes the basis row as done at the new actions time and keeps its memo', async () => {
    // given: sales(kim)와 Open Next Action 기준 행
    const { gateway } = await mockAs('kim')
    const code = dealCode(2)
    const previous = await gateway.actions.create(code, input())

    // when: 그 id를 닫도록 지정해 등록한다
    const created = await gateway.actions.create(code, input({ closePreviousNextActionId: previous.id }))

    // then: 기준 행은 done이고 종료일이 새 Action의 수행일이며 Memo는 그대로다
    expect(await find(gateway, code, previous.id)).toMatchObject({
      nextActionStatus: 'done',
      nextActionClosedOn: created.actedOn,
      memo: '기존 메모',
    })
  })

  // 종료 줄이 먼저, 등록 줄이 그 다음에 남는다.
  // 테스트 코드: AC-090
  it('writes the status line first and the registration line after it', async () => {
    // given: sales(kim)와 기준 행·등록 전 History 건수
    const { gateway } = await mockAs('kim')
    const code = dealCode(2)
    const previous = await gateway.actions.create(code, input())
    const base = (await gateway.history.list(code, {})).length

    // when: 기준 행을 닫으며 등록한다
    await gateway.actions.create(code, input({ closePreviousNextActionId: previous.id }))

    // then: History가 2건 늘고 맨 위는 Action 등록 줄이다
    const history = await gateway.history.list(code, {})
    expect(history).toHaveLength(base + 2)
    expect(history[0]).toMatchObject({ category: 'action', target: 'Action' })
    // then: 그 아래는 Next Action 종료(수행) 줄이다
    expect(history[1]).toMatchObject({
      category: 'action',
      target: 'Next Action',
      before: '견적 재전달 (Due 2026-10-22) · Open',
      after: '종료(수행)',
    })
  })

  // 닫을 id가 없으면 이전 행은 Open 그대로다.
  // 테스트 코드: AC-090
  it('leaves the previous row open when the field is absent', async () => {
    // given: sales(kim)와 기준 행
    const { gateway } = await mockAs('kim')
    const code = dealCode(2)
    const previous = await gateway.actions.create(code, input())

    // when: 닫을 id 없이 등록한다
    await gateway.actions.create(code, input())

    // then: 이전 행은 Open 그대로다
    expect(await find(gateway, code, previous.id)).toMatchObject({ nextActionStatus: 'open', nextActionClosedOn: null })
  })

  // 기준 행이 아닌 id는 409이고 아무것도 저장되지 않는다.
  // 테스트 코드: AC-090
  it('is a 409 and saves nothing when the id is not the basis row', async () => {
    // given: 기준 행 뒤에 더 최근 Next Action 행이 생겼다
    const { gateway } = await mockAs('kim')
    const code = dealCode(2)
    const stale = await gateway.actions.create(code, input())
    await gateway.actions.create(code, input({ progress: '그 사이 추가' }))
    const count = (await gateway.actions.list(code, {})).length
    const history = (await gateway.history.list(code, {})).length

    // when·then: 옛 행 id로 닫으며 등록하면 409다
    await expectApiError(gateway.actions.create(code, input({ closePreviousNextActionId: stale.id })), 409, CHANGED)

    // then: Action·History가 늘지 않고 옛 행은 Open이다
    expect(await gateway.actions.list(code, {})).toHaveLength(count)
    expect(await gateway.history.list(code, {})).toHaveLength(history)
    expect(await find(gateway, code, stale.id)).toMatchObject({ nextActionStatus: 'open' })
  })

  // 다른 Deal의 Action id와 없는 id는 409다.
  // 테스트 코드: AC-090
  it('is a 409 for an action of another deal and for an unknown id', async () => {
    // given: 이 Deal의 Next Action 행과 다른 Deal의 Action
    const { gateway } = await mockAs('kim')
    const code = dealCode(2)
    await gateway.actions.create(code, input())
    const foreign = await gateway.actions.create(dealCode(1), input())

    // when·then: 다른 Deal의 id로 닫으며 등록하면 409다
    await expectApiError(gateway.actions.create(code, input({ closePreviousNextActionId: foreign.id })), 409, CHANGED)
    // when·then: 없는 id로 닫으며 등록해도 409다
    await expectApiError(gateway.actions.create(code, input({ closePreviousNextActionId: Number.MAX_SAFE_INTEGER })), 409, CHANGED)
  })

  // 이미 종료된 기준 행은 건너뛰고 새 Action만 저장한다.
  // 테스트 코드: AC-090
  it('skips an already closed basis row and saves only the new action', async () => {
    // given: 미수행으로 닫은 기준 행과 History 건수
    const { gateway } = await mockAs('kim')
    const code = dealCode(2)
    const previous = await gateway.actions.create(code, input())
    const closed = await gateway.actions.changeNextActionStatus(previous.id, { status: 'notDone', memo: '' })
    const history = (await gateway.history.list(code, {})).length

    // when: 그 id로 닫으며 등록한다
    await gateway.actions.create(code, input({ closePreviousNextActionId: previous.id }))

    // then: 이전 행의 상태·종료일이 그대로다
    expect(await find(gateway, code, previous.id)).toMatchObject({
      nextActionStatus: 'notDone',
      nextActionClosedOn: closed.nextActionClosedOn,
    })
    // then: History는 등록 줄 하나만 늘었다
    expect(await gateway.history.list(code, {})).toHaveLength(history + 1)
  })

  // 남의 기준 행은 sales에게 403이고 admin은 닫을 수 있다.
  // 테스트 코드: AC-090
  it('is a 403 for another sales users row and saves nothing, but admin may close it', async () => {
    // given: kim의 기준 행과 Action 건수
    const kim = await mockAs('kim')
    const code = dealCode(2)
    const previous = await kim.gateway.actions.create(code, input())
    const count = (await kim.gateway.actions.list(code, {})).length

    // given: 다른 sales(park)로 로그인한다
    await kim.signInAs(3) // park (sales)
    // when·then: 닫으며 등록하면 상태 변경 권한 403이다
    await expectApiError(kim.gateway.actions.create(code, input({ closePreviousNextActionId: previous.id })), 403, STATUS_FORBIDDEN)
    // then: 저장된 것이 없고 기준 행은 Open이다
    expect(await kim.gateway.actions.list(code, {})).toHaveLength(count)
    expect(await find(kim.gateway, code, previous.id)).toMatchObject({ nextActionStatus: 'open' })

    // given: admin(root)으로 로그인한다
    await kim.signInAs(1) // root (admin)
    // when: 닫으며 등록한다
    await kim.gateway.actions.create(code, input({ closePreviousNextActionId: previous.id }))
    // then: 기준 행은 done이다
    expect(await find(kim.gateway, code, previous.id)).toMatchObject({ nextActionStatus: 'done' })
  })

  // 새 내용이 틀리면 이전 행은 Open 그대로다.
  // 테스트 코드: AC-090
  it('keeps the previous row open when the new content is invalid', async () => {
    // given: sales(kim)와 기준 행
    const { gateway } = await mockAs('kim')
    const code = dealCode(2)
    const previous = await gateway.actions.create(code, input())

    // when·then: 내용이 빈 등록에 닫기를 지정하면 422다
    await expectApiError(
      gateway.actions.create(code, input({ progress: '', nextAction: '', dueDate: '', closePreviousNextActionId: previous.id })),
      422,
      '진행사항 또는 Next Action을 입력하세요.',
    )

    // then: 이전 행은 Open 그대로다
    expect(await find(gateway, code, previous.id)).toMatchObject({ nextActionStatus: 'open' })
  })

  // 수행 시각이 같으면 id가 큰 행이 기준 행이다.
  // 테스트 코드: AC-090
  it('breaks ties of the same acted time by the higher id like the server', async () => {
    // given: 같은 시각에 등록한 두 Next Action 행
    const { gateway } = await mockAs('kim')
    const code = dealCode(2)
    const first = await gateway.actions.create(code, input({ progress: '첫째' }))
    const second = await gateway.actions.create(code, input({ progress: '둘째' })) // 같은 Fake 시각, 더 큰 id

    // when·then: 먼저 등록한 행 id로 닫으면 409다
    await expectApiError(gateway.actions.create(code, input({ closePreviousNextActionId: first.id })), 409, CHANGED)
    // when: 나중 행 id로 닫으며 등록한다
    await gateway.actions.create(code, input({ closePreviousNextActionId: second.id }))
    // then: 나중 행이 done이다
    expect(await find(gateway, code, second.id)).toMatchObject({ nextActionStatus: 'done' })
  })
})
