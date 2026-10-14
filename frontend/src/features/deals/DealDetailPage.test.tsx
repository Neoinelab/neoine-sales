import { screen, waitFor, within } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { Route, Routes } from 'react-router'
import { describe, expect, it } from 'vitest'
import {
  DETAIL_CUSTOMER,
  DETAIL_DEAL,
  DETAIL_PARTNER,
  listPage,
  stageChange,
} from '../../test/dealFixtures'
import { userRef } from '../../test/authFixtures'
import { mockApi, problem, renderApp } from '../../test/utils'
import { DealDetailPage } from './DealDetailPage'
import { PipelineSummary } from './PipelineSummary'

const ME = { subject: 's', email: null, name: '박영업', role: 'sales' }

/** 상세 화면이 부르는 기본 API. 테스트마다 필요한 것만 덮어쓴다. */
const baseRoutes = () => ({
  'GET /api/v1/auth/me': { body: ME },
  'GET /api/v1/deals/d-1': { body: DETAIL_DEAL },
  'GET /api/v1/customers/c-1': { body: DETAIL_CUSTOMER },
  'GET /api/v1/partners/p-1': { body: DETAIL_PARTNER },
  'GET /api/v1/deals/d-1/stage-changes': listPage([]),
  'GET /api/v1/deals/d-1/actions': listPage([]),
  'GET /api/v1/customers': listPage([DETAIL_CUSTOMER], 200),
  'GET /api/v1/partners': listPage([DETAIL_PARTNER], 200),
})

function renderDetail(extra?: React.ReactNode) {
  return renderApp(
    <Routes>
      <Route
        path="/deals/:dealId"
        element={
          <>
            <DealDetailPage />
            {extra}
          </>
        }
      />
    </Routes>,
    '/deals/d-1',
  )
}

describe('DealDetailPage customer and partner', () => {
  it('shows customer and partner details', async () => {
    mockApi(baseRoutes())

    renderDetail()

    const customer = await screen.findByRole('region', { name: '고객 정보' })
    await within(customer).findByText('네오인')
    for (const text of ['김고객', '부장', 'kim@neoine.example', '02-1234-5678']) {
      expect(customer).toHaveTextContent(text)
    }
    const partner = await screen.findByRole('region', { name: '파트너 정보' })
    await within(partner).findByText('한빛')
    for (const text of ['이파트', '이사', 'lee@hanbit.example', '031-987-6543']) {
      expect(partner).toHaveTextContent(text)
    }
  })

  it('shows the owner by the server label, including a resigned owner', async () => {
    mockApi({
      ...baseRoutes(),
      'GET /api/v1/deals/d-1': { body: { ...DETAIL_DEAL, owner: userRef('u-7', '이퇴사', true) } },
    })

    renderDetail()

    expect(await screen.findByText('이퇴사(퇴사)')).toBeInTheDocument()
  })

  it('shows no partner when the deal has none', async () => {
    const requests = mockApi({
      ...baseRoutes(),
      'GET /api/v1/deals/d-1': { body: { ...DETAIL_DEAL, partner_id: null } },
    })

    renderDetail()

    const partner = await screen.findByRole('region', { name: '파트너 정보' })
    expect(partner).toHaveTextContent('파트너 없음')
    await screen.findByText('네오인')
    expect(requests.some((r) => r.path.startsWith('/api/v1/partners/'))).toBe(false)
  })

  it('shows a dash for contact fields the customer does not have', async () => {
    mockApi({
      ...baseRoutes(),
      'GET /api/v1/customers/c-1': {
        body: { ...DETAIL_CUSTOMER, contact_title: null, email: null, phone: null },
      },
    })

    renderDetail()

    const customer = await screen.findByRole('region', { name: '고객 정보' })
    await within(customer).findByText('네오인')
    expect(customer).not.toHaveTextContent('null')
    expect(customer).not.toHaveTextContent('undefined')
  })

  it('keeps deal details when the customer cannot be loaded', async () => {
    mockApi({
      ...baseRoutes(),
      'GET /api/v1/customers/c-1': problem(404, 'not-found', '고객을 찾을 수 없습니다'),
    })

    renderDetail()

    expect(await screen.findByRole('heading', { name: /DEAL-001/ })).toBeInTheDocument()
    const customer = await screen.findByRole('region', { name: '고객 정보' })
    expect(await within(customer).findByRole('alert')).toHaveTextContent('고객을 찾을 수 없습니다')
    // 파트너 영역은 영향받지 않는다.
    const partner = screen.getByRole('region', { name: '파트너 정보' })
    expect(await within(partner).findByText('한빛')).toBeInTheDocument()
  })

  it('keeps deal details when the partner cannot be loaded', async () => {
    mockApi({
      ...baseRoutes(),
      'GET /api/v1/partners/p-1': problem(404, 'not-found', '파트너를 찾을 수 없습니다'),
    })

    renderDetail()

    expect(await screen.findByRole('heading', { name: /DEAL-001/ })).toBeInTheDocument()
    const partner = await screen.findByRole('region', { name: '파트너 정보' })
    expect(await within(partner).findByRole('alert')).toHaveTextContent('파트너를 찾을 수 없습니다')
  })
})

describe('DealDetailPage deal states', () => {
  it('shows the current stage in Korean', async () => {
    mockApi({
      ...baseRoutes(),
      'GET /api/v1/deals/d-1': { body: { ...DETAIL_DEAL, stage: 'price_negotiation' } },
    })

    renderDetail()

    const term = await screen.findByText('현재 단계')
    expect(term.nextElementSibling).toHaveTextContent('가격협상')
  })

  it('shows the server message and a way back when the deal does not exist or was deleted', async () => {
    mockApi({
      ...baseRoutes(),
      'GET /api/v1/deals/d-1': problem(404, 'not-found', '딜을 찾을 수 없습니다'),
    })

    renderDetail()

    expect(await screen.findByRole('alert')).toHaveTextContent('딜을 찾을 수 없습니다')
    expect(screen.getByRole('link', { name: '딜 목록으로' })).toHaveAttribute('href', '/deals')
    expect(screen.queryByRole('button', { name: '수정' })).not.toBeInTheDocument()
    expect(screen.queryByRole('region', { name: '단계 변경' })).not.toBeInTheDocument()
  })

  it('keeps the activity history on the page', async () => {
    mockApi(baseRoutes())

    renderDetail()

    expect(await screen.findByRole('region', { name: '활동 이력' })).toBeInTheDocument()
  })
})

describe('DealDetailPage edit', () => {
  it('edits the deal from the detail page', async () => {
    let name = 'ERP 구축'
    const requests = mockApi({
      ...baseRoutes(),
      'GET /api/v1/deals/d-1': () => ({ body: { ...DETAIL_DEAL, name } }),
      'PUT /api/v1/deals/d-1': (request) => {
        name = (request.body as { name: string }).name
        return { body: { ...DETAIL_DEAL, name } }
      },
    })
    renderDetail()
    await screen.findByRole('heading', { name: /ERP 구축/ })

    await userEvent.click(screen.getByRole('button', { name: '수정' }))
    const nameInput = await screen.findByLabelText('Deal Name')
    expect(nameInput).toHaveValue('ERP 구축')
    expect(screen.getByLabelText('Deal Code')).toHaveValue('DEAL-001')
    await userEvent.clear(nameInput)
    await userEvent.type(nameInput, 'ERP 고도화')
    await userEvent.click(screen.getByRole('button', { name: '저장' }))

    await waitFor(() => expect(screen.queryByLabelText('Deal Name')).not.toBeInTheDocument())
    expect(await screen.findByRole('heading', { name: /ERP 고도화/ })).toBeInTheDocument()
    const put = requests.find((r) => r.method === 'PUT')
    expect(put?.path).toBe('/api/v1/deals/d-1')
    expect(put?.body).toMatchObject({ code: 'DEAL-001', name: 'ERP 고도화', customer_id: 'c-1', partner_id: 'p-1' })
  })

  it('closes the edit form without saving when cancelled', async () => {
    const requests = mockApi(baseRoutes())
    renderDetail()
    await screen.findByRole('heading', { name: /ERP 구축/ })

    await userEvent.click(screen.getByRole('button', { name: '수정' }))
    await screen.findByLabelText('Deal Name')
    await userEvent.click(screen.getByRole('button', { name: '취소' }))

    expect(screen.queryByLabelText('Deal Name')).not.toBeInTheDocument()
    expect(requests.some((r) => r.method === 'PUT')).toBe(false)
  })

  it('shows server errors inside the edit form and keeps it open', async () => {
    mockApi({
      ...baseRoutes(),
      'PUT /api/v1/deals/d-1': problem(409, 'already-exists', '이미 존재하는 Deal Code입니다: DEAL-001'),
    })
    renderDetail()
    await screen.findByRole('heading', { name: /ERP 구축/ })

    await userEvent.click(screen.getByRole('button', { name: '수정' }))
    await screen.findByLabelText('Deal Name')
    await userEvent.click(screen.getByRole('button', { name: '저장' }))

    expect(await screen.findByRole('alert')).toHaveTextContent('이미 존재하는 Deal Code')
    expect(screen.getByLabelText('Deal Name')).toBeInTheDocument()
  })
})

describe('DealDetailPage stage change', () => {
  it('refreshes the stage, the history and the pipeline after a successful change', async () => {
    let stage = 'prospecting'
    let history: unknown[] = []
    let pipelineCalls = 0
    const requests = mockApi({
      ...baseRoutes(),
      'GET /api/v1/deals/d-1': () => ({ body: { ...DETAIL_DEAL, stage } }),
      'GET /api/v1/deals/d-1/stage-changes': () => listPage(history),
      'GET /api/v1/deals/pipeline': () => {
        pipelineCalls += 1
        return { body: { stages: [] } }
      },
      'POST /api/v1/deals/d-1/stage': (request) => {
        const body = request.body as { stage: string; reason?: string | null }
        history = [stageChange({ from_stage: stage, to_stage: body.stage, reason: body.reason })]
        stage = body.stage
        return { body: { ...DETAIL_DEAL, stage } }
      },
    })
    renderDetail(<PipelineSummary />)
    const region = await screen.findByRole('region', { name: '단계 변경' })
    await screen.findByText('단계 변경 이력이 없습니다.')
    await waitFor(() => expect(pipelineCalls).toBe(1))

    await userEvent.selectOptions(within(region).getByLabelText('변경할 단계'), 'price_negotiation')
    await userEvent.type(within(region).getByLabelText('사유'), '견적 제출')
    await userEvent.click(within(region).getByRole('button', { name: '단계 변경' }))

    const term = screen.getByText('현재 단계')
    await waitFor(() => expect(term.nextElementSibling).toHaveTextContent('가격협상'))
    const historyRegion = screen.getByRole('region', { name: '단계 이력' })
    expect(await within(historyRegion).findByText(/기회발굴 → 가격협상/)).toBeInTheDocument()
    expect(historyRegion).toHaveTextContent('견적 제출')
    await waitFor(() => expect(pipelineCalls).toBe(2))
    // 현재 단계는 선택지에서 빠지고 이전 단계가 다시 선택지에 나타난다.
    expect(screen.queryByRole('option', { name: '가격협상' })).not.toBeInTheDocument()
    expect(screen.getByRole('option', { name: '기회발굴' })).toBeInTheDocument()
    expect(requests.filter((r) => r.method === 'POST')).toHaveLength(1)
  })

  it('refreshes the deal list queries after a stage change', async () => {
    let listCalls = 0
    mockApi({
      ...baseRoutes(),
      'GET /api/v1/deals': () => {
        listCalls += 1
        return listPage([DETAIL_DEAL])
      },
      'POST /api/v1/deals/d-1/stage': { body: { ...DETAIL_DEAL, stage: 'introduction' } },
    })
    const { DealsPage } = await import('./DealsPage')
    renderDetail(<DealsPage />)
    const region = await screen.findByRole('region', { name: '단계 변경' })
    await waitFor(() => expect(listCalls).toBeGreaterThan(0))
    const before = listCalls

    await userEvent.selectOptions(within(region).getByLabelText('변경할 단계'), 'introduction')
    await userEvent.click(within(region).getByRole('button', { name: '단계 변경' }))

    await waitFor(() => expect(listCalls).toBeGreaterThan(before))
  })

  it('shows a server error from the stage change without changing the displayed stage', async () => {
    mockApi({
      ...baseRoutes(),
      'POST /api/v1/deals/d-1/stage': problem(409, 'invalid-state', '이미 같은 단계입니다'),
    })
    renderDetail()
    const region = await screen.findByRole('region', { name: '단계 변경' })

    await userEvent.selectOptions(within(region).getByLabelText('변경할 단계'), 'introduction')
    await userEvent.click(within(region).getByRole('button', { name: '단계 변경' }))

    expect(await within(region).findByRole('alert')).toHaveTextContent('이미 같은 단계입니다')
    expect(screen.getByText('현재 단계').nextElementSibling).toHaveTextContent('기회발굴')
  })

  it('refreshes the deal and the history when the change fails with 409 because someone else changed it first', async () => {
    let stage = 'prospecting'
    let history: unknown[] = []
    mockApi({
      ...baseRoutes(),
      'GET /api/v1/deals/d-1': () => ({ body: { ...DETAIL_DEAL, stage } }),
      'GET /api/v1/deals/d-1/stage-changes': () => listPage(history),
      'POST /api/v1/deals/d-1/stage': () => {
        // 다른 사용자가 먼저 가격협상으로 바꾼 상태.
        stage = 'price_negotiation'
        history = [stageChange({ from_stage: 'prospecting', to_stage: 'price_negotiation', reason: '타인 변경' })]
        return problem(409, 'invalid-state', '이미 변경된 단계입니다')
      },
    })
    renderDetail()
    const region = await screen.findByRole('region', { name: '단계 변경' })
    await screen.findByText('단계 변경 이력이 없습니다.')

    await userEvent.selectOptions(within(region).getByLabelText('변경할 단계'), 'introduction')
    await userEvent.click(within(region).getByRole('button', { name: '단계 변경' }))

    const term = screen.getByText('현재 단계')
    await waitFor(() => expect(term.nextElementSibling).toHaveTextContent('가격협상'))
    const historyRegion = screen.getByRole('region', { name: '단계 이력' })
    expect(await within(historyRegion).findByText(/기회발굴 → 가격협상/)).toBeInTheDocument()
    // 최신 단계가 선택지에서 빠지고 이전 단계가 다시 나타난다.
    expect(within(region).queryByRole('option', { name: '가격협상' })).not.toBeInTheDocument()
    expect(within(region).getByRole('option', { name: '기회발굴' })).toBeInTheDocument()
  })

  it('lets a lost deal be revived to another stage', async () => {
    const requests = mockApi({
      ...baseRoutes(),
      'GET /api/v1/deals/d-1': { body: { ...DETAIL_DEAL, stage: 'lost' } },
      'POST /api/v1/deals/d-1/stage': { body: { ...DETAIL_DEAL, stage: 'prospecting' } },
    })
    renderDetail()
    const region = await screen.findByRole('region', { name: '단계 변경' })

    await userEvent.selectOptions(within(region).getByLabelText('변경할 단계'), 'prospecting')
    await userEvent.click(within(region).getByRole('button', { name: '단계 변경' }))

    await waitFor(() => expect(requests.some((r) => r.method === 'POST')).toBe(true))
    const post = requests.find((r) => r.method === 'POST')
    expect((post?.body as { stage: string }).stage).toBe('prospecting')
  })
})
