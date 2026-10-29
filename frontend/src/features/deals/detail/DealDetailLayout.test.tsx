import { screen, waitFor, within } from '@testing-library/react'
import { describe, expect, it } from 'vitest'
import { renderAt } from '../../../test/mockApp'
import { detailPath } from '../../../test/detailTestUtils'
import { kvPairs, kvValue } from '../../../test/kvPairs'
import type { TestRole } from '../../../test/mockApp'

async function openDetail(no: number, title: string, role?: TestRole) {
  const view = await renderAt(await detailPath(no), role === undefined ? {} : { role })
  await screen.findByRole('heading', { level: 1, name: title })
  return view
}

/** dl 안의 dt/dd를 [라벨, 값] 쌍으로 읽는다. */
const pairsOf = kvPairs

const INFO_LABELS = [
  'Deal code',
  'Owner',
  'Status',
  'Forecast',
  '금액(단위:천원)',
  'Expected Close',
  'Next Action',
  '최종 업데이트',
  'Vendor',
  'Solution',
  'Users count',
  '견적',
  'POC',
  '구매절차',
  '등록일',
]

const infoTile = () => screen.getByRole('region', { name: 'Deal 정보' })

describe('Deal 정보 타일 (상단 통합 영역)', () => {
  it('shows a deal info tile titled like the other tiles with vendor, solution, users, quote, poc and procurement', async () => {
    await openDetail(1, '한빛은행 ITDR 도입')
    const heading = screen.getByRole('heading', { level: 2, name: 'Deal 정보' })
    const bar = infoTile()
    expect(within(bar).getAllByRole('heading')[0]).toBe(heading)
    expect(screen.queryByRole('region', { name: '현재 값' })).not.toBeInTheDocument()
    const facts = Object.fromEntries(pairsOf(bar))
    expect(facts['Vendor']).toBe('Silverfort')
    expect(facts['Solution']).toBe('ITDR')
    expect(facts['Users count']).toBe('1500')
    expect(facts['견적']).toMatch(/^제출/)
    expect(facts['POC']).toMatch(/^YES · 완료/)
    expect(facts['구매절차']).toBe('조달청 경쟁 입찰')
  })

  it('keeps status and forecast editors in the same top area as the facts', async () => {
    await openDetail(1, '한빛은행 ITDR 도입')
    const bar = infoTile()
    expect(within(bar).getByRole('button', { name: 'Status 수정' })).toHaveTextContent('가격협상')
    expect(within(bar).getByRole('button', { name: 'Forecast 수정' })).toHaveTextContent('Commit')
    expect(within(bar).getByText('Vendor')).toBeVisible()
  })

  it('shows the owner and the deal code in the deal info tile, not in the header', async () => {
    await openDetail(1, '한빛은행 ITDR 도입')
    const header = screen.getByRole('heading', { level: 1 }).closest('header') as HTMLElement
    expect(header.textContent).not.toContain('Owner')
    expect(header.textContent).not.toContain('Deal code')
    const labels = pairsOf(infoTile()).map(([k]) => k)
    expect(labels).toContain('Owner')
    expect(labels).toContain('Deal code')
  })

  it('orders the deal info items from deal code and owner to the registration date', async () => {
    await openDetail(1, '한빛은행 ITDR 도입')
    const tile = infoTile()
    expect(tile.querySelectorAll('dl')).toHaveLength(1)
    expect(pairsOf(tile).map(([k]) => k)).toEqual(INFO_LABELS)
  })

  it('titles the four tiles with level two headings in order', async () => {
    await openDetail(1, '한빛은행 ITDR 도입')
    const names = ['Deal 정보', '고객', '파트너', 'BANT']
    const tiles = names.map((name) => screen.getByRole('region', { name }))
    tiles.forEach((tile, i) => {
      const first = tile.firstElementChild as HTMLElement
      expect(first.tagName).toBe('H2')
      expect(first).toHaveTextContent(names[i] as string)
      const next = tiles[i + 1]
      if (next) expect(tile.compareDocumentPosition(next) & Node.DOCUMENT_POSITION_FOLLOWING).toBeTruthy()
    })
  })

  it('shows the deal code as plain text without an edit button', async () => {
    await openDetail(1, '한빛은행 ITDR 도입')
    const code = kvValue(infoTile(), 'Deal code')
    expect(code.textContent).toMatch(/^\S+-D001$/)
    expect(screen.queryByRole('button', { name: 'Deal code 수정' })).not.toBeInTheDocument()
    expect(within(code).queryByRole('button')).not.toBeInTheDocument()
  })

  it('edits the owner in place inside the deal info tile', async () => {
    const { user } = await openDetail(1, '한빛은행 ITDR 도입')
    await user.click(within(infoTile()).getByRole('button', { name: 'Owner 수정' }))
    await user.selectOptions(within(infoTile()).getByLabelText('Owner'), '박영업')
    await waitFor(() => expect(within(infoTile()).getByRole('button', { name: 'Owner 수정' })).toHaveTextContent('박영업'))
    expect(await screen.findByText('Owner가 변경되었습니다.')).toBeVisible()
    await user.click(screen.getByRole('tab', { name: 'Deal History' }))
    expect(await screen.findByRole('cell', { name: 'Owner' })).toBeVisible()
  })

  it('shows the owner as plain text for a viewer', async () => {
    await openDetail(1, '한빛은행 ITDR 도입', 'user')
    const owner = kvValue(infoTile(), 'Owner')
    expect(owner).toHaveTextContent(/^김영업$/)
    expect(screen.queryByRole('button', { name: 'Owner 수정' })).not.toBeInTheDocument()
  })

  it('wraps every read-only value of a viewer in the same box as the edit button', async () => {
    await openDetail(1, '한빛은행 ITDR 도입', 'user')
    expect(kvValue(infoTile(), 'Owner').firstElementChild).toHaveClass('kv-static')
    expect(kvValue(infoTile(), 'Vendor').firstElementChild).toHaveClass('kv-static')
    expect(kvValue(screen.getByRole('region', { name: 'BANT' }), 'Budget').firstElementChild).toHaveClass('kv-static')
  })

  it('keeps the header to the deal name and the list and delete buttons', async () => {
    await openDetail(1, '한빛은행 ITDR 도입')
    const header = screen.getByRole('heading', { level: 1 }).closest('header') as HTMLElement
    expect(header.textContent).not.toContain('Deal code')
    expect(header.textContent).not.toContain('Owner')
    const controls = Array.from(header.querySelectorAll('a, button')).map((el) => el.getAttribute('title') === 'Deal 이름 수정' ? 'title' : (el.getAttribute('aria-label') ?? el.textContent ?? '').trim())
    expect(controls.sort()).toEqual(['title', 'Deal 삭제', '← 목록'].sort())
  })
})

describe('고객 · 파트너 · BANT 타일 (라벨-값 한 줄 격자)', () => {
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

describe('모든 타일의 dt dd 구조와 연락처 편집 세션', () => {
  it('renders every item of the four tiles as a dt dd pair in one row element', async () => {
    await openDetail(1, '한빛은행 ITDR 도입')
    for (const name of ['Deal 정보', '고객', '파트너', 'BANT']) {
      const tile = screen.getByRole('region', { name })
      const dl = tile.querySelector('dl') as HTMLElement
      const terms = Array.from(dl.querySelectorAll('dt'))
      expect(terms.length).toBeGreaterThan(0)
      for (const dt of terms) {
        const row = dt.parentElement as HTMLElement
        expect(row.classList.contains('kv-row')).toBe(true)
        expect(row.children[0]).toBe(dt)
        expect(row.children[1]?.tagName).toBe('DD')
        expect(row.parentElement).toBe(dl)
      }
    }
  })

  it('shows the contact edit session as label rows with short visible labels', async () => {
    const { user } = await openDetail(1, '한빛은행 ITDR 도입')
    const customer = () => screen.getByRole('region', { name: '고객' })
    await user.click(within(customer()).getByRole('button', { name: '고객 회사명 수정' }))
    expect(within(customer()).getByRole('combobox', { name: '고객 회사명' })).toHaveFocus()
    const visible = [
      ['고객 회사명', '회사'],
      ['고객 담당자명', '담당자'],
      ['고객 직급', '직급'],
      ['고객 이메일', '이메일'],
      ['고객 전화', '전화'],
    ] as const
    for (const [accessible, shown] of visible) {
      // 회사명 입력에 포커스가 있으면 같은 이름의 목록(listbox)도 열려 있으므로 input만 고른다.
      const input = within(customer()).getAllByLabelText(accessible).find((el): el is HTMLInputElement => el instanceof HTMLInputElement)
      if (!input) throw new Error(`${accessible} 입력이 없습니다.`)
      expect(Array.from(input.labels ?? []).map((l) => l.textContent)).toContain(shown)
    }
  })
})
