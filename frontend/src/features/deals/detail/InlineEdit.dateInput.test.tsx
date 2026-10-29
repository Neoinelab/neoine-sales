import { screen, waitFor } from '@testing-library/react'
import { afterEach, describe, expect, it, vi } from 'vitest'
import { gateway } from '../../../gateway'
import { detailPath } from '../../../test/detailTestUtils'
import { renderAt } from '../../../test/mockApp'

afterEach(() => {
  vi.restoreAllMocks()
  Reflect.deleteProperty(HTMLInputElement.prototype, 'showPicker')
})

function stubShowPicker() {
  const showPicker = vi.fn()
  Object.defineProperty(HTMLInputElement.prototype, 'showPicker', { configurable: true, writable: true, value: showPicker })
  return showPicker
}

async function openDeal() {
  const view = await renderAt(await detailPath(1))
  await screen.findByRole('heading', { level: 1, name: '한빛은행 ITDR 도입' })
  return view
}

describe('상세 화면 클릭 편집의 날짜 입력 (AC-D3, AC-D7)', () => {
  it('saves a typed yyyymmdd on Enter', async () => {
    const update = vi.spyOn(gateway.deals, 'update')
    const { user } = await openDeal()
    await user.click(screen.getByRole('button', { name: 'POC 완료일 수정' }))
    const date = screen.getByLabelText('POC 완료일')
    await user.clear(date)
    await user.type(date, '20270601{Enter}')
    await waitFor(() => expect(update).toHaveBeenCalledTimes(1))
    expect(update.mock.calls[0]?.[1].poc?.completedDate).toBe('2027-06-01')
  })

  it('does not save a wrong date on Enter, keeps editing and shows the message', async () => {
    const update = vi.spyOn(gateway.deals, 'update')
    const { user } = await openDeal()
    await user.click(screen.getByRole('button', { name: 'POC 완료일 수정' }))
    const date = screen.getByLabelText('POC 완료일')
    await user.clear(date)
    await user.type(date, '20271301{Enter}')
    expect(update).not.toHaveBeenCalled()
    expect(screen.getByLabelText('POC 완료일')).toBeVisible()
    expect(await screen.findByText('없는 날짜입니다.')).toBeVisible()
  })

  it('does not save an incomplete Expected Close on Enter', async () => {
    const update = vi.spyOn(gateway.deals, 'update')
    const { user } = await openDeal()
    await user.click(screen.getByRole('button', { name: 'Expected Close 수정' }))
    const date = screen.getByLabelText('Expected Close')
    await user.clear(date)
    await user.type(date, '2027.06{Enter}')
    expect(update).not.toHaveBeenCalled()
    expect(await screen.findByText('날짜를 yyyymmdd 형식으로 입력하세요.')).toBeVisible()
  })

  it('does not save when the focus moves to the calendar button', async () => {
    const update = vi.spyOn(gateway.deals, 'update')
    const { user } = await openDeal()
    await user.click(screen.getByRole('button', { name: '견적 제출일 수정' }))
    const date = screen.getByLabelText('견적 제출일')
    await user.clear(date)
    await user.type(date, '20270601')
    await user.click(screen.getByRole('button', { name: '견적 제출일 달력 열기' }))
    await new Promise((resolve) => setTimeout(resolve, 50))
    expect(update).not.toHaveBeenCalled()
    expect(screen.getByLabelText('견적 제출일')).toBeVisible()
  })

  it('does not save when the focus moves to the hidden native date input', async () => {
    const update = vi.spyOn(gateway.deals, 'update')
    const { user, container } = await openDeal()
    await user.click(screen.getByRole('button', { name: '견적 제출일 수정' }))
    const date = screen.getByLabelText('견적 제출일')
    await user.clear(date)
    await user.type(date, '20270601')
    container.querySelector<HTMLInputElement>('input[type="date"]')?.focus()
    await new Promise((resolve) => setTimeout(resolve, 50))
    expect(update).not.toHaveBeenCalled()
    expect(screen.getByLabelText('견적 제출일')).toBeVisible()
  })

  it.each(['견적 제출일', 'POC 완료일', 'Expected Close'])(
    'opens the calendar with Tab then Enter on the calendar button of %s without closing or saving',
    async (label) => {
      const showPicker = stubShowPicker()
      const update = vi.spyOn(gateway.deals, 'update')
      const { user } = await openDeal()
      await user.click(screen.getByRole('button', { name: `${label} 수정` }))
      expect(screen.getByLabelText(label)).toHaveFocus()

      await user.tab()
      expect(screen.getByRole('button', { name: `${label} 달력 열기` })).toHaveFocus()
      await user.keyboard('{Enter}')

      expect(showPicker).toHaveBeenCalledTimes(1)
      expect(update).not.toHaveBeenCalled()
      expect(screen.getByLabelText(label)).toBeVisible()
    },
  )

  it('opens the calendar with Space on the calendar button and keeps editing', async () => {
    const showPicker = stubShowPicker()
    const update = vi.spyOn(gateway.deals, 'update')
    const { user } = await openDeal()
    await user.click(screen.getByRole('button', { name: 'POC 완료일 수정' }))
    await user.tab()
    await user.keyboard(' ')
    expect(showPicker).toHaveBeenCalledTimes(1)
    expect(update).not.toHaveBeenCalled()
    expect(screen.getByLabelText('POC 완료일')).toBeVisible()
  })
})
