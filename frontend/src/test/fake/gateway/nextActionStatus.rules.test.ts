import { describe, expect, it } from 'vitest'
import type { ActionInput } from '../../../shared/model/types'
import { NO_SUCH_ID, USER_ID } from '../seed/ids'
import { dealCode, expectApiError, mockAs } from '../testing'

/** Fake 게이트웨이의 Next Action 상태 변경이 서버(NA-R2~R9)와 같은 결과를 내는지 본다. */
const input = (over: Partial<ActionInput> = {}): ActionInput => ({
  type: { name: '미팅' },
  progress: '고객사 방문',
  nextAction: '견적 재전달',
  dueDate: '2026-12-01',
  memo: '기존',
  ...over,
})
const PROGRESS_ONLY = { nextAction: '', dueDate: '' } as const

describe('actions.changeNextActionStatus: 상태 전이와 메모', () => {
  // Fake는 종료하면 메모를 Memo 뒤에 붙이고, 공백뿐인 메모는 Memo를 바꾸지 않으며, Open으로 되돌리면 종료일이 없어진다.
  // 테스트 코드: NA-068
  it('appends the closing memo, keeps the memo for a blank note and clears the closed time on reopen', async () => {
    // given: Memo "기존"인 Open Action 둘이 있다.
    const { gateway, clock } = await mockAs('kim')
    const withNote = await gateway.actions.create(dealCode(2), input())
    const blank = await gateway.actions.create(dealCode(2), input())
    // when: 하나는 메모 "전달 완료"로 종료(수행)하고 다른 하나는 공백 메모로 종료(미수행)한다.
    const closed = await gateway.actions.changeNextActionStatus(withNote.id, { status: 'done', memo: ' 전달 완료 ' })
    const keptMemo = await gateway.actions.changeNextActionStatus(blank.id, { status: 'notDone', memo: '   ' })
    // then: 앞의 Memo는 "기존\n전달 완료"이고 종료일이 서버 업무 날짜(오늘)이며 뒤의 Memo는 그대로다.
    expect(closed).toMatchObject({ nextActionStatus: 'done', memo: '기존\n전달 완료', nextActionClosedOn: clock.now().slice(0, 10) })
    expect(keptMemo).toMatchObject({ nextActionStatus: 'notDone', memo: '기존' })
    // when: 종료(수행)한 Action을 Open으로 되돌린다.
    const reopened = await gateway.actions.changeNextActionStatus(withNote.id, { status: 'open', memo: '' })
    // then: 종료일이 없어지고 덧붙인 Memo는 남는다.
    expect(reopened).toMatchObject({ nextActionStatus: 'open', nextActionClosedOn: null, memo: '기존\n전달 완료' })
  })

  // Fake는 종료(수행)에서 종료(미수행)으로 바로 바꾸고 종료일을 그 날의 업무 날짜로 새로 정한다.
  // 테스트 코드: NA-068
  it('switches between the closed statuses with a new closed date', async () => {
    // given: 어느 날 종료(수행)된 Action이 있다.
    const { gateway, clock } = await mockAs('kim')
    const created = await gateway.actions.create(dealCode(2), input())
    const first = await gateway.actions.changeNextActionStatus(created.id, { status: 'done', memo: '' })
    clock.advance(86_400_000)
    // when: 다음 날 not_done, 메모 "취소됨"으로 바꾼다.
    const switched = await gateway.actions.changeNextActionStatus(created.id, { status: 'notDone', memo: '취소됨' })
    // then: 종료일이 다음 날로 바뀌고 Memo 끝에 "취소됨"이 붙는다.
    expect(switched.nextActionClosedOn).not.toBe(first.nextActionClosedOn)
    expect(switched).toMatchObject({ nextActionStatus: 'notDone', memo: '기존\n취소됨' })
  })

  // 같은 상태, Next Action 없음, Open+메모는 서버와 같은 상태·문구로 거절하고 Action과 History를 바꾸지 않는다.
  // 테스트 코드: NA-068
  it('refuses the same status, a missing Next Action and a memo on reopen, changing nothing', async () => {
    // given: Open Action, 종료(수행) Action, 진행사항만 Action이 있다.
    const { gateway } = await mockAs('kim')
    const code = dealCode(2)
    const open = await gateway.actions.create(code, input())
    const closed = await gateway.actions.create(code, input())
    await gateway.actions.changeNextActionStatus(closed.id, { status: 'done', memo: '' })
    const plain = await gateway.actions.create(code, input(PROGRESS_ONLY))
    const base = (await gateway.history.list(code, {})).length
    // when·then: 같은 상태는 409, Next Action 없음은 409, Open+메모는 422다.
    await expectApiError(gateway.actions.changeNextActionStatus(open.id, { status: 'open', memo: '' }), 409, '이미 Open 상태입니다.')
    await expectApiError(gateway.actions.changeNextActionStatus(closed.id, { status: 'done', memo: '또' }), 409, '이미 종료(수행) 상태입니다.')
    await expectApiError(
      gateway.actions.changeNextActionStatus(plain.id, { status: 'done', memo: '메모' }),
      409,
      'Next Action이 없는 Action은 상태를 바꿀 수 없습니다.',
    )
    await expectApiError(
      gateway.actions.changeNextActionStatus(closed.id, { status: 'open', memo: '되돌리며' }),
      422,
      'Open으로 되돌릴 때는 메모를 남길 수 없습니다.',
    )
    // then: History가 늘지 않았다.
    expect(await gateway.history.list(code, {})).toHaveLength(base)
  })

  // 종료 메모에 NUL이 있으면 서버와 같은 문구의 422이고 Action과 History가 그대로이며 같은 상태 409보다 먼저 판정한다.
  // 테스트 코드: NA-068, NA-009
  it('rejects a closing memo with NUL as a validation error before the state checks', async () => {
    // given: Open Action이 있다.
    const { gateway } = await mockAs('kim')
    const code = dealCode(2)
    const created = await gateway.actions.create(code, input())
    const base = (await gateway.history.list(code, {})).length
    // when·then: 메모 "가\0나"로 종료하면 422 NUL 문구다.
    const error = await expectApiError(
      gateway.actions.changeNextActionStatus(created.id, { status: 'done', memo: '가\u0000나' }),
      422,
      '메모에는 NUL 문자를 쓸 수 없습니다',
    )
    expect(error.kind).toBe('validation')
    // when·then: 같은 상태(open)에 NUL 메모를 보내도 409가 아니라 NUL 422다.
    await expectApiError(
      gateway.actions.changeNextActionStatus(created.id, { status: 'open', memo: '\u0000' }),
      422,
      '메모에는 NUL 문자를 쓸 수 없습니다',
    )
    // then: Action과 History가 그대로다.
    expect((await gateway.actions.list(code, {})).find((a) => a.id === created.id)).toMatchObject({
      nextActionStatus: 'open',
      memo: '기존',
    })
    expect(await gateway.history.list(code, {})).toHaveLength(base)
  })
})

describe('actions.changeNextActionStatus: 권한과 판정 순서', () => {
  // user는 403, 작성자가 아닌 sales는 403 고정 문구, admin은 남의 Action도 바꿀 수 있다.
  // 테스트 코드: NA-068
  it('refuses the user role and another sales, and lets admin change the action of a sales', async () => {
    // given: 김영업의 Open Action이 있다.
    const mock = await mockAs('kim')
    const created = await mock.gateway.actions.create(dealCode(2), input())
    // when·then: 박영업(다른 sales)은 고정 문구의 403이다.
    await mock.signInAs(USER_ID.park)
    await expectApiError(
      mock.gateway.actions.changeNextActionStatus(created.id, { status: 'done', memo: '' }),
      403,
      '본인 Action 또는 admin만 Next Action 상태를 바꿀 수 있습니다.',
    )
    // when·then: user 역할은 403이다.
    await mock.signInAs(USER_ID.han)
    await expectApiError(mock.gateway.actions.changeNextActionStatus(created.id, { status: 'done', memo: '' }), 403)
    // when: admin이 종료(미수행)으로 바꾼다.
    await mock.signInAs(USER_ID.root)
    const changed = await mock.gateway.actions.changeNextActionStatus(created.id, { status: 'notDone', memo: '' })
    // then: 바뀐다.
    expect(changed.nextActionStatus).toBe('notDone')
  })

  // 없는 Action은 404다.
  // 테스트 코드: NA-068
  it('answers 404 for an unknown action', async () => {
    // given: 김영업으로 로그인했다.
    const { gateway } = await mockAs('kim')
    // when·then: 없는 id로 바꾸면 404 "Action을 찾을 수 없습니다."다.
    await expectApiError(gateway.actions.changeNextActionStatus(NO_SUCH_ID, { status: 'done', memo: '' }), 404, 'Action을 찾을 수 없습니다.')
  })

  // 성공한 변경마다 History에 "Next Action" 1건이 정해진 문구로 남는다.
  // 테스트 코드: NA-068
  it('writes one Next Action history entry per successful change', async () => {
    // given: Next Action "견적 재전달"(Due 2026-12-01)인 Open Action이 있다.
    const { gateway } = await mockAs('kim')
    const code = dealCode(2)
    const created = await gateway.actions.create(code, input())
    const base = (await gateway.history.list(code, {})).length
    // when: 종료(수행)+메모 "전달 완료"로 바꾼다.
    await gateway.actions.changeNextActionStatus(created.id, { status: 'done', memo: '전달 완료' })
    // then: 정해진 변경 전/후 문구의 History 1건이 늘었다.
    const history = await gateway.history.list(code, {})
    expect(history).toHaveLength(base + 1)
    expect(history[0]).toMatchObject({
      category: 'action',
      target: 'Next Action',
      before: '견적 재전달 (Due 2026-12-01) · Open',
      after: '종료(수행) / Memo: 전달 완료',
    })
  })
})
