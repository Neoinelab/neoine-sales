import { screen, waitFor, within } from '@testing-library/react'
import { afterEach, describe, expect, it, vi } from 'vitest'
import { gateway } from '../../../gateway'
import type { DealRow } from '../../../shared/model/types'
import { renderAt } from '../../../test/mockApp'
import { dealCodeOf } from '../../../test/detailTestUtils'
import { rowOf } from './testHelpers'

/** 머리글 순서로 BANT 칸(td)을 찾는다. 열이 없으면 오류로 실패한다. */
function bantCell(row: HTMLElement): HTMLElement {
  const index = screen.getAllByRole('columnheader').findIndex((h) => h.textContent?.trim() === 'BANT')
  if (index < 0) throw new Error('BANT 열이 없습니다.')
  const cell = within(row).getAllByRole('cell')[index]
  if (!cell) throw new Error('BANT 칸이 없습니다.')
  return cell
}

afterEach(() => {
  vi.restoreAllMocks()
})

const ITEM_NAME = /^(Budget|Authority|Need|Timeline): /

async function labelId(category: string, name: string): Promise<number> {
  const labels = await gateway.labels.list()
  const found = labels.find((l) => l.category === category && l.name === name)
  if (!found) throw new Error(`Label ${name} 없음`)
  return found.id
}

describe('목록의 BANT 열 (P8 AC-14~18)', () => {
  it('shows the chosen BANT labels in the BANT column', async () => {
    await renderAt('/deals?q=한빛은행 ITDR')
    const cell = bantCell(await rowOf(/한빛은행 ITDR 도입/))

    const items = [
      within(cell).getByLabelText('Budget: 단독 예산 확보'),
      within(cell).getByLabelText('Authority: CISO 보고 완료'),
      within(cell).getByLabelText('Need: 보안 강화 요건'),
      within(cell).getByLabelText('Timeline: 금년 구매'),
    ]
    items.forEach((item, i) => {
      const next = items[i + 1]
      if (next) expect(item.compareDocumentPosition(next) & Node.DOCUMENT_POSITION_FOLLOWING).toBeTruthy()
    })
    expect(within(cell).getAllByLabelText(ITEM_NAME)).toHaveLength(4)
    expect(cell).toHaveTextContent('B')
    expect(cell).toHaveTextContent('단독 예산 확보')
  })

  it('shows only the chosen categories and keeps the fixed order', async () => {
    await renderAt('/deals?q=대한제조 MFA')
    const cell = bantCell(await rowOf(/대한제조 MFA 확대/)) // Need가 비어 있는 Deal

    expect(within(cell).getByLabelText('Budget: 풀 예산 확보')).toBeVisible()
    expect(within(cell).getByLabelText('Authority: 팀장 보고 완료')).toBeVisible()
    expect(within(cell).getByLabelText('Timeline: POC 후 일정수립')).toBeVisible()
    expect(within(cell).queryByLabelText(/^Need: /)).not.toBeInTheDocument()
  })

  it('shows a dash when no BANT label is chosen', async () => {
    await renderAt('/deals?q=누리통신 NGFW')
    const cell = bantCell(await rowOf(/누리통신 NGFW/))

    expect(cell).toHaveTextContent(/^—$/)
    expect(within(cell).queryByLabelText(ITEM_NAME)).not.toBeInTheDocument()
  })

  it('bant column header is not sortable', async () => {
    await renderAt('/deals')
    await rowOf(/한빛은행 ITDR 도입/)

    const header = screen.getByRole('columnheader', { name: 'BANT' })
    expect(within(header).queryByRole('button')).not.toBeInTheDocument()
    expect(header).not.toHaveAttribute('aria-sort')
  })

  it('keeps the existing sortable headers sortable', async () => {
    await renderAt('/deals')
    await rowOf(/한빛은행 ITDR 도입/)

    for (const name of ['Deal', 'Status', '금액(단위:천원)', 'Expected Close', '최종 업데이트']) {
      expect(within(screen.getByRole('columnheader', { name })).getByRole('button')).toBeVisible()
    }
  })

  it('long label names keep the full name in the title', async () => {
    const longName = '가'.repeat(50)
    const { client } = await renderAt('/deals?q=한빛은행 ITDR')
    const row = await rowOf(/한빛은행 ITDR 도입/)
    const target = await dealRowOfName('한빛은행 ITDR 도입')
    const keep = (id: number | null) => (id === null ? null : { id })
    await gateway.deals.update(target.code, {
      bant: { budget: { name: longName }, authority: keep(target.bant.authority), need: keep(target.bant.need), timeline: keep(target.bant.timeline) },
    })
    await client.invalidateQueries()

    await waitFor(() => {
      const hit = within(bantCell(row)).getByTitle((title) => title.includes(longName))
      expect(hit).toBeVisible()
    })
  })

  it('quick view row spans every column', async () => {
    const { user } = await renderAt('/deals?q=한빛은행 ITDR')
    const row = await rowOf(/한빛은행 ITDR 도입/)
    await user.click(within(row).getByRole('button', { name: /빠른 보기/ }))

    const view = screen.getByRole('region', { name: /빠른 보기/ })
    const headerCount = screen.getAllByRole('columnheader').length
    expect(headerCount).toBe(12)
    expect(view.closest('td')).toHaveAttribute('colspan', String(headerCount))
  })
})

describe('목록의 BANT 열 갱신 (P8 AC-18)', () => {
  it('renamed label shows up in the list', async () => {
    const { client } = await renderAt('/deals?q=한빛은행 ITDR', { role: 'admin' })
    const row = await rowOf(/한빛은행 ITDR 도입/)
    const id = await labelId('budget', '단독 예산 확보')

    await gateway.labels.rename(id, '단독 예산 승인')
    await client.invalidateQueries()

    await waitFor(() => expect(within(bantCell(row)).getByLabelText('Budget: 단독 예산 승인')).toBeVisible())
    expect(within(bantCell(row)).queryByLabelText('Budget: 단독 예산 확보')).not.toBeInTheDocument()
  })

  it('label changed on the detail shows up when returning to the list', async () => {
    const code = await dealCodeOf(1)
    const { user, location } = await renderAt(`/deals/${code}`)
    const bant = await screen.findByRole('region', { name: 'BANT' })
    await user.click(within(bant).getByRole('button', { name: 'Timeline 수정' }))
    await user.clear(within(bant).getByRole('combobox', { name: 'Timeline' }))
    await user.keyboard('{Enter}')
    await waitFor(() => expect(within(bant).getByRole('button', { name: 'Timeline 수정' })).toHaveTextContent('—'))

    await user.click(screen.getByRole('link', { name: /목록/ }))
    await waitFor(() => expect(location()).toMatch(/^\/deals(\?|$)/))

    const cell = bantCell(await rowOf(/한빛은행 ITDR 도입/))
    await waitFor(() => expect(within(cell).queryByLabelText(/^Timeline: /)).not.toBeInTheDocument())
    expect(within(cell).getByLabelText('Budget: 단독 예산 확보')).toBeVisible()
  })
})

describe('목록의 BANT 열: Label 조회 상태', () => {
  it('shows a failure text, not the dash, when the label list cannot be read', async () => {
    vi.spyOn(gateway.labels, 'list').mockRejectedValue(new Error('Label 조회 실패'))
    await renderAt('/deals?q=한빛은행 ITDR')
    const cell = bantCell(await rowOf(/한빛은행 ITDR 도입/))

    expect(await within(cell).findByText('불러오지 못함')).toBeVisible()
    expect(cell).not.toHaveTextContent(/^—$/)
    expect(within(cell).queryByLabelText(ITEM_NAME)).not.toBeInTheDocument()
  })

  it('keeps the dash while the label list is still loading', async () => {
    vi.spyOn(gateway.labels, 'list').mockReturnValue(new Promise(() => undefined))
    await renderAt('/deals?q=한빛은행 ITDR')
    const cell = bantCell(await rowOf(/한빛은행 ITDR 도입/))

    expect(cell).toHaveTextContent(/^—$/)
    expect(within(cell).queryByText('불러오지 못함')).not.toBeInTheDocument()
  })

  it('does not show the failure text when the label list is read', async () => {
    await renderAt('/deals?q=한빛은행 ITDR')
    const cell = bantCell(await rowOf(/한빛은행 ITDR 도입/))

    await within(cell).findByLabelText('Budget: 단독 예산 확보')
    expect(within(cell).queryByText('불러오지 못함')).not.toBeInTheDocument()
  })
})

/** 목록 조회로 이름이 같은 Deal 행을 찾는다(로그인된 상태). */
async function dealRowOfName(name: string): Promise<DealRow> {
  const page = await gateway.deals.list({ keyword: name })
  const found = page.items.find((d) => d.name === name)
  if (!found) throw new Error(`Deal ${name} 없음`)
  return found
}
