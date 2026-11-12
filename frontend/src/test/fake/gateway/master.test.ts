import { BIND_PASSWORD } from '../../directoryFixtures'
import { describe, expect, it } from 'vitest'
import { dealCode, expectApiError, mockAs, newMock, TEST_NOW } from '../testing'
import { NO_SUCH_ID, USER_ID } from '../seed/ids'
import { SEED_PASSWORD } from '../seed/users'

describe('codes', () => {
  // 코드 변경은 admin만 할 수 있고 읽기는 모든 역할이 한다.
  it('변경은 admin만(sales·user 403), 읽기는 모두', async () => {
    for (const key of ['kim', 'han'] as const) {
      const { gateway } = await mockAs(key)
      // when: 코드를 읽는다
      const codes = await gateway.codes.all()
      // then: Status 7개를 돌려준다
      expect(codes.statuses).toHaveLength(7)
      // when·then: 추가·이름 변경·순서 변경·삭제를 요청한다 → 모두 403이다
      await expectApiError(gateway.codes.create({ kind: 'status', name: '새 단계' }), 403)
      await expectApiError(gateway.codes.rename(1, '이름'), 403)
      await expectApiError(gateway.codes.reorder('status', []), 403)
      await expectApiError(gateway.codes.remove(1), 403)
    }
  })

  // 코드 목록은 사용 중인 Deal 수를 포함한다.
  it('list는 사용 중 Deal 수를 포함한다', async () => {
    // given: admin 로그인과 시드 Deal 24건
    const { gateway } = await mockAs('root')
    // when: Forecast 코드 목록을 읽는다
    const forecasts = await gateway.codes.list('forecast')
    // then: Won 3건·Lost 1건이고 합이 24건이다
    expect(forecasts.find((c) => c.key === 'won')?.usageCount).toBe(3)
    expect(forecasts.find((c) => c.key === 'lost')?.usageCount).toBe(1)
    expect(forecasts.reduce((sum, c) => sum + c.usageCount, 0)).toBe(24)
  })

  // 코드 추가는 key를 자동으로 만들고 맨 끝 순서에 두며 빈 이름·중복 이름을 거절한다.
  it('추가: key 자동 생성, 맨 끝 순서, 빈 이름·중복 이름 거부', async () => {
    // given: admin 로그인
    const { gateway } = await mockAs('root')
    // when: Status 코드를 추가한다
    const created = await gateway.codes.create({ kind: 'status', name: '법무 검토' })
    // then: key는 자동 생성되고 순서는 맨 끝이다
    expect(created).toMatchObject({ kind: 'status', name: '법무 검토', order: 8, locked: false, usageCount: 0 })
    expect(created.key).toMatch(/^[a-z0-9_]+$/)
    // when: Status 코드를 하나 더 추가한다
    const second = await gateway.codes.create({ kind: 'status', name: '또 다른 단계' })
    // then: key가 서로 다르다
    expect(second.key).not.toBe(created.key)
    // when·then: 빈 이름과 중복 이름으로 추가한다 → 빈 이름은 422, 중복은 409다
    await expectApiError(gateway.codes.create({ kind: 'status', name: '  ' }), 422, '이름을 입력하세요.')
    await expectApiError(gateway.codes.create({ kind: 'status', name: '법무 검토' }), 409, '같은 이름의 코드가 이미 있습니다.')
    // when: Forecast 코드를 추가한다
    const fc = await gateway.codes.create({ kind: 'forecast', name: 'Upside', probabilityHint: '30–40' })
    // then: outcome이 open이고 확률 힌트가 그대로다
    expect(fc).toMatchObject({ outcome: 'open', probabilityHint: '30–40' })
  })

  // 코드 이름 변경은 즉시 반영되고 locked 코드도 key를 유지한 채 바꿀 수 있다.
  it('이름 변경은 목록·상세에 즉시 반영되고 locked 코드도 바꿀 수 있다(key 유지)', async () => {
    // given: admin 로그인과 locked 계약완료 코드
    const { gateway } = await mockAs('root')
    const done = (await gateway.codes.list('status')).find((c) => c.key === 'contract_completed')
    if (!done) throw new Error('status')
    // when: 계약완료 코드의 이름을 바꾸고 중복·없는 id로도 바꾼다
    const renamed = await gateway.codes.rename(done.id, '수주확정')
    // then: 새 이름이 목록에 반영되고 key·locked는 유지되며 중복은 409, 없는 id는 404, 동기화 알림은 새 이름을 쓴다
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

  // 순서 변경은 1부터 다시 매기고 잘못된 목록은 거절한다.
  it('순서 변경은 1부터 다시 매기고 잘못된 목록은 422', async () => {
    // given: admin 로그인과 Status 코드 목록
    const { gateway } = await mockAs('root')
    const statuses = await gateway.codes.list('status')
    const reversed = [...statuses].reverse().map((c) => c.id)
    // when: 순서를 뒤집어 저장하고 항목이 빠진 목록으로도 저장한다
    const result = await gateway.codes.reorder('status', reversed)
    // then: 순서가 1~7로 다시 매겨지고 빠진 목록은 422다
    expect(result.map((c) => c.order)).toEqual([1, 2, 3, 4, 5, 6, 7])
    expect(result[0]?.key).toBe('contract_completed')
    expect((await gateway.codes.all()).statuses[0]?.key).toBe('contract_completed')
    await expectApiError(gateway.codes.reorder('status', reversed.slice(1)), 422)
  })

  // locked·사용 중 코드는 삭제할 수 없고 쓰지 않는 코드는 삭제된다.
  it('삭제: locked는 409, 사용 중은 409(건수), 안 쓰는 코드는 삭제', async () => {
    // given: admin 로그인과 locked·사용 중·미사용 코드
    const { gateway } = await mockAs('root')
    const statuses = await gateway.codes.list('status')
    const locked = statuses.find((c) => c.key === 'contract_completed')
    const used = statuses.find((c) => c.key === 'price_negotiation')
    const forecasts = await gateway.codes.list('forecast')
    if (!locked || !used) throw new Error('status')
    // when·then: 각 코드를 삭제한다 → locked와 사용 중은 409, 미사용은 삭제되고 다시 지우면 404다
    await expectApiError(gateway.codes.remove(locked.id), 409, '시스템과 연결된 코드는 삭제할 수 없습니다. 이름과 순서는 변경할 수 있습니다.')
    await expectApiError(gateway.codes.remove(forecasts.find((c) => c.key === 'won')?.id ?? NO_SUCH_ID), 409, '시스템과 연결된 코드는 삭제할 수 없습니다. 이름과 순서는 변경할 수 있습니다.')
    await expectApiError(gateway.codes.remove(used.id), 409, `사용 중인 코드는 삭제할 수 없습니다. (Deal ${used.usageCount}건)`)
    const created = await gateway.codes.create({ kind: 'status', name: '임시 단계' })
    await gateway.codes.remove(created.id)
    expect((await gateway.codes.all()).statuses.map((c) => c.name)).not.toContain('임시 단계')
    await expectApiError(gateway.codes.remove(created.id), 404)
  })

  // Action만 참조하는 코드도 사용 중으로 본다.
  it('Action만 참조하는 코드도 사용 중으로 본다', async () => {
    // given: Deal에는 더 이상 쓰이지 않고 Action에서만 참조되는 코드
    const { gateway } = await mockAs('root')
    const created = await gateway.codes.create({ kind: 'status', name: '임시 단계' })
    const key = created.key
    await gateway.deals.applyChange(dealCode(2), { change: { field: 'statusKey', value: key } })
    await gateway.actions.create(dealCode(2), { type: { name: '기타' }, progress: 'a', nextAction: 'b', dueDate: '2026-10-20', memo: '' })
    await gateway.deals.applyChange(dealCode(2), { change: { field: 'statusKey', value: 'technical_evaluation' } })
    // when·then: 그 코드를 삭제한다 → 사용 중이라 409다
    await expectApiError(gateway.codes.remove(created.id), 409, /사용 중인 코드는 삭제할 수 없습니다\./)
  })
})

describe('labels (T-LABEL)', () => {
  // 같은 구분 안 중복(대소문자 무시)은 409이고 다른 구분이면 허용한다.
  it('T-LABEL-01 같은 구분 안 중복(대소문자 무시)은 409, 구분이 다르면 허용', async () => {
    // given: sales로 로그인한다
    const { gateway } = await mockAs('kim')
    // when: Budget에 'Q1 확정'을 만들고 같은·다른 구분으로 다시 만든다
    const created = await gateway.labels.create('budget', 'Q1 확정')
    // then: Label이 만들어진다
    expect(created).toMatchObject({ category: 'budget', name: 'Q1 확정', isDefault: false, usageCount: 0 })
    // when·then: 같은 구분에 같은 이름을 다시 만든다 → 409 중복 문구다
    await expectApiError(gateway.labels.create('budget', 'q1 확정'), 409, '같은 구분에 이미 있는 Label 이름입니다.')
    await expectApiError(gateway.labels.create('budget', '미확인'), 409, '같은 구분에 이미 있는 Label 이름입니다.')
    // when: 다른 구분에 같은 이름을 만든다
    const other = await gateway.labels.create('need', 'Q1 확정')
    // then: 허용된다
    expect(other.category).toBe('need')
  })

  // Label 이름은 앞뒤 공백을 지우고 빈 값·50자 초과는 422다.
  it('T-LABEL 이름 검증: 앞뒤 공백 제거, 빈 값·50자 초과 422', async () => {
    // given: sales로 로그인한다
    const { gateway } = await mockAs('kim')
    // when·then: 빈 값·51자·50자·공백 붙은 이름으로 만든다 → 422 서버 문구이고 50자와 공백 제거 이름은 만들어진다
    await expectApiError(gateway.labels.create('need', '   '), 422, 'Label 이름을 입력하세요.')
    await expectApiError(gateway.labels.create('need', 'x'.repeat(51)), 422, 'Label 이름은 50자 이내로 입력하세요.')
    expect((await gateway.labels.create('need', 'x'.repeat(50))).name).toHaveLength(50)
    expect((await gateway.labels.create('timeline', '  내후년 구매  ')).name).toBe('내후년 구매')
  })

  // 만든 Label은 Deal에서 바로 선택할 수 있고 사용 수가 반영되며 다른 구분 선택은 422다.
  it('T-LABEL-03 만든 Label을 Deal에 즉시 선택할 수 있고 사용 수가 반영된다', async () => {
    const { gateway } = await mockAs('kim')
    // given: sales가 timeline Label을 만들었다
    const label = await gateway.labels.create('timeline', '분기 말 구매')
    // when: 그 Label을 Deal의 timeline으로 고른다
    const updated = await gateway.deals.update(dealCode(2), { bant: { budget: null, authority: null, need: null, timeline: { id: label.id } } })
    // then: Deal이 그 Label을 가리키고 사용 수가 1이며 다른 구분에 고르면 422다
    expect(updated.bant.timeline).toBe(label.id)
    expect((await gateway.labels.list()).find((l) => l.id === label.id)?.usageCount).toBe(1)
    await expectApiError(gateway.deals.update(dealCode(2), { bant: { budget: { id: label.id }, authority: null, need: null, timeline: null } }), 422)
  })

  // sales·user의 이름 변경·삭제는 403이고 user의 등록도 403이다.
  // 테스트 코드: CL-090
  it('T-LABEL-04 sales·user의 rename/remove는 403, user의 create도 403', async () => {
    const kim = await mockAs('kim')
    // given: sales가 Label을 만들었다
    const label = await kim.gateway.labels.create('need', '새 Need')
    // when·then: sales가 이름 변경·삭제를, user가 등록을 요청한다 → 모두 403이고 user도 목록은 읽을 수 있다
    await expectApiError(kim.gateway.labels.rename(label.id, '다른 이름'), 403)
    await expectApiError(kim.gateway.labels.remove(label.id), 403)
    const han = await mockAs('han')
    await expectApiError(han.gateway.labels.create('need', 'x'), 403)
    expect((await han.gateway.labels.list()).length).toBeGreaterThan(0)
  })

  // admin은 사용 중 Label의 이름을 바꿀 수 있고 삭제는 건수가 든 409이며 안 쓰면 삭제한다.
  it('T-LABEL-05 admin: 사용 중 Label 이름 변경 가능, 삭제는 409(건수), 안 쓰면 삭제', async () => {
    // given: admin이고 사용 중인 Label이 있다
    const { gateway } = await mockAs('root')
    const labels = await gateway.labels.list()
    const inUse = labels.find((l) => l.usageCount > 0)
    if (!inUse) throw new Error('사용 중인 Label이 시드에 있어야 한다')
    // when: 사용 중 Label의 이름을 바꾼다
    const renamed = await gateway.labels.rename(inUse.id, '이름 변경됨')
    // then: 이름이 바뀐다
    expect(renamed.name).toBe('이름 변경됨')
    // when·then: 사용 중 Label을 삭제하고 같은 구분의 이름으로 바꾼다 → 모두 409다
    await expectApiError(gateway.labels.remove(inUse.id), 409, `사용 중인 Label은 삭제할 수 없습니다. (Deal ${inUse.usageCount}건)`)
    const sameCategory = labels.find((l) => l.category === inUse.category && l.id !== inUse.id)
    await expectApiError(gateway.labels.rename(inUse.id, sameCategory?.name.toUpperCase() ?? '없음'), 409, '같은 구분에 이미 있는 Label 이름입니다.')
    // when: 안 쓰는 Label을 만들어 삭제한다
    const fresh = await gateway.labels.create('authority', '삭제할 Label')
    await gateway.labels.remove(fresh.id)
    // then: 목록에서 사라진다
    expect((await gateway.labels.list()).some((l) => l.id === fresh.id)).toBe(false)
    // when·then: 다시 지운다 → 404다
    await expectApiError(gateway.labels.remove(fresh.id), 404)
  })
})

describe('users', () => {
  // 사용자 목록·등록·삭제는 admin만 하고 후보 조회는 모든 로그인 사용자가 한다.
  it('list/create/remove는 admin만, options는 모든 로그인 사용자', async () => {
    // given: sales(kim) 로그인
    const kim = await mockAs('kim')
    // when: 사용자 목록·등록·삭제와 후보 조회를 요청한다
    await expectApiError(kim.gateway.users.list('all'), 403)
    await expectApiError(kim.gateway.users.create({ loginId: 'new', name: '신규', role: 'sales' }), 403)
    await expectApiError(kim.gateway.users.remove(USER_ID.lee), 403)
    // then: 목록·등록·삭제는 403이고 후보 조회는 된다
    expect((await kim.gateway.users.options({ role: 'sales' })).length).toBeGreaterThan(0)
  })

  // 사용자 후보는 재직 sales만(퇴사자 포함 옵션 있음) 이름순으로 돌려준다.
  it('options: sales 후보는 재직 sales만, includeResigned면 퇴사자 포함, 이름순', async () => {
    // given: user(han) 로그인
    const { gateway } = await mockAs('han')
    // when: sales 후보를 조회한다
    const sales = await gateway.users.options({ role: 'sales' })
    // then: 재직 sales만 이름순이고 includeResigned면 퇴사자도 포함한다
    expect(sales.map((u) => u.name)).toEqual(['김영업', '박영업', '이영업', '정영업'].sort((a, b) => a.localeCompare(b, 'ko')))
    const withResigned = await gateway.users.options({ role: 'sales', includeResigned: true })
    expect(withResigned.map((u) => u.name)).toContain('강퇴사')
    expect((await gateway.users.options({})).map((u) => u.role)).toContain('admin')
  })

  // 사용자 목록은 재직·퇴사·전체 필터를 지원한다.
  it('list 필터(재직/퇴사/전체)와 최신 등록순', async () => {
    // given: admin 로그인
    const { gateway } = await mockAs('root')
    // when: 재직·퇴사·전체로 목록을 읽는다
    const active = await gateway.users.list('active')
    const resigned = await gateway.users.list('resigned')
    const all = await gateway.users.list('all')
    // then: 재직 6명, 퇴사 1명(강퇴사), 전체 7명이다
    expect(active).toHaveLength(6)
    expect(resigned.map((u) => u.name)).toEqual(['강퇴사'])
    expect(all).toHaveLength(7)
  })

  // 사용자 등록은 입력을 검증하고 재직자 아이디 중복을 막으며 퇴사자 아이디는 새 행으로 재입사시킨다.
  it('create: 검증과 아이디 중복(재직자만), 재입사는 새 행', async () => {
    // given: admin 로그인
    const { gateway } = await mockAs('root')
    // when·then: 빈 값과 재직자 중복 아이디로 등록한다 → 빈 값은 422, 재직자 중복은 409다
    await expectApiError(gateway.users.create({ loginId: '', name: '홍', role: 'sales' }), 422)
    await expectApiError(gateway.users.create({ loginId: 'hong', name: '', role: 'sales' }), 422)
    await expectApiError(gateway.users.create({ loginId: 'kim', name: '또 김영업', role: 'sales' }), 409, '이미 존재하는 사용자입니다: kim')
    // when: 새 아이디로 등록한다
    const created = await gateway.users.create({ loginId: 'hong', name: '홍길동', role: 'sales' })
    // then: 새 사용자가 등록된다
    expect(created).toMatchObject({ loginId: 'hong', status: 'active', createdBy: { id: USER_ID.root }, createdAt: TEST_NOW })
    // when: 퇴사자 아이디로 등록한다
    const rehire = await gateway.users.create({ loginId: 'old', name: '강재입사', role: 'sales' })
    // then: 재입사는 새 행이다
    expect(rehire.id).not.toBe(USER_ID.old)
    expect(await gateway.users.list('all')).toHaveLength(9)
  })

  // 사용자 삭제는 본인을 막고, 연결이 있으면 퇴사 처리하고, 없으면 물리 삭제한다.
  it('remove: 본인은 409, 연결이 있으면 퇴사 처리, 없으면 물리 삭제', async () => {
    // given: admin 로그인
    const { gateway } = await mockAs('root')
    // when·then: 본인과 없는 id를 삭제한다 → 본인은 409, 없는 id는 404다
    await expectApiError(gateway.users.remove(USER_ID.root), 409, '자기 자신은 삭제할 수 없습니다')
    await expectApiError(gateway.users.remove(NO_SUCH_ID), 404)
    // when: Deal 담당자를 삭제한다
    const resigned = await gateway.users.remove(USER_ID.lee)
    // then: 퇴사 처리된다
    expect(resigned).toEqual({ outcome: 'resigned' })
    const lee = (await gateway.users.list('all')).find((u) => u.id === USER_ID.lee)
    expect(lee).toMatchObject({ status: 'resigned', resignedAt: TEST_NOW })
    // Deal 담당은 그대로 유지되며 퇴사자 표기로 바뀐다
    expect((await gateway.deals.get(dealCode(5))).owner).toMatchObject({ id: USER_ID.lee, status: 'resigned' })
    const fresh = await gateway.users.create({ loginId: 'tmp', name: '임시', role: 'user' })
    // when: 새로 만든 사용자를 삭제한다
    const deleted = await gateway.users.remove(fresh.id)
    // then: 삭제되어 목록에서 사라진다
    expect(deleted).toEqual({ outcome: 'deleted' })
    expect((await gateway.users.list('all')).some((u) => u.id === fresh.id)).toBe(false)
  })
})

describe('settings', () => {
  const validInput = { host: 'dc1.corp.test', port: 636, security: 'ssl' as const, bindAccount: 'CORP\\svc-sales', bindPassword: BIND_PASSWORD, userFilter: '(sAMAccountName={login_id})', connectTimeoutSeconds: 5 }

  // AD·저장 위치 설정은 admin만 접근한다.
  it('admin만 접근한다', async () => {
    // when·then: AD 설정과 저장 위치를 읽거나 저장한다 → 모두 403이다
    for (const key of ['kim', 'han'] as const) {
      const { gateway } = await mockAs(key)
      await expectApiError(gateway.settings.getDirectory(), 403)
      await expectApiError(gateway.settings.saveStorage('/data/x'), 403)
      await expectApiError(gateway.settings.getStorage(), 403)
    }
  })

  // AD 설정 저장은 revision을 올리고 수정자·시각을 기록하며 비밀번호를 응답에 싣지 않는다.
  it('AD 설정 저장은 revision을 올리고 수정자·시각을 기록하며 비밀번호는 응답에 없다', async () => {
    // given: admin 로그인과 저장된 AD 설정
    const { gateway } = await mockAs('root')
    const before = await gateway.settings.getDirectory()
    expect(before).toMatchObject({ host: 'dc1.corp.test', port: 636, security: 'ssl', bindCredentialStatus: 'ok', baseDn: 'dc=corp,dc=test' })
    // when: 비밀번호를 생략하고 타임아웃을 바꿔 저장한다
    const saved = await gateway.settings.saveDirectory({ ...validInput, bindPassword: null, connectTimeoutSeconds: 9 }, { password: SEED_PASSWORD, expectedRevision: before?.revision ?? 1 })
    // then: revision이 1 오르고 수정자·시각이 기록되며 응답에 비밀번호가 없다
    expect(saved).toMatchObject({ revision: (before?.revision ?? 0) + 1, connectTimeoutSeconds: 9, baseDn: 'dc=corp,dc=test', bindCredentialStatus: 'ok', updatedAt: TEST_NOW, updatedBy: { id: USER_ID.root } })
    expect(JSON.stringify(saved)).not.toContain(validInput.bindPassword)
    expect(Object.keys(saved).some((key) => /password/i.test(key))).toBe(false)
  })

  // AD 설정 저장은 필수 값·포트·타임아웃 범위를 검증한다.
  it('AD 설정 저장 검증: 필수 값·포트·타임아웃 범위는 422', async () => {
    // given: admin 로그인
    const { gateway } = await mockAs('root')
    const keep = { ...validInput, bindPassword: null }
    // when·then: 호스트 비움·계정 비움·포트 0·65536·타임아웃 31로 저장한다 → 모두 422다
    await expectApiError(gateway.settings.saveDirectory({ ...keep, host: '' }, { password: null, expectedRevision: 1 }), 422)
    await expectApiError(gateway.settings.saveDirectory({ ...keep, bindAccount: '' }, { password: null, expectedRevision: 1 }), 422)
    await expectApiError(gateway.settings.saveDirectory({ ...keep, port: 0 }, { password: null, expectedRevision: 1 }), 422)
    await expectApiError(gateway.settings.saveDirectory({ ...keep, port: 65536 }, { password: null, expectedRevision: 1 }), 422)
    await expectApiError(gateway.settings.saveDirectory({ ...keep, connectTimeoutSeconds: 31 }, { password: null, expectedRevision: 1 }), 422)
  })

  // 서버나 계정을 바꾸면서 바인드 비밀번호를 생략하면 거절한다.
  it('서버·바인드 계정을 바꾸면서 바인드 비밀번호를 생략하면 422(비밀번호 재입력)', async () => {
    // given: admin 로그인과 저장된 AD 설정
    const { gateway } = await mockAs('root')
    const before = await gateway.settings.getDirectory()
    const auth = { password: SEED_PASSWORD, expectedRevision: before?.revision ?? 1 }
    // when: 호스트·포트·보안 연결·계정을 하나씩 바꾸고 비밀번호는 생략해 저장한다
    for (const change of [{ host: 'dc9.corp.test' }, { port: 3269 }, { security: 'starttls' as const }, { bindAccount: 'CORP\\other' }]) {
      await expectApiError(gateway.settings.saveDirectory({ ...validInput, bindPassword: null, ...change }, auth), 422, /비밀번호/)
    }
    // then: 모두 422(비밀번호 재입력)이고 revision은 그대로다
    expect((await gateway.settings.getDirectory())?.revision).toBe(before?.revision)
  })

  // 새 바인드 비밀번호를 주면 서버를 바꿔 저장할 수 있다.
  it('새 바인드 비밀번호를 주면 서버를 바꿔 저장할 수 있다', async () => {
    // given: admin 로그인과 저장된 AD 설정
    const { gateway } = await mockAs('root')
    const before = await gateway.settings.getDirectory()
    // when: 새 호스트와 새 바인드 비밀번호로 저장한다
    const saved = await gateway.settings.saveDirectory({ ...validInput, host: 'dc9.corp.test' }, { password: SEED_PASSWORD, expectedRevision: before?.revision ?? 1 })
    // then: 호스트가 바뀌고 자격 증명 상태는 ok다
    expect(saved).toMatchObject({ host: 'dc9.corp.test', bindCredentialStatus: 'ok' })
  })

  // expectedRevision이 null이면 설정이 없을 때만 새로 만든다.
  it('expectedRevision이 null이면 설정이 없을 때만 새로 만든다(비밀번호 필수), 있으면 409', async () => {
    // given: 설정이 없는 최초 설정 상태의 admin
    const mock = newMock()
    const { gateway } = mock
    mock.control.restartSetup()
    await mock.gateway.auth.login('root', SEED_PASSWORD)
    // when·then: 비밀번호 없이·있이 새로 만들고 한 번 더 만든다 → 비밀번호 없으면 422, 만들면 revision 1, 이미 있으면 409다
    await expectApiError(gateway.settings.saveDirectory({ ...validInput, bindPassword: null }, { password: SEED_PASSWORD, expectedRevision: null }), 422, /비밀번호/)
    const created = await gateway.settings.saveDirectory(validInput, { password: SEED_PASSWORD, expectedRevision: null })
    expect(created.revision).toBe(1)
    await expectApiError(gateway.settings.saveDirectory(validInput, { password: SEED_PASSWORD, expectedRevision: null }), 409)
  })

  // 연결 테스트는 성공하면 찾은 Base DN을, 실패하면 connect 단계 오류를 돌려준다.
  it('연결 테스트: 성공하면 찾은 Base DN을 돌려주고, 호스트에 fail이 들어가면 directory-verification-failed(stage connect)', async () => {
    // given: admin 로그인
    const { gateway } = await mockAs('root')
    // when: 정상 호스트와 fail 호스트로 연결 테스트한다
    const result = await gateway.settings.testDirectory(validInput, SEED_PASSWORD)
    // then: 정상은 Base DN을 돌려주고 fail은 directory-verification-failed(stage connect) 422다
    expect(result).toEqual({ baseDn: 'dc=corp,dc=test' })
    const error = await expectApiError(gateway.settings.testDirectory({ ...validInput, host: 'fail.corp.test' }, SEED_PASSWORD), 422, /연결 단계에서 실패했습니다/)
    expect(error.kind).toBe('directory-verification-failed')
    expect(error.stage).toBe('connect')
  })

  // 파일 저장 위치는 절대 경로만 받고 쓸 수 없는 위치는 거절하며 테스트는 저장하지 않는다.
  it('파일 저장 위치: 절대 경로 아니면 422, /readonly는 쓰기 실패, 테스트는 저장하지 않는다', async () => {
    // given: admin 로그인과 기본 저장 위치
    const { gateway } = await mockAs('root')
    expect((await gateway.settings.getStorage())?.path).toBe('/data/neoine-sales/files')
    // when·then: 상대 경로·읽기 전용 경로로 저장하고 새 경로를 테스트한 뒤 저장한다 → 상대 경로는 422, 읽기 전용은 쓰기 실패 422, 테스트는 저장하지 않고 저장하면 바뀐다
    await expectApiError(gateway.settings.saveStorage('files'), 422, '절대 경로를 입력하세요.')
    await expectApiError(gateway.settings.testStorage('files'), 422, '절대 경로를 입력하세요.')
    await expectApiError(gateway.settings.saveStorage('/readonly/x'), 422, '해당 위치에 쓸 수 없습니다.')
    await gateway.settings.testStorage('/mnt/new')
    expect((await gateway.settings.getStorage())?.path).toBe('/data/neoine-sales/files')
    const saved = await gateway.settings.saveStorage('/mnt/new')
    expect(saved).toMatchObject({ path: '/mnt/new', updatedBy: { id: USER_ID.root } })
  })
})
