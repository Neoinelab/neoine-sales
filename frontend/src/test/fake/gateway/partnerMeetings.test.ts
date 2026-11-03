import { describe, expect, it } from 'vitest'
import { MEETING_CONTENTS } from '../../fixtures/partnerMeetings'
import { dealCode, expectApiError, mockAs } from '../testing'
import { USER_ID } from '../seed/ids'

const DEFAULT = { sort: 'meetingDate', order: 'desc' } as const
const item = (company: string, content: string, meetingDate = '2026-10-01') => ({
  partnerCompany: company,
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

  it('has no deal in a listed meeting', async () => {
    const { gateway } = await mockAs('kim')

    const page = await gateway.partnerMeetings.list(DEFAULT, 0, 10)

    for (const meeting of page.items) expect(Object.keys(meeting)).not.toContain('deal')
  })

  it('has no deal options lookup any more', async () => {
    const { gateway } = await mockAs('kim')

    expect('dealOptions' in gateway.partnerMeetings).toBe(false)
  })
})

describe('partner meetings Fake: rules', () => {
  it('lets only the author sales or admin edit and delete', async () => {
    const kim = await mockAs('kim')
    const [created] = await kim.gateway.partnerMeetings.create([item('코어테크', '김영업 기록')])
    const id = created?.id ?? 0

    await kim.gateway.auth.quickLogin(USER_ID.park)
    await expectApiError(kim.gateway.partnerMeetings.update(id, item('코어테크', '가로채기')), 403, '본인 미팅 기록 또는 admin만 수정할 수 있습니다.')
    await expectApiError(kim.gateway.partnerMeetings.remove(id), 403, '본인 미팅 기록 또는 admin만 삭제할 수 있습니다.')
    await kim.gateway.auth.quickLogin(USER_ID.han)
    await expectApiError(kim.gateway.partnerMeetings.update(id, item('코어테크', '읽기 전용')), 403)
    await kim.gateway.auth.quickLogin(USER_ID.root)
    await expect(kim.gateway.partnerMeetings.update(id, item('코어테크', '관리자 수정'))).resolves.toMatchObject({ content: '관리자 수정' })
    await expect(kim.gateway.partnerMeetings.remove(id)).resolves.toBeUndefined()
  })

  it('answers 404 before 403 and 403 before 422', async () => {
    const kim = await mockAs('kim')
    const [created] = await kim.gateway.partnerMeetings.create([item('코어테크', '기록')])
    await kim.gateway.auth.quickLogin(USER_ID.park)

    await expectApiError(kim.gateway.partnerMeetings.update(Number.MAX_SAFE_INTEGER, item('코어테크', ' ')), 404, '미팅 기록을 찾을 수 없습니다.')
    await expectApiError(kim.gateway.partnerMeetings.update(created?.id ?? 0, item('코어테크', ' ')), 403)
  })

  it('checks every row of a batch, reports all locations and saves nothing', async () => {
    const kim = await mockAs('kim')

    const error = await expectApiError(
      kim.gateway.partnerMeetings.create([item('코어테크', '정상'), item('없는회사', '회사 없음'), item('시큐어원', ' ')]),
      422,
    )

    expect(error.problem?.itemErrors).toEqual([
      { location: ['items', 1, 'partner_company'], message: '등록된 파트너 회사가 아닙니다. 목록에서 다시 선택하세요.' },
      { location: ['items', 2, 'content'], message: '미팅 내용을 입력하세요.' },
    ])
    expect((await kim.gateway.partnerMeetings.list(DEFAULT, 0, 10)).total).toBe(12)
  })

  it('registers a meeting for a partner company without any deal', async () => {
    const kim = await mockAs('root')
    await kim.gateway.contacts.create('partner', { company: 'Deal없는파트너', name: '가나다', title: '', email: null, phone: null })
    await kim.gateway.auth.quickLogin(USER_ID.kim)

    const [created] = await kim.gateway.partnerMeetings.create([item('deal없는파트너', '첫 만남')])

    expect(created).toMatchObject({ partnerCompany: 'Deal없는파트너', content: '첫 만남' })
  })

  it('edits the date with the company unchanged and rejects an unknown company', async () => {
    const kim = await mockAs('kim')
    const [created] = await kim.gateway.partnerMeetings.create([item('코어테크', '이전')])

    const edited = await kim.gateway.partnerMeetings.update(created?.id ?? 0, item('코어테크', '이전', '2026-11-30'))

    expect(edited).toMatchObject({ partnerCompany: '코어테크', meetingDate: '2026-11-30' })
    await expectApiError(kim.gateway.partnerMeetings.update(created?.id ?? 0, item('없는회사', '이전')), 422, '등록된 파트너 회사가 아닙니다. 목록에서 다시 선택하세요.')
  })

  it('keeps the meetings when their deal is deleted and counts only three things in the impact', async () => {
    const root = await mockAs('root')
    const code = dealCode(1)
    const impact = await root.gateway.deals.impact(code)
    expect(Object.keys(impact).sort()).toEqual(['actionCount', 'attachmentCount', 'historyCount'])

    await root.gateway.deals.remove(code, code)

    const page = await root.gateway.partnerMeetings.list(DEFAULT, 0, 50)
    expect(page.total).toBe(12)
  })
})
