import { act, fireEvent, screen, waitFor, within } from '@testing-library/react'
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'
import { gateway } from '../../../gateway'
import { A_INPUT, DETAIL, addAction, fieldValue, makeGate, openActionsTab, openDetail } from '../../../test/actionDetail'
import { resetMock } from '../../../test/fake/default'

/** Action 상세 팝업 진행사항·Next Action 편집의 명시적 저장·취소(AC-R56). 서버 시계는 2026-11-13로 고정한다. */
beforeEach(() => resetMock({ now: '2026-11-13T14:30:00+09:00' }))
afterEach(() => {
  vi.restoreAllMocks()
  resetMock({ now: null })
})

const detail = () => screen.getByRole('dialog', { name: DETAIL })
const group = (dialog: HTMLElement, name: string) => within(dialog).getByRole('group', { name })

/** 김영업의 Action A를 남기고 그 상세 팝업을 연다. */
async function openA() {
  const view = await openActionsTab()
  const action = await addAction(view, A_INPUT)
  return { view, action, dialog: await openDetail(view, '킥오프 미팅') }
}

describe('편집 그룹 밖으로 포커스가 나갈 때', () => {
  // 편집 그룹 밖으로 포커스가 나가면 저장하지 않고 취소한다.
  // 테스트 코드: AC-157
  it('편집 그룹 밖으로 포커스가 나가면 저장 없이 진행사항 수정을 취소한다', async () => {
    // given: 진행사항 편집에 " 후속"을 친 Action A 팝업(수정 요청 감시)
    const update = vi.spyOn(gateway.actions, 'update')
    const { view, dialog } = await openA()
    await view.user.click(within(dialog).getByRole('button', { name: '진행사항 수정' }))
    await view.user.type(within(dialog).getByLabelText('진행사항'), ' 후속')

    // when: Tab 세 번으로 칸 → 저장 → 취소를 지나 그룹 밖으로 나가고 "유형 수정"을 누른다
    await view.user.tab()
    await view.user.tab()
    await view.user.tab()
    expect(within(dialog).queryByRole('group', { name: '진행사항 편집' })).not.toBeInTheDocument()
    await view.user.click(within(dialog).getByRole('button', { name: '유형 수정' }))

    // then: 저장 요청 없이 원래 진행사항이 보이고 유형 편집으로 이동한다
    expect(update).not.toHaveBeenCalled()
    expect(within(dialog).getByRole('button', { name: '진행사항 수정' })).toHaveTextContent('킥오프 미팅')
    expect(within(dialog).queryByRole('button', { name: '진행사항 저장' })).not.toBeInTheDocument()
    expect(within(dialog).queryByRole('button', { name: '진행사항 취소' })).not.toBeInTheDocument()
    expect(within(dialog).getByRole('combobox', { name: '유형' })).toBeVisible()
  })
})

describe('Due Date 달력 선택', () => {
  // 달력으로 Due Date를 골라도 칸 값만 바뀌고 저장은 "저장" 버튼으로만 된다.
  // 테스트 코드: AC-158
  it('changes only the due date field when a date is picked in the calendar and saves it with the save button', async () => {
    // given: Action A의 "Next Action · Due Date 수정"을 연 팝업(수정 요청 감시)
    const update = vi.spyOn(gateway.actions, 'update')
    const { view, dialog } = await openA()
    await view.user.click(within(dialog).getByRole('button', { name: 'Next Action · Due Date 수정' }))
    const pair = group(dialog, 'Next Action · Due Date 편집')

    // when: 달력(숨은 날짜 칸)에서 2027-02-01을 고른다
    const native = pair.querySelector<HTMLInputElement>('input[type="date"]') as HTMLInputElement
    fireEvent.change(native, { target: { value: '2027-02-01' } })

    // then: 요청이 없고 편집이 열린 채 Due Date 칸이 2027.02.01이다
    expect(update).not.toHaveBeenCalled()
    expect(within(dialog).getByLabelText('Due Date')).toHaveValue('2027.02.01')

    // when: "Next Action · Due Date 저장"을 누른다
    await view.user.click(within(dialog).getByRole('button', { name: 'Next Action · Due Date 저장' }))
    // then: 요청 한 번에 Due 2027-02-01이 실린다
    await waitFor(() => expect(update).toHaveBeenCalledTimes(1))
    expect(update.mock.calls[0]?.[1]).toMatchObject({ dueDate: '2027-02-01' })
  })
})

describe('저장·취소 버튼의 위치와 이름', () => {
  // 진행사항·묶음 편집에만 저장·취소 버튼이 있고 접근 이름·primary·Tab 순서가 정해져 있다.
  // 테스트 코드: AC-159
  it('puts the save and cancel buttons only in the progress and pair editors with fixed names and tab order', async () => {
    // given: Action A 상세 팝업
    const { view, dialog } = await openA()

    // when: 진행사항 편집을 열어 Tab을 누른다
    await view.user.click(within(dialog).getByRole('button', { name: '진행사항 수정' }))
    const progress = group(dialog, '진행사항 편집')
    const save = within(progress).getByRole('button', { name: '진행사항 저장' })
    const cancel = within(progress).getByRole('button', { name: '진행사항 취소' })
    // then: 보이는 글자·클래스가 맞고 Tab 순서는 칸 → 저장 → 취소다
    expect(save).toHaveTextContent(/^저장$/)
    expect(save).toHaveClass('primary')
    expect(cancel).toHaveTextContent(/^취소$/)
    expect(within(progress).getAllByRole('button').map((b) => b.textContent)).toEqual(['저장', '취소'])
    expect(within(progress).getByLabelText('진행사항')).toHaveFocus()
    await view.user.tab()
    expect(save).toHaveFocus()
    await view.user.tab()
    expect(cancel).toHaveFocus()

    // when: 묶음 편집을 열어 Tab을 누른다
    await view.user.click(within(dialog).getByRole('button', { name: 'Next Action · Due Date 수정' }))
    const pair = group(dialog, 'Next Action · Due Date 편집')
    const pairSave = within(pair).getByRole('button', { name: 'Next Action · Due Date 저장' })
    const pairCancel = within(pair).getByRole('button', { name: 'Next Action · Due Date 취소' })
    // then: Tab 순서는 Next Action 칸 → Due Date 칸 → 달력 버튼 → 저장 → 취소다
    expect(pairSave).toHaveClass('primary')
    expect(within(pair).getByLabelText('Next Action')).toHaveFocus()
    await view.user.tab()
    expect(within(pair).getByLabelText('Due Date')).toHaveFocus()
    await view.user.tab()
    expect(pair.querySelector('.date-input-button')).toHaveFocus()
    await view.user.tab()
    expect(pairSave).toHaveFocus()
    await view.user.tab()
    expect(pairCancel).toHaveFocus()

    // then: 묶음 편집으로 이동하면 진행사항 편집은 취소된다
    expect(within(dialog).queryByRole('group', { name: '진행사항 편집' })).not.toBeInTheDocument()
    await view.user.click(pairCancel)
    expect(within(dialog).queryByRole('group', { name: 'Next Action · Due Date 편집' })).not.toBeInTheDocument()
    expect(within(dialog).queryByRole('group', { name: '진행사항 편집' })).not.toBeInTheDocument()

    // when: 수행일·유형 편집을 하나씩 연다
    // then: 그 편집 그룹에는 저장·취소 버튼이 없다
    for (const name of ['수행일', '유형']) {
      await view.user.click(within(dialog).getByRole('button', { name: `${name} 수정` }))
      expect(within(group(dialog, `${name} 편집`)).queryByRole('button', { name: /(저장|취소)$/ })).not.toBeInTheDocument()
      await view.user.keyboard('{Escape}')
    }
  })
})

describe('편집을 닫은 뒤 포커스', () => {
  // 저장 성공과 취소 뒤 포커스는 그 칸의 값 버튼으로 돌아온다.
  // 테스트 코드: AC-160
  it('returns the focus to the value button after a successful save and after a cancel', async () => {
    // given: Action A 상세 팝업(수정 요청 감시)
    const update = vi.spyOn(gateway.actions, 'update')
    const { view, dialog } = await openA()

    // when: 진행사항을 고쳐 "진행사항 저장"을 누른다
    await view.user.click(within(dialog).getByRole('button', { name: '진행사항 수정' }))
    await view.user.type(within(dialog).getByLabelText('진행사항'), ' 추가')
    await view.user.click(within(dialog).getByRole('button', { name: '진행사항 저장' }))
    // then: 포커스가 "진행사항 수정" 버튼에 있다
    await waitFor(() => expect(within(dialog).getByRole('button', { name: '진행사항 수정' })).toHaveFocus())

    // when: 묶음 편집을 열어 Next Action을 고친 뒤 "Next Action · Due Date 취소"를 누른다
    await view.user.click(within(dialog).getByRole('button', { name: 'Next Action · Due Date 수정' }))
    await view.user.type(within(dialog).getByLabelText('Next Action'), ' 버릴 글')
    await view.user.click(within(dialog).getByRole('button', { name: 'Next Action · Due Date 취소' }))
    // then: 포커스가 "Next Action · Due Date 수정" 버튼에 있고 Next Action은 그대로이며 요청은 저장 한 번뿐이다
    expect(within(dialog).getByRole('button', { name: 'Next Action · Due Date 수정' })).toHaveFocus()
    expect(fieldValue(detail(), 'Next Action')).toHaveTextContent(/^요구사항 문서 전달$/)
    expect(update).toHaveBeenCalledTimes(1)
  })
})

describe('저장하지 않은 편집이 있는 채 팝업을 닫을 때', () => {
  // "닫기"를 누르면 확인 창 없이 닫히고 입력이 버려진다.
  // 테스트 코드: AC-161
  it('discards the unsaved input without a confirmation or a request when the close button is pressed', async () => {
    // given: 진행사항 편집을 "닫으면 버려질 글"로 바꾼 Action A 팝업(수정 요청 감시)
    const update = vi.spyOn(gateway.actions, 'update')
    const { view, dialog } = await openA()
    await view.user.click(within(dialog).getByRole('button', { name: '진행사항 수정' }))
    const input = within(dialog).getByLabelText('진행사항')
    await view.user.clear(input)
    await view.user.type(input, '닫으면 버려질 글')

    // when: "닫기"를 누른다
    await view.user.click(within(dialog).getByRole('button', { name: '닫기' }))
    // then: 확인 창 없이 팝업이 닫히고 요청이 없다
    expect(screen.queryByRole('dialog')).not.toBeInTheDocument()
    expect(update).not.toHaveBeenCalled()

    // when: A 행을 다시 눌러 팝업을 연다
    const again = await openDetail(view, '킥오프 미팅')
    // then: 진행사항은 서버 값이고 편집은 닫혀 있다
    expect(fieldValue(again, '진행사항')).toHaveTextContent(/^킥오프 미팅$/)
    expect(within(again).queryByLabelText('진행사항')).not.toBeInTheDocument()
  })

  // 포커스가 편집 그룹 밖일 때 Esc로 팝업을 닫아도 입력이 버려진다.
  // 테스트 코드: AC-161
  it('discards the unsaved input when the popup is closed with Escape while the focus is outside the edit group', async () => {
    // given: 진행사항 편집을 바꾼 채 포커스가 그룹 밖 "유형 수정" 버튼에 있는 팝업(수정 요청 감시)
    const update = vi.spyOn(gateway.actions, 'update')
    const { view, dialog } = await openA()
    await view.user.click(within(dialog).getByRole('button', { name: '진행사항 수정' }))
    await view.user.type(within(dialog).getByLabelText('진행사항'), ' 버려질 글')
    act(() => within(dialog).getByRole('button', { name: '유형 수정' }).focus())

    // when: Esc를 누른다
    await view.user.keyboard('{Escape}')
    // then: 팝업이 닫히고 요청이 없다
    expect(screen.queryByRole('dialog')).not.toBeInTheDocument()
    expect(update).not.toHaveBeenCalled()

    // when: 팝업을 다시 연다
    const again = await openDetail(view, '킥오프 미팅')
    // then: 서버 값이고 편집이 닫혀 있다
    expect(fieldValue(again, '진행사항')).toHaveTextContent(/^킥오프 미팅$/)
    expect(within(again).queryByLabelText('진행사항')).not.toBeInTheDocument()
  })
})

describe('한 편집을 저장하는 동안', () => {
  // 진행사항을 저장하는 동안 Next Action·Due Date 저장도 꺼져 앞 수정을 덮어쓰지 않는다.
  // 테스트 코드: AC-162
  it('disables the other editors save button while one is saving so the later request carries the saved progress', async () => {
    // given: 진행사항을 고쳤으며 저장 응답을 붙들어 둔다
    const { view, dialog } = await openA()
    const original = gateway.actions.update.bind(gateway.actions)
    const { gate, release } = makeGate()
    const update = vi.spyOn(gateway.actions, 'update').mockImplementationOnce(async (...args) => {
      await gate
      return original(...args)
    })
    await view.user.click(within(dialog).getByRole('button', { name: '진행사항 수정' }))
    const progress = within(dialog).getByLabelText('진행사항')
    await view.user.clear(progress)
    await view.user.type(progress, '먼저 저장한 진행')
    // when: "진행사항 저장"을 누르고 응답 전에 "Next Action · Due Date 저장"을 누르려 한다
    await view.user.click(within(dialog).getByRole('button', { name: '진행사항 저장' }))
    await waitFor(() => expect(within(dialog).getByRole('button', { name: '진행사항 저장' })).toBeDisabled())
    await view.user.click(within(dialog).getByRole('button', { name: 'Next Action · Due Date 수정' }))
    await view.user.type(within(dialog).getByLabelText('Next Action'), ' 보강')
    const pairSave = within(dialog).getByRole('button', { name: 'Next Action · Due Date 저장' })
    await view.user.click(pairSave)

    // then: 두 저장이 모두 꺼져 있고 요청은 첫 번째 하나뿐이다
    expect(pairSave).toBeDisabled()
    expect(update).toHaveBeenCalledTimes(1)

    // when: 응답이 온다
    release()
    // then: 진행사항 저장 후 포커스 복귀로 묶음 편집도 닫힌다
    await waitFor(() => expect(within(dialog).queryByRole('group', { name: '진행사항 편집' })).not.toBeInTheDocument())
    await waitFor(() => expect(within(dialog).getByRole('button', { name: 'Next Action · Due Date 수정' })).toBeEnabled())

    // when: 묶음 편집을 다시 열고 보강 내용을 저장한다
    await view.user.click(within(dialog).getByRole('button', { name: 'Next Action · Due Date 수정' }))
    await view.user.type(within(dialog).getByLabelText('Next Action'), ' 보강')
    await view.user.click(within(dialog).getByRole('button', { name: 'Next Action · Due Date 저장' }))
    // then: 그 요청의 진행사항은 방금 저장한 값이다
    await waitFor(() => expect(update).toHaveBeenCalledTimes(2))
    expect(update.mock.calls[1]?.[1]).toMatchObject({ progress: '먼저 저장한 진행', nextAction: '요구사항 문서 전달 보강' })
  })
})
