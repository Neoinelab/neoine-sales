import { describe, expect, it } from 'vitest'
import { expectApiError, mockAs } from '../testing'
import { NO_SUCH_ID } from '../seed/ids'

const DUPLICATE = '같은 이름의 코드가 이미 있습니다.'
const LOCKED = '시스템과 연결된 코드는 삭제할 수 없습니다. 이름과 순서는 변경할 수 있습니다.'
const ORDER_LIST = '순서 목록이 올바르지 않습니다.'

describe('Fake codes: 읽기와 권한', () => {
  // 모든 역할이 코드 목록을 읽고 sales·user의 관리 요청은 403이다.
  // 테스트 코드: CD-071
  it('lets every role read the codes and refuses sales and user every management request', async () => {
    for (const key of ['root', 'kim', 'han'] as const) {
      // given: 역할별로 로그인한다
      const { gateway } = await mockAs(key)
      // when: 코드 목록을 읽는다
      const set = await gateway.codes.all()
      // then: 기본 코드가 보인다
      expect(set.statuses).toHaveLength(7)
      expect(set.forecasts).toHaveLength(6)
    }
    for (const key of ['kim', 'han'] as const) {
      const { gateway } = await mockAs(key)
      await expectApiError(gateway.codes.list('status'), 403)
      await expectApiError(gateway.codes.create({ kind: 'status', name: 'x' }), 403)
      await expectApiError(gateway.codes.rename(1, 'y'), 403)
      await expectApiError(gateway.codes.reorder('status', []), 403)
      await expectApiError(gateway.codes.remove(1), 403)
    }
  })
})

describe('Fake codes: 추가', () => {
  // 맨 끝에 open으로 추가하고 key를 이름에서 만든다.
  // 테스트 코드: CD-071
  it('adds a code at the end as open with a key made from the name', async () => {
    // given: admin
    const { gateway } = await mockAs('root')

    // when: Status "Final Review"를 추가한다
    const created = await gateway.codes.create({ kind: 'status', name: '  Final Review  ' })

    // then: 맨 끝, open, 잠금 아님, 사용 0, key final_review, 이름은 공백이 지워진다
    expect(created).toMatchObject({ key: 'final_review', name: 'Final Review', order: 8, outcome: 'open', locked: false, usageCount: 0, probabilityHint: null })
    const list = await gateway.codes.list('status')
    expect(list[list.length - 1]?.id).toBe(created.id)
  })

  // 이름 규칙: 빈 이름·51자·NUL은 422이고 50자는 허용한다.
  // 테스트 코드: CD-071
  it('validates the name like the server', async () => {
    // given: admin
    const { gateway } = await mockAs('root')

    // when·then: 빈 이름, 공백뿐, 51자, NUL은 422
    await expectApiError(gateway.codes.create({ kind: 'status', name: '' }), 422, '이름을 입력하세요.')
    await expectApiError(gateway.codes.create({ kind: 'status', name: '   ' }), 422, '이름을 입력하세요.')
    await expectApiError(gateway.codes.create({ kind: 'status', name: '가'.repeat(51) }), 422, '이름은 50자 이내로 입력하세요.')
    await expectApiError(gateway.codes.create({ kind: 'status', name: 'a\u0000b' }), 422, '이름에는 NUL 문자를 쓸 수 없습니다')
    expect((await gateway.codes.create({ kind: 'status', name: '가'.repeat(50) })).name).toBe('가'.repeat(50))
    expect(await gateway.codes.list('status')).toHaveLength(8)
  })

  // 같은 종류의 대소문자·공백만 다른 이름은 409이고 다른 종류와는 같은 이름을 쓸 수 있다.
  // 테스트 코드: CD-071
  it('rejects a same-kind duplicate ignoring case but allows the other kind', async () => {
    // given: admin
    const { gateway } = await mockAs('root')

    // when·then: 같은 종류 중복은 409, 중복 이름이 힌트 오류보다 먼저다
    await expectApiError(gateway.codes.create({ kind: 'forecast', name: ' BEST ' }), 409, DUPLICATE)
    await expectApiError(gateway.codes.create({ kind: 'status', name: '기회발굴', probabilityHint: '1-2' }), 409, DUPLICATE)
    // then: 다른 종류에는 같은 이름을 쓸 수 있고 key는 종류 안에서만 겹침을 센다
    expect(await gateway.codes.create({ kind: 'status', name: 'Best' })).toMatchObject({ key: 'best' })
    expect(await gateway.codes.create({ kind: 'forecast', name: 'Best!' })).toMatchObject({ key: 'best_2' })
  })

  // key 규칙: 영문이 없으면 code_N, 숫자로 시작하면 c_, 50자를 넘지 않는다.
  // 테스트 코드: CD-071
  it('makes keys like the server', async () => {
    // given: admin
    const { gateway } = await mockAs('root')

    // when: 여러 이름을 추가한다
    const keys = []
    const longA = `${'a'.repeat(25)} ${'b'.repeat(24)}`
    const longB = `${'a'.repeat(25)}-${'b'.repeat(24)}`
    for (const name of ['보류', '검토 중', '2026 Plan', '--Deal Close--', longA, longB]) {
      keys.push((await gateway.codes.create({ kind: 'status', name })).key)
    }

    // then: 서버 규칙과 같은 key다(50자 key가 겹치면 앞 48자 + _2로 50자를 넘지 않는다)
    const base = `${'a'.repeat(25)}_${'b'.repeat(24)}`
    expect(keys).toEqual(['code_1', 'code_2', 'c_2026_plan', 'deal_close', base, `${base.slice(0, 48)}_2`])
  })

  // 확률 힌트: 공백을 지우고 빈 값은 없음, Status는 거절, 20자 초과·NUL은 거절한다.
  // 테스트 코드: CD-071
  it('normalizes and validates the probability hint like the server', async () => {
    // given: admin
    const { gateway } = await mockAs('root')

    // when·then: Forecast 힌트는 공백이 지워지고 빈 값은 null이다
    expect((await gateway.codes.create({ kind: 'forecast', name: 'U1', probabilityHint: '  10-20  ' })).probabilityHint).toBe('10-20')
    expect((await gateway.codes.create({ kind: 'forecast', name: 'U2', probabilityHint: '   ' })).probabilityHint).toBeNull()
    expect((await gateway.codes.create({ kind: 'forecast', name: 'U3', probabilityHint: '9'.repeat(20) })).probabilityHint).toBe('9'.repeat(20))
    // then: Status는 빈 힌트만 허용하고 내용이 있으면 422(조용히 버리지 않는다)
    expect((await gateway.codes.create({ kind: 'status', name: 'S1', probabilityHint: ' ' })).probabilityHint).toBeNull()
    await expectApiError(gateway.codes.create({ kind: 'status', name: 'S2', probabilityHint: '10-20' }), 422, 'Status에는 확률 힌트를 둘 수 없습니다.')
    // then: 20자 초과와 NUL은 422이고 저장되지 않는다
    await expectApiError(gateway.codes.create({ kind: 'forecast', name: 'U4', probabilityHint: '9'.repeat(21) }), 422, '확률 힌트는 20자 이내로 입력하세요.')
    await expectApiError(gateway.codes.create({ kind: 'forecast', name: 'U5', probabilityHint: '1\u00002' }), 422, '확률 힌트에는 NUL 문자를 쓸 수 없습니다')
    expect(await gateway.codes.list('forecast')).toHaveLength(9)
  })
})

describe('Fake codes: 이름 변경과 순서 변경', () => {
  // 이름 변경은 key·순서를 그대로 두고 자기 이름의 대소문자 변경은 허용하며 중복은 409다.
  // 테스트 코드: CD-071
  it('renames keeping the key, allows a case change of its own name and rejects a duplicate', async () => {
    // given: admin과 Forecast Best
    const { gateway } = await mockAs('root')
    const best = (await gateway.codes.list('forecast')).find((c) => c.key === 'best')
    if (!best) throw new Error('best가 없습니다.')

    // when·then: 대소문자만 바꾸면 허용되고 key·순서·결과는 그대로다
    expect(await gateway.codes.rename(best.id, 'BEST')).toMatchObject({ name: 'BEST', key: 'best', order: best.order, outcome: 'open' })
    // then: 다른 코드 이름은 409, 빈 이름·51자·NUL은 422
    await expectApiError(gateway.codes.rename(best.id, 'commit'), 409, DUPLICATE)
    await expectApiError(gateway.codes.rename(best.id, ''), 422, '이름을 입력하세요.')
    await expectApiError(gateway.codes.rename(best.id, '가'.repeat(51)), 422, '이름은 50자 이내로 입력하세요.')
    await expectApiError(gateway.codes.rename(best.id, 'a\u0000b'), 422, '이름에는 NUL 문자를 쓸 수 없습니다')
  })

  // 없는 코드는 서버와 같은 404 문구다.
  // 테스트 코드: CD-071
  it('answers a missing code with the server 404 message', async () => {
    // given: admin
    const { gateway } = await mockAs('root')

    // when·then: 이름 변경과 삭제 모두 같은 문구의 404다
    await expectApiError(gateway.codes.rename(NO_SUCH_ID, '아무거나'), 404, `코드을(를) 찾을 수 없습니다: ${NO_SUCH_ID}`)
    await expectApiError(gateway.codes.remove(NO_SUCH_ID), 404, `코드을(를) 찾을 수 없습니다: ${NO_SUCH_ID}`)
  })

  // 순서 변경은 1부터 다시 매기고 잘못된 목록은 422다.
  // 테스트 코드: CD-071
  it('renumbers from 1 for a full id list and rejects an invalid list', async () => {
    // given: admin과 Status 전체 id
    const { gateway } = await mockAs('root')
    const ids = (await gateway.codes.list('status')).map((c) => c.id)
    const foreign = (await gateway.codes.list('forecast'))[0]?.id ?? NO_SUCH_ID

    // when: 거꾸로 보낸다
    const after = await gateway.codes.reorder('status', [...ids].reverse())

    // then: 보낸 순서이고 order는 1부터다
    expect(after.map((c) => c.id)).toEqual([...ids].reverse())
    expect(after.map((c) => c.order)).toEqual([1, 2, 3, 4, 5, 6, 7])
    // then: 빠진·중복·다른 종류·빈 목록은 422이다
    await expectApiError(gateway.codes.reorder('status', ids.slice(1)), 422, ORDER_LIST)
    await expectApiError(gateway.codes.reorder('status', [...ids.slice(1), ids[1] ?? NO_SUCH_ID]), 422, ORDER_LIST)
    await expectApiError(gateway.codes.reorder('status', [...ids.slice(1), foreign]), 422, ORDER_LIST)
    await expectApiError(gateway.codes.reorder('status', []), 422, ORDER_LIST)
  })
})

describe('Fake codes: 삭제', () => {
  // 잠금 코드는 409이고 Deal이 쓰는 코드는 Deal 수가 든 409이며 쓰이지 않는 코드는 지워진다.
  // 테스트 코드: CD-071
  it('refuses locked and in-use codes and deletes an unused one', async () => {
    // given: admin
    const { gateway } = await mockAs('root')
    const statuses = await gateway.codes.list('status')
    const locked = statuses.find((c) => c.key === 'prospecting')
    const used = statuses.find((c) => c.key === 'price_negotiation')
    if (!locked || !used) throw new Error('시드 코드가 없습니다.')
    const created = await gateway.codes.create({ kind: 'status', name: '내부검토' })

    // when·then: 잠금은 409, Deal이 쓰는 코드는 Deal 수가 든 409
    await expectApiError(gateway.codes.remove(locked.id), 409, LOCKED)
    await expectApiError(gateway.codes.remove(used.id), 409, `사용 중인 코드는 삭제할 수 없습니다. (Deal ${used.usageCount}건)`)
    // then: 쓰이지 않는 코드는 지워진다
    await gateway.codes.remove(created.id)
    expect((await gateway.codes.list('status')).some((c) => c.id === created.id)).toBe(false)
  })
})
