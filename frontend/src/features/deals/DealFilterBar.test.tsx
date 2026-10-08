import { screen } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { describe, expect, it, vi } from 'vitest'
import { mockApi, renderApp } from '../../test/utils'
import { DealFilterBar } from './DealFilterBar'

const page = (items: unknown[]) => ({ body: { items, offset: 0, limit: 200 } })
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
const PARTNER = { id: 'p-1', company_name: '한빛' }

function setup() {
  mockApi({
    'GET /api/v1/customers': page([CUSTOMER]),
    'GET /api/v1/partners': page([PARTNER]),
  })
  const onSearch = vi.fn()
  renderApp(<DealFilterBar onSearch={onSearch} />)
  return onSearch
}

describe('DealFilterBar', () => {
  it('renders a search form with every condition field and a search button', async () => {
    setup()

    const form = screen.getByRole('search')
    expect(form).toBeInTheDocument()
    for (const label of ['검색어', '고객', '파트너', '단계', 'Owner', 'Vendor', '매출 시작일', '매출 종료일']) {
      expect(screen.getByLabelText(label)).toBeInTheDocument()
    }
    expect(screen.getByRole('button', { name: '검색' })).toBeInTheDocument()
  })

  it('lists customers and partners with an all option first', async () => {
    setup()
    await screen.findByRole('option', { name: '네오인' })
    await screen.findByRole('option', { name: '한빛' })

    for (const label of ['고객', '파트너']) {
      const options = Array.from(screen.getByLabelText(label).querySelectorAll('option'))
      expect(options[0]).toHaveTextContent('전체')
      expect(options[0]).toHaveValue('')
    }
  })

  it('submits trimmed filters and sends the end date as the next day', async () => {
    const onSearch = setup()
    await screen.findByRole('option', { name: '네오인' })
    await screen.findByRole('option', { name: '한빛' })

    await userEvent.type(screen.getByLabelText('검색어'), '  erp ')
    await userEvent.selectOptions(screen.getByLabelText('고객'), 'c-1')
    await userEvent.selectOptions(screen.getByLabelText('파트너'), 'p-1')
    await userEvent.type(screen.getByLabelText('Owner'), ' 박영업 ')
    await userEvent.type(screen.getByLabelText('Vendor'), ' SAP ')
    await userEvent.type(screen.getByLabelText('매출 시작일'), '2026-06-01')
    await userEvent.type(screen.getByLabelText('매출 종료일'), '2026-06-30')
    await userEvent.click(screen.getByRole('button', { name: '검색' }))

    expect(onSearch).toHaveBeenCalledTimes(1)
    expect(onSearch).toHaveBeenCalledWith({
      keyword: 'erp',
      customer_id: 'c-1',
      partner_id: 'p-1',
      owner: '박영업',
      vendor: 'SAP',
      revenue_from: '2026-06-01',
      revenue_to: '2026-07-01',
    })
  })

  it('omits empty and blank fields', async () => {
    const onSearch = setup()
    await screen.findByRole('option', { name: '네오인' })

    await userEvent.type(screen.getByLabelText('검색어'), '   ')
    await userEvent.type(screen.getByLabelText('Owner'), '  ')
    await userEvent.type(screen.getByLabelText('Vendor'), ' ')
    await userEvent.click(screen.getByRole('button', { name: '검색' }))

    expect(onSearch).toHaveBeenCalledTimes(1)
    const filters = onSearch.mock.calls[0]![0] as Record<string, unknown>
    for (const key of ['keyword', 'customer_id', 'partner_id', 'owner', 'vendor', 'revenue_from', 'revenue_to']) {
      expect(filters[key] ?? undefined).toBeUndefined()
    }
  })

  it('sends only the end date bound when only the end date is filled', async () => {
    const onSearch = setup()
    await screen.findByRole('option', { name: '네오인' })

    await userEvent.type(screen.getByLabelText('매출 종료일'), '2026-12-31')
    await userEvent.click(screen.getByRole('button', { name: '검색' }))

    const filters = onSearch.mock.calls[0]![0] as Record<string, unknown>
    expect(filters.revenue_to).toBe('2027-01-01')
    expect(filters.revenue_from ?? undefined).toBeUndefined()
  })

  it('lists an all option and the eight stages in Korean, in pipeline order', async () => {
    setup()

    const options = Array.from(screen.getByLabelText('단계').querySelectorAll('option'))

    expect(options).toHaveLength(9)
    expect(options[0]).toHaveTextContent('전체')
    expect(options[0]).toHaveValue('')
    expect(options.slice(1).map((o) => o.getAttribute('value'))).toEqual(STAGE_CODES)
    expect(options.slice(1).map((o) => o.textContent)).toEqual(STAGE_CODES.map((s) => LABELS[s]))
  })

  it('sends the selected stage code with the other conditions', async () => {
    const onSearch = setup()
    await screen.findByRole('option', { name: '네오인' })

    await userEvent.selectOptions(screen.getByLabelText('단계'), 'lost')
    await userEvent.type(screen.getByLabelText('Owner'), '박영업')
    await userEvent.click(screen.getByRole('button', { name: '검색' }))

    expect(onSearch).toHaveBeenCalledTimes(1)
    expect(onSearch).toHaveBeenCalledWith(expect.objectContaining({ stage: 'lost', owner: '박영업' }))
  })

  it('does not send a stage when the all option is selected', async () => {
    const onSearch = setup()
    await screen.findByRole('option', { name: '네오인' })

    await userEvent.selectOptions(screen.getByLabelText('단계'), 'poc_completed')
    await userEvent.selectOptions(screen.getByLabelText('단계'), '')
    await userEvent.click(screen.getByRole('button', { name: '검색' }))

    const filters = onSearch.mock.calls[0]![0] as Record<string, unknown>
    expect(filters.stage ?? undefined).toBeUndefined()
  })
})
