import { screen, waitFor, within } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { describe, expect, it, vi } from 'vitest'
import { mockApi, renderApp, type RecordedRequest } from '../../test/utils'
import { DealsPage } from './DealsPage'

const STAGE_CODES = [
  'prospecting',
  'introduction',
  'poc_preparation',
  'poc_completed',
  'technical_evaluation',
  'price_negotiation',
  'contract_completed',
  'lost',
]
const LABELS: Record<string, string> = {
  prospecting: '기회발굴',
  introduction: '제품소개',
  poc_preparation: 'POC준비',
  poc_completed: 'POC완료',
  technical_evaluation: '기술평가',
  price_negotiation: '가격협상',
  contract_completed: '계약완료',
  lost: '실주',
}
const CUSTOMER = { id: 'c-1', company_name: '네오인' }
const deal = (n: number, stage: string) => ({
  id: `d-${n}`,
  code: `DEAL-${String(n).padStart(3, '0')}`,
  name: 'ERP 구축',
  owner: '박영업',
  vendor: 'SAP',
  solution: 'S/4',
  revenue_amount: '1',
  revenue_currency: 'KRW',
  revenue_date: '2026-06-30',
  customer_id: 'c-1',
  partner_id: null,
  stage,
  created_at: '2026-01-01T00:00:00Z',
  updated_at: '2026-01-01T00:00:00Z',
})
const options = (items: unknown[]) => ({ body: { items, offset: 0, limit: 200 } })

/** 8개 단계 전부를 담은 파이프라인 응답. 지정하지 않은 단계는 0건. */
function pipeline(counts: Record<string, { count: number; totals: { currency: string; amount: string }[] }> = {}) {
  return {
    body: {
      stages: STAGE_CODES.map((stage) => ({
        stage,
        deal_count: counts[stage]?.count ?? 0,
        totals: counts[stage]?.totals ?? [],
      })),
    },
  }
}

function routes(items: unknown[], pipelineReply = pipeline()) {
  return {
    'GET /api/v1/deals': { body: { items, offset: 0, limit: 20 } },
    'GET /api/v1/deals/pipeline': pipelineReply,
    'GET /api/v1/customers': options([CUSTOMER]),
    'GET /api/v1/partners': options([]),
  }
}

const dealRequests = (requests: RecordedRequest[]) =>
  requests.filter((r) => r.method === 'GET' && r.path === '/api/v1/deals')

describe('DealsPage stage column', () => {
  it('shows the stage column in Korean', async () => {
    mockApi(routes([deal(1, 'price_negotiation'), deal(2, 'lost'), deal(3, 'prospecting')]))

    renderApp(<DealsPage />, '/deals')

    await screen.findByRole('link', { name: 'DEAL-001' })
    expect(screen.getByRole('columnheader', { name: '단계' })).toBeInTheDocument()
    const rowOf = (code: string) => screen.getByRole('link', { name: code }).closest('tr') as HTMLElement
    expect(within(rowOf('DEAL-001')).getByText('가격협상')).toBeInTheDocument()
    expect(within(rowOf('DEAL-002')).getByText('실주')).toBeInTheDocument()
    expect(within(rowOf('DEAL-003')).getByText('기회발굴')).toBeInTheDocument()
  })

  it('shows every stage in the Korean label table for each deal', async () => {
    mockApi(routes(STAGE_CODES.map((stage, n) => deal(n + 1, stage))))

    renderApp(<DealsPage />, '/deals')

    await screen.findByRole('link', { name: 'DEAL-001' })
    STAGE_CODES.forEach((stage, n) => {
      const row = screen.getByRole('link', { name: `DEAL-${String(n + 1).padStart(3, '0')}` }).closest('tr') as HTMLElement
      expect(within(row).getByText(LABELS[stage]!)).toBeInTheDocument()
    })
  })

  it('spans the whole table in the empty message after adding the stage column', async () => {
    mockApi(routes([]))

    renderApp(<DealsPage />, '/deals')

    const cell = (await screen.findByText('등록된 딜이 없습니다.')).closest('td') as HTMLElement
    const headers = screen.getAllByRole('columnheader')
    expect(headers).toHaveLength(10)
    expect(cell).toHaveAttribute('colspan', String(headers.length))
  })
})

describe('DealsPage stage filter', () => {
  it('requests only offset and limit when no stage is chosen', async () => {
    const requests = mockApi(routes([deal(1, 'prospecting')]))

    renderApp(<DealsPage />, '/deals')
    await screen.findByRole('link', { name: 'DEAL-001' })

    expect(dealRequests(requests)[0]!.query.has('stage')).toBe(false)
  })

  it('searches with the chosen stage code', async () => {
    const requests = mockApi(routes([deal(1, 'prospecting')]))
    renderApp(<DealsPage />, '/deals')
    await screen.findByRole('link', { name: 'DEAL-001' })

    await userEvent.selectOptions(screen.getByLabelText('단계'), 'lost')
    await userEvent.click(screen.getByRole('button', { name: '검색' }))

    await waitFor(() => expect(dealRequests(requests).at(-1)!.query.get('stage')).toBe('lost'))
    expect(dealRequests(requests).at(-1)!.query.get('offset')).toBe('0')
  })

  it('says nothing matches when a stage search finds no deals', async () => {
    mockApi({
      ...routes([deal(1, 'prospecting')]),
      'GET /api/v1/deals': (r: RecordedRequest) => ({
        body: { items: r.query.has('stage') ? [] : [deal(1, 'prospecting')], offset: 0, limit: 20 },
      }),
    })
    renderApp(<DealsPage />, '/deals')
    await screen.findByRole('link', { name: 'DEAL-001' })

    await userEvent.selectOptions(screen.getByLabelText('단계'), 'contract_completed')
    await userEvent.click(screen.getByRole('button', { name: '검색' }))

    expect(await screen.findByText('조건에 맞는 딜이 없습니다.')).toBeInTheDocument()
  })
})

describe('DealsPage pipeline summary', () => {
  const COUNTS = {
    prospecting: { count: 7, totals: [{ currency: 'KRW', amount: '1200000' }] },
    price_negotiation: {
      count: 4,
      totals: [
        { currency: 'KRW', amount: '5000' },
        { currency: 'USD', amount: '88.5' },
      ],
    },
  }

  it('shows the pipeline summary above the list', async () => {
    mockApi(routes([deal(1, 'prospecting')], pipeline(COUNTS)))

    renderApp(<DealsPage />, '/deals')

    const summary = await screen.findByRole('region', { name: '파이프라인 현황' })
    const table = screen.getByRole('table')
    expect(summary.compareDocumentPosition(table) & Node.DOCUMENT_POSITION_FOLLOWING).toBeTruthy()
  })

  it('shows count and per-currency totals for each stage', async () => {
    mockApi(routes([deal(1, 'prospecting')], pipeline(COUNTS)))
    renderApp(<DealsPage />, '/deals')
    const summary = await screen.findByRole('region', { name: '파이프라인 현황' })

    const stageItem = async (label: string) =>
      (await within(summary).findByText(label)).closest('li, tr') as HTMLElement
    const first = await stageItem('기회발굴')
    expect(first).toHaveTextContent(/(^|\D)7(\D|$)/)
    expect(first).toHaveTextContent('1,200,000 KRW')
    const negotiation = await stageItem('가격협상')
    expect(negotiation).toHaveTextContent(/(^|\D)4(\D|$)/)
    expect(negotiation).toHaveTextContent('5,000 KRW')
    expect(negotiation).toHaveTextContent('88.5 USD')
  })

  it('lists all eight stages including the empty ones, in order', async () => {
    mockApi(routes([], pipeline(COUNTS)))
    renderApp(<DealsPage />, '/deals')
    const summary = await screen.findByRole('region', { name: '파이프라인 현황' })

    await within(summary).findByText('기회발굴')

    const text = summary.textContent ?? ''
    const positions = STAGE_CODES.map((stage) => text.indexOf(LABELS[stage]!))
    expect(positions.every((p) => p >= 0)).toBe(true)
    expect([...positions].sort((a, b) => a - b)).toEqual(positions)
    const empty = within(summary).getByText('실주').closest('li, tr') as HTMLElement
    expect(empty).toHaveTextContent(/(^|\D)0(\D|$)/)
  })

  it('refreshes the summary after a deal is deleted', async () => {
    const requests = mockApi({
      ...routes([deal(1, 'prospecting')], pipeline(COUNTS)),
      'DELETE /api/v1/deals/d-1': { status: 204 },
    })
    vi.spyOn(window, 'confirm').mockReturnValue(true)
    renderApp(<DealsPage />, '/deals')
    await screen.findByRole('link', { name: 'DEAL-001' })
    await screen.findByRole('region', { name: '파이프라인 현황' })
    const before = requests.filter((r) => r.path === '/api/v1/deals/pipeline').length

    await userEvent.click(screen.getByRole('button', { name: '삭제' }))

    await waitFor(() =>
      expect(requests.filter((r) => r.path === '/api/v1/deals/pipeline').length).toBeGreaterThan(before),
    )
  })

  it('shows the server message when deleting a deal that has activities or stage history', async () => {
    const detail = '활동 또는 단계 변경 이력이 있어 삭제할 수 없습니다: d-1'
    const confirm = vi.spyOn(window, 'confirm').mockReturnValue(true)
    mockApi({
      ...routes([deal(1, 'prospecting')], pipeline(COUNTS)),
      'DELETE /api/v1/deals/d-1': {
        status: 409,
        body: { type: 'x', title: 'Conflict', status: 409, detail, instance: '/x' },
      },
    })
    renderApp(<DealsPage />, '/deals')
    await screen.findByRole('link', { name: 'DEAL-001' })

    await userEvent.click(screen.getByRole('button', { name: '삭제' }))

    expect(confirm).toHaveBeenCalledWith(expect.stringContaining('활동 또는 단계 변경 이력이 있으면 삭제할 수 없습니다'))
    expect(await screen.findByRole('alert')).toHaveTextContent(detail)
    expect(screen.getByRole('link', { name: 'DEAL-001' })).toBeInTheDocument()
  })

  it('keeps the list usable when the summary cannot be loaded', async () => {
    mockApi({
      ...routes([deal(1, 'prospecting')]),
      'GET /api/v1/deals/pipeline': { status: 500, body: { type: 'x', title: 'x', status: 500, detail: '실패', instance: '/x' } },
    })

    renderApp(<DealsPage />, '/deals')

    expect(await screen.findByRole('link', { name: 'DEAL-001' })).toBeInTheDocument()
  })
})
