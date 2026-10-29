import { describe, expect, it } from 'vitest'
import { MEETING_CONTENTS } from '../../fixtures/partnerMeetings'
import { dealCode, expectApiError, mockAs } from '../testing'
import { USER_ID } from '../seed/ids'

const DEFAULT = { sort: 'meetingDate', order: 'desc' } as const
const item = (company: string, deal: number, content: string, meetingDate = '2026-10-01') => ({
  partnerCompany: company,
  dealCode: dealCode(deal),
  meetingDate,
  content,
})

describe('partner meetings Fake: seed', () => {
  it('has twelve sample meetings in the planned default order', async () => {
    const { gateway } = await mockAs('kim')

    const first = await gateway.partnerMeetings.list(DEFAULT, 0, 10)
    const second = await gateway.partnerMeetings.list(DEFAULT, 10, 10)

    expect(first.total).toBe(12)
    expect(first.items.map((m) => m.content)).toEqual(MEETING_CONTENTS.slice(0, 10))
    expect(second.items.map((m) => m.content)).toEqual(MEETING_CONTENTS.slice(10))
  })

  it('links each seed meeting to a deal the company is an active partner of, including won deals', async () => {
    const { gateway } = await mockAs('kim')

    const options = await gateway.partnerMeetings.dealOptions('디지털웨이')

    expect(options.map((o) => o.code)).toContain(dealCode(11)) // Won
    const names = options.map((o) => o.name.toLowerCase())
    expect(names).toEqual([...names].sort())
  })

  it('excludes a deal whose partner was replaced from the previous company (Deal 17 left 코어테크)', async () => {
    const { gateway } = await mockAs('kim')

    const core = await gateway.partnerMeetings.dealOptions('코어테크')
    const aone = await gateway.partnerMeetings.dealOptions('에이원시스템')

    expect(core.map((o) => o.code)).not.toContain(dealCode(17))
    expect(aone.map((o) => o.code)).toContain(dealCode(17))
  })
})

describe('partner meetings Fake: rules', () => {
  it('lets only the author sales or admin edit and delete (AC14)', async () => {
    const kim = await mockAs('kim')
    const [created] = await kim.gateway.partnerMeetings.create([item('코어테크', 2, '김영업 기록')])
    const id = created?.id ?? 0

    await kim.gateway.auth.quickLogin(USER_ID.park)
    await expectApiError(kim.gateway.partnerMeetings.update(id, item('코어테크', 2, '가로채기')), 403, '본인 미팅 기록 또는 admin만 수정할 수 있습니다.')
    await expectApiError(kim.gateway.partnerMeetings.remove(id), 403, '본인 미팅 기록 또는 admin만 삭제할 수 있습니다.')
    await kim.gateway.auth.quickLogin(USER_ID.han)
    await expectApiError(kim.gateway.partnerMeetings.update(id, item('코어테크', 2, '읽기 전용')), 403)
    await kim.gateway.auth.quickLogin(USER_ID.root)
    await expect(kim.gateway.partnerMeetings.update(id, item('코어테크', 2, '관리자 수정'))).resolves.toMatchObject({ content: '관리자 수정' })
    await expect(kim.gateway.partnerMeetings.remove(id)).resolves.toBeUndefined()
  })

  it('answers 404 before 403 and 403 before 422', async () => {
    const kim = await mockAs('kim')
    const [created] = await kim.gateway.partnerMeetings.create([item('코어테크', 2, '기록')])
    await kim.gateway.auth.quickLogin(USER_ID.park)

    await expectApiError(kim.gateway.partnerMeetings.update(Number.MAX_SAFE_INTEGER, item('코어테크', 2, ' ')), 404, '미팅 기록을 찾을 수 없습니다.')
    await expectApiError(kim.gateway.partnerMeetings.update(created?.id ?? 0, item('코어테크', 2, ' ')), 403)
  })

  it('checks every row of a batch, reports all locations and saves nothing', async () => {
    const kim = await mockAs('kim')

    const error = await expectApiError(
      kim.gateway.partnerMeetings.create([item('코어테크', 2, '정상'), item('없는회사', 2, '회사 없음'), item('시큐어원', 2, ' ')]),
      422,
    )

    expect(error.problem?.itemErrors).toEqual([
      { location: ['items', 1, 'partner_company'], message: '등록된 파트너 회사가 아닙니다. 목록에서 다시 선택하세요.' },
      { location: ['items', 2, 'deal_code'], message: '선택한 파트너와 연결된 Deal이 아닙니다.' },
      { location: ['items', 2, 'content'], message: '미팅 내용을 입력하세요.' },
    ])
    expect((await kim.gateway.partnerMeetings.list(DEFAULT, 0, 10)).total).toBe(12)
  })

  it('keeps a content-only edit valid after the deal partner changed', async () => {
    const kim = await mockAs('kim')
    const [created] = await kim.gateway.partnerMeetings.create([item('코어테크', 2, '이전')])
    await kim.gateway.deals.update(dealCode(2), { partner: null })

    const edited = await kim.gateway.partnerMeetings.update(created?.id ?? 0, item('코어테크', 2, '이후'))

    expect(edited.content).toBe('이후')
    await expectApiError(kim.gateway.partnerMeetings.update(created?.id ?? 0, item('코어테크', 5, '이후')), 422, '선택한 파트너와 연결된 Deal이 아닙니다.')
  })

  it('removes the meetings with their deal and counts them in the deletion impact', async () => {
    const root = await mockAs('root')
    const code = dealCode(1)
    expect((await root.gateway.deals.impact(code)).partnerMeetingCount).toBe(1)

    await root.gateway.deals.remove(code, code)

    const page = await root.gateway.partnerMeetings.list(DEFAULT, 0, 50)
    expect(page.total).toBe(11)
    expect(page.items.map((m) => m.deal.code)).not.toContain(code)
  })
})
