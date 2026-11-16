/** Fake 게이트웨이의 Vendor 관리가 서버 규칙을 따른다. 같은 규칙을 HTTP 어댑터는 vendors.contract.ts로 확인한다. */

import { describe, expect, it } from 'vitest'
import { seedVendorId } from '../../fixtures/vendors'
import { dealCode, expectApiError, mockAs } from '../testing'
import { NO_SUCH_ID } from '../seed/ids'

describe('vendors.list', () => {
  // Vendor 목록은 소문자 이름순이고 사용 수를 담으며 Solution은 없다.
  it('sorts vendors by lower-case name and carries usage counts without solutions', async () => {
    // given: han으로 로그인한다
    const { gateway } = await mockAs('han')

    // when: Vendor 목록을 읽는다
    const vendors = await gateway.vendors.list()

    // then: 이름순 10개이고 사용 수가 있으며 solutions가 없다
    expect(vendors.map((v) => v.name)).toEqual([
      'CrowdStrike', 'CyberArk', 'Okta', 'Palo Alto', 'SentinelOne', 'Silverfort', 'Splunk', 'Tenable', 'Veeam', 'Zscaler',
    ])
    const silverfort = vendors.find((v) => v.name === 'Silverfort')
    expect(silverfort).toEqual({ id: seedVendorId('Silverfort'), name: 'Silverfort', usageCount: 7 })
    expect(silverfort).not.toHaveProperty('solutions')
  })

  // 로그인하지 않으면 Vendor 목록을 읽을 수 없다.
  it('requires a login', async () => {
    // given: 로그인하지 않는다
    const { gateway } = await mockAs(null)

    // when·then: Vendor 목록을 읽는다 → 401이다
    await expectApiError(gateway.vendors.list(), 401)
  })
})

describe('vendors write', () => {
  // Vendor를 만들면 공백이 지워지고 사용 수는 0이다.
  it('creates a trimmed vendor with zero usage', async () => {
    // given: admin으로 로그인한다
    const { gateway } = await mockAs('root')

    // when: '  Acme  '를 만든다
    const created = await gateway.vendors.create('  Acme  ')

    // then: 사용 0인 Vendor가 목록에 있다
    expect(created).toEqual({ id: created.id, name: 'Acme', usageCount: 0 })
    expect((await gateway.vendors.list()).map((v) => v.id)).toContain(created.id)
  })

  // Vendor 게이트웨이에는 Solution 관리 메서드가 없다.
  it('has no solution management methods', async () => {
    // given: admin으로 로그인한다
    const { gateway } = await mockAs('root')

    // when: Solution 관리 메서드를 찾는다
    for (const method of ['createSolution', 'renameSolution', 'removeSolution']) {
      // then: 세 메서드가 모두 없다
      expect(gateway.vendors).not.toHaveProperty(method)
    }
  })

  // Vendor 쓰기는 admin만 되고 sales·user는 403이다.
  it('lets only the admin write', async () => {
    // given: sales와 user로 각각 로그인한다
    for (const key of ['kim', 'han'] as const) {
      const { gateway } = await mockAs(key)
      const id = seedVendorId('Splunk')

      // when·then: 등록·이름 변경·삭제를 요청한다 → 모두 403이고 Vendor는 그대로다
      await expectApiError(gateway.vendors.create('Acme'), 403)
      await expectApiError(gateway.vendors.rename(id, 'Acme'), 403)
      await expectApiError(gateway.vendors.remove(id), 403)
      expect((await gateway.vendors.list()).map((v) => v.id)).toContain(id)
    }
  })

  // 빈 이름·101자·NUL 이름은 서버 문구로 거절하고 100자는 허용한다.
  it('rejects blank, 101 character and NUL names with the server messages', async () => {
    // given: admin으로 로그인한다
    const { gateway } = await mockAs('root')

    // when·then: 유효하지 않은 이름으로 만든다 → 서버 문구의 422가 나오고 100자는 만들어진다
    await expectApiError(gateway.vendors.create('   '), 422, 'Vendor 이름을 입력하세요.')
    await expectApiError(gateway.vendors.create('v'.repeat(101)), 422, 'Vendor 이름은 100자 이내로 입력하세요.')
    await expect(gateway.vendors.create('v'.repeat(100))).resolves.toBeDefined()
    await expectApiError(gateway.vendors.create('a\u0000b'), 422)
  })

  // 대소문자만 다른 이름은 등록·이름 변경 모두 409다.
  it('rejects a vendor name that differs only in case', async () => {
    // given: admin으로 로그인한다
    const { gateway } = await mockAs('root')

    // when·then: 대소문자만 다른 이름으로 만들고 바꾼다 → 둘 다 409 중복 문구다
    await expectApiError(gateway.vendors.create('silverfort'), 409, '이미 있는 Vendor 이름입니다.')
    await expectApiError(gateway.vendors.rename(seedVendorId('Okta'), 'CYBERARK'), 409, '이미 있는 Vendor 이름입니다.')
  })

  // 자기 이름의 대소문자만 바꾸는 것은 허용된다.
  it('allows changing only the case of its own name', async () => {
    // given: admin으로 로그인한다
    const { gateway } = await mockAs('root')

    // when: 'Okta'를 'OKTA'로 바꾼다
    const renamed = await gateway.vendors.rename(seedVendorId('Okta'), 'OKTA')

    // then: 이름이 'OKTA'다
    expect(renamed.name).toBe('OKTA')
  })

  // Vendor 이름을 바꾸면 그 Vendor를 쓰는 Deal이 새 이름을 보인다.
  it('shows a renamed vendor on every deal', async () => {
    // given: admin으로 로그인한다
    const { gateway } = await mockAs('root')
    // when: 'Silverfort'를 'Silverfort Inc'로 바꾼다
    await gateway.vendors.rename(seedVendorId('Silverfort'), 'Silverfort Inc')

    // then: Deal의 Vendor가 새 이름이고 Product는 그대로다
    const deal = await gateway.deals.get(dealCode(1))

    expect(deal.vendor).toEqual({ id: seedVendorId('Silverfort'), name: 'Silverfort Inc' })
    expect(deal.product).toBe('ITDR')
  })

  // 없는 id의 이름 변경·삭제는 404다.
  it('treats unknown ids as missing', async () => {
    // given: admin으로 로그인한다
    const { gateway } = await mockAs('root')

    // when·then: 없는 id의 이름 변경·삭제를 요청한다 → 둘 다 404다
    await expectApiError(gateway.vendors.rename(NO_SUCH_ID, 'X'), 404)
    await expectApiError(gateway.vendors.remove(NO_SUCH_ID), 404)
  })
})

describe('vendors delete', () => {
  // Deal이 쓰는 Vendor는 건수가 든 문구의 409로 삭제를 거절한다.
  it('refuses a used vendor with the Deal count and keeps it', async () => {
    // given: 'Silverfort'는 Deal 7건이 쓴다
    const { gateway } = await mockAs('root')
    const silverfort = seedVendorId('Silverfort')

    // when·then: 'Silverfort'를 삭제한다 → 409 '(Deal 7건)'이고 Vendor는 남는다
    await expectApiError(gateway.vendors.remove(silverfort), 409, '사용 중인 Vendor는 삭제할 수 없습니다. (Deal 7건)')
    expect((await gateway.vendors.list()).map((v) => v.id)).toContain(silverfort)
  })

  // 쓰이지 않는 Vendor는 삭제되고 다시 지우면 404다.
  it('deletes an unused vendor', async () => {
    // given: 'Splunk'는 쓰이지 않는다
    const { gateway } = await mockAs('root')
    const splunk = seedVendorId('Splunk')

    // when: 'Splunk'를 삭제한다
    await gateway.vendors.remove(splunk)

    // then: 목록에서 사라지고 다시 지우면 404다
    expect((await gateway.vendors.list()).map((v) => v.id)).not.toContain(splunk)
    await expectApiError(gateway.vendors.remove(splunk), 404)
  })
})
