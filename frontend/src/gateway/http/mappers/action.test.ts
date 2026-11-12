import { describe, expect, it } from 'vitest'
import type { ActionInput } from '../../../shared/model/types'
import { ACTION_TYPE_ID, serverAction } from '../../../test/fixtures/serverAction'
import { serverUserRef } from '../../../test/fixtures/serverDeal'
import { toActionCreateBody, toActionUpdateBody, toDealAction } from './action'
import { USER_ID } from '../../../test/fake/seed/ids'

const input = (over: Partial<ActionInput> = {}): ActionInput => ({
  type: { id: ACTION_TYPE_ID },
  progress: '고객사 방문',
  nextAction: '견적 재전달',
  dueDate: '2026-10-22',
  memo: '',
  ...over,
})

describe('action type mapping', () => {
  // 유형은 닫힌 enum이 아니라 카탈로그 항목이라 enum 매핑 함수가 없다.
  it('has no enum mapping any more (the type is a catalog item, not a closed set)', async () => {
    // when: 매퍼 모듈을 읽는다
    const module = await import('./action')

    // then: 예전 enum 매핑 함수가 없다
    expect(module).not.toHaveProperty('toApiActionType')
    expect(module).not.toHaveProperty('fromApiActionType')
  })

  // {id, name} 참조는 현재 이름과 유형 id로 바뀐다.
  // 테스트 코드: AC-089
  it('maps the {id, name} reference to type (current name) and typeId', () => {
    // when: 유형 참조가 있는 서버 Action을 바꾼다
    const mapped = toDealAction(serverAction({ action_type: { id: 9, name: '웨비나' } }))

    // then: 유형 이름과 유형 id가 채워진다
    expect(mapped.type).toBe('웨비나')
    expect(mapped.typeId).toBe(9)
  })

  // 목록의 유형은 id 객체로, 새 유형은 이름 객체로 보낸다.
  // 테스트 코드: AC-089
  it('sends the id object for a listed type and the name object for a new one', () => {
    // when·then: id 유형은 {id}로, 이름 유형은 {name}으로 본문이 만들어진다
    expect(toActionCreateBody(input({ type: { id: 1 } })).action_type).toEqual({ id: 1 })
    expect(toActionUpdateBody({ ...input(), type: { name: '웨비나' } }).action_type).toEqual({ name: '웨비나' })
  })
})

describe('toDealAction', () => {
  // 서버 Action은 화면 Action으로 바뀌고 action은 진행사항이 된다.
  // 테스트 코드: AC-089
  it('maps the server action to the screen action (action becomes progress)', () => {
    // when: 서버 Action을 화면 Action으로 바꾼다
    const mapped = toDealAction(
      serverAction({
        action_type: { id: 3, name: '협상' },
        action: '최종 가격 협의',
        next_action: '계약서 초안 검토',
        due_date: '2026-10-18',
        memo: '메모',
        status_key: 'price_negotiation',
        forecast_key: 'commit',
      }),
    )

    // then: 모든 칸이 화면 이름으로 바뀐다
    expect(mapped).toEqual({
      id: 41,
      dealCode: '20261016-AB12',
      actedAt: '2026-10-15T09:00:00+09:00',
      actor: { id: USER_ID.kim, name: '김영업', role: 'sales', status: 'active' },
      type: '협상',
      typeId: 3,
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

  // 담당자 역할을 유지하고 퇴사자를 표시한다.
  // 테스트 코드: AC-089
  it('keeps the actor role and marks a resigned actor', () => {
    // when: 퇴사한 담당자의 서버 Action을 바꾼다
    const mapped = toDealAction(serverAction({ actor: serverUserRef({ id: USER_ID.old, resigned: true, role: 'sales' }) }))

    // then: 담당자는 역할을 유지하고 상태가 resigned다
    expect(mapped.actor).toMatchObject({ id: USER_ID.old, role: 'sales', status: 'resigned' })
  })

  // 긴 텍스트를 다듬거나 자르지 않는다.
  // 테스트 코드: AC-089
  it('does not trim or cut a long text', () => {
    // given: 5,000자·20,000자 텍스트
    const long = '가'.repeat(5000)

    // when: 서버 Action을 바꾼다
    const mapped = toDealAction(serverAction({ action: long, next_action: long, memo: '나'.repeat(20000) }))

    // then: 길이가 그대로다
    expect(mapped.progress).toBe(long)
    expect(mapped.nextAction).toBe(long)
    expect(mapped.memo).toHaveLength(20000)
  })
})

describe('toActionCreateBody', () => {
  // 본문은 snake_case이고 수행일시·담당자 칸이 없다.
  // 테스트 코드: AC-089
  it('uses snake_case keys and has no acted_at or actor field', () => {
    // when: 유형 이름이 있는 입력으로 등록 본문을 만든다
    const body = toActionCreateBody(input({ type: { name: '통화' }, memo: '메모' }))

    // then: 서버 이름의 본문뿐이다
    expect(body).toEqual({
      action_type: { name: '통화' },
      action: '고객사 방문',
      next_action: '견적 재전달',
      due_date: '2026-10-22',
      memo: '메모',
    })
  })

  // 빈 Due Date는 null로 보낸다.
  // 테스트 코드: AC-089
  it('sends an empty due date as null so the server answers with its own message', () => {
    // when·then: Due가 빈 입력의 본문은 due_date가 null이다
    expect(toActionCreateBody(input({ dueDate: '' })).due_date).toBeNull()
  })

  // 텍스트를 다듬거나 자르지 않고 보낸다.
  // 테스트 코드: AC-089
  it('does not trim or cut the texts', () => {
    // when: 공백이 낀 긴 텍스트로 본문을 만든다
    const body = toActionCreateBody(input({ progress: `  ${'가'.repeat(5000)}  `, memo: '나'.repeat(20000) }))

    // then: 진행사항과 Memo가 그대로다
    expect(body.action).toBe(`  ${'가'.repeat(5000)}  `)
    expect(body.memo).toHaveLength(20000)
  })

  // 동반 변경은 resolution과 함께 status_changes로 바뀐다.
  // 테스트 코드: AC-089
  it('maps a status change with its resolution to status_changes', () => {
    // when: 매출 답이 있는 계약완료 변경으로 본문을 만든다
    const body = toActionCreateBody(
      input({
        statusChanges: [{
          change: { field: 'statusKey', value: 'contract_completed' },
          resolution: { revenueAmount: 1_800_000_000, revenueDate: '2026-10-15' },
        }],
      }),
    )

    // then: status_changes가 서버 이름이고 단건 status_change는 없다
    expect(body.status_changes).toEqual([
      {
        change: { field: 'status_key', value: 'contract_completed' },
        resolution: { revenue_amount: 1_800_000_000, revenue_date: '2026-10-15' },
      },
    ])
    expect(body).not.toHaveProperty('status_change')
  })

  // Forecast 변경과 되돌림 선택은 forecast_key/status_key 이름으로 바뀐다.
  // 테스트 코드: AC-089
  it('maps a forecast change and a reopen choice (status_key / forecast_key resolution)', () => {
    // when: Forecast 변경과 Status 선택으로 본문을 만든다
    const body = toActionCreateBody(
      input({
        statusChanges: [{
          change: { field: 'forecastKey', value: 'pipeline' },
          resolution: { statusKey: 'price_negotiation' },
        }],
      }),
    )

    // then: 서버 이름으로 바뀐다
    expect(body.status_changes).toEqual([
      {
        change: { field: 'forecast_key', value: 'pipeline' },
        resolution: { status_key: 'price_negotiation' },
      },
    ])
  })

  // 동반 변경이 없으면 status_changes와 resolution을 보내지 않는다.
  // 테스트 코드: AC-089
  it('omits status_changes and resolution when there is none', () => {
    // when: 변경이 없는·빈·resolution 없는 입력으로 본문을 만든다
    const plain = toActionCreateBody(input())
    const empty = toActionCreateBody(input({ statusChanges: [] }))
    const noResolution = toActionCreateBody(input({ statusChanges: [{ change: { field: 'statusKey', value: 'qualified' } }] }))

    // then: 변경 없음 둘에는 키가 없고 resolution 없는 변경에는 resolution 키가 없다
    expect(plain).not.toHaveProperty('status_changes')
    expect(plain).not.toHaveProperty('status_change')
    expect(empty).not.toHaveProperty('status_changes')
    expect(noResolution.status_changes).toEqual([{ change: { field: 'status_key', value: 'qualified' } }])
  })

  // 두 변경은 사용자가 바꾼 순서로, 각자 자기 resolution과 함께 보낸다.
  // 테스트 코드: AC-089
  it('sends two changes in the order the user made them, each with its own resolution', () => {
    // when: 두 변경이 있는 입력으로 본문을 만든다
    const body = toActionCreateBody(
      input({
        statusChanges: [
          { change: { field: 'forecastKey', value: 'commit' }, resolution: { statusKey: 'poc_completed' } },
          { change: { field: 'statusKey', value: 'contract_completed' }, resolution: { revenueAmount: 5_000_000, revenueDate: '2026-10-20' } },
        ],
      }),
    )

    // then: 순서와 resolution이 그대로이고 단건 키는 없다
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
  // 수정 본문은 내용 칸뿐이다.
  // 테스트 코드: AC-089
  it('has the content fields only', () => {
    // when: 수정 본문을 만든다
    const body = toActionUpdateBody({ type: { id: 5 }, progress: '수정', nextAction: '다음', dueDate: '2026-11-01', memo: '' })

    // then: 내용 칸 다섯 개뿐이다
    expect(body).toEqual({ action_type: { id: 5 }, action: '수정', next_action: '다음', due_date: '2026-11-01', memo: '' })
  })

  // 수정 본문도 빈 Due Date를 null로 보낸다.
  // 테스트 코드: AC-089
  it('sends an empty due date as null', () => {
    // when: Due가 빈 입력으로 수정 본문을 만든다
    const body = toActionUpdateBody({ type: { id: 5 }, progress: 'x', nextAction: 'y', dueDate: '', memo: '' })

    // then: due_date가 null이다
    expect(body.due_date).toBeNull()
  })
})

describe('toDealAction nullable plan fields and Next Action status', () => {
  // 서버가 null로 준 진행사항·Next Action·Due·상태·종료 시각은 null로 둔다.
  it('keeps null progress, Next Action, due date, status and closed time as null', () => {
    // when: 모두 null인 서버 Action을 화면 Action으로 바꾼다.
    const mapped = toDealAction(
      serverAction({ action: null, next_action: null, due_date: null, next_action_status: null, next_action_closed_at: null }),
    )

    // then: 다섯 필드가 null이다.
    expect(mapped).toMatchObject({ progress: null, nextAction: null, dueDate: null, nextActionStatus: null, nextActionClosedAt: null })
  })

  // 서버 상태 이름을 화면 상태 값으로 바꾼다(not_done -> notDone).
  it.each([
    ['open', 'open'],
    ['done', 'done'],
    ['not_done', 'notDone'],
  ] as const)('maps the server status %s to %s', (wire, status) => {
    // given: 상태와 종료 시각이 있는 서버 Action이다.
    const closed = wire === 'open' ? null : '2026-10-16T10:00:00+09:00'

    // when: 화면 Action으로 바꾼다.
    const mapped = toDealAction(serverAction({ next_action_status: wire, next_action_closed_at: closed }))

    // then: 화면 상태와 종료 시각이 기대와 같다.
    expect(mapped.nextActionStatus).toBe(status)
    expect(mapped.nextActionClosedAt).toBe(closed)
  })
})

describe('request bodies of a partial input', () => {
  // 진행사항만 내용은 빈 Next Action과 null Due로 보낸다.
  // 테스트 코드: AC-089
  it('sends a progress-only content with an empty Next Action and a null due date', () => {
    // when: Next Action이 빈 입력으로 본문을 만든다
    const body = toActionCreateBody(input({ nextAction: '', dueDate: '' }))

    // then: 빈 Next Action과 null Due가 있다
    expect(body).toMatchObject({ action: '고객사 방문', next_action: '', due_date: null })
  })

  // Next Action만 내용은 빈 진행사항으로 보낸다.
  // 테스트 코드: AC-089
  it('sends a Next-Action-only content with an empty progress', () => {
    // when: 진행사항이 빈 입력으로 수정 본문을 만든다
    const body = toActionUpdateBody({ type: { id: 1 }, progress: '', nextAction: '견적', dueDate: '2026-11-01', memo: '' })

    // then: 빈 진행사항과 Next Action·Due가 있다
    expect(body).toMatchObject({ action: '', next_action: '견적', due_date: '2026-11-01' })
  })
})

describe('closePreviousNextActionId mapping', () => {
  // 닫을 id는 close_previous_next_action_id로 바뀐다.
  // 테스트 코드: AC-089
  it('maps closePreviousNextActionId to close_previous_next_action_id', () => {
    // when: 닫을 id가 있는 입력으로 본문을 만든다
    const body = toActionCreateBody(input({ closePreviousNextActionId: 41 }))

    // then: 서버 이름의 필드가 있다
    expect(body).toMatchObject({ close_previous_next_action_id: 41 })
  })

  // 닫을 id가 없으면 필드를 보내지 않는다.
  // 테스트 코드: AC-089
  it('omits the field when it is absent so older servers see the same body', () => {
    // when: 닫을 id 없는 입력으로 본문을 만든다
    const body = toActionCreateBody(input())

    // then: 필드가 없다
    expect(body).not.toHaveProperty('close_previous_next_action_id')
  })

  // 수정 본문에는 닫을 id를 보내지 않는다.
  // 테스트 코드: AC-089
  it('never sends it in an update body', () => {
    // when: 수정 본문을 만든다
    const body = toActionUpdateBody({ ...input() })

    // then: 그 필드가 없다
    expect(body).not.toHaveProperty('close_previous_next_action_id')
  })
})

