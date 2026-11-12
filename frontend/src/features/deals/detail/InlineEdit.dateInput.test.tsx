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

describe('상세 화면 클릭 편집의 날짜 입력', () => {
  // POC 완료일에 yyyymmdd를 입력하고 Enter를 누르면 ISO 날짜로 저장한다.
  // 테스트 코드: DD-083
  it('saves a typed yyyymmdd on Enter', async () => {
    // given: POC 완료일 편집을 연 sales
    const update = vi.spyOn(gateway.deals, 'update')
    const { user } = await openDeal()
    await user.click(screen.getByRole('button', { name: 'POC 완료일 수정' }))
    const date = screen.getByLabelText('POC 완료일')
    // when: '20270601'을 입력하고 Enter를 누른다
    await user.clear(date)
    await user.type(date, '20270601{Enter}')
    // then: 수정 요청이 한 번이고 완료일이 2027-06-01이다
    await waitFor(() => expect(update).toHaveBeenCalledTimes(1))
    expect(update.mock.calls[0]?.[1].poc?.completedDate).toBe('2027-06-01')
  })

  // 없는 날짜는 저장하지 않고 문구를 보이며 편집을 유지한다.
  // 테스트 코드: DD-083
  it('does not save a wrong date on Enter, keeps editing and shows the message', async () => {
    // given: POC 완료일 편집을 연 sales
    const update = vi.spyOn(gateway.deals, 'update')
    const { user } = await openDeal()
    await user.click(screen.getByRole('button', { name: 'POC 완료일 수정' }))
    const date = screen.getByLabelText('POC 완료일')
    // when: '20271301'을 입력하고 Enter를 누른다
    await user.clear(date)
    await user.type(date, '20271301{Enter}')
    // then: 요청이 없고 입력이 열려 있으며 '없는 날짜입니다.'가 보인다
    expect(update).not.toHaveBeenCalled()
    expect(screen.getByLabelText('POC 완료일')).toBeVisible()
    expect(await screen.findByText('없는 날짜입니다.')).toBeVisible()
  })

  // 덜 친 Expected Close는 저장하지 않고 형식 문구를 보인다.
  // 테스트 코드: DD-083
  it('does not save an incomplete Expected Close on Enter', async () => {
    // given: Expected Close 편집을 연 sales
    const update = vi.spyOn(gateway.deals, 'update')
    const { user } = await openDeal()
    await user.click(screen.getByRole('button', { name: 'Expected Close 수정' }))
    const date = screen.getByLabelText('Expected Close')
    // when: '2027.06'을 입력하고 Enter를 누른다
    await user.clear(date)
    await user.type(date, '2027.06{Enter}')
    // then: 요청이 없고 '날짜를 yyyymmdd 형식으로 입력하세요.'가 보인다
    expect(update).not.toHaveBeenCalled()
    expect(await screen.findByText('날짜를 yyyymmdd 형식으로 입력하세요.')).toBeVisible()
  })

  // 포커스가 달력 버튼으로 옮겨 가는 것은 저장으로 보지 않는다.
  // 테스트 코드: DD-083
  it('does not save when the focus moves to the calendar button', async () => {
    // given: 견적 제출일에 날짜를 입력한 편집 상태
    const update = vi.spyOn(gateway.deals, 'update')
    const { user } = await openDeal()
    await user.click(screen.getByRole('button', { name: '견적 제출일 수정' }))
    const date = screen.getByLabelText('견적 제출일')
    await user.clear(date)
    await user.type(date, '20270601')
    await user.click(screen.getByRole('button', { name: '견적 제출일 달력 열기' }))
    // when: 달력 열기 버튼을 누른다
    await new Promise((resolve) => setTimeout(resolve, 50))
    // then: 요청이 없고 입력이 그대로 열려 있다
    expect(update).not.toHaveBeenCalled()
    expect(screen.getByLabelText('견적 제출일')).toBeVisible()
  })

  // 포커스가 숨은 날짜 칸으로 옮겨 가는 것도 저장으로 보지 않는다.
  // 테스트 코드: DD-083
  it('does not save when the focus moves to the hidden native date input', async () => {
    // given: 견적 제출일에 날짜를 입력한 편집 상태
    const update = vi.spyOn(gateway.deals, 'update')
    const { user, container } = await openDeal()
    await user.click(screen.getByRole('button', { name: '견적 제출일 수정' }))
    const date = screen.getByLabelText('견적 제출일')
    await user.clear(date)
    await user.type(date, '20270601')
    container.querySelector<HTMLInputElement>('input[type="date"]')?.focus()
    // when: 숨은 native date 칸에 포커스를 준다
    await new Promise((resolve) => setTimeout(resolve, 50))
    // then: 요청이 없고 입력이 그대로 열려 있다
    expect(update).not.toHaveBeenCalled()
    expect(screen.getByLabelText('견적 제출일')).toBeVisible()
  })

  // Tab 다음 Enter로 달력을 열어도 편집이 닫히거나 저장되지 않는다.
  // 테스트 코드: DD-083
  it.each(['견적 제출일', 'POC 완료일', 'Expected Close'])(
    'opens the calendar with Tab then Enter on the calendar button of %s without closing or saving',
    async (label) => {
    // given: 견적 제출일·POC 완료일·Expected Close 각각의 편집 상태
      const showPicker = stubShowPicker()
      const update = vi.spyOn(gateway.deals, 'update')
      const { user } = await openDeal()
      await user.click(screen.getByRole('button', { name: `${label} 수정` }))
      expect(screen.getByLabelText(label)).toHaveFocus()

    // when: Tab으로 달력 버튼에 가서 Enter를 누른다
      await user.tab()
      expect(screen.getByRole('button', { name: `${label} 달력 열기` })).toHaveFocus()
      await user.keyboard('{Enter}')

    // then: 달력이 한 번 열리고 요청이 없으며 입력이 열려 있다
      expect(showPicker).toHaveBeenCalledTimes(1)
      expect(update).not.toHaveBeenCalled()
      expect(screen.getByLabelText(label)).toBeVisible()
    },
  )

  // 달력 버튼에서 Space로도 달력이 열리고 편집이 유지된다.
  // 테스트 코드: DD-083
  it('opens the calendar with Space on the calendar button and keeps editing', async () => {
    // given: POC 완료일 편집 상태
    const showPicker = stubShowPicker()
    const update = vi.spyOn(gateway.deals, 'update')
    const { user } = await openDeal()
    // when: Tab으로 달력 버튼에 가서 Space를 누른다
    await user.click(screen.getByRole('button', { name: 'POC 완료일 수정' }))
    await user.tab()
    await user.keyboard(' ')
    // then: 달력이 한 번 열리고 요청이 없으며 입력이 열려 있다
    expect(showPicker).toHaveBeenCalledTimes(1)
    expect(update).not.toHaveBeenCalled()
    expect(screen.getByLabelText('POC 완료일')).toBeVisible()
  })
})
