import { describe, expect, it } from 'vitest'
import { seedActionTypeId } from '../seed/actionTypes'
import { dealCode, expectApiError, mockAs } from '../testing'

const DEFAULTS = ['통화', '미팅', '이메일', '데모', '제안', '협상', '계약', '기타']

describe('actionTypes.list (AC-1)', () => {
  it('every role sees the eight default types in order, seeded as default without a creator', async () => {
    for (const key of ['root', 'kim', 'han'] as const) {
      const { gateway } = await mockAs(key)
      const list = await gateway.actionTypes.list()
      expect(list.map((t) => t.name)).toEqual(DEFAULTS)
      expect(list.every((t) => t.isDefault && t.createdBy === null)).toBe(true)
      expect(list[1]?.id).toBe(seedActionTypeId('미팅'))
    }
  })

  it('requires a login', async () => {
    const { gateway } = await mockAs(null)
    await expectApiError(gateway.actionTypes.list(), 401)
  })

  it('puts custom types after the defaults ordered by lower-case name, then id', async () => {
    const { gateway } = await mockAs('kim')
    for (const name of ['Zeta', 'alpha', '나중']) await gateway.actionTypes.create(name)
    const names = (await gateway.actionTypes.list()).map((t) => t.name)
    expect(names).toEqual([...DEFAULTS, 'alpha', 'Zeta', '나중'])
  })

  it('counts the actions that use each type', async () => {
    const { gateway } = await mockAs('kim')
    const code = dealCode(1)
    const base = (await gateway.actions.list(code, {})).filter((a) => a.type === '협상').length
    const list = await gateway.actionTypes.list()
    expect(list.find((t) => t.name === '협상')?.usageCount).toBeGreaterThanOrEqual(base)
    expect(base).toBeGreaterThan(0)
  })
})

describe('actionTypes.create / rename / remove', () => {
  it('sales creates a trimmed type with the creator, the user role is refused', async () => {
    const kim = await mockAs('kim')
    const created = await kim.gateway.actionTypes.create('  웨비나  ')
    expect(created).toMatchObject({ name: '웨비나', isDefault: false, usageCount: 0, createdBy: { id: 'u-kim' } })
    const han = await mockAs('han')
    await expectApiError(han.gateway.actionTypes.create('x'), 403)
  })

  it('rejects blank, 51 characters and a case-insensitive duplicate; 50 characters pass', async () => {
    const { gateway } = await mockAs('root')
    await expectApiError(gateway.actionTypes.create('   '), 422, '유형을 입력하세요.')
    await expectApiError(gateway.actionTypes.create('x'.repeat(51)), 422, '유형은 50자 이내로 입력하세요.')
    await gateway.actionTypes.create('x'.repeat(50))
    await expectApiError(gateway.actionTypes.create('미팅'), 409, '이미 있는 유형 이름입니다.')
    await gateway.actionTypes.create('Demo2')
    await expectApiError(gateway.actionTypes.create('demo2'), 409, '이미 있는 유형 이름입니다.')
  })

  it('only the admin renames or deletes, including a default type', async () => {
    const kim = await mockAs('kim')
    await expectApiError(kim.gateway.actionTypes.rename(seedActionTypeId('기타'), '그 외'), 403, '이 작업을 수행할 권한이 없습니다. 관리자에게 문의하세요.')
    await expectApiError(kim.gateway.actionTypes.remove(seedActionTypeId('기타')), 403)
    const root = await mockAs('root')
    expect((await root.gateway.actionTypes.rename(seedActionTypeId('기타'), '그 외')).name).toBe('그 외')
  })

  it('allows changing only the case of its own name and refuses another type name', async () => {
    const { gateway } = await mockAs('root')
    const created = await gateway.actionTypes.create('Webinar')
    expect((await gateway.actionTypes.rename(created.id, 'WEBINAR')).name).toBe('WEBINAR')
    await expectApiError(gateway.actionTypes.rename(created.id, '통화'), 409, '이미 있는 유형 이름입니다.')
  })

  it('renames the type on every action and keeps the old history text', async () => {
    const { gateway } = await mockAs('root')
    const code = dealCode(1)
    const registered = await gateway.actions.create(code, { type: { name: '미팅' }, progress: '방문', nextAction: '견적', dueDate: '2026-11-01', memo: '' })
    await gateway.actionTypes.rename(seedActionTypeId('미팅'), '대면 미팅')
    expect((await gateway.actions.list(code, {})).find((a) => a.id === registered.id)?.type).toBe('대면 미팅')
    expect((await gateway.history.list(code, {}))[0]?.after.startsWith('등록: 미팅 · 방문')).toBe(true)
  })

  it('refuses to delete a used type with the count and deletes an unused one', async () => {
    const { gateway } = await mockAs('root')
    const used = (await gateway.actionTypes.list()).find((t) => t.name === '협상')
    await expectApiError(gateway.actionTypes.remove(seedActionTypeId('협상')), 409, `사용 중인 유형은 삭제할 수 없습니다. (Action ${used?.usageCount}건)`)
    const created = await gateway.actionTypes.create('임시')
    await gateway.actionTypes.remove(created.id)
    expect((await gateway.actionTypes.list()).some((t) => t.id === created.id)).toBe(false)
    await expectApiError(gateway.actionTypes.remove('at-none'), 404)
  })
})
