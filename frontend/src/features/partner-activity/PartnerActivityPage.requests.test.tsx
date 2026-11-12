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

describe('저장 뒤 목록 재요청은 한 번', () => {
  // 등록 뒤 목록 첫 쪽을 한 번만 다시 요청한다.
  // 테스트 코드: PA-088
  it('asks for the first page once after a registration', async () => {
    // given: 한 행을 채운 입력 팝업과 목록 요청 관찰
    const { user } = await renderAt(PAGE)
    await waitForRows(10)
    const dialog = await openEntryDialog(user)
    await fillRow(user, dialog, 1, { company: '코어테크', date: '20270315', content: '한 번만 요청' })
    const spy = vi.spyOn(gateway.partnerMeetings, 'list')

    // when: 저장한다
    await user.click(within(dialog).getByRole('button', { name: '저장' }))

    // then: 새 기록이 맨 위에 보이고 첫 쪽 요청은 한 번이다
    await waitFor(() => expect(shownContents()[0]).toBe('한 번만 요청'))
    await settle()
    expect(firstPageRequests(spy)).toBe(1)
  })

  // 수정 뒤 목록 첫 쪽을 한 번만 다시 요청한다.
  // 테스트 코드: PA-088
  it('asks for the first page once after an edit', async () => {
    // given: 내용을 고친 수정 팝업과 목록 요청 관찰
    const { user } = await renderAt(PAGE)
    await waitForRows(10)
    await user.click(within(rowWithContent('ITDR 가격 협상')).getByRole('button', { name: '수정' }))
    const dialog = await screen.findByRole('dialog', { name: '미팅 수정' })
    const content = within(dialog).getByRole('textbox', { name: '미팅 내용' })
    await user.clear(content)
    await user.type(content, '고친 내용')
    const spy = vi.spyOn(gateway.partnerMeetings, 'list')

    // when: 저장한다
    await user.click(within(dialog).getByRole('button', { name: '저장' }))

    // then: 고친 내용이 보이고 첫 쪽 요청은 한 번이다
    await waitFor(() => expect(shownContents()).toContain('고친 내용'))
    await settle()
    expect(firstPageRequests(spy)).toBe(1)
  })

  // 삭제 뒤 목록 첫 쪽을 한 번만 다시 요청한다.
  // 테스트 코드: PA-088
  it('asks for the first page once after a deletion', async () => {
    // given: 삭제 확인 창과 목록 요청 관찰
    const { user } = await renderAt(PAGE)
    await waitForRows(10)
    await user.click(within(rowWithContent('ITDR 가격 협상')).getByRole('button', { name: '삭제' }))
    const ask = await screen.findByRole('dialog', { name: '미팅 기록 삭제' })
    const spy = vi.spyOn(gateway.partnerMeetings, 'list')

    // when: 삭제를 확인한다
    await user.click(within(ask).getByRole('button', { name: '삭제' }))

    // then: 기록이 사라지고 첫 쪽 요청은 한 번이며 10행이 보인다
    await waitFor(() => expect(shownContents()).not.toContain('ITDR 가격 협상'))
    await settle()
    expect(firstPageRequests(spy)).toBe(1)
    expect(meetingRows()).toHaveLength(10)
  })
})
