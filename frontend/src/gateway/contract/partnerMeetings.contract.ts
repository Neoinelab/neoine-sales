/**
 * 파트너 Activity(미팅 기록) 계약. mock과 실제 서버가 같은 규칙을 지킨다.
 * 호출마다 고유한 내용 접두사를 써서 다른 기록과 섞이지 않게 하고, 만든 것은 스스로 치운다.
 * 미팅은 Deal과 무관하다. 파트너 회사는 이미 등록된 파트너 연락처의 회사를 쓴다(첫 회사).
 */

import { describe, expect, it } from 'vitest'
import type { Gateway } from '../types'
import { expectRejects, NO_SUCH_ID, unique, type MakeGateway } from './support'

const DEFAULT_QUERY = { sort: 'meetingDate', order: 'desc' } as const
const CONTENT_REQUIRED = '미팅 내용을 입력하세요.'
const COMPANY_NOT_FOUND = '등록된 파트너 회사가 아닙니다. 목록에서 다시 선택하세요.'
const NOT_FOUND = '미팅 기록을 찾을 수 없습니다.'

async function target(gateway: Gateway): Promise<{ company: string }> {
  const [company] = await gateway.contacts.companies('partner')
  if (!company) throw new Error('등록된 파트너 회사가 없다')
  return { company }
}

const input = (t: { company: string }, content: string, meetingDate = '2026-10-01') => ({
  partnerCompany: t.company,
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

    it('returns the documented fields with the representative company and author, and no deal', async () => {
      const gateway = await make('sales')
      const me = await gateway.auth.me()
      const t = await target(gateway)
      const [created] = await gateway.partnerMeetings.create([input(t, `${unique('pm')} 내용\n둘째 줄`)])

      expect(created).toMatchObject({ partnerCompany: t.company, meetingDate: '2026-10-01' })
      expect(created?.author).toMatchObject({ id: me.id, status: 'active' })
      expect(created?.content).toContain('\n')
      expect(Object.keys(created ?? {}).sort()).toEqual(['author', 'content', 'createdAt', 'id', 'meetingDate', 'partnerCompany', 'updatedAt'])
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

    it('registers a meeting for a partner company that has no deal', async () => {
      const admin = await make('admin')
      const company = unique('NoDealPartner')
      await admin.contacts.create('partner', { company, name: '가나다', title: '', email: null, phone: null })
      const sales = await make('sales')

      const [created] = await sales.partnerMeetings.create([{ partnerCompany: company, meetingDate: '2026-10-01', content: unique('pm') }])

      expect(created?.partnerCompany).toBe(company)
      if (created) await sales.partnerMeetings.remove(created.id)
    })

    it('rejects an empty list and more than 50 items', async () => {
      const gateway = await make('sales')
      const t = await target(gateway)

      await expectRejects(gateway.partnerMeetings.create([]), 422, '입력한 미팅이 없습니다.')
      await expectRejects(gateway.partnerMeetings.create(Array.from({ length: 51 }, () => input(t, unique('pm')))), 422)
    })

    it('filters by content, partner, date range (inclusive) and author with AND, and reports the total (AC3)', async () => {
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
        { ...DEFAULT_QUERY, content: tag, partner: t.company.slice(0, 2), authorId: me.id },
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

    it('lets every role read and refuses an anonymous caller (AC12)', async () => {
      for (const role of ['admin', 'sales', 'user'] as const) {
        const { partnerMeetings } = await make(role)
        const page = await partnerMeetings.list(DEFAULT_QUERY, 0, 10)
        expect(page.limit).toBe(10)
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

    it('rechecks the company only when it changes (AC6)', async () => {
      const gateway = await make('sales')
      const t = await target(gateway)
      const [created] = await gateway.partnerMeetings.create([input(t, unique('pm'))])
      if (!created) throw new Error('생성 실패')

      const same = await gateway.partnerMeetings.update(created.id, { ...input(t, unique('pm')), partnerCompany: t.company.toUpperCase() })
      const error = await expectRejects(gateway.partnerMeetings.update(created.id, { ...input(t, unique('pm')), partnerCompany: '없는회사이름' }), 422)

      expect(same.partnerCompany).toBe(t.company)
      expect(error.problem?.itemErrors?.[0]?.location).toEqual(['partner_company'])
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

    it('does not count partner meetings in a deal deletion impact (AC7)', async () => {
      const admin = await make('admin')
      const t = await target(admin)
      const tag = unique('pm')
      const [created] = await admin.partnerMeetings.create([input(t, `${tag} a`)])
      const [deal] = (await admin.deals.list({ limit: 1 })).items
      if (!created || !deal) throw new Error('준비 실패')

      const impact = await admin.deals.impact(deal.code)

      expect(Object.keys(impact).sort()).toEqual(['actionCount', 'attachmentCount', 'historyCount'])
      expect((await admin.partnerMeetings.list({ ...DEFAULT_QUERY, content: tag }, 0, 10)).total).toBe(1)
      await admin.partnerMeetings.remove(created.id)
    })
  })
}
