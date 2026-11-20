import { readFileSync } from 'node:fs'
import { screen, waitFor, within } from '@testing-library/react'
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'
import { gateway } from '../../../gateway'
import { A_INPUT, DETAIL, addAction, fieldValue, openActionsTab, openDetail, type DetailView } from '../../../test/actionDetail'
import { ruleOf } from '../../../test/cssRule'
import { resetMock } from '../../../test/fake/default'

/** Action 상세 팝업 폭과 진행사항·Next Action 편집 칸 크기(AC-R55). jsdom은 레이아웃을 계산하지 못하므로 측정값은 spy로 고정하고 CSS는 문자열로 점검한다. */
const detailCss = readFileSync('src/features/deals/detail/detail.css', 'utf8')
const uiCss = readFileSync('src/shared/ui/ui.css', 'utf8')

beforeEach(() => resetMock({ now: '2026-11-13T14:30:00+09:00' }))
afterEach(() => {
  vi.restoreAllMocks()
  resetMock({ now: null })
})

/** 값 버튼(`button.dd-click-fill`)의 offsetHeight를 `height()`로, 모든 요소의 scrollHeight를 `scroll()`로 고정한다. */
function fixMeasures(height: () => number, scroll: () => number) {
  vi.spyOn(HTMLElement.prototype, 'offsetHeight', 'get').mockImplementation(function (this: HTMLElement) {
    return this.classList.contains('dd-click-fill') ? height() : 0
  })
  vi.spyOn(Element.prototype, 'scrollHeight', 'get').mockImplementation(() => scroll())
}

async function openA(): Promise<{ view: DetailView; dialog: HTMLElement }> {
  const view = await openActionsTab()
  await addAction(view, A_INPUT)
  return { view, dialog: await openDetail(view, '킥오프 미팅') }
}

describe('상세 팝업 폭 (정적 점검)', () => {
  // 상세 팝업만 전용 폭 클래스를 갖고, 그 규칙은 화면 폭 80%이며 최대 폭이 없다.
  // 테스트 코드: AC-153
  it('gives only the Action detail dialog the dedicated width class and a 80vw rule without max-width', async () => {
    // given: Action A가 있는 Actions 탭에서 "Action 추가" 팝업을 열었다 닫는다
    const view = await openActionsTab()
    await addAction(view, A_INPUT)
    await view.user.click(screen.getByRole('button', { name: 'Action 추가' }))
    // then: 추가 팝업에는 전용 클래스가 없다
    expect(screen.getByRole('dialog', { name: 'Action 추가' })).not.toHaveClass('dd-action-detail-modal')
    await view.user.keyboard('{Escape}')

    // when: A 행을 눌러 상세 팝업을 열고 삭제 확인 대화상자를 연다
    const detail = await openDetail(view, '킥오프 미팅')
    await view.user.click(within(detail).getByRole('button', { name: '삭제' }))
    const confirm = await screen.findByRole('dialog', { name: 'Action 삭제' })

    // then: 상세 대화상자는 modal·wide·dd-action-detail-modal을 모두 갖고, 삭제 확인에는 전용 클래스가 없다
    const dialog = screen.getByRole('dialog', { name: DETAIL })
    expect(dialog).toHaveClass('modal', 'wide', 'dd-action-detail-modal')
    expect(confirm).not.toHaveClass('dd-action-detail-modal')

    // then: 전용 규칙은 80vw 식이고 max-width가 없으며 공통 규칙은 그대로다
    const rule = ruleOf(detailCss, '.modal.wide.dd-action-detail-modal')
    expect(rule.replace(/\s+/g, ' ')).toMatch(/width:\s*min\(max\(640px,\s*80vw\),\s*100%\)/)
    expect(rule).not.toMatch(/max-width/)
    expect(ruleOf(uiCss, '.modal')).toMatch(/width:\s*min\(480px,\s*100%\)/)
    expect(ruleOf(uiCss, '.modal.wide')).toMatch(/width:\s*min\(640px,\s*100%\)/)
  })
})

describe('진행사항 편집 칸 크기', () => {
  // 값 버튼은 칸 폭 전체, 편집 칸은 값 버튼 높이로 시작하며 높이를 잴 수 없으면 3줄이다.
  // 테스트 코드: AC-154
  it('opens the progress editor full width at the value button height, or three rows when it cannot be measured', async () => {
    // given: 값 버튼 높이가 96px로 측정되는 Action A 상세 팝업
    let height = 96
    fixMeasures(() => height, () => 0)
    const { view, dialog } = await openA()

    // then: 진행사항 값 버튼은 dd-click·dd-click-fill, 수행일·유형 값 버튼에는 dd-click-fill이 없다
    const opener = within(dialog).getByRole('button', { name: '진행사항 수정' })
    expect(opener).toHaveClass('dd-click', 'dd-click-fill')
    expect(within(dialog).getByRole('button', { name: '수행일 수정' })).not.toHaveClass('dd-click-fill')
    expect(within(dialog).getByRole('button', { name: '유형 수정' })).not.toHaveClass('dd-click-fill')
    // then: 값 버튼 규칙과 편집 칸 규칙
    const buttonRule = ruleOf(detailCss, 'button.dd-click.dd-click-fill')
    expect(buttonRule).toMatch(/display:\s*block/)
    expect(buttonRule).toMatch(/width:\s*100%/)
    const textRule = ruleOf(detailCss, '.dd-fill-text')
    expect(textRule).toMatch(/width:\s*100%/)
    expect(textRule).toMatch(/resize:\s*vertical/)

    // when: "진행사항 수정"을 누른다
    await view.user.click(opener)
    // then: dd-fill-text 칸이 인라인 높이 96px, 값 "킥오프 미팅"으로 포커스를 받아 열린다
    const input = within(dialog).getByLabelText('진행사항')
    expect(input.tagName).toBe('TEXTAREA')
    expect(input).toHaveClass('dd-fill-text')
    expect(input).toHaveStyle({ height: '96px' })
    expect(input).toHaveValue('킥오프 미팅')
    expect(input).toHaveFocus()

    // when: Esc로 닫고 잰 높이가 0인 상태로 다시 연다
    await view.user.keyboard('{Escape}')
    height = 0
    await view.user.click(within(detail()).getByRole('button', { name: '진행사항 수정' }))
    // then: 인라인 높이가 없고 rows는 3이다
    const again = within(detail()).getByLabelText('진행사항')
    expect(again.style.height).toBe('')
    expect(again).toHaveAttribute('rows', '3')
  })
})

describe('편집 칸 자동 늘림', () => {
  // 내용이 길어지면 내용 높이(+2)로 늘고, 지워도 시작 높이 아래로는 줄지 않으며 저장 요청은 없다.
  // 테스트 코드: AC-155
  it('grows to scrollHeight plus 2px and never shrinks below the start height', async () => {
    // given: 값 버튼 높이 48px로 진행사항 편집이 열려 있다(수정 요청 감시)
    let scroll = 30
    fixMeasures(() => 48, () => scroll)
    const update = vi.spyOn(gateway.actions, 'update')
    const { view, dialog } = await openA()
    await view.user.click(within(dialog).getByRole('button', { name: '진행사항 수정' }))
    const input = within(dialog).getByLabelText('진행사항')
    expect(input).toHaveStyle({ height: '48px' })

    // when: 내용 높이가 120px이 되도록 글을 더 친다
    scroll = 120
    await view.user.type(input, ' 추가')
    // then: 인라인 높이는 122px이다
    expect(input).toHaveStyle({ height: '122px' })

    // when: 내용 높이가 30px이 되도록 글을 지운다
    scroll = 30
    await view.user.clear(input)
    // then: 시작 높이 48px로 돌아오고 저장 요청은 없다
    expect(input).toHaveStyle({ height: '48px' })
    expect(update).not.toHaveBeenCalled()
  })
})

describe('Next Action 편집 칸', () => {
  // Next Action도 같은 크기의 여러 줄 칸이고 Shift+Enter는 줄바꿈, Enter는 Due Date와 함께 한 번 저장한다.
  // 테스트 코드: AC-156
  it('is a multi-line field of the same size where Shift+Enter breaks the line and Enter saves with the due date', async () => {
    // given: Next Action 값 버튼 높이 48px인 Action A 상세 팝업(수정 요청 감시)
    fixMeasures(() => 48, () => 0)
    const update = vi.spyOn(gateway.actions, 'update')
    const { view, dialog } = await openA()
    const opener = within(dialog).getByRole('button', { name: 'Next Action · Due Date 수정' })
    expect(opener).toHaveClass('dd-click-fill')

    // when: 수정을 열어 Next Action 칸 끝에 Shift+Enter, "추가 자료"를 치고 Enter를 누른다
    await view.user.click(opener)
    const next = within(dialog).getByLabelText('Next Action')
    // then: 여러 줄 칸(textarea)이 dd-fill-text, 높이 48px, 포커스로 열리고 Due Date 칸이 함께 있다
    expect(next.tagName).toBe('TEXTAREA')
    expect(next).toHaveClass('dd-fill-text')
    expect(next).toHaveStyle({ height: '48px' })
    expect(next).toHaveFocus()
    expect(within(dialog).getByLabelText('Due Date')).toBeVisible()

    await view.user.type(next, '{Shift>}{Enter}{/Shift}추가 자료')
    // then: Enter 전에 칸 값에 줄바꿈이 실제로 들어 있다(공백으로 바뀌지 않았다)
    expect((next as HTMLTextAreaElement).value).toBe('요구사항 문서 전달\n추가 자료')
    await view.user.keyboard('{Enter}')

    // then: 수정 요청은 한 번이고 줄바꿈이 든 Next Action과 Due를 보내며 팝업이 두 줄로 보인다
    await waitFor(() => expect(update).toHaveBeenCalledTimes(1))
    expect(update.mock.calls[0]?.[1]).toMatchObject({ nextAction: '요구사항 문서 전달\n추가 자료', dueDate: '2027-01-15' })
    await waitFor(() => expect(fieldValue(detail(), 'Next Action').textContent).toContain('요구사항 문서 전달\n추가 자료'))
    expect(within(detail()).queryByLabelText('Next Action')).not.toBeInTheDocument()
  })
})

const detail = () => screen.getByRole('dialog', { name: DETAIL })
