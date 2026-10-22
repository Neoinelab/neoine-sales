import { screen, waitFor, within } from '@testing-library/react'
import { describe, expect, it } from 'vitest'
import { gateway } from '../../../gateway'
import { dealCodeOf } from '../../../test/detailTestUtils'
import { renderAt } from '../../../test/mockApp'
import { dataRows } from './testHelpers'

describe('Deals 필터: Next Action 상태 (AC-23·24)', () => {
  it('offers the five choices in the "Next Action 상태" select', async () => {
    await renderAt('/deals')
    const select = await screen.findByLabelText('Next Action 상태')

    expect(within(select).getAllByRole('option').map((o) => o.textContent)).toEqual([
      '전체',
      'Open',
      '종료(수행)',
      '종료(미수행)',
      '종료(전체)',
    ])
  })

  it('puts the choice in the URL as next_status and keeps the first page', async () => {
    const { user, location } = await renderAt('/deals?page=2')
    await user.selectOptions(await screen.findByLabelText('Next Action 상태'), 'Open')

    expect(location()).toContain('next_status=open')
    expect(location()).not.toContain('page=')
    await screen.findByRole('row', { name: /한빛은행 ITDR 도입/ })
  })

  it.each([
    ['종료(수행)', 'done'],
    ['종료(미수행)', 'not_done'],
    ['종료(전체)', 'closed'],
  ])('writes %s as next_status=%s and tells nothing matches while every Next Action is Open', async (label, wire) => {
    const { user, location } = await renderAt('/deals')
    await screen.findByRole('row', { name: /한빛은행 ITDR 도입/ })

    await user.selectOptions(screen.getByLabelText('Next Action 상태'), label)

    expect(location()).toContain(`next_status=${wire}`)
    expect(await screen.findByText('조건에 맞는 Deal이 없습니다.')).toBeVisible()
  })

  it('restores the select from the URL and shows the Open deals', async () => {
    await renderAt('/deals?next_status=open')

    await screen.findByRole('row', { name: /한빛은행 ITDR 도입/ })

    expect(screen.getByLabelText('Next Action 상태')).toHaveDisplayValue('Open')
  })

  it('restores not_done as 종료(미수행)', async () => {
    await renderAt('/deals?next_status=not_done')

    expect(await screen.findByLabelText('Next Action 상태')).toHaveDisplayValue('종료(미수행)')
  })

  it('ignores a wrong URL value and lists everything', async () => {
    await renderAt('/deals?next_status=bogus')

    await screen.findByRole('row', { name: /한빛은행 ITDR 도입/ })

    expect(screen.getByLabelText('Next Action 상태')).toHaveDisplayValue('전체')
    expect(dataRows().length).toBeGreaterThan(0)
  })

  it('resets the status choice with the reset button', async () => {
    const { user, location } = await renderAt('/deals?next_status=closed')
    await user.click(await screen.findByRole('button', { name: '초기화' }))

    expect(location()).toBe('/deals')
  })
})

describe('Deals 목록: Next Action 열의 상태 라벨 (AC-23)', () => {
  it('shows the text, the due date and the status label of the basis Next Action', async () => {
    await renderAt('/deals')

    const row = await screen.findByRole('row', { name: /한빛은행 ITDR 도입/ })

    expect(row).toHaveTextContent('계약서 초안 검토')
    expect(row).toHaveTextContent('Open')
  })
})

describe('Deals 목록: Next Action 칸은 모든 상태에서 내용·Due·상태 라벨을 보인다 (AC-5)', () => {
  it.each([
    ['open', 'Open'],
    ['done', '종료(수행)'],
    ['notDone', '종료(미수행)'],
  ] as const)('shows the text, the due date and the label of a %s Next Action', async (status, label) => {
    const code = await dealCodeOf(1)
    const { client } = await renderAt('/deals?q=한빛은행 ITDR')
    await screen.findByRole('row', { name: /한빛은행 ITDR 도입/ })
    const basis = (await gateway.actions.list(code, {})).find((a) => a.nextAction === '계약서 초안 검토')
    if (!basis) throw new Error('기준 Action이 없습니다.')
    if (status !== 'open') await gateway.actions.changeNextActionStatus(basis.id, { status, memo: '' }) // 시드는 이미 Open
    await client.invalidateQueries()

    await waitFor(() => {
      const row = screen.getByRole('row', { name: /한빛은행 ITDR 도입/ })
      expect(within(row).getByText(label, { selector: 'small' })).toBeVisible()
      expect(row).toHaveTextContent('계약서 초안 검토')
      expect(row).toHaveTextContent(`Due ${basis.dueDate}`)
    })
    const labels = ['Open', '종료(수행)', '종료(미수행)'].filter((l) => l !== label)
    const row = screen.getByRole('row', { name: /한빛은행 ITDR 도입/ })
    for (const other of labels) expect(within(row).queryByText(other, { selector: 'small' })).not.toBeInTheDocument()
  })
})
