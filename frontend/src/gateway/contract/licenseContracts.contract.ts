/**
 * 라이선스 계약(계약관리) 계약. mock과 실제 서버가 같은 규칙을 지킨다.
 * 계약은 Deal이 Won이 될 때 자동으로 생긴다(수동 생성 API 없음). 그래서 스위트는 Deal을 Won으로 만들어 계약을 얻고
 * 호출마다 고유한 이름을 쓰며, 만든 것은 스스로 치운다(Deal 삭제는 계약을 함께 지운다).
 * 규칙: 발급 상태(발급(신규)·발급(갱신)) 계약은 Deal당 하나, 종료일은 서버가 `시작일 + 기간 - 1일`로 계산한다.
 */

import { describe, expect, it } from 'vitest'
import type { Gateway } from '../types'
import type { DealInput } from '../../shared/model/types'
import { expectRejects, NO_SUCH_ID, unique, type MakeGateway, anyVendorId } from './support'

const FIELDS = { techOwner: '', inspection: 'none', note: '' } as const
const DEFAULT_QUERY = { sort: 'licenseEnd', order: 'asc' } as const
const NOT_ISSUED_ONLY = '미발급 계약만 발급할 수 있습니다.'
const ISSUED_ONLY = '발급 상태 계약만 갱신할 수 있습니다.'
const ALREADY_ENDED = '이미 종료된 계약입니다.'
const DELETE_ADMIN_ONLY = '계약 삭제는 관리자만 할 수 있습니다.'
const WON_EXIT_BLOCKED =
  '발급된 라이선스 계약이 있는 Deal은 Won에서 다른 상태로 바꿀 수 없습니다. 계약 정보가 잘못되었다면 관리자에게 계약 삭제를 요청하세요.'
const DEAL_NOT_WON = 'Won인 Deal의 계약만 발급하거나 갱신할 수 있습니다.'
const LEAVE_WON = { change: { field: 'forecastKey', value: 'commit' }, resolution: { statusKey: 'technical_evaluation' } } as const
const ENTER_WON = { change: { field: 'forecastKey', value: 'won' }, resolution: { revenueAmount: 900_000_000, revenueDate: '2027-02-01' } } as const
const YEAR = { ...FIELDS, start: '2026-01-01', term: { amount: 1, unit: 'year' } } as const

/** 유효한 Deal 등록 입력(담당자는 영업 역할 사용자, 없으면 로그인한 사용자). 이름·고객 회사명은 호출마다 고유하다. */
async function validInput(gateway: Gateway, over: Partial<DealInput>): Promise<DealInput> {
  const owner = (await gateway.users.options({ role: 'sales' }))[0]?.id ?? (await gateway.auth.me()).id
  return {
    name: unique('deal'),
    ownerId: owner,
    vendorId: await anyVendorId(gateway),
    product: 'ITDR',
    users: 10,
    statusKey: 'prospecting',
    forecastKey: 'pipeline',
    revenueAmount: 500_000_000,
    revenueDate: '2027-01-31',
    customer: { contactId: null, company: unique('co'), name: unique('nm'), title: '', email: null, phone: null },
    partner: null,
    quote: { submitted: null, submittedDate: null },
    poc: { state: null, completedDate: null },
    procurement: '',
    bant: { budget: null, authority: null, need: null, timeline: null },
    ...over,
  }
}

/** Won으로 등록한 Deal 하나와 그 Deal의 자동 생성 계약(미발급). */
async function wonDeal(gateway: Gateway, name: string, company?: string) {
  const deal = await gateway.deals.create(await validInput(gateway, { name, statusKey: 'contract_completed', forecastKey: 'won', ...(company ? { customer: { contactId: null, company, name: unique('nm'), title: '', email: null, phone: null } } : {}) }))
  const page = await gateway.licenseContracts.list(DEFAULT_QUERY, 0, 200)
  const contract = page.items.find((c) => c.dealCode === deal.code)
  if (!contract) throw new Error('Won 등록 Deal의 계약이 자동 생성되지 않았다')
  return { deal, contract }
}

export function licenseContractsContract(make: MakeGateway): void {
  describe('licenseContracts 계약', () => {
    it('Deal을 Won으로 등록하면 미발급 계약 하나가 생긴다', async () => {
      const gateway = await make('admin')

      // when: Deal을 Won으로 등록해 자동 생성된 계약을 읽는다
      const { deal, contract } = await wonDeal(gateway, unique('lc'))

      // then: 미발급 기본값의 계약이고 Deal의 계약 건수가 1이다
      expect(contract).toMatchObject({ dealCode: deal.code, status: 'not_issued', licenseStart: null, licenseEnd: null, term: null })
      expect(contract).toMatchObject({ techOwner: '', inspection: 'none', note: '', renewedFromId: null, endedOn: null, attachmentCount: 0 })
      expect((await gateway.deals.get(deal.code)).licenseContractCount).toBe(1)
      await gateway.deals.remove(deal.code, deal.code)
    })

    it('변경으로 Deal이 Won이 되면 계약이 생기고 이미 계약이 있으면 더 만들지 않는다', async () => {
      const gateway = await make('admin')
      // given: Won이 아닌 Deal
      const deal = await gateway.deals.create(await validInput(gateway, { name: unique('lc') }))

      // when: Deal의 계약 건수를 읽는다
      const before = await gateway.deals.get(deal.code)
      // then: 계약이 아직 없다
      expect(before.licenseContractCount).toBe(0)

      // when: 변경으로 Won이 된다
      await gateway.deals.applyChange(deal.code, { change: { field: 'forecastKey', value: 'won' }, resolution: { revenueAmount: 900_000_000, revenueDate: '2027-02-01' } })
      // then: 계약이 한 건 생긴다
      expect((await gateway.deals.get(deal.code)).licenseContractCount).toBe(1)

      // when: Won을 벗어났다가 다시 Won이 된다
      await gateway.deals.applyChange(deal.code, { change: { field: 'forecastKey', value: 'commit' }, resolution: { statusKey: 'technical_evaluation' } })
      await gateway.deals.applyChange(deal.code, { change: { field: 'forecastKey', value: 'won' }, resolution: { revenueAmount: 900_000_000, revenueDate: '2027-02-01' } })

      // then: 재진입에는 계약을 더 만들지 않아 여전히 한 건이다
      expect((await gateway.deals.get(deal.code)).licenseContractCount).toBe(1)
      await gateway.deals.remove(deal.code, deal.code)
    })

    it('Won을 벗어날 때 deleteLicenseContracts를 켠 경우에만 계약을 삭제한다', async () => {
      const gateway = await make('admin')
      const { deal } = await wonDeal(gateway, unique('lc'))
      const leave = { change: { field: 'forecastKey', value: 'commit' }, resolution: { statusKey: 'technical_evaluation' } } as const

      // when: 삭제 없이 Won을 벗어난다
      await gateway.deals.applyChange(deal.code, { ...leave, deleteLicenseContracts: false })
      // then: 계약이 남는다
      expect((await gateway.deals.get(deal.code)).licenseContractCount).toBe(1)

      // when: 삭제를 켠 채 Won에 다시 들어온다
      await gateway.deals.applyChange(deal.code, { change: { field: 'forecastKey', value: 'won' }, resolution: { revenueAmount: 1_000, revenueDate: '2027-02-01' }, deleteLicenseContracts: true })
      // then: Won 진입에는 삭제 요청이 무시되어 계약이 남는다
      expect((await gateway.deals.get(deal.code)).licenseContractCount).toBe(1)

      // when: 삭제를 켜고 다시 Won을 벗어난다
      await gateway.deals.applyChange(deal.code, { ...leave, deleteLicenseContracts: true })
      // then: 이번에만 계약이 지워진다
      expect((await gateway.deals.get(deal.code)).licenseContractCount).toBe(0)
      await gateway.deals.remove(deal.code, deal.code)
    })

    it('계약은 정의된 필드를 Deal 값과 정수 id로 돌려준다', async () => {
      const gateway = await make('sales')

      // when: 영업이 Won으로 등록한 Deal의 계약을 읽는다
      const { deal, contract } = await wonDeal(gateway, unique('lc'))

      // then: id는 정수이고 Deal 값이 채워지며 필드 집합이 정의와 같다
      expect(Number.isInteger(contract.id)).toBe(true)
      expect(contract.dealName).toBe(deal.name)
      expect(contract.customer).toBe(deal.customer.company)
      expect(contract.product).toBe(deal.product)
      expect(contract.salesOwner.id).toBe(deal.owner.id)
      expect(Object.keys(contract).sort()).toEqual(
        ['attachmentCount', 'createdAt', 'createdBy', 'customer', 'dealCode', 'dealIsWon', 'dealName', 'endedOn', 'id', 'inspection', 'licenseEnd', 'licenseStart', 'note', 'partner', 'product', 'renewedFromId', 'salesOwner', 'status', 'techOwner', 'term', 'updatedAt', 'updatedBy', 'vendor'].sort(),
      )
      await make('admin').then((g) => g.deals.remove(deal.code, deal.code))
    })

    it('미발급 계약을 발급하면 종료일을 계산한다', async () => {
      const gateway = await make('sales')
      const { deal, contract } = await wonDeal(gateway, unique('lc'))

      // when: 시작일 1월 31일, 기간 1개월로 발급한다
      const issued = await gateway.licenseContracts.issue(contract.id, { ...FIELDS, techOwner: '이기술', start: '2026-01-31', term: { amount: 1, unit: 'month' } })

      // then: 발급(신규)이 되고 종료일은 시작일+기간-1일을 말일에 맞춘 2월 28일이며, 다시 발급하면 409다
      expect(issued).toMatchObject({ status: 'issued_new', licenseStart: '2026-01-31', licenseEnd: '2026-02-28', term: { amount: 1, unit: 'month' }, techOwner: '이기술' })
      await expectRejects(gateway.licenseContracts.issue(contract.id, { ...FIELDS, start: '2027-01-01', term: { amount: 1, unit: 'year' } }), 409, NOT_ISSUED_ONLY)
      await make('admin').then((g) => g.deals.remove(deal.code, deal.code))
    })

    it('발급 계약을 갱신하면 새 행이 생기고 이전 행은 종료되며 Deal당 발급 계약은 하나다', async () => {
      const gateway = await make('sales')
      const { deal, contract } = await wonDeal(gateway, unique('lc'))
      await gateway.licenseContracts.issue(contract.id, { ...FIELDS, start: '2026-01-01', term: { amount: 1, unit: 'year' } })

      // when: 2027-01-01부터 2년으로 갱신한다
      const renewal = await gateway.licenseContracts.renew(contract.id, { ...FIELDS, note: '갱신', start: '2027-01-01', term: { amount: 2, unit: 'year' } })

      // then: 새 행이 이전 행을 가리키고, 이전 행은 종료되며, 발급 상태 계약은 하나뿐이고, 갱신된 행을 또 갱신하면 409다
      expect(renewal).toMatchObject({ status: 'issued_renewal', renewedFromId: contract.id, licenseStart: '2027-01-01', licenseEnd: '2028-12-31', note: '갱신', dealCode: deal.code })
      expect(renewal.id).not.toBe(contract.id)
      expect((await gateway.licenseContracts.get(contract.id)).status).toBe('ended')
      const all = (await gateway.licenseContracts.list(DEFAULT_QUERY, 0, 200)).items.filter((c) => c.dealCode === deal.code)
      expect(all.filter((c) => c.status === 'issued_new' || c.status === 'issued_renewal')).toHaveLength(1)
      await expectRejects(gateway.licenseContracts.renew(contract.id, { ...FIELDS, start: '2028-01-01', term: { amount: 1, unit: 'year' } }), 409, ISSUED_ONLY)
      await make('admin').then((g) => g.deals.remove(deal.code, deal.code))
    })

    it('계약은 한 번만 종료되고 종료 뒤에도 수정할 수 있다', async () => {
      const gateway = await make('sales')
      const { deal, contract } = await wonDeal(gateway, unique('lc'))

      // when: 계약을 종료한다
      const ended = await gateway.licenseContracts.end(contract.id)

      // then: 종료 시각이 기록되고, 다시 종료·발급은 409이며, 수정은 계속 된다
      expect(ended.status).toBe('ended')
      expect(ended.endedOn).toMatch(/^\d{4}-\d{2}-\d{2}$/) // 종료일은 시각 없는 날짜다
      await expectRejects(gateway.licenseContracts.end(contract.id), 409, ALREADY_ENDED)
      await expectRejects(gateway.licenseContracts.issue(contract.id, { ...FIELDS, start: '2027-01-01', term: { amount: 1, unit: 'year' } }), 409, NOT_ISSUED_ONLY)
      const edited = await gateway.licenseContracts.update(contract.id, { techOwner: '종료 후', inspection: 'yearly', note: '메모' })
      expect(edited).toMatchObject({ status: 'ended', techOwner: '종료 후', inspection: 'yearly', note: '메모' })
      await make('admin').then((g) => g.deals.remove(deal.code, deal.code))
    })

    it('상태와 무관하게 계약 삭제는 관리자만 할 수 있다', async () => {
      const sales = await make('sales')
      const { deal, contract } = await wonDeal(sales, unique('lc'))

      // when·then: 영업이 삭제를 시도하면 403으로 거절된다
      await expectRejects(sales.licenseContracts.remove(contract.id), 403, DELETE_ADMIN_ONLY)

      // when: 관리자가 삭제한다
      const admin = await make('admin')
      await admin.licenseContracts.remove(contract.id)

      // then: 계약이 사라지고 Deal의 계약 건수가 0이다
      await expectRejects(admin.licenseContracts.get(contract.id), 404)
      expect((await admin.deals.get(deal.code)).licenseContractCount).toBe(0)
      await admin.deals.remove(deal.code, deal.code)
    })

    it('조회 전용 사용자의 쓰기는 거절하고 없는 id는 404로 답한다', async () => {
      const sales = await make('sales')
      const { deal, contract } = await wonDeal(sales, unique('lc'))
      const user = await make('user')

      // when: 조회 전용 사용자가 계약을 조회한다
      const found = await user.licenseContracts.get(contract.id)
      // then: 조회된다
      expect(found.id).toBe(contract.id)

      // when·then: 같은 사용자의 수정·종료·발급은 403, 없는 id 조회는 404다
      await expectRejects(user.licenseContracts.update(contract.id, { techOwner: 'x', inspection: 'none', note: '' }), 403)
      await expectRejects(user.licenseContracts.end(contract.id), 403)
      await expectRejects(user.licenseContracts.issue(contract.id, { ...FIELDS, start: '2027-01-01', term: { amount: 1, unit: 'year' } }), 403)
      await expectRejects(user.licenseContracts.get(NO_SUCH_ID), 404)
      await make('admin').then((g) => g.deals.remove(deal.code, deal.code))
    })

    it('잘못된 기간과 너무 긴 필드는 422로 거절한다', async () => {
      const gateway = await make('sales')
      const { deal, contract } = await wonDeal(gateway, unique('lc'))

      // when·then: 기간 0·100, 기술담당 101자, Note 2001자는 모두 422이고 계약은 그대로다
      await expectRejects(gateway.licenseContracts.issue(contract.id, { ...FIELDS, start: '2027-01-01', term: { amount: 0, unit: 'year' } }), 422)
      await expectRejects(gateway.licenseContracts.issue(contract.id, { ...FIELDS, start: '2027-01-01', term: { amount: 100, unit: 'year' } }), 422)
      await expectRejects(gateway.licenseContracts.update(contract.id, { techOwner: '가'.repeat(101), inspection: 'none', note: '' }), 422)
      await expectRejects(gateway.licenseContracts.update(contract.id, { techOwner: '', inspection: 'none', note: '가'.repeat(2001) }), 422)
      expect((await gateway.licenseContracts.get(contract.id)).status).toBe('not_issued')
      await make('admin').then((g) => g.deals.remove(deal.code, deal.code))
    })

    it('Deal 값으로 검색하고 전체 건수와 함께 쪽을 나눈다', async () => {
      const gateway = await make('sales')
      const tag = unique('lcs')
      const a = await wonDeal(gateway, `${tag}a`, `${tag}co`)
      const b = await wonDeal(gateway, `${tag}b`, `${tag}co`)
      await gateway.licenseContracts.issue(a.contract.id, { ...FIELDS, start: '2026-01-01', term: { amount: 1, unit: 'year' } })

      // when: 상태·시작일 조건과 고객사명 조건(대문자)으로 목록을 조회한다
      const issued = await gateway.licenseContracts.list({ ...DEFAULT_QUERY, status: 'issued_new', startFrom: '2026-01-01', startTo: '2026-01-01' }, 0, 200)
      // then: 조건에 맞는 계약만 나오고, 쪽 크기 1이어도 전체 건수는 2 이상이며, 거꾸로 된 기간은 422다
      expect(issued.items.map((c) => c.id)).toContain(a.contract.id)
      expect(issued.items.map((c) => c.id)).not.toContain(b.contract.id)
      const byCustomer = await gateway.licenseContracts.list({ ...DEFAULT_QUERY, customer: a.deal.customer.company.toUpperCase() }, 0, 1)
      expect(byCustomer.items).toHaveLength(1)
      expect(byCustomer.total).toBeGreaterThanOrEqual(2)
      await expectRejects(gateway.licenseContracts.list({ ...DEFAULT_QUERY, startFrom: '2026-02-01', startTo: '2026-01-01' }, 0, 10), 422)
      const admin = await make('admin')
      await admin.deals.remove(a.deal.code, a.deal.code)
      await admin.deals.remove(b.deal.code, b.deal.code)
    })

    it('열 정렬은 빈 값을 맨 뒤에 두고 같은 값은 id 순으로 정한다', async () => {
      const gateway = await make('sales')
      const { deal, contract } = await wonDeal(gateway, unique('lc'))

      // when: 시작일 오름·내림차순으로 조회한다
      const asc = await gateway.licenseContracts.list({ sort: 'licenseStart', order: 'asc' }, 0, 200)
      const desc = await gateway.licenseContracts.list({ sort: 'licenseStart', order: 'desc' }, 0, 200)

      // then: 빈 값이 두 방향 모두 맨 뒤에 있다
      expect(asc.items.at(-1)?.licenseStart).toBeNull()
      expect(desc.items.at(-1)?.licenseStart).toBeNull()
      expect(asc.items.map((c) => c.id)).toContain(contract.id)
      await make('admin').then((g) => g.deals.remove(deal.code, deal.code))
    })

    it('Deal 이름 정렬은 대소문자를 무시하고 오름·내림차순을 지원한다', async () => {
      const gateway = await make('sales')

      // when: Deal 이름 오름·내림차순으로 조회한다
      const asc = (await gateway.licenseContracts.list({ sort: 'dealName', order: 'asc' }, 0, 200)).items.map((c) => c.dealName.toLowerCase())
      const desc = (await gateway.licenseContracts.list({ sort: 'dealName', order: 'desc' }, 0, 200)).items.map((c) => c.dealName.toLowerCase())

      // then: 대소문자를 무시한 순서로 정렬되어 있다
      expect(asc.length).toBeGreaterThan(0)
      expect(asc).toEqual([...asc].sort())
      expect(desc).toEqual([...desc].sort().reverse())
    })

    it('계약 첨부를 Deal과 같은 규칙으로 올리고 조회·내려받기·삭제한다', async () => {
      const gateway = await make('sales')
      const { deal, contract } = await wonDeal(gateway, unique('lc'))
      const file = new File(['hello'], 'contract.pdf', { type: 'application/pdf' })

      // when: 첨부를 올리고 목록을 읽는다
      const uploaded = await gateway.licenseContracts.attachments.upload(contract.id, { file, description: '최종본', onExists: 'ask' })
      const listed = await gateway.licenseContracts.attachments.list(contract.id)
      // then: 올린 결과가 목록과 계약의 첨부 건수에 반영된다
      expect(uploaded.outcome).toBe('uploaded')
      expect(listed.map((a) => a.fileName)).toEqual(['contract.pdf'])
      expect((await gateway.licenseContracts.get(contract.id)).attachmentCount).toBe(1)

      // when·then: 같은 파일을 묻기 방식으로 다시 올리면 409다
      await expectRejects(gateway.licenseContracts.attachments.upload(contract.id, { file, description: '', onExists: 'ask' }), 409)

      // when: 같은 파일을 건너뛰기 방식으로 다시 올린다
      const skipped = await gateway.licenseContracts.attachments.upload(contract.id, { file, description: '', onExists: 'skip' })
      // then: 건너뛴 것으로 응답한다
      expect(skipped.outcome).toBe('skipped')

      // when: 첨부를 내려받는다
      const downloaded = await gateway.licenseContracts.attachments.download(listed[0]!.id)
      // then: 파일 이름이 올린 것과 같다
      expect(downloaded.fileName).toBe('contract.pdf')

      // when: 첨부를 삭제한다
      await gateway.licenseContracts.attachments.remove(listed[0]!.id)
      // then: 첨부 목록이 비어 있다
      expect(await gateway.licenseContracts.attachments.list(contract.id)).toEqual([])
      await make('admin').then((g) => g.deals.remove(deal.code, deal.code))
    })

    it('발급 계약이 있으면 deleteLicenseContracts 값과 무관하게 Won을 벗어나는 것을 거절한다', async () => {
      const gateway = await make('sales')
      const { deal, contract } = await wonDeal(gateway, unique('lc'))
      await gateway.licenseContracts.issue(contract.id, YEAR)

      // when·then: 삭제 플래그가 없거나 true·false여도 Won 이탈은 409이고 Deal과 계약은 그대로다
      for (const flag of [undefined, true, false]) {
        await expectRejects(gateway.deals.applyChange(deal.code, { ...LEAVE_WON, ...(flag === undefined ? {} : { deleteLicenseContracts: flag }) }), 409, WON_EXIT_BLOCKED)
      }

      const after = await gateway.deals.get(deal.code)
      expect([after.statusKey, after.forecastKey]).toEqual(['contract_completed', 'won'])
      expect((await gateway.licenseContracts.get(contract.id)).status).toBe('issued_new')
      await make('admin').then((g) => g.deals.remove(deal.code, deal.code))
    })

    it('미발급 또는 종료 계약만 있는 Deal은 Won을 벗어날 수 있다', async () => {
      const gateway = await make('sales')
      const waiting = await wonDeal(gateway, unique('lc'))
      const ended = await wonDeal(gateway, unique('lc'))
      await gateway.licenseContracts.issue(ended.contract.id, YEAR)
      await gateway.licenseContracts.end(ended.contract.id)

      // when: 미발급 계약 Deal은 삭제를 켜고, 종료 계약 Deal은 삭제를 끄고 Won을 벗어난다
      await gateway.deals.applyChange(waiting.deal.code, { ...LEAVE_WON, deleteLicenseContracts: true })
      await gateway.deals.applyChange(ended.deal.code, { ...LEAVE_WON, deleteLicenseContracts: false })

      // then: 미발급 계약은 삭제되고 종료 계약은 남는다
      expect((await gateway.deals.get(waiting.deal.code)).licenseContractCount).toBe(0)
      expect((await gateway.deals.get(ended.deal.code)).licenseContractCount).toBe(1)
      const admin = await make('admin')
      await admin.deals.remove(waiting.deal.code, waiting.deal.code)
      await admin.deals.remove(ended.deal.code, ended.deal.code)
    })

    it('관리자가 발급 계약을 삭제하면 Deal이 Won을 벗어날 수 있다', async () => {
      const gateway = await make('sales')
      const { deal, contract } = await wonDeal(gateway, unique('lc'))
      await gateway.licenseContracts.issue(contract.id, YEAR)
      // given: 발급 계약이 있어 Won 이탈이 막힌 Deal을 관리자가 계약 삭제로 정정한다
      await expectRejects(gateway.deals.applyChange(deal.code, LEAVE_WON), 409, WON_EXIT_BLOCKED)
      const admin = await make('admin')
      await admin.licenseContracts.remove(contract.id)

      // when: 이제 Won을 벗어난다
      await gateway.deals.applyChange(deal.code, { ...LEAVE_WON, deleteLicenseContracts: true })

      // then: 벗어나서 Forecast가 commit이다
      expect((await gateway.deals.get(deal.code)).forecastKey).toBe('commit')
      await admin.deals.remove(deal.code, deal.code)
    })

    it('발급 계약이 있을 때 Won을 벗어나는 Deal 수정과 Action 등록은 거절한다', async () => {
      const gateway = await make('sales')
      const { deal, contract } = await wonDeal(gateway, unique('lc'))
      await gateway.licenseContracts.issue(contract.id, YEAR)

      // when·then: 폼 수정과 Action 등록으로 Won을 벗어나려 하면 409이고 Deal 상태와 Action 목록은 그대로다
      await expectRejects(gateway.deals.update(deal.code, { statusKey: 'technical_evaluation', forecastKey: 'commit', deleteLicenseContracts: true }), 409, WON_EXIT_BLOCKED)
      await expectRejects(
        gateway.actions.create(deal.code, {
          type: { name: '미팅' },
          progress: '고객사 방문',
          nextAction: '',
          dueDate: null,
          memo: '',
          statusChanges: [LEAVE_WON],
          deleteLicenseContracts: true,
        }),
        409,
        WON_EXIT_BLOCKED,
      )

      expect((await gateway.deals.get(deal.code)).forecastKey).toBe('won')
      expect(await gateway.actions.list(deal.code, {})).toEqual([])
      await make('admin').then((g) => g.deals.remove(deal.code, deal.code))
    })

    it('Won이 아닌 Deal의 발급·갱신은 거절하지만 수정과 종료는 허용한다', async () => {
      const gateway = await make('sales')
      const waiting = await wonDeal(gateway, unique('lc'))
      await gateway.deals.applyChange(waiting.deal.code, { ...LEAVE_WON, deleteLicenseContracts: false })

      // when·then: 발급·갱신은 409이고 계약은 미발급 그대로이며, 수정과 종료는 된다
      await expectRejects(gateway.licenseContracts.issue(waiting.contract.id, YEAR), 409, DEAL_NOT_WON)
      await expectRejects(gateway.licenseContracts.renew(waiting.contract.id, YEAR), 409, DEAL_NOT_WON)
      expect((await gateway.licenseContracts.get(waiting.contract.id)).status).toBe('not_issued')
      const edited = await gateway.licenseContracts.update(waiting.contract.id, { techOwner: '수정', inspection: 'yearly', note: '' })
      expect(edited.techOwner).toBe('수정')
      expect((await gateway.licenseContracts.end(waiting.contract.id)).status).toBe('ended')

      await gateway.deals.applyChange(waiting.deal.code, ENTER_WON)
      const again = await wonDeal(gateway, unique('lc'))
      expect((await gateway.licenseContracts.issue(again.contract.id, YEAR)).status).toBe('issued_new')
      const admin = await make('admin')
      await admin.deals.remove(waiting.deal.code, waiting.deal.code)
      await admin.deals.remove(again.deal.code, again.deal.code)
    })

    it('Deal은 hasIssuedLicenseContract를, 계약은 dealIsWon을 알려 준다', async () => {
      const gateway = await make('sales')
      const { deal, contract } = await wonDeal(gateway, unique('lc'))
      const flag = async () => [(await gateway.deals.get(deal.code)).hasIssuedLicenseContract, (await gateway.deals.list({ keyword: deal.name, limit: 50 })).items.find((d) => d.code === deal.code)?.hasIssuedLicenseContract]

      // when: 발급 전에 Deal 상세·목록의 플래그를 읽는다
      const initial = await flag()
      // then: 플래그가 모두 false이고 Deal이 Won이라 계약의 dealIsWon은 true이다
      expect(initial).toEqual([false, false])
      expect(contract.dealIsWon).toBe(true)

      // when: 계약을 발급한다
      await gateway.licenseContracts.issue(contract.id, YEAR)
      // then: Deal 상세·목록의 플래그가 true이다
      expect(await flag()).toEqual([true, true])

      // when: 계약을 갱신한다
      const renewal = await gateway.licenseContracts.renew(contract.id, { ...YEAR, start: '2027-01-01' })
      // then: 플래그는 계속 true이다
      expect(await flag()).toEqual([true, true])

      // when: 갱신된 계약을 종료한다
      await gateway.licenseContracts.end(renewal.id)
      // then: 플래그가 false로 돌아온다
      expect(await flag()).toEqual([false, false])

      // when: Deal이 Won을 벗어난다
      await gateway.deals.applyChange(deal.code, LEAVE_WON)
      const left = await gateway.licenseContracts.get(contract.id)
      // then: 계약의 dealIsWon이 false이다
      expect(left.dealIsWon).toBe(false)
      await make('admin').then((g) => g.deals.remove(deal.code, deal.code))
    })

    it('Deal을 삭제하면 계약도 함께 삭제되고 삭제 영향에 건수가 잡힌다', async () => {
      const gateway = await make('admin')
      const { deal, contract } = await wonDeal(gateway, unique('lc'))

      // when: Deal의 삭제 영향을 읽는다
      const impact = await gateway.deals.impact(deal.code)
      // then: 영향에 계약 1건이 잡힌다
      expect(impact.licenseContractCount).toBe(1)

      // when: Deal을 삭제한다
      await gateway.deals.remove(deal.code, deal.code)
      // then: 계약도 함께 삭제되어 404다
      await expectRejects(gateway.licenseContracts.get(contract.id), 404)
    })
  })
}
