/**
 * 라이선스 계약(계약관리) 계약. mock과 실제 서버가 같은 규칙을 지킨다.
 * 계약은 Deal이 Won이 될 때 자동으로 생긴다(수동 생성 API 없음). 그래서 스위트는 Deal을 Won으로 만들어 계약을 얻고
 * 호출마다 고유한 이름을 쓰며, 만든 것은 스스로 치운다(Deal 삭제는 계약을 함께 지운다).
 * 규칙: 발급 상태(발급(신규)·발급(갱신)) 계약은 Deal당 하나, 종료일은 서버가 `시작일 + 기간 - 1일`로 계산한다.
 */

import { describe, expect, it } from 'vitest'
import type { Gateway } from '../types'
import type { DealInput } from '../../shared/model/types'
import { expectRejects, NO_SUCH_ID, unique, type MakeGateway } from './support'

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
    vendorId: null,
    solution: 'ITDR',
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
    it('creates one not-issued contract when a deal is registered as Won (AC6)', async () => {
      const gateway = await make('admin')
      const { deal, contract } = await wonDeal(gateway, unique('lc'))

      expect(contract).toMatchObject({ dealCode: deal.code, status: 'not_issued', licenseStart: null, licenseEnd: null, term: null })
      expect(contract).toMatchObject({ techOwner: '', inspection: 'none', note: '', renewedFromId: null, endedAt: null, attachmentCount: 0 })
      expect((await gateway.deals.get(deal.code)).licenseContractCount).toBe(1)
      await gateway.deals.remove(deal.code, deal.code)
    })

    it('creates a contract when a deal enters Won by a change and not when it already has one (AC6)', async () => {
      const gateway = await make('admin')
      const deal = await gateway.deals.create(await validInput(gateway, { name: unique('lc') }))
      expect((await gateway.deals.get(deal.code)).licenseContractCount).toBe(0)

      await gateway.deals.applyChange(deal.code, { change: { field: 'forecastKey', value: 'won' }, resolution: { revenueAmount: 900_000_000, revenueDate: '2027-02-01' } })
      expect((await gateway.deals.get(deal.code)).licenseContractCount).toBe(1)
      await gateway.deals.applyChange(deal.code, { change: { field: 'forecastKey', value: 'commit' }, resolution: { statusKey: 'technical_evaluation' } })
      await gateway.deals.applyChange(deal.code, { change: { field: 'forecastKey', value: 'won' }, resolution: { revenueAmount: 900_000_000, revenueDate: '2027-02-01' } })

      expect((await gateway.deals.get(deal.code)).licenseContractCount).toBe(1)
      await gateway.deals.remove(deal.code, deal.code)
    })

    it('deletes the contracts only when leaving Won with deleteLicenseContracts (AC7, AC8)', async () => {
      const gateway = await make('admin')
      const { deal } = await wonDeal(gateway, unique('lc'))
      const leave = { change: { field: 'forecastKey', value: 'commit' }, resolution: { statusKey: 'technical_evaluation' } } as const

      await gateway.deals.applyChange(deal.code, { ...leave, deleteLicenseContracts: false })
      expect((await gateway.deals.get(deal.code)).licenseContractCount).toBe(1)
      await gateway.deals.applyChange(deal.code, { change: { field: 'forecastKey', value: 'won' }, resolution: { revenueAmount: 1_000, revenueDate: '2027-02-01' }, deleteLicenseContracts: true })
      expect((await gateway.deals.get(deal.code)).licenseContractCount).toBe(1) // Won 진입에는 무시된다
      await gateway.deals.applyChange(deal.code, { ...leave, deleteLicenseContracts: true })

      expect((await gateway.deals.get(deal.code)).licenseContractCount).toBe(0)
      await gateway.deals.remove(deal.code, deal.code)
    })

    it('returns the documented fields with the deal values and integer ids (AC1, Q1)', async () => {
      const gateway = await make('sales')
      const { deal, contract } = await wonDeal(gateway, unique('lc'))

      expect(Number.isInteger(contract.id)).toBe(true)
      expect(contract.dealName).toBe(deal.name)
      expect(contract.customer).toBe(deal.customer.company)
      expect(contract.product).toBe(deal.solution)
      expect(contract.salesOwner.id).toBe(deal.owner.id)
      expect(Object.keys(contract).sort()).toEqual(
        ['attachmentCount', 'createdAt', 'createdBy', 'customer', 'dealCode', 'dealIsWon', 'dealName', 'endedAt', 'id', 'inspection', 'licenseEnd', 'licenseStart', 'note', 'partner', 'product', 'renewedFromId', 'salesOwner', 'status', 'techOwner', 'term', 'updatedAt', 'updatedBy', 'vendor'].sort(),
      )
      await make('admin').then((g) => g.deals.remove(deal.code, deal.code))
    })

    it('issues a not-issued contract and computes the end date (AC4, AC12)', async () => {
      const gateway = await make('sales')
      const { deal, contract } = await wonDeal(gateway, unique('lc'))

      const issued = await gateway.licenseContracts.issue(contract.id, { ...FIELDS, techOwner: '이기술', start: '2026-01-31', term: { amount: 1, unit: 'month' } })

      expect(issued).toMatchObject({ status: 'issued_new', licenseStart: '2026-01-31', licenseEnd: '2026-02-28', term: { amount: 1, unit: 'month' }, techOwner: '이기술' })
      await expectRejects(gateway.licenseContracts.issue(contract.id, { ...FIELDS, start: '2027-01-01', term: { amount: 1, unit: 'year' } }), 409, NOT_ISSUED_ONLY)
      await make('admin').then((g) => g.deals.remove(deal.code, deal.code))
    })

    it('renews an issued contract: a new row, the previous one ended, one issued contract per deal (AC3, AC13)', async () => {
      const gateway = await make('sales')
      const { deal, contract } = await wonDeal(gateway, unique('lc'))
      await gateway.licenseContracts.issue(contract.id, { ...FIELDS, start: '2026-01-01', term: { amount: 1, unit: 'year' } })

      const renewal = await gateway.licenseContracts.renew(contract.id, { ...FIELDS, note: '갱신', start: '2027-01-01', term: { amount: 2, unit: 'year' } })

      expect(renewal).toMatchObject({ status: 'issued_renewal', renewedFromId: contract.id, licenseStart: '2027-01-01', licenseEnd: '2028-12-31', note: '갱신', dealCode: deal.code })
      expect(renewal.id).not.toBe(contract.id)
      expect((await gateway.licenseContracts.get(contract.id)).status).toBe('ended')
      const all = (await gateway.licenseContracts.list(DEFAULT_QUERY, 0, 200)).items.filter((c) => c.dealCode === deal.code)
      expect(all.filter((c) => c.status === 'issued_new' || c.status === 'issued_renewal')).toHaveLength(1)
      await expectRejects(gateway.licenseContracts.renew(contract.id, { ...FIELDS, start: '2028-01-01', term: { amount: 1, unit: 'year' } }), 409, ISSUED_ONLY)
      await make('admin').then((g) => g.deals.remove(deal.code, deal.code))
    })

    it('ends a contract once and keeps edits and attachments possible afterwards (AC14)', async () => {
      const gateway = await make('sales')
      const { deal, contract } = await wonDeal(gateway, unique('lc'))

      const ended = await gateway.licenseContracts.end(contract.id)

      expect(ended.status).toBe('ended')
      expect(ended.endedAt).not.toBeNull()
      await expectRejects(gateway.licenseContracts.end(contract.id), 409, ALREADY_ENDED)
      await expectRejects(gateway.licenseContracts.issue(contract.id, { ...FIELDS, start: '2027-01-01', term: { amount: 1, unit: 'year' } }), 409, NOT_ISSUED_ONLY)
      const edited = await gateway.licenseContracts.update(contract.id, { techOwner: '종료 후', inspection: 'yearly', note: '메모' })
      expect(edited).toMatchObject({ status: 'ended', techOwner: '종료 후', inspection: 'yearly', note: '메모' })
      await make('admin').then((g) => g.deals.remove(deal.code, deal.code))
    })

    it('lets only an admin delete a contract, whatever its status (AC15)', async () => {
      const sales = await make('sales')
      const { deal, contract } = await wonDeal(sales, unique('lc'))

      await expectRejects(sales.licenseContracts.remove(contract.id), 403, DELETE_ADMIN_ONLY)
      const admin = await make('admin')
      await admin.licenseContracts.remove(contract.id)

      await expectRejects(admin.licenseContracts.get(contract.id), 404)
      expect((await admin.deals.get(deal.code)).licenseContractCount).toBe(0)
      await admin.deals.remove(deal.code, deal.code)
    })

    it('refuses writes to a read-only user and answers 404 for unknown ids (AC16)', async () => {
      const sales = await make('sales')
      const { deal, contract } = await wonDeal(sales, unique('lc'))
      const user = await make('user')

      expect((await user.licenseContracts.get(contract.id)).id).toBe(contract.id)
      await expectRejects(user.licenseContracts.update(contract.id, { techOwner: 'x', inspection: 'none', note: '' }), 403)
      await expectRejects(user.licenseContracts.end(contract.id), 403)
      await expectRejects(user.licenseContracts.issue(contract.id, { ...FIELDS, start: '2027-01-01', term: { amount: 1, unit: 'year' } }), 403)
      await expectRejects(user.licenseContracts.get(NO_SUCH_ID), 404)
      await make('admin').then((g) => g.deals.remove(deal.code, deal.code))
    })

    it('rejects an invalid period and over-long fields with 422 (AC11)', async () => {
      const gateway = await make('sales')
      const { deal, contract } = await wonDeal(gateway, unique('lc'))

      await expectRejects(gateway.licenseContracts.issue(contract.id, { ...FIELDS, start: '2027-01-01', term: { amount: 0, unit: 'year' } }), 422)
      await expectRejects(gateway.licenseContracts.issue(contract.id, { ...FIELDS, start: '2027-01-01', term: { amount: 100, unit: 'year' } }), 422)
      await expectRejects(gateway.licenseContracts.update(contract.id, { techOwner: '가'.repeat(101), inspection: 'none', note: '' }), 422)
      await expectRejects(gateway.licenseContracts.update(contract.id, { techOwner: '', inspection: 'none', note: '가'.repeat(2001) }), 422)
      expect((await gateway.licenseContracts.get(contract.id)).status).toBe('not_issued')
      await make('admin').then((g) => g.deals.remove(deal.code, deal.code))
    })

    it('searches by the deal values and pages with the total (AC17)', async () => {
      const gateway = await make('sales')
      const tag = unique('lcs')
      const a = await wonDeal(gateway, `${tag}a`, `${tag}co`)
      const b = await wonDeal(gateway, `${tag}b`, `${tag}co`)
      await gateway.licenseContracts.issue(a.contract.id, { ...FIELDS, start: '2026-01-01', term: { amount: 1, unit: 'year' } })

      const issued = await gateway.licenseContracts.list({ ...DEFAULT_QUERY, status: 'issued_new', startFrom: '2026-01-01', startTo: '2026-01-01' }, 0, 200)
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

    it('sorts by a column with empty values last and ties by id (AC18)', async () => {
      const gateway = await make('sales')
      const { deal, contract } = await wonDeal(gateway, unique('lc'))

      const asc = await gateway.licenseContracts.list({ sort: 'licenseStart', order: 'asc' }, 0, 200)
      const desc = await gateway.licenseContracts.list({ sort: 'licenseStart', order: 'desc' }, 0, 200)

      expect(asc.items.at(-1)?.licenseStart).toBeNull()
      expect(desc.items.at(-1)?.licenseStart).toBeNull()
      expect(asc.items.map((c) => c.id)).toContain(contract.id)
      await make('admin').then((g) => g.deals.remove(deal.code, deal.code))
    })

    it('sorts by the deal name ignoring case, ascending and descending', async () => {
      const gateway = await make('sales')

      const asc = (await gateway.licenseContracts.list({ sort: 'dealName', order: 'asc' }, 0, 200)).items.map((c) => c.dealName.toLowerCase())
      const desc = (await gateway.licenseContracts.list({ sort: 'dealName', order: 'desc' }, 0, 200)).items.map((c) => c.dealName.toLowerCase())

      expect(asc.length).toBeGreaterThan(0)
      expect(asc).toEqual([...asc].sort())
      expect(desc).toEqual([...desc].sort().reverse())
    })

    it('uploads, lists, downloads and deletes a contract attachment with the deal rules (AC20)', async () => {
      const gateway = await make('sales')
      const { deal, contract } = await wonDeal(gateway, unique('lc'))
      const file = new File(['hello'], 'contract.pdf', { type: 'application/pdf' })

      const uploaded = await gateway.licenseContracts.attachments.upload(contract.id, { file, description: '최종본', onExists: 'ask' })
      expect(uploaded.outcome).toBe('uploaded')
      const listed = await gateway.licenseContracts.attachments.list(contract.id)
      expect(listed.map((a) => a.fileName)).toEqual(['contract.pdf'])
      expect((await gateway.licenseContracts.get(contract.id)).attachmentCount).toBe(1)
      await expectRejects(gateway.licenseContracts.attachments.upload(contract.id, { file, description: '', onExists: 'ask' }), 409)
      const skipped = await gateway.licenseContracts.attachments.upload(contract.id, { file, description: '', onExists: 'skip' })
      expect(skipped.outcome).toBe('skipped')
      const downloaded = await gateway.licenseContracts.attachments.download(listed[0]!.id)
      expect(downloaded.fileName).toBe('contract.pdf')
      await gateway.licenseContracts.attachments.remove(listed[0]!.id)
      expect(await gateway.licenseContracts.attachments.list(contract.id)).toEqual([])
      await make('admin').then((g) => g.deals.remove(deal.code, deal.code))
    })

    it('refuses to leave Won while an issued contract exists, whatever deleteLicenseContracts says (AC23)', async () => {
      const gateway = await make('sales')
      const { deal, contract } = await wonDeal(gateway, unique('lc'))
      await gateway.licenseContracts.issue(contract.id, YEAR)

      for (const flag of [undefined, true, false]) {
        await expectRejects(gateway.deals.applyChange(deal.code, { ...LEAVE_WON, ...(flag === undefined ? {} : { deleteLicenseContracts: flag }) }), 409, WON_EXIT_BLOCKED)
      }

      const after = await gateway.deals.get(deal.code)
      expect([after.statusKey, after.forecastKey]).toEqual(['contract_completed', 'won'])
      expect((await gateway.licenseContracts.get(contract.id)).status).toBe('issued_new')
      await make('admin').then((g) => g.deals.remove(deal.code, deal.code))
    })

    it('still lets a Deal with only a not-issued or ended contract leave Won (AC24)', async () => {
      const gateway = await make('sales')
      const waiting = await wonDeal(gateway, unique('lc'))
      const ended = await wonDeal(gateway, unique('lc'))
      await gateway.licenseContracts.issue(ended.contract.id, YEAR)
      await gateway.licenseContracts.end(ended.contract.id)

      await gateway.deals.applyChange(waiting.deal.code, { ...LEAVE_WON, deleteLicenseContracts: true })
      await gateway.deals.applyChange(ended.deal.code, { ...LEAVE_WON, deleteLicenseContracts: false })

      expect((await gateway.deals.get(waiting.deal.code)).licenseContractCount).toBe(0)
      expect((await gateway.deals.get(ended.deal.code)).licenseContractCount).toBe(1)
      const admin = await make('admin')
      await admin.deals.remove(waiting.deal.code, waiting.deal.code)
      await admin.deals.remove(ended.deal.code, ended.deal.code)
    })

    it('lets the Deal leave Won after an admin deletes the issued contract (AC25)', async () => {
      const gateway = await make('sales')
      const { deal, contract } = await wonDeal(gateway, unique('lc'))
      await gateway.licenseContracts.issue(contract.id, YEAR)
      await expectRejects(gateway.deals.applyChange(deal.code, LEAVE_WON), 409, WON_EXIT_BLOCKED)
      const admin = await make('admin')
      await admin.licenseContracts.remove(contract.id)

      await gateway.deals.applyChange(deal.code, { ...LEAVE_WON, deleteLicenseContracts: true })

      expect((await gateway.deals.get(deal.code)).forecastKey).toBe('commit')
      await admin.deals.remove(deal.code, deal.code)
    })

    it('rejects Deal form updates and action registrations that leave Won with an issued contract (AC23)', async () => {
      const gateway = await make('sales')
      const { deal, contract } = await wonDeal(gateway, unique('lc'))
      await gateway.licenseContracts.issue(contract.id, YEAR)

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

    it('rejects issue and renew on a Deal that is not Won, but still allows edits and ending (AC27)', async () => {
      const gateway = await make('sales')
      const waiting = await wonDeal(gateway, unique('lc'))
      await gateway.deals.applyChange(waiting.deal.code, { ...LEAVE_WON, deleteLicenseContracts: false })

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

    it('reports hasIssuedLicenseContract on the deal and dealIsWon on the contract (AC28)', async () => {
      const gateway = await make('sales')
      const { deal, contract } = await wonDeal(gateway, unique('lc'))
      const flag = async () => [(await gateway.deals.get(deal.code)).hasIssuedLicenseContract, (await gateway.deals.list({ keyword: deal.name, limit: 50 })).items.find((d) => d.code === deal.code)?.hasIssuedLicenseContract]

      expect(await flag()).toEqual([false, false])
      expect(contract.dealIsWon).toBe(true)
      await gateway.licenseContracts.issue(contract.id, YEAR)
      expect(await flag()).toEqual([true, true])
      const renewal = await gateway.licenseContracts.renew(contract.id, { ...YEAR, start: '2027-01-01' })
      expect(await flag()).toEqual([true, true])
      await gateway.licenseContracts.end(renewal.id)
      expect(await flag()).toEqual([false, false])
      await gateway.deals.applyChange(deal.code, LEAVE_WON)
      expect((await gateway.licenseContracts.get(contract.id)).dealIsWon).toBe(false)
      await make('admin').then((g) => g.deals.remove(deal.code, deal.code))
    })

    it('removes the contracts together with the deal and counts them in the deletion impact (AC21)', async () => {
      const gateway = await make('admin')
      const { deal, contract } = await wonDeal(gateway, unique('lc'))

      expect((await gateway.deals.impact(deal.code)).licenseContractCount).toBe(1)
      await gateway.deals.remove(deal.code, deal.code)

      await expectRejects(gateway.licenseContracts.get(contract.id), 404)
    })
  })
}
