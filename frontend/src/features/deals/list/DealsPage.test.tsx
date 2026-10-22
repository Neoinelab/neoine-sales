import { cleanup, screen, waitFor, within } from '@testing-library/react'
import { describe, expect, it } from 'vitest'
import { gateway } from '../../../gateway'
import { renderAt } from '../../../test/mockApp'
import { dataRows, rowOf } from './testHelpers'

const HEADERS = ['Deal', '담당자', '고객사', '파트너사', 'Vendor', 'Status', 'Forecast', 'BANT', '금액(단위:천원)', 'Expected Close', 'Next Action', '최종 업데이트']

describe('목록 표 (T-LIST-01~04)', () => {
  it('shows the PRD columns with the BANT column', async () => {
    await renderAt('/deals')
    await screen.findByRole('row', { name: /한빛은행 ITDR 도입/ })
    const headers = screen.getAllByRole('columnheader').map((h) => h.textContent?.trim())
    expect(headers).toEqual(HEADERS)
  })

  it('AC-21 orders the columns with the owner before the customer, and each row follows the same order', async () => {
    await renderAt('/deals?q=누리통신 MFA')
    const row = await rowOf(/누리통신 MFA/)

    const cells = within(row).getAllByRole('cell')
    expect(cells[HEADERS.indexOf('담당자')]).toHaveTextContent('이영업')
    expect(cells[HEADERS.indexOf('고객사')]).toHaveTextContent('누리통신')
    expect(cells[HEADERS.indexOf('파트너사')]).toHaveTextContent('에이원시스템')
    expect(cells[HEADERS.indexOf('Vendor')]).toHaveTextContent('Silverfort')
    expect(HEADERS.indexOf('담당자')).toBe(HEADERS.indexOf('고객사') - 1)
  })

  it('AC-21 shows a dash in the Vendor cell of a deal without a vendor', async () => {
    const { client } = await renderAt('/deals?q=누리통신 MFA')
    const row = await rowOf(/누리통신 MFA/)
    const code = (within(row).getByRole('link', { name: '누리통신 MFA' }).getAttribute('href') ?? '').replace('/deals/', '')
    await gateway.deals.update(code, { vendorId: null })
    await client.invalidateQueries()

    await waitFor(() => expect(within(screen.getByRole('row', { name: /누리통신 MFA/ })).getAllByRole('cell')[HEADERS.indexOf('Vendor')]).toHaveTextContent(/^—$/))
  })

  it('shows twenty deals on the first page and the rest on the second', async () => {
    const { user, location } = await renderAt('/deals')
    await screen.findByRole('row', { name: /한빛은행 ITDR 도입/ })
    expect(dataRows()).toHaveLength(20)
    await user.click(screen.getByRole('button', { name: '다음' }))
    expect(location()).toBe('/deals?page=2')
    await screen.findByRole('button', { name: '이전' })
    expect(dataRows()).toHaveLength(4)
    await user.click(screen.getByRole('button', { name: '이전' }))
    expect(location()).toBe('/deals')
  })

  it('shows the customer, only the active partner, the owner and the formatted amount', async () => {
    await renderAt('/deals?q=누리통신 MFA')
    const row = await rowOf(/누리통신 MFA/)
    expect(within(row).getByText('누리통신')).toBeVisible()
    expect(within(row).getByText('에이원시스템')).toBeVisible()
    expect(within(row).queryByText('코어테크')).not.toBeInTheDocument()
    expect(within(row).getByText('이영업')).toBeVisible()
    expect(within(row).getByText('330,000')).not.toHaveAttribute('title')
  })

  it('shows a dash for a deal without a partner and the resigned owner label', async () => {
    await renderAt('/deals?q=누리통신 NGFW')
    const cells = within(await rowOf(/누리통신 NGFW/)).getAllByRole('cell')
    expect(cells[HEADERS.indexOf('파트너사')]).toHaveTextContent(/^—$/)
    cleanup()
    await renderAt('/deals?q=한빛은행 PAM')
    expect(within(await rowOf(/한빛은행 PAM/)).getByText('강퇴사(퇴사)')).toBeVisible()
  })

  it('marks overdue, not-updated and both with badge text and row classes', async () => {
    await renderAt('/deals?q=미래전자 EDR')
    const overdue = await rowOf(/미래전자 EDR 교체/)
    expect(within(overdue).getByText('기한초과')).toBeVisible()
    expect(within(overdue).queryByText('미업데이트')).not.toBeInTheDocument()
    expect(overdue).toHaveClass('risk-overdue')
    cleanup()

    await renderAt('/deals?q=새론병원 PAM')
    const stale = await rowOf(/새론병원 PAM/)
    expect(within(stale).getByText('미업데이트')).toBeVisible()
    expect(within(stale).queryByText('기한초과')).not.toBeInTheDocument()
    expect(stale).toHaveClass('risk-stale')
    cleanup()

    await renderAt('/deals?q=하늘카드 AD')
    const both = await rowOf(/하늘카드 AD 보안 강화/)
    expect(within(both).getByText('기한초과')).toBeVisible()
    expect(within(both).getByText('미업데이트')).toBeVisible()
  })

  it('shows no risk on a healthy deal and on closed deals', async () => {
    await renderAt('/deals?q=대한제조 MFA')
    const healthy = await rowOf(/대한제조 MFA 확대/)
    expect(within(healthy).queryByText('기한초과')).not.toBeInTheDocument()
    expect(within(healthy).queryByText('미업데이트')).not.toBeInTheDocument()
    cleanup()

    await renderAt('/deals?q=청명대학교 SSO')
    const won = await rowOf(/청명대학교 SSO\/MFA/)
    expect(won).not.toHaveClass('risk-overdue')
    expect(within(won).queryByText('기한초과')).not.toBeInTheDocument()
  })

  it('explains the risk colors with a legend, not by color alone', async () => {
    await renderAt('/deals')
    const legend = await screen.findByRole('list', { name: 'Risk 범례' })
    expect(within(legend).getByText('기한초과')).toBeVisible()
    expect(await within(legend).findByText('14일 이상 미업데이트')).toBeVisible()
  })

  it('links the deal name to its detail page', async () => {
    await renderAt('/deals?q=한빛은행 ITDR')
    const link = await screen.findByRole('link', { name: '한빛은행 ITDR 도입' })
    expect(link.getAttribute('href')).toMatch(/^\/deals\/\d{8}-[A-Z0-9]{4}$/)
  })
})

describe('빠른 보기 (T-LIST-10)', () => {
  it('expands quote, POC, customer contact, partner sales rep and BANT under the row', async () => {
    const { user } = await renderAt('/deals?q=한빛은행 ITDR')
    const row = await rowOf(/한빛은행 ITDR 도입/)
    const toggle = within(row).getByRole('button', { name: /빠른 보기/ })
    expect(toggle).toHaveAttribute('aria-expanded', 'false')
    await user.click(toggle)
    expect(toggle).toHaveAttribute('aria-expanded', 'true')
    const view = screen.getByRole('region', { name: /빠른 보기.*한빛은행 ITDR 도입/ })
    expect(within(view).getByText('견적')).toBeVisible()
    expect(within(view).getByText('POC')).toBeVisible()
    expect(within(view).getByText('고객 담당자')).toBeVisible()
    expect(within(view).getByText(/정민수/)).toBeVisible()
    expect(within(view).getByText('파트너 영업대표')).toBeVisible()
    expect(within(view).getByText(/표성호/)).toBeVisible()
    expect(within(view).getByText('단독 예산 확보')).toBeVisible()
    expect(within(view).getByText('조달청 경쟁 입찰')).toBeVisible()
    expect(within(view).getByRole('link', { name: '상세 보기' })).toBeVisible()
    await user.click(toggle)
    expect(screen.queryByRole('region', { name: /빠른 보기/ })).not.toBeInTheDocument()
  })

  it('says there is no partner in the quick view of a deal without one', async () => {
    const { user } = await renderAt('/deals?q=대한제조 NGFW')
    const row = await rowOf(/대한제조 NGFW/)
    await user.click(within(row).getByRole('button', { name: /빠른 보기/ }))
    const view = screen.getByRole('region', { name: /빠른 보기/ })
    expect(within(view).getByText('파트너 없음')).toBeVisible()
  })
})

describe('권한 (T-LIST-11)', () => {
  it('gives a viewer the list without register or edit controls', async () => {
    await renderAt('/deals', { role: 'user' })
    await screen.findByRole('row', { name: /한빛은행 ITDR 도입/ })
    expect(screen.queryByRole('link', { name: /Deal 등록/ })).not.toBeInTheDocument()
    expect(screen.queryByRole('button', { name: /편집/ })).not.toBeInTheDocument()
  })

  it.each(['sales', 'admin'] as const)('shows the register link and edit buttons to %s', async (role) => {
    await renderAt('/deals', { role })
    await screen.findByRole('row', { name: /한빛은행 ITDR 도입/ })
    expect(screen.getByRole('link', { name: '+ Deal 등록' })).toHaveAttribute('href', '/deals/new')
    expect(screen.getAllByRole('button', { name: /Forecast 편집/ }).length).toBeGreaterThan(0)
  })
})
