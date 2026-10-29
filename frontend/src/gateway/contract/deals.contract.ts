/**
 * Deal 원장 계약(AC-05·AC-22·삭제·applyChange). mock과 실제 서버가 같은 결과를 내야 한다.
 * 시드에 기대지 않고 호출마다 고유한 Deal 이름·회사명으로 만든 Deal만 본다(만든 Deal은 스스로 지운다).
 */

import { describe, expect, it } from 'vitest'
import { DEAL_CODE_PATTERN } from '../../shared/model/constants'
import type { DealDetail, DealInput } from '../../shared/model/types'
import type { Gateway } from '../types'
import { action } from './actions.contract'
import { expectRejects, unique, type MakeGateway, NO_SUCH_ID } from './support'

const SYNC_MISMATCH = 'Status와 Forecast의 동기화가 맞지 않습니다.'
const REVENUE_NEEDED = 'Won·계약완료로 바꾸려면 매출금액과 매출일이 필요합니다.'
const CHOICE_NEEDED = '함께 바꿀 값을 선택하세요.'

/** 유효한 등록 입력. 이름·고객 회사명은 호출마다 고유하다(Vendor는 선택 안 함, Solution은 필수 텍스트). */
async function validInput(gateway: Gateway, over: Partial<DealInput> = {}): Promise<DealInput> {
  const me = await gateway.auth.me()
  return {
    name: unique('deal'),
    ownerId: me.id,
    vendorId: null,
    solution: 'ITDR',
    users: 10,
    statusKey: 'prospecting',
    forecastKey: 'pipeline',
    revenueAmount: 1_000_000,
    revenueDate: '2027-02-15',
    customer: { contactId: null, company: unique('co'), name: unique('nm'), title: '', email: null, phone: null },
    partner: null,
    quote: { submitted: null, submittedDate: null },
    poc: { state: null, completedDate: null },
    procurement: '',
    bant: { budget: null, authority: null, need: null, timeline: null },
    ...over,
  }
}

export function dealsContract(make: MakeGateway): void {
  describe('deals 계약', () => {
    it('registers a deal with a YYYYMMDD-XXXX code that can be read back', async () => {
      const sales = await make('sales')
      const input = await validInput(sales)

      const created = await sales.deals.create(input)

      expect(created.code).toMatch(DEAL_CODE_PATTERN)
      const read = await sales.deals.get(created.code)
      expect(read).toMatchObject({ name: input.name, ownerId: input.ownerId, statusKey: 'prospecting', forecastKey: 'pipeline', revenueAmount: 1_000_000 })
      expect(read.customer.company).toBe(input.customer.company)
      await sales.deals.remove(created.code, created.code)
    })

    it('refuses the user role to register with 403', async () => {
      const sales = await make('sales')
      const input = await validInput(sales)
      const user = await make('user')

      await expectRejects(user.deals.create(input), 403)
    })

    it('answers 404 for an unknown code', async () => {
      const { deals } = await make('sales')

      await expectRejects(deals.get('20000101-ZZZZ'), 404)
    })

    it('reports the first violation in the fixed order: name, amount, Expected Close, Users count, sync', async () => {
      const sales = await make('sales')
      const base = await validInput(sales)

      await expectRejects(sales.deals.create({ ...base, name: '  ', revenueAmount: 0 }), 422, 'Deal Name을 입력하세요.')
      await expectRejects(sales.deals.create({ ...base, revenueAmount: 0, revenueDate: '' }), 422, '매출금액은 1원 이상의 정수로 입력하세요.')
      await expectRejects(sales.deals.create({ ...base, revenueDate: '', users: -1 }), 422, 'Expected Close를 입력하세요.')
      await expectRejects(sales.deals.create({ ...base, users: -1, statusKey: 'contract_completed' }), 422, 'Users count는 0 이상의 정수로 입력하세요.')
      await expectRejects(sales.deals.create({ ...base, statusKey: 'contract_completed' }), 422, SYNC_MISMATCH)
    })

    it('checks the procurement length after Status and BANT, as the server does', async () => {
      const sales = await make('sales')
      const base = await validInput(sales)
      const tooLong = 'a'.repeat(501)

      await expectRejects(sales.deals.create({ ...base, procurement: tooLong, statusKey: 'no_such_status' }), 422, 'Status를 선택하세요.')
      await expectRejects(
        sales.deals.create({ ...base, procurement: tooLong, bant: { budget: { id: NO_SUCH_ID }, authority: null, need: null, timeline: null } }),
        422,
        'BANT Label이 올바르지 않습니다.',
      )
      await expectRejects(sales.deals.create({ ...base, procurement: tooLong }), 422, '구매절차는 500자 이내로 입력하세요.')
    })

    it('measures the Deal Name length after trimming', async () => {
      const sales = await make('sales')
      const created = await sales.deals.create(await validInput(sales, { name: ` ${'a'.repeat(200)}` }))

      expect(created.name).toBe('a'.repeat(200))
      await sales.deals.remove(created.code, created.code)
    })

    it('refuses an update that empties Expected Close with 422', async () => {
      const sales = await make('sales')
      const created = await sales.deals.create(await validInput(sales))

      await expectRejects(sales.deals.update(created.code, { revenueDate: '' }), 422, 'Expected Close를 입력하세요.')

      expect((await sales.deals.get(created.code)).revenueDate).toBe('2027-02-15')
      await sales.deals.remove(created.code, created.code)
    })

    it('records the creation as the only history entry of a new deal', async () => {
      const sales = await make('sales')
      const created = await sales.deals.create(await validInput(sales))

      const history = await sales.history.list(created.code, {})

      expect(history).toHaveLength(1)
      expect(history[0]).toMatchObject({ category: 'created', before: '', after: 'Deal 등록' })
      await sales.deals.remove(created.code, created.code)
    })

    it('applies a won change with the revenue answer and reports the co-changed status', async () => {
      const sales = await make('sales')
      const created = await sales.deals.create(await validInput(sales))

      const result = await sales.deals.applyChange(created.code, {
        change: { field: 'forecastKey', value: 'won' },
        resolution: { revenueAmount: 2_000_000, revenueDate: '2026-10-14' },
      })

      expect(result.deal).toMatchObject({ forecastKey: 'won', statusKey: 'contract_completed', revenueAmount: 2_000_000, revenueDate: '2026-10-14' })
      expect(result.coChanged).toEqual([{ field: 'statusKey', from: 'prospecting', to: 'contract_completed' }])
      expect(result.notice).not.toBeNull()
      await sales.deals.remove(created.code, created.code)
    })

    it('refuses the won change without the revenue answer and changes nothing', async () => {
      const sales = await make('sales')
      const created = await sales.deals.create(await validInput(sales))

      await expectRejects(sales.deals.applyChange(created.code, { change: { field: 'forecastKey', value: 'won' } }), 422, REVENUE_NEEDED)

      expect((await sales.deals.get(created.code)).forecastKey).toBe('pipeline')
      await sales.deals.remove(created.code, created.code)
    })

    it('asks which forecast to take when a contract-completed deal goes back', async () => {
      const sales = await make('sales')
      const created = await sales.deals.create(await validInput(sales))
      await sales.deals.applyChange(created.code, {
        change: { field: 'statusKey', value: 'contract_completed' },
        resolution: { revenueAmount: 2_000_000, revenueDate: '2026-10-14' },
      })

      await expectRejects(sales.deals.applyChange(created.code, { change: { field: 'statusKey', value: 'prospecting' } }), 422, CHOICE_NEEDED)
      const back = await sales.deals.applyChange(created.code, {
        change: { field: 'statusKey', value: 'prospecting' },
        resolution: { forecastKey: 'pipeline' },
      })

      expect(back.deal).toMatchObject({ statusKey: 'prospecting', forecastKey: 'pipeline' })
      await sales.deals.remove(created.code, created.code)
    })

    it('lists the history newest first and filters it by category', async () => {
      const sales = await make('sales')
      const created = await sales.deals.create(await validInput(sales))
      await sales.deals.applyChange(created.code, { change: { field: 'forecastKey', value: 'commit' } })

      const all = await sales.history.list(created.code, {})
      const forecast = await sales.history.list(created.code, { category: 'forecast' })

      expect(all.map((h) => h.category)).toEqual(['forecast', 'created'])
      expect(forecast).toHaveLength(1)
      expect(forecast[0]).toMatchObject({ target: 'Forecast', after: 'Commit' })
      await sales.deals.remove(created.code, created.code)
    })

    it('checks the delete permission (403) before the confirm code (422)', async () => {
      const sales = await make('sales')
      const created = await sales.deals.create(await validInput(sales))
      const user = await make('user')

      await expectRejects(user.deals.remove(created.code, 'wrong'), 403)
      const owner = await make('sales')
      await expectRejects(owner.deals.remove(created.code, 'wrong'), 422, 'Deal code가 일치하지 않습니다.')
      expect((await owner.deals.get(created.code)).code).toBe(created.code)

      await owner.deals.remove(created.code, created.code)
      await expectRejects(owner.deals.get(created.code), 404)
    })

    it('counts what a delete would remove', async () => {
      const sales = await make('sales')
      const created = await sales.deals.create(await validInput(sales))

      const impact = await sales.deals.impact(created.code)

      expect(impact).toEqual({ historyCount: 1, actionCount: 0, attachmentCount: 0, partnerMeetingCount: 0 })
      await sales.deals.remove(created.code, created.code)
    })

    it('returns vendor as null when none is chosen and the solution as entered', async () => {
      const sales = await make('sales')
      const created = await sales.deals.create(await validInput(sales, { solution: 'ITDR' }))

      expect(created.vendor).toBeNull()
      expect(created.solution).toBe('ITDR')
      await sales.deals.remove(created.code, created.code)
    })

    it('registers a deal with a vendor as {id, name} and a trimmed solution text and filters by them', async () => {
      const admin = await make('admin')
      const vendor = await admin.vendors.create(unique('vendor'))
      const sales = await make('sales')
      const text = unique('Solution')

      const created = await sales.deals.create(await validInput(sales, { vendorId: vendor.id, solution: `  ${text}  ` }))

      expect(created.vendor).toEqual({ id: vendor.id, name: vendor.name })
      expect(created.solution).toBe(text)
      expect((await sales.deals.list({ vendorId: vendor.id })).items.map((d) => d.code)).toEqual([created.code])
      expect((await sales.deals.list({ solution: text.toLowerCase() })).items.map((d) => d.code)).toEqual([created.code])
      expect((await sales.deals.list({ vendorId: vendor.id, solution: 'no-such-solution-text' })).total).toBe(0)
      await sales.deals.remove(created.code, created.code)
      const cleanup = await make('admin')
      await cleanup.vendors.remove(vendor.id)
    })

    it('accepts a solution text without a vendor and keeps it when the vendor changes', async () => {
      const admin = await make('admin')
      const vendor = await admin.vendors.create(unique('vendor'))
      const sales = await make('sales')
      const created = await sales.deals.create(await validInput(sales, { solution: 'ITDR' }))

      const withVendor = await sales.deals.update(created.code, { vendorId: vendor.id })
      const cleared = await sales.deals.update(created.code, { vendorId: null })

      expect(created.vendor).toBeNull()
      expect(withVendor.solution).toBe('ITDR')
      expect(cleared.solution).toBe('ITDR')
      await sales.deals.remove(created.code, created.code)
      await (await make('admin')).vendors.remove(vendor.id)
    })

    it('replaces the solution text on update, refuses to clear it and records the change in the history', async () => {
      const sales = await make('sales')
      const created = await sales.deals.create(await validInput(sales, { solution: 'MFA' }))

      const replaced = await sales.deals.update(created.code, { solution: '  ITDR ' })
      await expectRejects(sales.deals.update(created.code, { solution: '   ' }), 422, 'Solution을 입력하세요.')
      await expectRejects(sales.deals.update(created.code, { solution: '' }), 422, 'Solution을 입력하세요.')
      const kept = await sales.deals.update(created.code, { name: unique('renamed') })

      expect(replaced.solution).toBe('ITDR')
      expect(kept.solution).toBe('ITDR')
      const entries = (await sales.history.list(created.code, {})).filter((h) => h.target === 'Solution')
      expect(entries.map((h) => [h.before, h.after])).toEqual([['MFA', 'ITDR']])
      await sales.deals.remove(created.code, created.code)
    })

    it('requires a solution on registration', async () => {
      const sales = await make('sales')
      const base = await validInput(sales)

      await expectRejects(sales.deals.create({ ...base, solution: '' }), 422, 'Solution을 입력하세요.')
      await expectRejects(sales.deals.create({ ...base, solution: '   ' }), 422, 'Solution을 입력하세요.')
    })

    it('filters the list by a case-insensitive part of the solution text', async () => {
      const sales = await make('sales')
      const token = unique('Tok').toLowerCase()
      const hit = await sales.deals.create(await validInput(sales, { solution: `Pre-${token.toUpperCase()}-Post` }))
      const miss = await sales.deals.create(await validInput(sales, { solution: 'other' }))

      const found = await sales.deals.list({ solution: token })

      expect(found.items.map((d) => d.code)).toEqual([hit.code])
      await sales.deals.remove(hit.code, hit.code)
      await sales.deals.remove(miss.code, miss.code)
    })

    it('accepts a 200 character solution text', async () => {
      const sales = await make('sales')

      const created = await sales.deals.create(await validInput(sales, { solution: 'a'.repeat(200) }))

      expect(created.solution).toBe('a'.repeat(200))
      await sales.deals.remove(created.code, created.code)
    })

    it('refuses an unknown vendor and a too long solution in the server order, after the name check', async () => {
      const sales = await make('sales')
      const base = await validInput(sales)
      const tooLong = 'a'.repeat(201)

      await expectRejects(sales.deals.create({ ...base, solution: tooLong }), 422, 'Solution은 200자 이내로 입력하세요.')
      await expectRejects(
        sales.deals.create({ ...base, vendorId: NO_SUCH_ID, solution: tooLong }),
        422,
        '선택한 Vendor가 없습니다. 목록에서 다시 선택하세요.',
      )
      await expectRejects(sales.deals.create({ ...base, name: '  ', solution: tooLong }), 422, 'Deal Name을 입력하세요.')
    })

    it('combines the filters with AND', async () => {
      const sales = await make('sales')
      const input = await validInput(sales)
      const created = await sales.deals.create(input)

      expect((await sales.deals.list({ keyword: input.name })).total).toBe(1)
      expect((await sales.deals.list({ keyword: input.name, statusKey: 'prospecting', forecastKeys: ['pipeline'] })).total).toBe(1)
      expect((await sales.deals.list({ keyword: input.name, forecastKeys: ['commit'] })).total).toBe(0)
      expect((await sales.deals.list({ keyword: input.name, forecastKeys: ['commit', 'pipeline'] })).total).toBe(1)
      expect((await sales.deals.list({ keyword: input.name, forecastKeys: ['pipeline', 'pipeline'] })).total).toBe(1)
      expect((await sales.deals.list({ keyword: input.name, vendorId: NO_SUCH_ID })).total).toBe(0)
      await sales.deals.remove(created.code, created.code)
    })

    it('filters by year and quarter of Expected Close, both ends of the quarter included', async () => {
      const sales = await make('sales')
      const tag = unique('tag')
      const first = await sales.deals.create(await validInput(sales, { name: `${tag}${unique('d')}`, revenueDate: '2027-01-01' }))
      const last = await sales.deals.create(await validInput(sales, { name: `${tag}${unique('d')}`, revenueDate: '2027-03-31' }))
      const next = await sales.deals.create(await validInput(sales, { name: `${tag}${unique('d')}`, revenueDate: '2027-04-01' }))

      const q1 = await sales.deals.list({ keyword: tag, year: 2027, quarters: [1] })
      const q2 = await sales.deals.list({ keyword: tag, year: 2027, quarters: [2] })
      const year = await sales.deals.list({ keyword: tag, year: 2027 })
      const other = await sales.deals.list({ keyword: tag, year: 2026 })

      expect(q1.items.map((d) => d.code).sort()).toEqual([first.code, last.code].sort())
      expect(q2.items.map((d) => d.code)).toEqual([next.code])
      expect(year.total).toBe(3)
      expect(other.total).toBe(0)
      for (const d of [first, last, next]) await sales.deals.remove(d.code, d.code)
    })

    it('filters by several quarters of Expected Close without the quarter between them (Quarter 다중 선택 AC-01)', async () => {
      const sales = await make('sales')
      const tag = unique('tag')
      const days = ['2027-01-01', '2027-03-31', '2027-04-01', '2027-06-30', '2027-07-01', '2027-09-30', '2027-10-01']
      const created: DealDetail[] = []
      for (const revenueDate of days) created.push(await sales.deals.create(await validInput(sales, { name: `${tag}${unique('d')}`, revenueDate })))

      const q13 = await sales.deals.list({ keyword: tag, year: 2027, quarters: [1, 3] })
      const single = await sales.deals.list({ keyword: tag, year: 2027, quarters: [2] })

      const code = (index: number) => created[index]?.code
      expect(q13.items.map((d) => d.code).sort()).toEqual([0, 1, 4, 5].map(code).sort())
      expect(q13.total).toBe(4)
      expect(single.items.map((d) => d.code).sort()).toEqual([2, 3].map(code).sort())
      for (const d of created) await sales.deals.remove(d.code, d.code)
    })

    it('reads no quarters, an empty list and all four quarters as no quarter condition (Quarter 다중 선택 AC-02)', async () => {
      const sales = await make('sales')
      const tag = unique('tag')
      const created = [
        await sales.deals.create(await validInput(sales, { name: `${tag}${unique('d')}`, revenueDate: '2027-02-01' })),
        await sales.deals.create(await validInput(sales, { name: `${tag}${unique('d')}`, revenueDate: '2027-11-01' })),
      ]

      const none = await sales.deals.list({ keyword: tag, year: 2027 })
      const empty = await sales.deals.list({ keyword: tag, year: 2027, quarters: [] })
      const four = await sales.deals.list({ keyword: tag, year: 2027, quarters: [4, 3, 2, 1] })
      const twice = await sales.deals.list({ keyword: tag, year: 2027, quarters: [1, 1] })

      expect([none.total, empty.total, four.total]).toEqual([2, 2, 2])
      expect(twice.total).toBe(1)
      for (const d of created) await sales.deals.remove(d.code, d.code)
    })

    it('refuses several quarters together with a month, but all four quarters with a month pass (Quarter 다중 선택 AC-05)', async () => {
      const sales = await make('sales')

      await expectRejects(sales.deals.list({ year: 2027, quarters: [1, 3], month: 2 }), 422)
      await expectRejects(sales.deals.list({ year: 2027, quarters: [1], month: 2 }), 422)
      await expect(sales.deals.list({ year: 2027, quarters: [1, 2, 3, 4], month: 2 })).resolves.toHaveProperty('total')
    })

    it('refuses a quarter outside 1 to 4 and more than four quarters (Quarter 다중 선택 AC-04)', async () => {
      const sales = await make('sales')

      await expectRejects(sales.deals.list({ year: 2027, quarters: [0] as never }), 422)
      await expectRejects(sales.deals.list({ year: 2027, quarters: [1, 5] as never }), 422)
      await expectRejects(sales.deals.list({ year: 2027, quarters: [1, 2, 3, 4, 1] as never }), 422)
    })

    it('includes the updatedFrom and updatedTo days themselves', async () => {
      const sales = await make('sales')
      const tag = unique('tag')
      const created = await sales.deals.create(await validInput(sales, { name: `${tag}${unique('d')}` }))
      const day = created.lastUpdatedAt.slice(0, 10)
      const next = new Date(Date.parse(`${day}T00:00:00Z`) + 86_400_000).toISOString().slice(0, 10)
      const prev = new Date(Date.parse(`${day}T00:00:00Z`) - 86_400_000).toISOString().slice(0, 10)

      expect((await sales.deals.list({ keyword: tag, updatedFrom: day, updatedTo: day })).total).toBe(1)
      expect((await sales.deals.list({ keyword: tag, updatedFrom: next })).total).toBe(0)
      expect((await sales.deals.list({ keyword: tag, updatedTo: prev })).total).toBe(0)
      expect((await sales.deals.list({ keyword: tag, updatedFrom: prev })).total).toBe(1)
      expect((await sales.deals.list({ keyword: tag, updatedTo: next })).total).toBe(1)
      await sales.deals.remove(created.code, created.code)
    })

    it('refuses an updated period whose start is after its end with 422', async () => {
      const sales = await make('sales')

      await expectRejects(sales.deals.list({ updatedFrom: '2026-07-01', updatedTo: '2026-06-30' }), 422)
    })

    it('resolves the presets from the server date for every role', async () => {
      const user = await make('user')

      const result = await user.deals.updatedPeriods()

      expect(result.periods.map((p) => p.key)).toEqual(['2w', '1m', '2m', '3m', '6m'])
      for (const period of result.periods) {
        expect(period.to).toBe(result.today)
        expect(period.from < period.to).toBe(true)
      }
      expect(result.periods[0]?.from).toBe(
        new Date(Date.parse(`${result.today}T00:00:00Z`) - 14 * 86_400_000).toISOString().slice(0, 10),
      )
      expect(result.upcoming.map((p) => p.key)).toEqual(['1m', '2m'])
      for (const period of result.upcoming) {
        expect(period.from).toBe(result.today)
        expect(period.to > period.from).toBe(true)
      }
    })

    it('sorts by owner, customer, partner, vendor and forecast in both directions with code ties ascending', async () => {
      const admin = await make('admin')
      const vendors = [await admin.vendors.create(unique('vb')), await admin.vendors.create(unique('va'))]
      const sales = await make('sales')
      const tag = unique('tag')
      const rows: [string, string, string][] = [
        ['Cc', 'pipeline', 'ZZb'],
        ['aa', 'commit', 'ZZa'],
        ['Bb', 'best', 'ZZc'],
      ]
      const made = []
      for (const [index, [company, forecastKey, partnerCompany]] of rows.entries()) {
        const base = await validInput(sales, { name: `${tag}${unique('d')}`, forecastKey, vendorId: vendors[index % 2]?.id ?? null })
        made.push(
          await sales.deals.create({
            ...base,
            customer: { ...base.customer, company: `${tag}${company}` },
            partner: { contactId: null, company: `${tag}${partnerCompany}`, name: unique('pn'), title: '', email: null, phone: null },
          }),
        )
      }
      const byCustomer = made.map((d) => d.code)
      const asc = (await sales.deals.list({ keyword: tag, sort: 'customer', order: 'asc' })).items.map((d) => d.code)
      const desc = (await sales.deals.list({ keyword: tag, sort: 'customer', order: 'desc' })).items.map((d) => d.code)

      // 소문자 기준: aa < bb < cc
      expect(asc).toEqual([byCustomer[1], byCustomer[2], byCustomer[0]])
      expect(desc).toEqual([byCustomer[0], byCustomer[2], byCustomer[1]])
      const partner = (await sales.deals.list({ keyword: tag, sort: 'partner', order: 'asc' })).items.map((d) => d.code)
      expect(partner).toEqual([byCustomer[1], byCustomer[0], byCustomer[2]])
      for (const sort of ['owner', 'vendor', 'forecastKey'] as const) {
        const found = await sales.deals.list({ keyword: tag, sort, order: 'desc' })
        expect(found.total).toBe(3)
      }
      for (const d of made) await sales.deals.remove(d.code, d.code)
      const cleanup = await make('admin')
      for (const v of vendors) await cleanup.vendors.remove(v.id)
    })

    it('puts deals without a partner or vendor last in both directions', async () => {
      const sales = await make('sales')
      const tag = unique('tag')
      const base = await validInput(sales, { name: `${tag}${unique('d')}` })
      const withPartner = await sales.deals.create({
        ...base,
        partner: { contactId: null, company: `${tag}partner`, name: unique('pn'), title: '', email: null, phone: null },
      })
      const without = await sales.deals.create(await validInput(sales, { name: `${tag}${unique('d')}` }))

      for (const order of ['asc', 'desc'] as const) {
        const found = await sales.deals.list({ keyword: tag, sort: 'partner', order })
        expect(found.items.map((d) => d.code)).toEqual([withPartner.code, without.code])
        const byVendor = await sales.deals.list({ keyword: tag, sort: 'vendor', order })
        expect(byVendor.items.map((d) => d.code)).toEqual([withPartner.code, without.code].sort())
      }
      for (const d of [withPartner, without]) await sales.deals.remove(d.code, d.code)
    })

    it('lists only overdue deals with overdue and only stale-or-overdue deals with both, as the badge says', async () => {
      const sales = await make('sales')
      const tag = unique('tag')
      const overdue = await sales.deals.create(await validInput(sales, { name: `${tag}${unique('d')}` }))
      const onTime = await sales.deals.create(await validInput(sales, { name: `${tag}${unique('d')}` }))
      await sales.actions.create(overdue.code, action({ progress: '', nextAction: '지난 계획', dueDate: '2000-01-01' }))
      await sales.actions.create(onTime.code, action({ progress: '', nextAction: '먼 계획', dueDate: '2999-01-01' }))

      const found = await sales.deals.list({ keyword: tag, overdue: true })
      const either = await sales.deals.list({ keyword: tag, overdue: true, stale: true })
      const none = await sales.deals.list({ keyword: tag, stale: true })

      expect(found.items.map((d) => d.code)).toEqual([overdue.code])
      expect(found.total).toBe(1)
      expect(found.items[0]?.risk === 'overdue' || found.items[0]?.risk === 'overdue_stale').toBe(true)
      expect(either.items.map((d) => d.code)).toEqual([overdue.code])
      expect(none.items.map((d) => d.code)).not.toContain(onTime.code)
      for (const d of [overdue, onTime]) await sales.deals.remove(d.code, d.code)
    })

    it('orders ties by code ascending whatever the sort direction', async () => {
      const sales = await make('sales')
      const tag = unique('tag')
      const made = [
        await sales.deals.create(await validInput(sales, { name: `${tag}${unique('d')}`, revenueAmount: 7_000_000 })),
        await sales.deals.create(await validInput(sales, { name: `${tag}${unique('d')}`, revenueAmount: 7_000_000 })),
        await sales.deals.create(await validInput(sales, { name: `${tag}${unique('d')}`, revenueAmount: 7_000_000 })),
      ]
      const expected = made.map((d) => d.code).sort()

      const asc = await sales.deals.list({ keyword: tag, sort: 'revenueAmount', order: 'asc' })
      const desc = await sales.deals.list({ keyword: tag, sort: 'revenueAmount', order: 'desc' })

      expect(asc.items.map((d) => d.code)).toEqual(expected)
      expect(desc.items.map((d) => d.code)).toEqual(expected)
      for (const d of made) await sales.deals.remove(d.code, d.code)
    })

    it('sorts by revenue amount in the requested direction', async () => {
      const sales = await make('sales')
      const tag = unique('tag')
      const small = await sales.deals.create(await validInput(sales, { name: `${tag}${unique('d')}`, revenueAmount: 1_000_000 }))
      const big = await sales.deals.create(await validInput(sales, { name: `${tag}${unique('d')}`, revenueAmount: 9_000_000 }))

      const asc = await sales.deals.list({ keyword: tag, sort: 'revenueAmount', order: 'asc' })
      const desc = await sales.deals.list({ keyword: tag, sort: 'revenueAmount', order: 'desc' })

      expect(asc.items.map((d) => d.code)).toEqual([small.code, big.code])
      expect(desc.items.map((d) => d.code)).toEqual([big.code, small.code])
      for (const d of [small, big]) await sales.deals.remove(d.code, d.code)
    })

    it('trims the procurement before the length check and stores the trimmed value', async () => {
      const sales = await make('sales')
      const procurement = '가'.repeat(500)

      const created = await sales.deals.create(await validInput(sales, { procurement: `  ${procurement}  ` }))

      expect(created.procurement).toBe(procurement)
      await expectRejects(
        sales.deals.create(await validInput(sales, { procurement: ` ${'가'.repeat(501)} ` })),
        422,
        '구매절차는 500자 이내로 입력하세요.',
      )
      await sales.deals.remove(created.code, created.code)
    })

    it('starts the status stay at registration: statusDays 0, statusChangedAt set, no risk', async () => {
      const sales = await make('sales')

      const created = await sales.deals.create(await validInput(sales))

      expect(created.statusDays).toBe(0)
      expect(Number.isNaN(Date.parse(created.statusChangedAt))).toBe(false)
      expect(created.risk).toBeNull()
      const row = (await sales.deals.list({ keyword: created.code })).items.find((d) => d.code === created.code)
      expect(row).toMatchObject({ statusChangedAt: created.statusChangedAt, statusDays: 0, risk: null })
      await sales.deals.remove(created.code, created.code)
    })

    it('keeps statusChangedAt when only the forecast changes and moves it forward when the status changes', async () => {
      const sales = await make('sales')
      const created = await sales.deals.create(await validInput(sales))

      const forecastOnly = await sales.deals.applyChange(created.code, { change: { field: 'forecastKey', value: 'best' } })
      expect(forecastOnly.deal.statusChangedAt).toBe(created.statusChangedAt)

      const moved = await sales.deals.applyChange(created.code, { change: { field: 'statusKey', value: 'introduction' } })
      expect(moved.deal.statusKey).toBe('introduction')
      expect(Date.parse(moved.deal.statusChangedAt)).toBeGreaterThanOrEqual(Date.parse(created.statusChangedAt))
      expect(moved.deal.statusDays).toBe(0)
      await sales.deals.remove(created.code, created.code)
    })
  })
}
