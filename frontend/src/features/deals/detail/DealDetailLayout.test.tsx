import { screen, within } from '@testing-library/react'
import { describe, expect, it } from 'vitest'
import { renderAt } from '../../../test/mockApp'
import { detailPath } from './detailTestUtils'

async function openDetail(no: number, title: string) {
  const view = await renderAt(await detailPath(no))
  await screen.findByRole('heading', { level: 1, name: title })
  return view
}

/** dl 안의 dt/dd를 [라벨, 값] 쌍으로 읽는다. */
function pairsOf(root: HTMLElement): Array<[string, string]> {
  const dl = root.querySelector('dl')
  if (!dl) throw new Error('dl이 없습니다.')
  const terms = Array.from(dl.querySelectorAll('dt'))
  return terms.map((dt): [string, string] => [dt.textContent ?? '', dt.parentElement?.querySelector('dd')?.textContent ?? ''])
}

describe('Deal 상세 상단 통합 영역 (Deal 정보 타일 제거)', () => {
  it('has no 정보 tile and shows vendor, solution, users, quote, poc and procurement in the top area', async () => {
    await openDetail(1, '한빛은행 ITDR 도입')
    expect(screen.queryByRole('heading', { name: 'Deal 정보' })).not.toBeInTheDocument()
    expect(screen.queryByRole('region', { name: 'Deal 정보' })).not.toBeInTheDocument()
    const bar = screen.getByRole('region', { name: '현재 값' })
    const facts = Object.fromEntries(pairsOf(bar))
    expect(facts['Vendor']).toBe('Silverfort')
    expect(facts['Solution']).toBe('ITDR')
    expect(facts['Users']).toBe('1500')
    expect(facts['견적']).toMatch(/^제출/)
    expect(facts['POC']).toMatch(/^YES · 완료/)
    expect(facts['구매절차']).toBe('조달청 경쟁 입찰')
  })

  it('keeps status and forecast editors in the same top area as the facts', async () => {
    await openDetail(1, '한빛은행 ITDR 도입')
    const bar = screen.getByRole('region', { name: '현재 값' })
    expect(within(bar).getByRole('button', { name: 'Status 수정' })).toHaveTextContent('가격협상')
    expect(within(bar).getByRole('button', { name: 'Forecast 수정' })).toHaveTextContent('Commit')
    expect(within(bar).getByText('Vendor')).toBeVisible()
  })

  it('shows the owner in the title area only, not again in the top area', async () => {
    await openDetail(1, '한빛은행 ITDR 도입')
    expect(screen.getByText('Owner: 김영업')).toBeVisible()
    const bar = screen.getByRole('region', { name: '현재 값' })
    expect(within(bar).queryByText('Owner')).not.toBeInTheDocument()
  })
})

describe('고객 · 파트너 · BANT 타일 (1열, 가로 라벨-값)', () => {
  it('renders the three tiles in DOM order customer, partner, BANT', async () => {
    await openDetail(1, '한빛은행 ITDR 도입')
    const tiles = ['고객', '파트너', 'BANT'].map((name) => screen.getByRole('region', { name }))
    const [customer, partner, bant] = tiles as [HTMLElement, HTMLElement, HTMLElement]
    expect(customer.compareDocumentPosition(partner) & Node.DOCUMENT_POSITION_FOLLOWING).toBeTruthy()
    expect(partner.compareDocumentPosition(bant) & Node.DOCUMENT_POSITION_FOLLOWING).toBeTruthy()
    expect(customer.parentElement).toBe(bant.parentElement)
  })

  it('renders customer and partner contents as label-value pairs', async () => {
    await openDetail(1, '한빛은행 ITDR 도입')
    const customer = pairsOf(screen.getByRole('region', { name: '고객' }))
    expect(customer.map(([k]) => k)).toEqual(['회사', '담당자', '직급', '이메일', '전화'])
    expect(customer.map(([, v]) => v).slice(0, 2)).toEqual(['한빛은행', '정민수'])
    const partner = pairsOf(screen.getByRole('region', { name: '파트너' }))
    expect(partner.map(([k]) => k)).toEqual(['회사', '담당자', '직급', '이메일', '전화'])
    expect(partner.map(([, v]) => v).slice(0, 1)).toEqual(['에이원시스템'])
  })

  it('renders the four BANT items as label-value pairs with a click-to-edit value each', async () => {
    await openDetail(1, '한빛은행 ITDR 도입')
    const bant = screen.getByRole('region', { name: 'BANT' })
    expect(pairsOf(bant).map(([k]) => k)).toEqual(['Budget', 'Authority', 'Need', 'Timeline'])
    expect(within(bant).getByRole('button', { name: 'Budget 수정' })).toHaveTextContent('단독 예산 확보')
  })
})
