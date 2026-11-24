import { act, fireEvent, screen, waitFor, within } from '@testing-library/react'
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'
import { gateway } from '../../../gateway'
import { ApiError } from '../../../shared/api/problem'
import {
  A_INPUT,
  DETAIL,
  NOTICE_DELETE_TITLE,
  NOTICE_EDIT,
  addAction,
  bodyRows,
  fieldValue,
  openActionsTab,
  openDetail,
  rowWith,
} from '../../../test/actionDetail'
import { resetMock } from '../../../test/fake/default'
import { USER_ID } from '../../../test/fake/seed/ids'

/** Action 상세 팝업: 열기·보기·권한·삭제(AC-R48~R52). 서버 시계는 2026-11-13로 고정한다. */
const NOW = '2026-11-13T14:30:00+09:00'

beforeEach(() => resetMock({ now: NOW }))
afterEach(() => {
  vi.restoreAllMocks()
  resetMock({ now: null })
})

const detail = () => screen.getByRole('dialog', { name: DETAIL })
const queryDetail = () => screen.queryByRole('dialog', { name: DETAIL })

describe('행을 눌러 여는 상세 팝업의 내용', () => {
  // 행을 누르면 모든 항목(담당자·등록 시점 Status·Forecast·상태 포함, Memo 없음)을 보인다.
  // 테스트 코드: AC-132
  it('shows every field of the clicked action including actor, status and forecast at registration and state, without a Memo row', async () => {
    // given: 김영업이 수행일 2026-11-10의 Action A를 남겼다
    const view = await openActionsTab()
    await addAction(view, A_INPUT)

    // when: A의 행을 누른다
    const dialog = await openDetail(view, '킥오프 미팅')

    // then: 제목 "Action 상세" 대화상자에 모든 값이 보인다
    expect(fieldValue(dialog, '수행일')).toHaveTextContent('2026-11-10')
    expect(fieldValue(dialog, '담당자')).toHaveTextContent('김영업')
    expect(fieldValue(dialog, '유형')).toHaveTextContent('미팅')
    expect(fieldValue(dialog, '진행사항')).toHaveTextContent('킥오프 미팅')
    expect(fieldValue(dialog, 'Next Action')).toHaveTextContent('요구사항 문서 전달')
    expect(fieldValue(dialog, 'Due Date')).toHaveTextContent('2027-01-15')
    expect(fieldValue(dialog, 'Next Action 상태')).toHaveTextContent('Open')
    expect(Array.from(dialog.querySelectorAll('dt')).map((el) => el.textContent)).not.toContain('Memo')
    expect(within(dialog).queryByRole('button', { name: 'Memo 수정' })).not.toBeInTheDocument()
    // then: 등록 시점 Status·Forecast 배지도 있다(Deal의 지금 값)
    expect(dialog).toHaveTextContent('가격협상')
    expect(dialog).toHaveTextContent('Commit')
  })

  // 등록 때의 Status·Forecast는 Deal의 지금 값과 다를 수 있다.
  // 테스트 코드: AC-132
  it('shows the status at registration of an older action, which differs from the current one', async () => {
    // given: Actions 탭의 가장 오래된 행(등록 당시 POC완료)
    const view = await openActionsTab()
    const oldest = bodyRows(view.table).at(-1)!

    // when: 그 행을 누른다
    await view.user.click(within(oldest).getByRole('link'))
    const dialog = await screen.findByRole('dialog', { name: DETAIL })

    // then: 등록 당시 Status가 보이고 Deal의 지금 Status는 아니다
    expect(dialog).toHaveTextContent('POC완료')
    expect(dialog).not.toHaveTextContent('가격협상')
  })

  // 진행사항만 있는 Action은 Next Action·Due Date·상태가 "—"다.
  // 테스트 코드: AC-132
  it('shows dashes for next action, due date and state of a progress-only action', async () => {
    // given: 진행사항만 있는 Action
    const view = await openActionsTab()
    await addAction(view, { progress: '자료 송부' })

    // when: 그 행을 누른다
    const dialog = await openDetail(view, '자료 송부')

    // then: 세 값이 "—"이고 상태 버튼이 없다
    expect(fieldValue(dialog, 'Next Action')).toHaveTextContent('—')
    expect(fieldValue(dialog, 'Due Date')).toHaveTextContent('—')
    expect(fieldValue(dialog, 'Next Action 상태')).toHaveTextContent('—')
    expect(within(dialog).queryByRole('button', { name: '종료(수행)' })).not.toBeInTheDocument()
  })

  // 종료(수행)된 Action은 상태가 "종료(수행) · 종료일 <날짜>"다.
  // 테스트 코드: AC-132
  it('shows the closed state with its close date', async () => {
    // given: 종료(수행)된 Action
    const view = await openActionsTab()
    const created = await addAction(view, A_INPUT)
    await gateway.actions.changeNextActionStatus(created.id, { status: 'done', comment: '' })
    await view.client.invalidateQueries()

    // when: 그 행을 누른다
    const dialog = await openDetail(view, '킥오프 미팅')

    // then: 상태 줄이 종료일과 함께 보인다(오늘은 2026-11-13)
    await waitFor(() => expect(fieldValue(dialog, 'Next Action 상태')).toHaveTextContent('종료(수행) · 종료일 2026-11-13'))
  })

  // "닫기"를 누르면 팝업이 닫힌다.
  // 테스트 코드: AC-132
  it('closes with the close button', async () => {
    // given: 열린 상세 팝업
    const view = await openActionsTab()
    const dialog = await openDetail(view, '최종 가격 협의')

    // when: 닫기를 누른다
    await view.user.click(within(dialog).getByRole('button', { name: '닫기' }))

    // then: 팝업이 없다
    expect(queryDetail()).not.toBeInTheDocument()
  })
})

describe('키보드로 행 열기', () => {
  // Enter·Space가 상세 팝업을 열고 Esc로 닫으면 포커스가 그 행으로 돌아온다.
  // 테스트 코드: AC-133
  it('opens with Enter on the date link and returns focus to the link after Escape', async () => {
    // given: Actions 탭의 두 번째 행(Tab으로 닿는 행)
    const view = await openActionsTab()
    const row = bodyRows(view.table)[1]!
    const link = within(row).getByRole('link')
    const progress = '임원 보고용 ROI 자료 전달'

    // when: 행에 포커스를 두고 Enter를 누른다
    act(() => link.focus())
    await view.user.keyboard('{Enter}')
    // then: 그 Action의 상세 팝업이 열린다
    expect(fieldValue(await screen.findByRole('dialog', { name: DETAIL }), '진행사항')).toHaveTextContent(progress)

    // when: Esc로 닫는다
    await view.user.keyboard('{Escape}')
    // then: 팝업이 닫히고 포커스는 그 행에 있다
    await waitFor(() => expect(queryDetail()).not.toBeInTheDocument())
    expect(link).toHaveFocus()

    // when: 다시 Space를 누른다
    await view.user.keyboard('{Enter}')
    // then: 같은 Action의 상세 팝업이 다시 열린다
    expect(fieldValue(await screen.findByRole('dialog', { name: DETAIL }), '진행사항')).toHaveTextContent(progress)
  })

  // 행에서 Space를 눌러도 화면이 스크롤되지 않는다.
  // 테스트 코드: AC-133
  it('does not open a popup from keyboard events on the row itself', async () => {
    // given: Actions 탭의 행
    const view = await openActionsTab()
    const row = bodyRows(view.table)[0]!

    // when: 행에 Space 키 입력을 보낸다
    fireEvent.keyDown(row, { key: ' ' })
    fireEvent.keyDown(row, { key: 'Enter' })

    // then: 기본 동작(스크롤)이 막혀 있다
    expect(queryDetail()).not.toBeInTheDocument()
    expect(row).not.toHaveAttribute('tabindex')
  })
})

describe('행 안의 상태 칸 버튼', () => {
  // 종료 버튼을 누르면 종료 팝업만 열리고 상세 팝업은 열리지 않는다.
  // 테스트 코드: AC-134
  it('opens only the close dialog when the close button in the row is pressed', async () => {
    // given: KIM의 Open Action 행
    const view = await openActionsTab()

    // when: 행의 "종료(수행)"을 누른다
    await view.user.click(within(bodyRows(view.table)[0]!).getByRole('button', { name: '종료(수행)' }))

    // then: 종료 팝업만 열린다
    expect(await screen.findByRole('dialog', { name: 'Next Action 종료(수행)' })).toBeVisible()
    expect(queryDetail()).not.toBeInTheDocument()
  })

  // 키보드로 상태 버튼을 눌러도 상세 팝업은 열리지 않는다.
  // 테스트 코드: AC-134
  it('does not open the detail dialog when Enter or Space is pressed on the button in the row', async () => {
    // given: 상태 버튼에 포커스를 둔 행
    const view = await openActionsTab()
    const button = within(bodyRows(view.table)[0]!).getByRole('button', { name: '종료(미수행)' })
    act(() => button.focus())

    // when: Space를 누른다
    await view.user.keyboard(' ')

    // then: 종료 팝업만 열린다
    expect(await screen.findByRole('dialog', { name: 'Next Action 종료(미수행)' })).toBeVisible()
    expect(queryDetail()).not.toBeInTheDocument()

    // when: 취소한 뒤 Enter를 누른다
    await view.user.click(within(screen.getByRole('dialog')).getByRole('button', { name: '취소' }))
    act(() => button.focus())
    await view.user.keyboard('{Enter}')

    // then: 이번에도 종료 팝업만 열린다
    expect(await screen.findByRole('dialog', { name: 'Next Action 종료(미수행)' })).toBeVisible()
    expect(queryDetail()).not.toBeInTheDocument()
  })

  // "Open으로"는 팝업 없이 행을 Open으로 바꾸고 상세 팝업도 열지 않는다.
  // 테스트 코드: AC-134
  it('reopens in the row without any dialog', async () => {
    // given: 종료(수행)된 KIM의 행
    const view = await openActionsTab()
    const [first] = await gateway.actions.list(view.code, {})
    await gateway.actions.changeNextActionStatus(first!.id, { status: 'done', comment: '' })
    await view.client.invalidateQueries()
    const row = await waitFor(() => {
      const r = bodyRows(view.table)[0]!
      expect(within(r).getByRole('button', { name: 'Open으로' })).toBeVisible()
      return r
    })

    // when: "Open으로"를 누른다
    await view.user.click(within(row).getByRole('button', { name: 'Open으로' }))

    // then: 행이 Open이 되고 어떤 팝업도 열리지 않는다
    await waitFor(() => expect(within(bodyRows(view.table)[0]!).getByRole('button', { name: '종료(수행)' })).toBeVisible())
    expect(screen.queryByRole('dialog')).not.toBeInTheDocument()
  })
})

describe('상세 팝업의 편집·삭제 권한', () => {
  const editNames = ['수행일 수정', '유형 수정', '진행사항 수정', 'Next Action · Due Date 수정']

  // 본인 Action은 편집 버튼과 켜진 삭제가 있고 안내가 없다.
  // 테스트 코드: AC-135
  it('gives the author edit buttons and an enabled delete without any notice', async () => {
    // given: 김영업이 연 자기 Action(시드 최신 행)
    const view = await openActionsTab()

    // when: 행을 누른다
    const dialog = await openDetail(view, '최종 가격 협의')

    // then: 값마다 편집 버튼이 있고 삭제가 켜져 있으며 안내가 없다
    for (const name of editNames) expect(within(dialog).getByRole('button', { name })).toBeVisible()
    expect(within(dialog).getByRole('button', { name: '삭제' })).toBeEnabled()
    expect(within(dialog).queryByText(NOTICE_EDIT)).not.toBeInTheDocument()
    // then: 담당자·등록 시점 Status·Forecast에는 편집 버튼이 없다
    expect(within(dialog).queryByRole('button', { name: /^(담당자|Status|Forecast|등록 시점.*) 수정$/ })).not.toBeInTheDocument()
  })

  // 다른 sales의 Action은 값만 보이고 삭제가 꺼진 채 안내가 보인다.
  // 테스트 코드: AC-135
  it('shows another sales action read-only with a disabled delete and the notice', async () => {
    // given: LEE(박영업)의 Action B를 김영업이 본다
    const view = await openActionsTab()
    await addAction(view, { progress: '박영업의 진행', type: { name: '통화' } }, USER_ID.park)

    // when: B의 행을 누른다
    const dialog = await openDetail(view, '박영업의 진행')

    // then: 편집 버튼이 없고 삭제가 꺼져 title이 있으며 안내가 보인다
    expect(within(dialog).queryByRole('button', { name: /수정$/ })).not.toBeInTheDocument()
    const remove = within(dialog).getByRole('button', { name: '삭제' })
    expect(remove).toBeDisabled()
    expect(remove).toHaveAttribute('title', NOTICE_DELETE_TITLE)
    expect(within(dialog).getByText(NOTICE_EDIT)).toBeVisible()
    expect(fieldValue(dialog, '진행사항')).toHaveTextContent('박영업의 진행')
  })

  // admin은 남의 Action에도 편집 버튼과 켜진 삭제가 있다.
  // 테스트 코드: AC-135
  it('gives admin the edit buttons and an enabled delete on another users action', async () => {
    // given: 박영업의 Action B를 admin이 본다
    const view = await openActionsTab({ role: 'admin' })
    await addAction(view, { progress: '박영업의 진행' }, USER_ID.park, USER_ID.root)

    // when: B의 행을 누른다
    const dialog = await openDetail(view, '박영업의 진행')

    // then: 편집 버튼과 켜진 삭제가 있고 안내가 없다
    expect(within(dialog).getByRole('button', { name: '진행사항 수정' })).toBeVisible()
    expect(within(dialog).getByRole('button', { name: '삭제' })).toBeEnabled()
    expect(within(dialog).queryByText(NOTICE_EDIT)).not.toBeInTheDocument()
  })

  // user는 값만 보고 삭제·안내 없이 닫기만 있다.
  // 테스트 코드: AC-072
  it('lets the user role view every value with only the close button', async () => {
    // given: user(VIEWER)가 연 Actions 탭
    const view = await openActionsTab({ role: 'user' })
    expect(screen.queryByRole('button', { name: 'Action 추가' })).not.toBeInTheDocument()

    // when: KIM의 행을 누른다
    const dialog = await openDetail(view, '최종 가격 협의')

    // then: 값은 보이고 편집 버튼·삭제·안내가 없고 닫기만 있다
    expect(fieldValue(dialog, '진행사항')).toHaveTextContent('최종 가격 협의')
    expect(within(dialog).queryByRole('button', { name: /수정$/ })).not.toBeInTheDocument()
    expect(within(dialog).queryByRole('button', { name: '삭제' })).not.toBeInTheDocument()
    expect(within(dialog).queryByText(NOTICE_EDIT)).not.toBeInTheDocument()
    expect(within(dialog).getByRole('button', { name: '닫기' })).toBeVisible()
  })
})

describe('상세 팝업의 삭제', () => {
  // 확인 대화상자를 거쳐 삭제하면 두 팝업이 닫히고 행이 사라지며 요약 바가 이전 값으로 돌아간다.
  // 테스트 코드: AC-088
  it('deletes after the confirmation, closes both dialogs and rolls the summary bar back to the previous next action', async () => {
    // given: 김영업의 최신 Action(Next Action "계약서 초안 검토")과 그 이전 Action
    const view = await openActionsTab()
    const before = bodyRows(view.table).length
    const dialog = await openDetail(view, '최종 가격 협의')
    expect(within(view.table).queryByRole('button', { name: '삭제' })).not.toBeInTheDocument()

    // when: 팝업의 "삭제"를 누른다
    await view.user.click(within(dialog).getByRole('button', { name: '삭제' }))
    const confirm = await screen.findByRole('dialog', { name: 'Action 삭제' })

    // then: 확인 대화상자가 History 안내와 함께 상세 팝업 위에 열려 있다
    expect(confirm).toHaveTextContent('"최종 가격 협의" Action을 삭제합니다. 삭제는 Deal History에 기록됩니다.')
    expect(queryDetail()).toBeInTheDocument()

    // when: 확인 대화상자에서 삭제한다
    await view.user.click(within(confirm).getByRole('button', { name: '삭제' }))

    // then: 두 대화상자가 닫히고 행이 하나 줄며 알림이 보인다
    await waitFor(() => expect(screen.queryByRole('dialog')).not.toBeInTheDocument())
    await waitFor(() => expect(bodyRows(view.table)).toHaveLength(before - 1))
    expect(screen.getByText('Action이 삭제되었습니다.')).toBeVisible()
    // then: 요약 바 Next Action이 이전 Action의 값이다
    await view.user.click(screen.getByRole('tab', { name: 'Deal 상세' }))
    const bar = await screen.findByRole('region', { name: 'Deal 정보' })
    await waitFor(() => expect(within(bar).queryByText(/계약서 초안 검토/)).not.toBeInTheDocument())
    expect(within(bar).getByText(/최종 가격 협의 일정 확정/)).toBeVisible()
  })

  // 확인에서 취소하면 확인 대화상자만 닫히고 상세 팝업과 행이 남는다.
  // 테스트 코드: AC-088
  it('keeps the detail dialog and the row when the confirmation is cancelled', async () => {
    // given: 삭제 확인이 열린 상세 팝업
    const view = await openActionsTab()
    const before = bodyRows(view.table).length
    const dialog = await openDetail(view, '최종 가격 협의')
    await view.user.click(within(dialog).getByRole('button', { name: '삭제' }))
    const confirm = await screen.findByRole('dialog', { name: 'Action 삭제' })

    // when: 취소한다
    await view.user.click(within(confirm).getByRole('button', { name: '취소' }))

    // then: 확인만 닫히고 상세 팝업과 행이 그대로다
    expect(screen.queryByRole('dialog', { name: 'Action 삭제' })).not.toBeInTheDocument()
    expect(detail()).toBeVisible()
    expect(bodyRows(view.table)).toHaveLength(before)
  })

  // 서버가 삭제를 거절하면 확인이 닫히고 상세 팝업 안 오류 배너에 서버 문구가 보인다.
  // 테스트 코드: AC-088
  it('closes the confirmation and shows the server message inside the detail dialog when the delete is refused', async () => {
    // given: 서버가 삭제를 거절한다
    vi.spyOn(gateway.actions, 'remove').mockRejectedValue(
      new ApiError(403, {
        type: 'https://sales.neoine.test/problems/forbidden',
        title: 'x',
        status: 403,
        detail: '본인 Action 또는 admin만 삭제할 수 있습니다.',
      }),
    )
    const view = await openActionsTab()
    const before = bodyRows(view.table).length
    const dialog = await openDetail(view, '최종 가격 협의')
    await view.user.click(within(dialog).getByRole('button', { name: '삭제' }))
    const confirm = await screen.findByRole('dialog', { name: 'Action 삭제' })

    // when: 확인 대화상자에서 삭제한다
    await view.user.click(within(confirm).getByRole('button', { name: '삭제' }))

    // then: 확인이 닫히고 상세 팝업 안 배너에 서버 문구가 보인다
    await waitFor(() => expect(screen.queryByRole('dialog', { name: 'Action 삭제' })).not.toBeInTheDocument())
    expect(await within(detail()).findByRole('alert')).toHaveTextContent('본인 Action 또는 admin만 삭제할 수 있습니다.')
    // then: 행이 남고 삭제 알림은 없다
    expect(bodyRows(view.table)).toHaveLength(before)
    expect(rowWith(view.table, '최종 가격 협의')).toBeVisible()
    expect(screen.queryByText('Action이 삭제되었습니다.')).not.toBeInTheDocument()
  })
})
