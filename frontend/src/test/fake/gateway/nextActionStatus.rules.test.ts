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
  comment: '',
  ...over,
})
const PROGRESS_ONLY = { nextAction: '', dueDate: '' } as const

describe('actions.changeNextActionStatus: 상태 전이와 종료 Comment', () => {
  // Fake는 종료 Comment를 그 Action의 새 Comment로 남기고(작성자 요청자), 공백뿐인 Comment는 만들지 않으며, Open으로 되돌리면 종료일이 없어지고 Comment는 남는다.
  // 테스트 코드: NA-068, CM-082
  it('creates the closing comment as a new action comment, creates none for a blank one and clears the closed time on reopen', async () => {
    // given: Open Action 둘이 있다.
    const { gateway, clock } = await mockAs('kim')
    const withNote = await gateway.actions.create(dealCode(2), input())
    const blank = await gateway.actions.create(dealCode(2), input())
    // when: 하나는 Comment " 전달 완료 "로 종료(수행)하고 다른 하나는 공백 Comment로 종료(미수행)한다.
    const closed = await gateway.actions.changeNextActionStatus(withNote.id, { status: 'done', comment: ' 전달 완료 ' })
    const blankClosed = await gateway.actions.changeNextActionStatus(blank.id, { status: 'notDone', comment: '   ' })
    // then: 종료일이 서버 업무 날짜(오늘)이고 앞 Action에만 trim한 Comment 1건(작성자 김영업)이 생긴다.
    expect(closed).toMatchObject({ nextActionStatus: 'done', nextActionClosedOn: clock.now().slice(0, 10) })
    expect(blankClosed).toMatchObject({ nextActionStatus: 'notDone' })
    expect((await gateway.comments.list(dealCode(2), { actionId: withNote.id })).map((c) => [c.body, c.author.name])).toEqual([['전달 완료', '김영업']])
    expect(await gateway.comments.list(dealCode(2), { actionId: blank.id })).toEqual([])
    // when: 종료(수행)한 Action을 Open으로 되돌린다.
    const reopened = await gateway.actions.changeNextActionStatus(withNote.id, { status: 'open', comment: '' })
    // then: 종료일이 없어지고 만든 Comment는 남는다.
    expect(reopened).toMatchObject({ nextActionStatus: 'open', nextActionClosedOn: null })
    expect(await gateway.comments.list(dealCode(2), { actionId: withNote.id })).toHaveLength(1)
  })

  // Fake는 종료(수행)에서 종료(미수행)으로 바로 바꾸고 종료일을 그 날의 업무 날짜로 새로 정한다.
  // 테스트 코드: NA-068
  it('switches between the closed statuses with a new closed date', async () => {
    // given: 어느 날 종료(수행)된 Action이 있다.
    const { gateway, clock } = await mockAs('kim')
    const created = await gateway.actions.create(dealCode(2), input())
    const first = await gateway.actions.changeNextActionStatus(created.id, { status: 'done', comment: '' })
    clock.advance(86_400_000)
    // when: 다음 날 not_done, Comment "취소됨"으로 바꾼다.
    const switched = await gateway.actions.changeNextActionStatus(created.id, { status: 'notDone', comment: '취소됨' })
    // then: 종료일이 다음 날로 바뀌고 "취소됨" Comment가 생긴다.
    expect(switched.nextActionClosedOn).not.toBe(first.nextActionClosedOn)
    expect(switched).toMatchObject({ nextActionStatus: 'notDone' })
    expect((await gateway.comments.list(dealCode(2), { actionId: created.id })).map((c) => c.body)).toEqual(['취소됨'])
  })

  // 같은 상태, Next Action 없음, Open+Comment는 서버와 같은 상태·문구로 거절하고 Action과 History를 바꾸지 않는다.
  // 테스트 코드: NA-068
  it('refuses the same status, a missing Next Action and a comment on reopen, changing nothing', async () => {
    // given: Open Action, 종료(수행) Action, 진행사항만 Action이 있다.
    const { gateway } = await mockAs('kim')
    const code = dealCode(2)
    const open = await gateway.actions.create(code, input())
    const closed = await gateway.actions.create(code, input())
    await gateway.actions.changeNextActionStatus(closed.id, { status: 'done', comment: '' })
    const plain = await gateway.actions.create(code, input(PROGRESS_ONLY))
    const base = (await gateway.history.list(code, {})).length
    // when·then: 같은 상태는 409, Next Action 없음은 409, Open+Comment는 422다.
    await expectApiError(gateway.actions.changeNextActionStatus(open.id, { status: 'open', comment: '' }), 409, '이미 Open 상태입니다.')
    await expectApiError(gateway.actions.changeNextActionStatus(closed.id, { status: 'done', comment: '또' }), 409, '이미 종료(수행) 상태입니다.')
    await expectApiError(
      gateway.actions.changeNextActionStatus(plain.id, { status: 'done', comment: '메모' }),
      409,
      'Next Action이 없는 Action은 상태를 바꿀 수 없습니다.',
    )
    await expectApiError(
      gateway.actions.changeNextActionStatus(closed.id, { status: 'open', comment: '되돌리며' }),
      422,
      'Open으로 되돌릴 때는 Comment를 남길 수 없습니다.',
    )
    // then: History가 늘지 않았다.
    expect(await gateway.history.list(code, {})).toHaveLength(base)
  })

  // 종료 Comment에 NUL이 있으면 서버와 같은 문구의 422이고 Action과 History가 그대로이며 같은 상태 409보다 먼저 판정한다.
  // 테스트 코드: NA-068, NA-009
  it('rejects a closing comment with NUL as a validation error before the state checks', async () => {
    // given: Open Action이 있다.
    const { gateway } = await mockAs('kim')
    const code = dealCode(2)
    const created = await gateway.actions.create(code, input())
    const base = (await gateway.history.list(code, {})).length
    // when·then: Comment "가\0나"로 종료하면 422 NUL 문구다.
    const error = await expectApiError(
      gateway.actions.changeNextActionStatus(created.id, { status: 'done', comment: '가\u0000나' }),
      422,
      'Comment에는 NUL 문자를 쓸 수 없습니다',
    )
    expect(error.kind).toBe('validation')
    // when·then: 같은 상태(open)에 NUL Comment를 보내도 409가 아니라 NUL 422다.
    await expectApiError(
      gateway.actions.changeNextActionStatus(created.id, { status: 'open', comment: '\u0000' }),
      422,
      'Comment에는 NUL 문자를 쓸 수 없습니다',
    )
    // then: Action과 History가 그대로다.
    expect((await gateway.actions.list(code, {})).find((a) => a.id === created.id)).toMatchObject({ nextActionStatus: 'open' })
    expect(await gateway.comments.list(code)).toEqual([])
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
      mock.gateway.actions.changeNextActionStatus(created.id, { status: 'done', comment: '' }),
      403,
      '본인 Action 또는 admin만 Next Action 상태를 바꿀 수 있습니다.',
    )
    // when·then: user 역할은 403이다.
    await mock.signInAs(USER_ID.han)
    await expectApiError(mock.gateway.actions.changeNextActionStatus(created.id, { status: 'done', comment: '' }), 403)
    // when: admin이 종료(미수행)으로 바꾼다.
    await mock.signInAs(USER_ID.root)
    const changed = await mock.gateway.actions.changeNextActionStatus(created.id, { status: 'notDone', comment: '' })
    // then: 바뀐다.
    expect(changed.nextActionStatus).toBe('notDone')
  })

  // 없는 Action은 404다.
  // 테스트 코드: NA-068
  it('answers 404 for an unknown action', async () => {
    // given: 김영업으로 로그인했다.
    const { gateway } = await mockAs('kim')
    // when·then: 없는 id로 바꾸면 404 "Action을 찾을 수 없습니다."다.
    await expectApiError(gateway.actions.changeNextActionStatus(NO_SUCH_ID, { status: 'done', comment: '' }), 404, 'Action을 찾을 수 없습니다.')
  })

  // 성공한 변경마다 History에 "Next Action" 1건이 정해진 문구로 남는다.
  // 테스트 코드: NA-068
  it('writes one Next Action history entry per successful change', async () => {
    // given: Next Action "견적 재전달"(Due 2026-12-01)인 Open Action이 있다.
    const { gateway } = await mockAs('kim')
    const code = dealCode(2)
    const created = await gateway.actions.create(code, input())
    const base = (await gateway.history.list(code, {})).length
    // when: 종료(수행)+Comment "전달 완료"로 바꾼다.
    await gateway.actions.changeNextActionStatus(created.id, { status: 'done', comment: '전달 완료' })
    // then: Next Action 줄(변경 후는 라벨만) 다음에 Comment 등록 줄이 남아 History가 2건 늘었다.
    const history = await gateway.history.list(code, {})
    expect(history).toHaveLength(base + 2)
    expect(history[1]).toMatchObject({
      category: 'action',
      target: 'Next Action',
      before: '견적 재전달 (Due 2026-12-01) · Open',
      after: '종료(수행)',
    })
    expect(history[0]).toMatchObject({ category: 'comment', before: '', after: '등록: 전달 완료' })
  })
})
