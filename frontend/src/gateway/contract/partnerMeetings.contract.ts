/**
 * 파트너 Activity(미팅 기록) 계약. mock과 실제 서버가 같은 규칙을 지킨다.
 * 호출마다 고유한 내용 접두사를 써서 다른 기록과 섞이지 않게 하고, 만든 것은 스스로 치운다.
 * 파트너 회사·Deal은 이미 있는 것을 `dealOptions`로 찾아 쓴다(연결된 Deal이 하나 이상 있는 첫 회사).
 */

import { describe, expect, it } from 'vitest'
import type { Gateway } from '../types'
import { expectRejects, NO_SUCH_ID, unique, type MakeGateway } from './support'

const DEFAULT_QUERY = { sort: 'meetingDate', order: 'desc' } as const
const NOT_LINKED = '선택한 파트너와 연결된 Deal이 아닙니다.'
const CONTENT_REQUIRED = '미팅 내용을 입력하세요.'
const COMPANY_NOT_FOUND = '등록된 파트너 회사가 아닙니다. 목록에서 다시 선택하세요.'
const NOT_FOUND = '미팅 기록을 찾을 수 없습니다.'

async function target(gateway: Gateway): Promise<{ company: string; dealCode: string }> {
  for (const company of await gateway.contacts.companies('partner')) {
    const options = await gateway.partnerMeetings.dealOptions(company)
    const first = options[0]
    if (first) return { company, dealCode: first.code }
  }
  throw new Error('연결된 Deal이 있는 파트너 회사가 없다')
}

const input = (t: { company: string; dealCode: string }, content: string, meetingDate = '2026-10-01') => ({
  partnerCompany: t.company,
  dealCode: t.dealCode,
  meetingDate,
  content,
})

export function partnerMeetingsContract(make: MakeGateway): void {
  describe('partnerMeetings 계약', () => {
    it('creates several meetings in input order and lists them newest meeting date first (AC1)', async () => {
      const gateway = await make('sales')
      const t = await target(gateway)
      const tag = unique('pm')

      const created = await gateway.partnerMeetings.create([
        input(t, `${tag} 첫째`, '2026-10-01'),
        input(t, `${tag} 둘째`, '2026-10-03'),
        input(t, `${tag} 셋째`, '2026-10-02'),
      ])

      expect(created.map((m) => m.content)).toEqual([`${tag} 첫째`, `${tag} 둘째`, `${tag} 셋째`])
      const page = await gateway.partnerMeetings.list({ ...DEFAULT_QUERY, content: tag }, 0, 10)
      expect(page.items.map((m) => m.content)).toEqual([`${tag} 둘째`, `${tag} 셋째`, `${tag} 첫째`])
      expect(page.total).toBe(3)
      for (const m of created) await gateway.partnerMeetings.remove(m.id)
    })

    it('returns the documented fields with the representative company, current deal name and author', async () => {
      const gateway = await make('sales')
      const me = await gateway.auth.me()
      const t = await target(gateway)
      const [created] = await gateway.partnerMeetings.create([input(t, `${unique('pm')} 내용\n둘째 줄`)])

      expect(created).toMatchObject({ partnerCompany: t.company, meetingDate: '2026-10-01' })
      expect(created?.deal.code).toBe(t.dealCode)
      expect(created?.deal.name).toBeTruthy()
      expect(created?.author).toMatchObject({ id: me.id, status: 'active' })
      expect(created?.content).toContain('\n')
      expect(Object.keys(created ?? {}).sort()).toEqual(['author', 'content', 'createdAt', 'deal', 'id', 'meetingDate', 'partnerCompany', 'updatedAt'])
      if (created) await gateway.partnerMeetings.remove(created.id)
    })

    it('normalizes the company spelling to the registered one (AC17)', async () => {
      const gateway = await make('sales')
      const t = await target(gateway)
      const [created] = await gateway.partnerMeetings.create([{ ...input(t, unique('pm')), partnerCompany: t.company.toUpperCase() }])

      expect(created?.partnerCompany).toBe(t.company)
      if (created) await gateway.partnerMeetings.remove(created.id)
    })

    it('trims the content and accepts a future date', async () => {
      const gateway = await make('sales')
      const t = await target(gateway)
      const tag = unique('pm')
      const [created] = await gateway.partnerMeetings.create([input(t, `  ${tag}  \n`, '2999-12-31')])

      expect(created?.content).toBe(tag)
      expect(created?.meetingDate).toBe('2999-12-31')
      if (created) await gateway.partnerMeetings.remove(created.id)
    })

    it('saves nothing and reports every violation with its location when a row is invalid (AC12, AC17)', async () => {
      const gateway = await make('sales')
      const t = await target(gateway)
      const tag = unique('pm')

      const error = await expectRejects(
        gateway.partnerMeetings.create([input(t, `${tag} ok`), { ...input(t, `${tag} bad`), partnerCompany: '없는회사이름' }, input(t, '   ')]),
        422,
      )

      expect(error.problem?.itemErrors).toEqual([
        { location: ['items', 1, 'partner_company'], message: COMPANY_NOT_FOUND },
        { location: ['items', 2, 'content'], message: CONTENT_REQUIRED },
      ])
      expect((await gateway.partnerMeetings.list({ ...DEFAULT_QUERY, content: tag }, 0, 10)).total).toBe(0)
    })

    it('rejects a deal of another company with the not-linked message at the deal location (AC17)', async () => {
      const gateway = await make('sales')
      const optionsOf = new Map<string, string[]>()
      for (const company of await gateway.contacts.companies('partner')) {
        optionsOf.set(company, (await gateway.partnerMeetings.dealOptions(company)).map((o) => o.code))
      }
      let pair: { company: string; foreignDeal: string } | null = null
      for (const [company, codes] of optionsOf) {
        for (const [other, otherCodes] of optionsOf) {
          const foreign = otherCodes.find((code) => other !== company && !codes.includes(code))
          if (foreign && codes.length > 0) pair = { company, foreignDeal: foreign }
        }
      }
      if (!pair) throw new Error('서로 다른 Deal을 가진 파트너 회사 둘이 필요하다')

      const error = await expectRejects(
        gateway.partnerMeetings.create([{ partnerCompany: pair.company, dealCode: pair.foreignDeal, meetingDate: '2026-10-01', content: unique('pm') }]),
        422,
      )

      expect(error.problem?.itemErrors).toEqual([{ location: ['items', 0, 'deal_code'], message: NOT_LINKED }])
    })

    it('rejects an empty list and more than 50 items', async () => {
      const gateway = await make('sales')
      const t = await target(gateway)

      await expectRejects(gateway.partnerMeetings.create([]), 422, '입력한 미팅이 없습니다.')
      await expectRejects(gateway.partnerMeetings.create(Array.from({ length: 51 }, () => input(t, unique('pm')))), 422)
    })

    it('filters by content, partner, deal, date range (inclusive) and author with AND, and reports the total (AC3)', async () => {
      const gateway = await make('sales')
      const me = await gateway.auth.me()
      const t = await target(gateway)
      const tag = unique('pm')
      const created = await gateway.partnerMeetings.create([
        input(t, `${tag} a`, '2026-09-01'),
        input(t, `${tag} b`, '2026-09-02'),
        input(t, `${tag} c`, '2026-09-03'),
      ])

      const range = await gateway.partnerMeetings.list({ ...DEFAULT_QUERY, content: tag, dateFrom: '2026-09-02', dateTo: '2026-09-03' }, 0, 10)
      const paged = await gateway.partnerMeetings.list({ ...DEFAULT_QUERY, content: tag }, 1, 1)
      const anded = await gateway.partnerMeetings.list(
        { ...DEFAULT_QUERY, content: tag, partner: t.company.slice(0, 2), deal: t.dealCode.toLowerCase(), authorId: me.id },
        0,
        10,
      )
      const none = await gateway.partnerMeetings.list({ ...DEFAULT_QUERY, content: tag, authorId: NO_SUCH_ID }, 0, 10)

      expect(range.items.map((m) => m.content)).toEqual([`${tag} c`, `${tag} b`])
      expect(paged.items.map((m) => m.content)).toEqual([`${tag} b`])
      expect(paged).toMatchObject({ total: 3, offset: 1, limit: 1 })
      expect(anded.total).toBe(3)
      expect(none.total).toBe(0)
      for (const m of created) await gateway.partnerMeetings.remove(m.id)
    })

    it('treats % and _ in a filter literally', async () => {
      const gateway = await make('sales')
      const t = await target(gateway)
      const tag = unique('pm')
      const created = await gateway.partnerMeetings.create([input(t, `${tag} 10%`, '2026-09-01'), input(t, `${tag} 100`, '2026-09-02')])

      const page = await gateway.partnerMeetings.list({ ...DEFAULT_QUERY, content: `${tag} 10%` }, 0, 10)

      expect(page.items.map((m) => m.content)).toEqual([`${tag} 10%`])
      for (const m of created) await gateway.partnerMeetings.remove(m.id)
    })

    it('sorts by each column in both directions with ties by newest date', async () => {
      const gateway = await make('sales')
      const t = await target(gateway)
      const tag = unique('pm')
      const created = await gateway.partnerMeetings.create([
        input(t, `${tag} banana`, '2026-09-03'),
        input(t, `${tag} Apple`, '2026-09-01'),
        input(t, `${tag} cherry`, '2026-09-02'),
      ])

      const byContent = (order: 'asc' | 'desc') => gateway.partnerMeetings.list({ sort: 'content', order, content: tag }, 0, 10)
      const byPartner = (order: 'asc' | 'desc') => gateway.partnerMeetings.list({ sort: 'partner', order, content: tag }, 0, 10)

      expect((await byContent('asc')).items.map((m) => m.content.slice(tag.length + 1))).toEqual(['Apple', 'banana', 'cherry'])
      expect((await byContent('desc')).items.map((m) => m.content.slice(tag.length + 1))).toEqual(['cherry', 'banana', 'Apple'])
      for (const order of ['asc', 'desc'] as const) {
        expect((await byPartner(order)).items.map((m) => m.content.slice(tag.length + 1))).toEqual(['banana', 'cherry', 'Apple'])
      }
      const oldest = await gateway.partnerMeetings.list({ sort: 'meetingDate', order: 'asc', content: tag }, 0, 10)
      expect(oldest.items.map((m) => m.content.slice(tag.length + 1))).toEqual(['Apple', 'cherry', 'banana'])
      for (const m of created) await gateway.partnerMeetings.remove(m.id)
    })

    it('rejects a reversed date range in the search', async () => {
      const { partnerMeetings } = await make('sales')

      await expectRejects(partnerMeetings.list({ ...DEFAULT_QUERY, dateFrom: '2026-10-02', dateTo: '2026-10-01' }, 0, 10), 422, '미팅 날짜 범위의 시작은 끝보다 늦을 수 없습니다.')
    })

    it('lets every role read and refuses an anonymous caller (AC5)', async () => {
      for (const role of ['admin', 'sales', 'user'] as const) {
        const { partnerMeetings } = await make(role)
        const page = await partnerMeetings.list(DEFAULT_QUERY, 0, 10)
        expect(page.limit).toBe(10)
        expect(Array.isArray(await partnerMeetings.dealOptions('없는회사이름'))).toBe(true)
      }
      const gateway = await make('user')
      await gateway.auth.logout()

      await expectRejects(gateway.partnerMeetings.list(DEFAULT_QUERY, 0, 10), 401)
    })

    it('refuses writes from a read-only user with 403 (AC6)', async () => {
      const writer = await make('sales')
      const t = await target(writer)
      const [created] = await writer.partnerMeetings.create([input(t, unique('pm'))])
      const { partnerMeetings } = await make('user')

      await expectRejects(partnerMeetings.create([input(t, unique('pm'))]), 403)
      await expectRejects(partnerMeetings.update(created?.id ?? 0, input(t, unique('pm'))), 403)
      await expectRejects(partnerMeetings.remove(created?.id ?? 0), 403)
      const cleanup = await make('sales')
      if (created) await cleanup.partnerMeetings.remove(created.id)
    })

    it('updates the date and content, keeps the author and bumps updatedAt only when something changed (AC15)', async () => {
      const gateway = await make('sales')
      const t = await target(gateway)
      const tag = unique('pm')
      const [created] = await gateway.partnerMeetings.create([input(t, `${tag} 이전`)])
      if (!created) throw new Error('생성 실패')

      const same = await gateway.partnerMeetings.update(created.id, input(t, `${tag} 이전`))
      const changed = await gateway.partnerMeetings.update(created.id, input(t, `${tag} 이후`, '2026-11-02'))

      expect(same.updatedAt).toBe(created.updatedAt)
      expect(changed).toMatchObject({ id: created.id, content: `${tag} 이후`, meetingDate: '2026-11-02', author: created.author, createdAt: created.createdAt })
      await gateway.partnerMeetings.remove(created.id)
    })

    it('lets admin edit and delete someone elses record', async () => {
      const sales = await make('sales')
      const t = await target(sales)
      const tag = unique('pm')
      const [created] = await sales.partnerMeetings.create([input(t, `${tag} 원본`)])
      if (!created) throw new Error('생성 실패')

      const admin = await make('admin')
      const edited = await admin.partnerMeetings.update(created.id, input(t, `${tag} 관리자`))
      await admin.partnerMeetings.remove(created.id)

      expect(edited.content).toBe(`${tag} 관리자`)
      expect(edited.author).toEqual(created.author)
      expect((await admin.partnerMeetings.list({ ...DEFAULT_QUERY, content: tag }, 0, 10)).total).toBe(0)
    })

    it('answers 404 with the message for a missing record before anything else (AC14)', async () => {
      const gateway = await make('sales')
      const t = await target(gateway)

      await expectRejects(gateway.partnerMeetings.update(NO_SUCH_ID, input(t, '  ')), 404, NOT_FOUND)
      await expectRejects(gateway.partnerMeetings.remove(NO_SUCH_ID), 404, NOT_FOUND)
    })

    it('rechecks the deal link only when the company or deal changes (AC15)', async () => {
      const gateway = await make('sales')
      const t = await target(gateway)
      const [created] = await gateway.partnerMeetings.create([input(t, unique('pm'))])
      if (!created) throw new Error('생성 실패')

      const error = await expectRejects(gateway.partnerMeetings.update(created.id, { ...input(t, unique('pm')), dealCode: '20000101-ZZZZ' }), 422)

      expect(error.problem?.itemErrors?.[0]?.location).toEqual(['deal_code'])
      await gateway.partnerMeetings.remove(created.id)
    })

    it('reports an update violation with a field-only location (AC17)', async () => {
      const gateway = await make('sales')
      const t = await target(gateway)
      const [created] = await gateway.partnerMeetings.create([input(t, unique('pm'))])
      if (!created) throw new Error('생성 실패')

      const error = await expectRejects(gateway.partnerMeetings.update(created.id, input(t, '   ')), 422, CONTENT_REQUIRED)

      expect(error.problem?.itemErrors).toEqual([{ location: ['content'], message: CONTENT_REQUIRED }])
      await gateway.partnerMeetings.remove(created.id)
    })

    it('lists the deals of a company ordered by lower-case name then code, with the customer company (AC8)', async () => {
      const gateway = await make('sales')
      const t = await target(gateway)

      const options = await gateway.partnerMeetings.dealOptions(t.company.toUpperCase())

      expect(options.length).toBeGreaterThan(0)
      expect(Object.keys(options[0] ?? {}).sort()).toEqual(['code', 'customerCompany', 'name'])
      const keys = options.map((o) => `${o.name.toLowerCase()}\u0000${o.code}`)
      expect(keys).toEqual([...keys].sort())
    })

    it('returns an empty deal list for an unknown company', async () => {
      const { partnerMeetings } = await make('sales')

      expect(await partnerMeetings.dealOptions('없는회사이름')).toEqual([])
    })

    it('counts the meetings of a deal in the deletion impact and removes them with the deal (AC18)', async () => {
      const admin = await make('admin')
      const t = await target(admin)
      const tag = unique('pm')
      const before = (await admin.deals.impact(t.dealCode)).partnerMeetingCount
      await admin.partnerMeetings.create([input(t, `${tag} a`), input(t, `${tag} b`)])

      const impact = await admin.deals.impact(t.dealCode)

      expect(impact.partnerMeetingCount).toBe(before + 2)
      const mine = await admin.partnerMeetings.list({ ...DEFAULT_QUERY, content: tag }, 0, 10)
      for (const m of mine.items) await admin.partnerMeetings.remove(m.id)
      expect((await admin.deals.impact(t.dealCode)).partnerMeetingCount).toBe(before)
    })
  })
}
