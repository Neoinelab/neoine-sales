import { screen, waitFor, within } from '@testing-library/react'
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'
import { gateway } from '../../gateway'
import { renderAt } from '../../test/mockApp'
import { PAGE, fillRow, meetingRows, openEntryDialog, pinClock, rowWithContent, shownContents, unpinClock, waitForRows } from '../../test/partnerMeetings'

beforeEach(pinClock)
afterEach(() => {
  unpinClock()
  vi.restoreAllMocks()
})

/** 첫 쪽(offset 0) 목록 요청 횟수. 저장 뒤 다시 받는 요청이 한 번이어야 한다. */
function firstPageRequests(spy: { mock: { calls: readonly (readonly unknown[])[] } }): number {
  return spy.mock.calls.filter((call) => call[1] === 0).length
}

const settle = () => new Promise((resolve) => setTimeout(resolve, 80))

describe('저장 뒤 목록 재요청은 한 번 (리뷰 후속)', () => {
  it('asks for the first page once after a registration', async () => {
    const { user } = await renderAt(PAGE)
    await waitForRows(10)
    const dialog = await openEntryDialog(user)
    await fillRow(user, dialog, 1, { company: '코어테크', deal: /미래전자 ITDR/, date: '20270315', content: '한 번만 요청' })
    const spy = vi.spyOn(gateway.partnerMeetings, 'list')

    await user.click(within(dialog).getByRole('button', { name: '저장' }))

    await waitFor(() => expect(shownContents()[0]).toBe('한 번만 요청'))
    await settle()
    expect(firstPageRequests(spy)).toBe(1)
  })

  it('asks for the first page once after an edit', async () => {
    const { user } = await renderAt(PAGE)
    await waitForRows(10)
    await user.click(within(rowWithContent('ITDR 가격 협상')).getByRole('button', { name: '수정' }))
    const dialog = await screen.findByRole('dialog', { name: '미팅 수정' })
    const content = within(dialog).getByRole('textbox', { name: '미팅 내용' })
    await user.clear(content)
    await user.type(content, '고친 내용')
    const spy = vi.spyOn(gateway.partnerMeetings, 'list')

    await user.click(within(dialog).getByRole('button', { name: '저장' }))

    await waitFor(() => expect(shownContents()).toContain('고친 내용'))
    await settle()
    expect(firstPageRequests(spy)).toBe(1)
  })

  it('asks for the first page once after a deletion', async () => {
    const { user } = await renderAt(PAGE)
    await waitForRows(10)
    await user.click(within(rowWithContent('ITDR 가격 협상')).getByRole('button', { name: '삭제' }))
    const ask = await screen.findByRole('dialog', { name: '미팅 기록 삭제' })
    const spy = vi.spyOn(gateway.partnerMeetings, 'list')

    await user.click(within(ask).getByRole('button', { name: '삭제' }))

    await waitFor(() => expect(shownContents()).not.toContain('ITDR 가격 협상'))
    await settle()
    expect(firstPageRequests(spy)).toBe(1)
    expect(meetingRows()).toHaveLength(10)
  })
})
