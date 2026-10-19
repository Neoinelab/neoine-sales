/**
 * Deal 원장 계약(AC-05·AC-22·삭제·applyChange). mock과 실제 서버가 같은 결과를 내야 한다.
 * 시드에 기대지 않고 호출마다 고유한 Deal 이름·회사명으로 만든 Deal만 본다(만든 Deal은 스스로 지운다).
 */

import { describe, expect, it } from 'vitest'
import { DEAL_CODE_PATTERN } from '../../shared/model/constants'
import type { DealInput } from '../../shared/model/types'
import type { Gateway } from '../types'
import { expectRejects, unique, type MakeGateway } from './support'

const NO_SUCH_ID = '00000000-0000-4000-8000-000000000000'
const SYNC_MISMATCH = 'Status와 Forecast의 동기화가 맞지 않습니다.'
const REVENUE_NEEDED = 'Won·계약완료로 바꾸려면 매출금액과 매출일이 필요합니다.'
const CHOICE_NEEDED = '함께 바꿀 값을 선택하세요.'

/** 유효한 등록 입력. 이름·고객 회사명은 호출마다 고유하다(Vendor·Solution은 선택 안 함). */
async function validInput(gateway: Gateway, over: Partial<DealInput> = {}): Promise<DealInput> {
  const me = await gateway.auth.me()
  return {
    name: unique('deal'),
    ownerId: me.id,
    vendorId: null,
    solutionId: null,
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

    it('reports the first violation in the fixed order: name, amount, Expected Close, Users, sync', async () => {
      const sales = await make('sales')
      const base = await validInput(sales)

      await expectRejects(sales.deals.create({ ...base, name: '  ', revenueAmount: 0 }), 422, 'Deal Name을 입력하세요.')
      await expectRejects(sales.deals.create({ ...base, revenueAmount: 0, revenueDate: '' }), 422, '매출금액은 1원 이상의 정수로 입력하세요.')
      await expectRejects(sales.deals.create({ ...base, revenueDate: '', users: 0 }), 422, 'Expected Close를 입력하세요.')
      await expectRejects(sales.deals.create({ ...base, users: 0, statusKey: 'contract_completed' }), 422, 'Users는 1 이상의 정수로 입력하세요.')
      await expectRejects(sales.deals.create({ ...base, statusKey: 'contract_completed' }), 422, SYNC_MISMATCH)
    })

    it('checks the procurement length after Status and BANT, as the server does', async () => {
      const sales = await make('sales')
      const base = await validInput(sales)
      const tooLong = 'a'.repeat(501)

      await expectRejects(sales.deals.create({ ...base, procurement: tooLong, statusKey: 'no_such_status' }), 422, 'Status를 선택하세요.')
      await expectRejects(
        sales.deals.create({ ...base, procurement: tooLong, bant: { budget: '00000000-0000-4000-8000-000000000000', authority: null, need: null, timeline: null } }),
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

      expect(impact).toEqual({ historyCount: 1, actionCount: 0, attachmentCount: 0 })
      await sales.deals.remove(created.code, created.code)
    })

    it('returns vendor and solution as null when none is chosen', async () => {
      const sales = await make('sales')
      const created = await sales.deals.create(await validInput(sales))

      expect(created.vendor).toBeNull()
      expect(created.solution).toBeNull()
      await sales.deals.remove(created.code, created.code)
    })

    it('registers a deal with a vendor and its solution as {id, name} and filters by their ids', async () => {
      const admin = await make('admin')
      const vendor = await admin.vendors.create(unique('vendor'))
      const solution = await admin.vendors.createSolution(vendor.id, unique('solution'))
      const sales = await make('sales')

      const created = await sales.deals.create(await validInput(sales, { vendorId: vendor.id, solutionId: solution.id }))

      expect(created.vendor).toEqual({ id: vendor.id, name: vendor.name })
      expect(created.solution).toEqual({ id: solution.id, name: solution.name })
      expect((await sales.deals.list({ vendorId: vendor.id })).items.map((d) => d.code)).toEqual([created.code])
      expect((await sales.deals.list({ solutionId: solution.id })).items.map((d) => d.code)).toEqual([created.code])
      expect((await sales.deals.list({ vendorId: vendor.id, solutionId: NO_SUCH_ID })).total).toBe(0)
      await sales.deals.remove(created.code, created.code)
      const cleanup = await make('admin')
      await cleanup.vendors.remove(vendor.id)
    })

    it('refuses a solution without a vendor, an unknown vendor and a solution of another vendor, right after the name check', async () => {
      const admin = await make('admin')
      const first = await admin.vendors.create(unique('vendor'))
      const second = await admin.vendors.create(unique('vendor'))
      const solution = await admin.vendors.createSolution(second.id, unique('solution'))
      const sales = await make('sales')
      const base = await validInput(sales)

      await expectRejects(sales.deals.create({ ...base, solutionId: solution.id }), 422, 'Solution을 선택하려면 Vendor를 먼저 선택하세요.')
      await expectRejects(
        sales.deals.create({ ...base, vendorId: NO_SUCH_ID }),
        422,
        '선택한 Vendor가 없습니다. 목록에서 다시 선택하세요.',
      )
      await expectRejects(
        sales.deals.create({ ...base, vendorId: first.id, solutionId: solution.id }),
        422,
        '선택한 Solution은 이 Vendor에 속하지 않습니다.',
      )
      await expectRejects(sales.deals.create({ ...base, name: '  ', vendorId: first.id, solutionId: solution.id }), 422, 'Deal Name을 입력하세요.')
      const cleanup = await make('admin')
      await cleanup.vendors.remove(first.id)
      await cleanup.vendors.remove(second.id)
    })

    it('combines the filters with AND', async () => {
      const sales = await make('sales')
      const input = await validInput(sales)
      const created = await sales.deals.create(input)

      expect((await sales.deals.list({ keyword: input.name })).total).toBe(1)
      expect((await sales.deals.list({ keyword: input.name, statusKey: 'prospecting', forecastKey: 'pipeline' })).total).toBe(1)
      expect((await sales.deals.list({ keyword: input.name, forecastKey: 'commit' })).total).toBe(0)
      expect((await sales.deals.list({ keyword: input.name, vendorId: NO_SUCH_ID })).total).toBe(0)
      await sales.deals.remove(created.code, created.code)
    })

    it('filters by year and quarter of Expected Close, both ends of the quarter included', async () => {
      const sales = await make('sales')
      const tag = unique('tag')
      const first = await sales.deals.create(await validInput(sales, { name: `${tag}${unique('d')}`, revenueDate: '2027-01-01' }))
      const last = await sales.deals.create(await validInput(sales, { name: `${tag}${unique('d')}`, revenueDate: '2027-03-31' }))
      const next = await sales.deals.create(await validInput(sales, { name: `${tag}${unique('d')}`, revenueDate: '2027-04-01' }))

      const q1 = await sales.deals.list({ keyword: tag, year: 2027, quarter: 1 })
      const q2 = await sales.deals.list({ keyword: tag, year: 2027, quarter: 2 })
      const year = await sales.deals.list({ keyword: tag, year: 2027 })
      const other = await sales.deals.list({ keyword: tag, year: 2026 })

      expect(q1.items.map((d) => d.code).sort()).toEqual([first.code, last.code].sort())
      expect(q2.items.map((d) => d.code)).toEqual([next.code])
      expect(year.total).toBe(3)
      expect(other.total).toBe(0)
      for (const d of [first, last, next]) await sales.deals.remove(d.code, d.code)
    })

    it('includes the revenueFrom and revenueTo days themselves', async () => {
      const sales = await make('sales')
      const tag = unique('tag')
      const created = await sales.deals.create(await validInput(sales, { name: `${tag}${unique('d')}`, revenueDate: '2027-05-10' }))

      expect((await sales.deals.list({ keyword: tag, revenueFrom: '2027-05-10', revenueTo: '2027-05-10' })).total).toBe(1)
      expect((await sales.deals.list({ keyword: tag, revenueFrom: '2027-05-11' })).total).toBe(0)
      expect((await sales.deals.list({ keyword: tag, revenueTo: '2027-05-09' })).total).toBe(0)
      await sales.deals.remove(created.code, created.code)
    })

    it('filters by a BANT label of one category', async () => {
      const sales = await make('sales')
      const label = (await sales.labels.list()).find((l) => l.category === 'budget' && l.isDefault)
      if (!label) throw new Error('기본 Budget Label이 없습니다.')
      const tag = unique('tag')
      const withLabel = await sales.deals.create(
        await validInput(sales, { name: `${tag}${unique('d')}`, bant: { budget: label.id, authority: null, need: null, timeline: null } }),
      )
      const without = await sales.deals.create(await validInput(sales, { name: `${tag}${unique('d')}` }))

      const found = await sales.deals.list({ keyword: tag, bantLabelIds: { budget: label.id } })

      expect(found.items.map((d) => d.code)).toEqual([withLabel.code])
      expect(found.items[0]?.bant.budget).toBe(label.id)
      for (const d of [withLabel, without]) await sales.deals.remove(d.code, d.code)
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
