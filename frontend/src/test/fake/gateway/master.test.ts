import { describe, expect, it } from 'vitest'
import { dealCode, expectApiError, mockAs, TEST_NOW } from '../testing'
import { NO_SUCH_ID, USER_ID } from '../seed/ids'

describe('codes', () => {
  it('변경은 admin만(sales·user 403), 읽기는 모두', async () => {
    for (const key of ['kim', 'han'] as const) {
      const { gateway } = await mockAs(key)
      expect((await gateway.codes.all()).statuses).toHaveLength(7)
      await expectApiError(gateway.codes.create({ kind: 'status', name: '새 단계' }), 403)
      await expectApiError(gateway.codes.rename(1, '이름'), 403)
      await expectApiError(gateway.codes.reorder('status', []), 403)
      await expectApiError(gateway.codes.remove(1), 403)
    }
  })

  it('list는 사용 중 Deal 수를 포함한다', async () => {
    const { gateway } = await mockAs('root')
    const forecasts = await gateway.codes.list('forecast')
    expect(forecasts.find((c) => c.key === 'won')?.usageCount).toBe(3)
    expect(forecasts.find((c) => c.key === 'lost')?.usageCount).toBe(1)
    expect(forecasts.reduce((sum, c) => sum + c.usageCount, 0)).toBe(24)
  })

  it('추가: key 자동 생성, 맨 끝 순서, 빈 이름·중복 이름 거부', async () => {
    const { gateway } = await mockAs('root')
    const created = await gateway.codes.create({ kind: 'status', name: '법무 검토' })
    expect(created).toMatchObject({ kind: 'status', name: '법무 검토', order: 8, locked: false, usageCount: 0 })
    expect(created.key).toMatch(/^[a-z0-9_]+$/)
    const second = await gateway.codes.create({ kind: 'status', name: '또 다른 단계' })
    expect(second.key).not.toBe(created.key)
    await expectApiError(gateway.codes.create({ kind: 'status', name: '  ' }), 422, '이름을 입력하세요.')
    await expectApiError(gateway.codes.create({ kind: 'status', name: '법무 검토' }), 409, '같은 이름의 코드가 이미 있습니다.')
    const fc = await gateway.codes.create({ kind: 'forecast', name: 'Upside', probabilityHint: '30–40' })
    expect(fc).toMatchObject({ outcome: 'open', probabilityHint: '30–40' })
  })

  it('이름 변경은 목록·상세에 즉시 반영되고 locked 코드도 바꿀 수 있다(key 유지)', async () => {
    const { gateway } = await mockAs('root')
    const done = (await gateway.codes.list('status')).find((c) => c.key === 'contract_completed')
    if (!done) throw new Error('status')
    const renamed = await gateway.codes.rename(done.id, '수주확정')
    expect(renamed).toMatchObject({ name: '수주확정', key: 'contract_completed', locked: true })
    const codes = await gateway.codes.all()
    expect(codes.statuses.find((c) => c.key === 'contract_completed')?.name).toBe('수주확정')
    await expectApiError(gateway.codes.rename(done.id, '가격협상'), 409, '같은 이름의 코드가 이미 있습니다.')
    await expectApiError(gateway.codes.rename(NO_SUCH_ID, 'x'), 404)
    // 이름이 바뀐 뒤에도 동기화 규칙은 key로 동작하고 알림은 새 이름을 쓴다
    const result = await gateway.deals.applyChange(dealCode(1), {
      change: { field: 'statusKey', value: 'contract_completed' },
      resolution: { revenueAmount: 1_000_000_000, revenueDate: '2026-10-15' },
    })
    expect(result.notice).toContain("'수주확정'")
    expect(result.deal.forecastKey).toBe('won')
  })

  it('순서 변경은 1부터 다시 매기고 잘못된 목록은 422', async () => {
    const { gateway } = await mockAs('root')
    const statuses = await gateway.codes.list('status')
    const reversed = [...statuses].reverse().map((c) => c.id)
    const result = await gateway.codes.reorder('status', reversed)
    expect(result.map((c) => c.order)).toEqual([1, 2, 3, 4, 5, 6, 7])
    expect(result[0]?.key).toBe('contract_completed')
    expect((await gateway.codes.all()).statuses[0]?.key).toBe('contract_completed')
    await expectApiError(gateway.codes.reorder('status', reversed.slice(1)), 422)
  })

  it('삭제: locked는 409, 사용 중은 409(건수), 안 쓰는 코드는 삭제', async () => {
    const { gateway } = await mockAs('root')
    const statuses = await gateway.codes.list('status')
    const locked = statuses.find((c) => c.key === 'contract_completed')
    const used = statuses.find((c) => c.key === 'price_negotiation')
    const forecasts = await gateway.codes.list('forecast')
    if (!locked || !used) throw new Error('status')
    await expectApiError(gateway.codes.remove(locked.id), 409, '시스템과 연결된 코드는 삭제할 수 없습니다. 이름과 순서는 변경할 수 있습니다.')
    await expectApiError(gateway.codes.remove(forecasts.find((c) => c.key === 'won')?.id ?? NO_SUCH_ID), 409, '시스템과 연결된 코드는 삭제할 수 없습니다. 이름과 순서는 변경할 수 있습니다.')
    await expectApiError(gateway.codes.remove(used.id), 409, `사용 중인 코드는 삭제할 수 없습니다. (Deal ${used.usageCount}건)`)
    const created = await gateway.codes.create({ kind: 'status', name: '임시 단계' })
    await gateway.codes.remove(created.id)
    expect((await gateway.codes.all()).statuses.map((c) => c.name)).not.toContain('임시 단계')
    await expectApiError(gateway.codes.remove(created.id), 404)
  })

  it('Action만 참조하는 코드도 사용 중으로 본다', async () => {
    const { gateway } = await mockAs('root')
    const created = await gateway.codes.create({ kind: 'status', name: '임시 단계' })
    const key = created.key
    await gateway.deals.applyChange(dealCode(2), { change: { field: 'statusKey', value: key } })
    await gateway.actions.create(dealCode(2), { type: { name: '기타' }, progress: 'a', nextAction: 'b', dueDate: '2026-10-20', memo: '' })
    await gateway.deals.applyChange(dealCode(2), { change: { field: 'statusKey', value: 'technical_evaluation' } })
    await expectApiError(gateway.codes.remove(created.id), 409, /사용 중인 코드는 삭제할 수 없습니다\./)
  })
})

describe('labels (T-LABEL)', () => {
  it('T-LABEL-01 같은 구분 안 중복(대소문자 무시)은 409, 구분이 다르면 허용', async () => {
    const { gateway } = await mockAs('kim')
    const created = await gateway.labels.create('budget', 'Q1 확정')
    expect(created).toMatchObject({ category: 'budget', name: 'Q1 확정', isDefault: false, usageCount: 0 })
    await expectApiError(gateway.labels.create('budget', 'q1 확정'), 409, '같은 구분에 이미 있는 Label 이름입니다.')
    await expectApiError(gateway.labels.create('budget', '미확인'), 409, '같은 구분에 이미 있는 Label 이름입니다.')
    const other = await gateway.labels.create('need', 'Q1 확정')
    expect(other.category).toBe('need')
  })

  it('T-LABEL 이름 검증: 앞뒤 공백 제거, 빈 값·50자 초과 422', async () => {
    const { gateway } = await mockAs('kim')
    await expectApiError(gateway.labels.create('need', '   '), 422, 'Label 이름을 입력하세요.')
    await expectApiError(gateway.labels.create('need', 'x'.repeat(51)), 422, 'Label 이름은 50자 이내로 입력하세요.')
    expect((await gateway.labels.create('need', 'x'.repeat(50))).name).toHaveLength(50)
    expect((await gateway.labels.create('timeline', '  내후년 구매  ')).name).toBe('내후년 구매')
  })

  it('T-LABEL-03 만든 Label을 Deal에 즉시 선택할 수 있고 사용 수가 반영된다', async () => {
    const { gateway } = await mockAs('kim')
    const label = await gateway.labels.create('timeline', '분기 말 구매')
    const updated = await gateway.deals.update(dealCode(2), { bant: { budget: null, authority: null, need: null, timeline: { id: label.id } } })
    expect(updated.bant.timeline).toBe(label.id)
    expect((await gateway.labels.list()).find((l) => l.id === label.id)?.usageCount).toBe(1)
    await expectApiError(gateway.deals.update(dealCode(2), { bant: { budget: { id: label.id }, authority: null, need: null, timeline: null } }), 422)
  })

  it('T-LABEL-04 sales·user의 rename/remove는 403, user의 create도 403', async () => {
    const kim = await mockAs('kim')
    const label = await kim.gateway.labels.create('need', '새 Need')
    await expectApiError(kim.gateway.labels.rename(label.id, '다른 이름'), 403)
    await expectApiError(kim.gateway.labels.remove(label.id), 403)
    const han = await mockAs('han')
    await expectApiError(han.gateway.labels.create('need', 'x'), 403)
    expect((await han.gateway.labels.list()).length).toBeGreaterThan(0)
  })

  it('T-LABEL-05 admin: 사용 중 Label 이름 변경 가능, 삭제는 409(건수), 안 쓰면 삭제', async () => {
    const { gateway } = await mockAs('root')
    const labels = await gateway.labels.list()
    const inUse = labels.find((l) => l.usageCount > 0)
    if (!inUse) throw new Error('사용 중인 Label이 시드에 있어야 한다')
    const renamed = await gateway.labels.rename(inUse.id, '이름 변경됨')
    expect(renamed.name).toBe('이름 변경됨')
    await expectApiError(gateway.labels.remove(inUse.id), 409, `사용 중인 Label은 삭제할 수 없습니다. (Deal ${inUse.usageCount}건)`)
    const sameCategory = labels.find((l) => l.category === inUse.category && l.id !== inUse.id)
    await expectApiError(gateway.labels.rename(inUse.id, sameCategory?.name.toUpperCase() ?? '없음'), 409, '같은 구분에 이미 있는 Label 이름입니다.')
    const fresh = await gateway.labels.create('authority', '삭제할 Label')
    await gateway.labels.remove(fresh.id)
    expect((await gateway.labels.list()).some((l) => l.id === fresh.id)).toBe(false)
    await expectApiError(gateway.labels.remove(fresh.id), 404)
  })
})

describe('users', () => {
  it('list/create/remove는 admin만, options는 모든 로그인 사용자', async () => {
    const kim = await mockAs('kim')
    await expectApiError(kim.gateway.users.list('all'), 403)
    await expectApiError(kim.gateway.users.create({ loginId: 'new', name: '신규', role: 'sales' }), 403)
    await expectApiError(kim.gateway.users.remove(USER_ID.lee), 403)
    expect((await kim.gateway.users.options({ role: 'sales' })).length).toBeGreaterThan(0)
  })

  it('options: sales 후보는 재직 sales만, includeResigned면 퇴사자 포함, 이름순', async () => {
    const { gateway } = await mockAs('han')
    const sales = await gateway.users.options({ role: 'sales' })
    expect(sales.map((u) => u.name)).toEqual(['김영업', '박영업', '이영업', '정영업'].sort((a, b) => a.localeCompare(b, 'ko')))
    const withResigned = await gateway.users.options({ role: 'sales', includeResigned: true })
    expect(withResigned.map((u) => u.name)).toContain('강퇴사')
    expect((await gateway.users.options({})).map((u) => u.role)).toContain('admin')
  })

  it('list 필터(재직/퇴사/전체)와 최신 등록순', async () => {
    const { gateway } = await mockAs('root')
    expect(await gateway.users.list('active')).toHaveLength(6)
    expect((await gateway.users.list('resigned')).map((u) => u.name)).toEqual(['강퇴사'])
    expect(await gateway.users.list('all')).toHaveLength(7)
  })

  it('create: 검증과 아이디 중복(재직자만), 재입사는 새 행', async () => {
    const { gateway } = await mockAs('root')
    await expectApiError(gateway.users.create({ loginId: '', name: '홍', role: 'sales' }), 422)
    await expectApiError(gateway.users.create({ loginId: 'hong', name: '', role: 'sales' }), 422)
    await expectApiError(gateway.users.create({ loginId: 'kim', name: '또 김영업', role: 'sales' }), 409, '이미 사용 중인 아이디입니다.')
    const created = await gateway.users.create({ loginId: 'hong', name: '홍길동', role: 'sales' })
    expect(created).toMatchObject({ loginId: 'hong', status: 'active', createdBy: { id: USER_ID.root }, createdAt: TEST_NOW })
    const rehire = await gateway.users.create({ loginId: 'old', name: '강재입사', role: 'sales' })
    expect(rehire.id).not.toBe(USER_ID.old)
    expect(await gateway.users.list('all')).toHaveLength(9)
  })

  it('remove: 본인은 403, 연결이 있으면 퇴사 처리, 없으면 물리 삭제', async () => {
    const { gateway } = await mockAs('root')
    await expectApiError(gateway.users.remove(USER_ID.root), 403, '본인 계정은 삭제할 수 없습니다.')
    await expectApiError(gateway.users.remove(NO_SUCH_ID), 404)
    expect(await gateway.users.remove(USER_ID.lee)).toEqual({ outcome: 'resigned' })
    const lee = (await gateway.users.list('all')).find((u) => u.id === USER_ID.lee)
    expect(lee).toMatchObject({ status: 'resigned', resignedAt: TEST_NOW })
    // Deal 담당은 그대로 유지되며 퇴사자 표기로 바뀐다
    expect((await gateway.deals.get(dealCode(5))).owner).toMatchObject({ id: USER_ID.lee, status: 'resigned' })
    const fresh = await gateway.users.create({ loginId: 'tmp', name: '임시', role: 'user' })
    expect(await gateway.users.remove(fresh.id)).toEqual({ outcome: 'deleted' })
    expect((await gateway.users.list('all')).some((u) => u.id === fresh.id)).toBe(false)
  })
})

describe('settings', () => {
  const validInput = {
    serverUrls: ['ldaps://dc1.corp.test'], useStarttls: true, caCertPem: null, bindTemplate: 'CORP\\{login_id}',
    baseDn: 'dc=corp,dc=test', userFilter: '(sAMAccountName={login_id})', displayNameAttribute: 'displayName',
    emailAttribute: 'mail', connectTimeoutSeconds: 5, receiveTimeoutSeconds: 10,
  }

  it('admin만 접근한다', async () => {
    for (const key of ['kim', 'han'] as const) {
      const { gateway } = await mockAs(key)
      await expectApiError(gateway.settings.getDirectory(), 403)
      await expectApiError(gateway.settings.saveStorage('/data/x'), 403)
      await expectApiError(gateway.settings.getStorage(), 403)
    }
  })

  it('AD 설정 저장은 revision을 올리고 수정자·시각을 기록한다', async () => {
    const { gateway } = await mockAs('root')
    const before = await gateway.settings.getDirectory()
    expect(before?.serverUrls).toEqual(['ldaps://dc1.corp.test', 'ldaps://dc2.corp.test'])
    const saved = await gateway.settings.saveDirectory({ ...validInput, baseDn: 'dc=new,dc=test' }, { password: null, expectedRevision: before?.revision ?? 1 })
    expect(saved).toMatchObject({ revision: (before?.revision ?? 0) + 1, baseDn: 'dc=new,dc=test', updatedAt: TEST_NOW, updatedBy: { id: USER_ID.root }, useStarttls: true })
    await expectApiError(gateway.settings.saveDirectory({ ...validInput, serverUrls: [] }, { password: null, expectedRevision: 1 }), 422)
    await expectApiError(gateway.settings.saveDirectory({ ...validInput, baseDn: '' }, { password: null, expectedRevision: 1 }), 422)
  })

  it('연결 테스트: 서버 URL에 fail이 들어가면 directory-verification-failed(stage connect)', async () => {
    const { gateway } = await mockAs('root')
    await gateway.settings.testDirectory(validInput, null)
    const error = await expectApiError(gateway.settings.testDirectory({ ...validInput, serverUrls: ['ldaps://fail.corp.test'] }, null), 422, /연결 단계에서 실패했습니다/)
    expect(error.kind).toBe('directory-verification-failed')
    expect(error.stage).toBe('connect')
  })

  it('파일 저장 위치: 절대 경로 아니면 422, /readonly는 쓰기 실패, 테스트는 저장하지 않는다', async () => {
    const { gateway } = await mockAs('root')
    expect((await gateway.settings.getStorage())?.path).toBe('/data/neoine-sales/files')
    await expectApiError(gateway.settings.saveStorage('files'), 422, '절대 경로를 입력하세요.')
    await expectApiError(gateway.settings.testStorage('files'), 422, '절대 경로를 입력하세요.')
    await expectApiError(gateway.settings.saveStorage('/readonly/x'), 422, '해당 위치에 쓸 수 없습니다.')
    await gateway.settings.testStorage('/mnt/new')
    expect((await gateway.settings.getStorage())?.path).toBe('/data/neoine-sales/files')
    const saved = await gateway.settings.saveStorage('/mnt/new')
    expect(saved).toMatchObject({ path: '/mnt/new', updatedBy: { id: USER_ID.root } })
  })
})
