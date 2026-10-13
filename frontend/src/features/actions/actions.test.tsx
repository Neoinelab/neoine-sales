import { screen, waitFor, within } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { describe, expect, it } from 'vitest'
import { mockApi, renderApp, type RecordedRequest } from '../../test/utils'
import { ActionList } from './ActionList'

const ME = { subject: 's', email: null, name: '박영업', role: 'sales' }
const ACTION = {
  id: 'a-1',
  deal_id: 'd-1',
  action_type: 'meeting',
  action: '킥오프 미팅',
  next_action: '제안서 전달',
  due_date: '2026-03-10',
  memo: '요구사항 정리',
  acted_at: '2026-03-02T01:00:00Z',
  actor: '박영업',
  created_at: '2026-03-02T01:00:00Z',
  updated_at: '2026-03-02T01:00:00Z',
}
const page = { body: { items: [ACTION], offset: 0, limit: 20 } }

const searches = (requests: RecordedRequest[]) =>
  requests.filter((r) => r.path === '/api/v1/deals/d-1/actions')

describe('ActionList', () => {
  it('searches within the deal with only the filled-in conditions', async () => {
    const requests = mockApi({ 'GET /api/v1/auth/me': { body: ME }, 'GET /api/v1/deals/d-1/actions': page })
    renderApp(<ActionList dealId="d-1" />)
    await screen.findByText('킥오프 미팅')

    await userEvent.selectOptions(screen.getByLabelText('유형'), 'meeting')
    await userEvent.type(screen.getByLabelText('검색어(진행내역·계획·메모)'), '  견적 ')
    await userEvent.type(screen.getByLabelText('시작일'), '2026-03-01')
    await userEvent.click(screen.getByRole('button', { name: '검색' }))

    await waitFor(() => expect(searches(requests).length).toBeGreaterThan(1))
    const query = searches(requests).at(-1)!.query
    expect(query.get('action_type')).toBe('meeting')
    expect(query.get('keyword')).toBe('견적')
    expect(query.get('acted_from')).toMatch(/Z$/)
    expect(query.has('actor')).toBe(false)
    expect(query.has('acted_to')).toBe(false)
  })

  it('records a new activity for the deal with a timezone-aware time and the user as default actor', async () => {
    const requests = mockApi({
      'GET /api/v1/auth/me': { body: ME },
      'GET /api/v1/deals/d-1/actions': page,
      'POST /api/v1/deals/d-1/actions': { status: 201, body: ACTION },
    })
    renderApp(<ActionList dealId="d-1" />)
    await screen.findByText('킥오프 미팅')

    await userEvent.click(screen.getByRole('button', { name: '활동 기록' }))
    const form = (await screen.findByRole('heading', { name: '활동 기록', level: 3 })).closest('form')!
    await waitFor(() => expect(within(form).getByLabelText('활동자')).toHaveValue('박영업'))
    await userEvent.type(within(form).getByLabelText('진행내역'), '제안서 설명')
    await userEvent.type(within(form).getByLabelText('다음 진행 계획'), '견적 발송')
    await userEvent.type(within(form).getByLabelText('계획일'), '2026-04-01')
    await userEvent.type(within(form).getByLabelText('메모'), '참석 3명')
    await userEvent.click(within(form).getByRole('button', { name: '저장' }))

    await waitFor(() => expect(requests.some((r) => r.method === 'POST')).toBe(true))
    const body = requests.find((r) => r.method === 'POST')?.body as Record<string, string>
    expect(body).toMatchObject({
      action_type: 'meeting',
      action: '제안서 설명',
      next_action: '견적 발송',
      due_date: '2026-04-01',
      memo: '참석 3명',
      actor: '박영업',
    })
    expect(body.acted_at).toMatch(/Z$/)
    expect(body).not.toHaveProperty('title')
    expect(body).not.toHaveProperty('content')
  })

  it('requires action, next action and due date before saving', async () => {
    const requests = mockApi({ 'GET /api/v1/auth/me': { body: ME }, 'GET /api/v1/deals/d-1/actions': page })
    renderApp(<ActionList dealId="d-1" />)
    await screen.findByText('킥오프 미팅')

    await userEvent.click(screen.getByRole('button', { name: '활동 기록' }))
    const form = (await screen.findByRole('heading', { name: '활동 기록', level: 3 })).closest('form')!
    await userEvent.click(within(form).getByRole('button', { name: '저장' }))

    expect(within(form).getByLabelText('진행내역')).toBeRequired()
    expect(within(form).getByLabelText('다음 진행 계획')).toBeRequired()
    expect(within(form).getByLabelText('계획일')).toBeRequired()
    expect(within(form).getByLabelText('메모')).not.toBeRequired()
    expect(requests.some((r) => r.method === 'POST')).toBe(false)
  })

  it('edits an existing activity with the same fields', async () => {
    const requests = mockApi({
      'GET /api/v1/auth/me': { body: ME },
      'GET /api/v1/deals/d-1/actions': page,
      'PUT /api/v1/deal-actions/a-1': { body: ACTION },
    })
    renderApp(<ActionList dealId="d-1" />)
    await screen.findByText('킥오프 미팅')

    await userEvent.click(screen.getByRole('button', { name: '수정' }))
    const form = (await screen.findByRole('heading', { name: '활동 수정', level: 3 })).closest('form')!
    expect(within(form).getByLabelText('다음 진행 계획')).toHaveValue('제안서 전달')
    expect(within(form).getByLabelText('계획일')).toHaveValue('2026-03-10')
    await userEvent.clear(within(form).getByLabelText('다음 진행 계획'))
    await userEvent.type(within(form).getByLabelText('다음 진행 계획'), '계약 협의')
    await userEvent.click(within(form).getByRole('button', { name: '저장' }))

    await waitFor(() => expect(requests.some((r) => r.method === 'PUT')).toBe(true))
    expect(requests.find((r) => r.method === 'PUT')?.body).toMatchObject({
      action: '킥오프 미팅',
      next_action: '계약 협의',
      due_date: '2026-03-10',
      memo: '요구사항 정리',
    })
  })

  it('shows the plan columns and a placeholder for missing plan values', async () => {
    const legacy = { ...ACTION, id: 'a-2', action: '구 활동', next_action: null, due_date: null }
    mockApi({
      'GET /api/v1/auth/me': { body: ME },
      'GET /api/v1/deals/d-1/actions': { body: { items: [ACTION, legacy], offset: 0, limit: 20 } },
    })
    renderApp(<ActionList dealId="d-1" />)

    expect(await screen.findByRole('columnheader', { name: '다음 진행 계획' })).toBeInTheDocument()
    expect(screen.getByRole('columnheader', { name: '계획일' })).toBeInTheDocument()
    await screen.findByText('구 활동')
    const rows = screen.getAllByRole('row')
    const ok = rows.find((r) => within(r).queryByText('킥오프 미팅'))!
    expect(within(ok).getByText('제안서 전달')).toBeInTheDocument()
    expect(within(ok).getByText('2026-03-10')).toBeInTheDocument()
    const old = rows.find((r) => within(r).queryByText('구 활동'))!
    expect(within(old).getAllByText('미입력')).toHaveLength(2)
  })

  it('sends due range and sort conditions only when filled', async () => {
    const requests = mockApi({ 'GET /api/v1/auth/me': { body: ME }, 'GET /api/v1/deals/d-1/actions': page })
    renderApp(<ActionList dealId="d-1" />)
    await screen.findByText('킥오프 미팅')
    expect(searches(requests)[0]!.query.has('due_from')).toBe(false)
    expect(searches(requests)[0]!.query.has('sort')).toBe(false)

    await userEvent.type(screen.getByLabelText('계획일 시작'), '2026-03-05')
    await userEvent.type(screen.getByLabelText('계획일 종료'), '2026-03-20')
    await userEvent.selectOptions(screen.getByLabelText('정렬'), 'due_date_asc')
    await userEvent.click(screen.getByRole('button', { name: '검색' }))

    await waitFor(() => expect(searches(requests).length).toBeGreaterThan(1))
    const query = searches(requests).at(-1)!.query
    expect(query.get('due_from')).toBe('2026-03-05')
    expect(query.get('due_to')).toBe('2026-03-20')
    expect(query.get('sort')).toBe('due_date_asc')
  })

  it('is read-only in the global search and links to the deal', async () => {
    mockApi({ 'GET /api/v1/auth/me': { body: ME }, 'GET /api/v1/deal-actions': page })
    renderApp(<ActionList />)

    expect(await screen.findByRole('link', { name: '딜 보기' })).toHaveAttribute('href', '/deals/d-1')
    expect(screen.queryByRole('button', { name: '활동 기록' })).not.toBeInTheDocument()
    expect(screen.queryByRole('button', { name: '삭제' })).not.toBeInTheDocument()
  })
})
