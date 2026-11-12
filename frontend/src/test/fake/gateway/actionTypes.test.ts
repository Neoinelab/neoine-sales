import { describe, expect, it } from 'vitest'
import { seedActionTypeId } from '../seed/actionTypes'
import { dealCode, expectApiError, mockAs } from '../testing'
import { NO_SUCH_ID, USER_ID } from '../seed/ids'

const DEFAULTS = ['통화', '미팅', '이메일', '데모', '제안', '협상', '계약', '기타']

describe('actionTypes.list', () => {
  // 모든 역할이 기본 유형 8개를 시드 순서로, 만든 사람 없이 본다.
  it('every role sees the eight default types in order, seeded as default without a creator', async () => {
    for (const key of ['root', 'kim', 'han'] as const) {
      // given: 각 역할로 로그인한다
      const { gateway } = await mockAs(key)
      // when: 유형 목록을 읽는다
      const list = await gateway.actionTypes.list()
      // then: 기본 8개가 순서대로 있고 모두 기본·만든 사람 없음이다
      expect(list.map((t) => t.name)).toEqual(DEFAULTS)
      expect(list.every((t) => t.isDefault && t.createdBy === null)).toBe(true)
      expect(list[1]?.id).toBe(seedActionTypeId('미팅'))
    }
  })

  // 로그인하지 않으면 유형 목록을 읽을 수 없다.
  it('requires a login', async () => {
    // given: 로그인하지 않는다
    const { gateway } = await mockAs(null)
    // when·then: 유형 목록을 읽는다 → 401이다
    await expectApiError(gateway.actionTypes.list(), 401)
  })

  // 직접 만든 유형은 기본 유형 뒤에 소문자 이름순으로 나온다.
  it('puts custom types after the defaults ordered by lower-case name, then id', async () => {
    // given: sales가 'Zeta', 'alpha', '나중'을 만들었다
    const { gateway } = await mockAs('kim')
    for (const name of ['Zeta', 'alpha', '나중']) await gateway.actionTypes.create(name)
    // when: 유형 목록을 읽는다
    const names = (await gateway.actionTypes.list()).map((t) => t.name)
    // then: 기본 8개 뒤에 alpha, Zeta, 나중 순이다
    expect(names).toEqual([...DEFAULTS, 'alpha', 'Zeta', '나중'])
  })

  // 유형의 사용 수는 그 유형을 쓰는 Action 수다.
  it('counts the actions that use each type', async () => {
    // given: 시드 Action이 있다
    const { gateway } = await mockAs('kim')
    const code = dealCode(1)
    const base = (await gateway.actions.list(code, {})).filter((a) => a.type === '협상').length
    // when: 유형 목록을 읽는다
    const list = await gateway.actionTypes.list()
    // then: '협상'의 사용 수가 그 Action 수 이상이다
    expect(list.find((t) => t.name === '협상')?.usageCount).toBeGreaterThanOrEqual(base)
    expect(base).toBeGreaterThan(0)
  })
})

describe('actionTypes.create / rename / remove', () => {
  // sales는 유형을 만들 수 있고 user는 403이다.
  // 테스트 코드: CL-090
  it('sales creates a trimmed type with the creator, the user role is refused', async () => {
    // given: sales로 로그인한다
    const kim = await mockAs('kim')
    // when: '  웨비나  '를 만들고, user가 만들어 본다
    const created = await kim.gateway.actionTypes.create('  웨비나  ')
    // then: 공백이 지워진 직접 만든 유형이 생기고 user는 403이다
    expect(created).toMatchObject({ name: '웨비나', isDefault: false, usageCount: 0, createdBy: { id: USER_ID.kim } })
    const han = await mockAs('han')
    await expectApiError(han.gateway.actionTypes.create('x'), 403)
  })

  // 빈 이름·51자·대소문자만 다른 중복은 서버 문구로 거절하고 50자는 허용한다.
  it('rejects blank, 51 characters and a case-insensitive duplicate; 50 characters pass', async () => {
    // given: admin으로 로그인한다
    const { gateway } = await mockAs('root')
    // when·then: 유효하지 않은 이름으로 만든다 → 서버 문구의 422·409가 나오고 50자는 만들어진다
    await expectApiError(gateway.actionTypes.create('   '), 422, '유형을 입력하세요.')
    await expectApiError(gateway.actionTypes.create('x'.repeat(51)), 422, '유형은 50자 이내로 입력하세요.')
    await gateway.actionTypes.create('x'.repeat(50))
    await expectApiError(gateway.actionTypes.create('미팅'), 409, '이미 있는 유형 이름입니다.')
    await gateway.actionTypes.create('Demo2')
    await expectApiError(gateway.actionTypes.create('demo2'), 409, '이미 있는 유형 이름입니다.')
  })

  // 이름 변경·삭제는 admin만 되고 sales는 403이다.
  // 테스트 코드: CL-090
  it('only the admin renames or deletes, including a default type', async () => {
    // given: sales로 로그인한다
    const kim = await mockAs('kim')
    // when·then: sales가 기본 유형의 이름 변경·삭제를 요청한다 → 403이고 admin은 바꿀 수 있다
    await expectApiError(kim.gateway.actionTypes.rename(seedActionTypeId('기타'), '그 외'), 403, '관리자 권한이 필요합니다')
    await expectApiError(kim.gateway.actionTypes.remove(seedActionTypeId('기타')), 403)
    const root = await mockAs('root')
    expect((await root.gateway.actionTypes.rename(seedActionTypeId('기타'), '그 외')).name).toBe('그 외')
  })

  // 자기 이름의 대소문자만 바꾸는 것은 되고 다른 유형 이름은 409다.
  it('allows changing only the case of its own name and refuses another type name', async () => {
    const { gateway } = await mockAs('root')
    // given: 'Webinar' 유형이 있다
    const created = await gateway.actionTypes.create('Webinar')
    // when·then: 'WEBINAR'로, 이어 '통화'로 바꾼다 → 앞은 바뀌고 뒤는 409 중복 문구다
    expect((await gateway.actionTypes.rename(created.id, 'WEBINAR')).name).toBe('WEBINAR')
    await expectApiError(gateway.actionTypes.rename(created.id, '통화'), 409, '이미 있는 유형 이름입니다.')
  })

  // 유형 이름을 바꾸면 Action은 새 이름을 보이고 이미 남은 History 문구는 그대로다.
  it('renames the type on every action and keeps the old history text', async () => {
    const { gateway } = await mockAs('root')
    const code = dealCode(1)
    // given: '미팅' 유형으로 Action을 등록했다
    const registered = await gateway.actions.create(code, { type: { name: '미팅' }, progress: '방문', nextAction: '견적', dueDate: '2026-11-01', memo: '' })
    // when: '미팅'을 '대면 미팅'으로 바꾼다
    await gateway.actionTypes.rename(seedActionTypeId('미팅'), '대면 미팅')
    // then: Action은 새 이름이고 History는 '등록: 미팅 ·'로 남는다
    expect((await gateway.actions.list(code, {})).find((a) => a.id === registered.id)?.type).toBe('대면 미팅')
    expect((await gateway.history.list(code, {}))[0]?.after.startsWith('등록: 미팅 · 방문')).toBe(true)
  })

  // 쓰이는 유형은 건수가 든 문구의 409로 삭제를 거절하고 안 쓰는 유형은 삭제한다.
  it('refuses to delete a used type with the count and deletes an unused one', async () => {
    const { gateway } = await mockAs('root')
    // given: '협상'은 Action이 쓴다
    const used = (await gateway.actionTypes.list()).find((t) => t.name === '협상')
    // when·then: '협상'을 삭제한다 → 409 건수 문구이고, 안 쓰는 유형은 삭제되며 없는 id는 404다
    await expectApiError(gateway.actionTypes.remove(seedActionTypeId('협상')), 409, `사용 중인 유형은 삭제할 수 없습니다. (Action ${used?.usageCount}건)`)
    const created = await gateway.actionTypes.create('임시')
    await gateway.actionTypes.remove(created.id)
    expect((await gateway.actionTypes.list()).some((t) => t.id === created.id)).toBe(false)
    await expectApiError(gateway.actionTypes.remove(NO_SUCH_ID), 404)
  })
})
