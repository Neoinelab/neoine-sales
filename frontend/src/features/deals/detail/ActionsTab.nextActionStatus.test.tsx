import { fireEvent, screen, waitFor, within } from '@testing-library/react'
import { describe, expect, it } from 'vitest'
import { gateway } from '../../../gateway'
import { defaultMock } from '../../../test/fake/default'
import { dealCodeOf, detailPath } from '../../../test/detailTestUtils'
import { renderAt } from '../../../test/mockApp'
import { USER_ID } from '../../../test/fake/seed/ids'

type View = Awaited<ReturnType<typeof renderAt>>

async function openActions(role: 'sales' | 'admin' | 'user' = 'sales', userId?: number) {
  const view = await renderAt(await detailPath(1, '?tab=actions'), userId ? { userId } : { role })
  await screen.findByRole('heading', { level: 1, name: '한빛은행 ITDR 도입' })
  const table = await screen.findByRole('table', { name: 'Action 목록' })
  return { ...view, table }
}

const bodyRows = (table: HTMLElement) => within(table).getAllByRole('row').slice(1)

async function openForm(user: View['user']) {
  await user.click(screen.getByRole('button', { name: 'Action 추가' }))
  return screen.getByRole('form', { name: 'Action 추가' })
}

async function register(user: View['user'], form: HTMLElement, fill: { progress?: string; next?: string; due?: string }) {
  await user.type(within(form).getByLabelText('유형'), '미팅')
  if (fill.progress) await user.type(within(form).getByLabelText('진행사항'), fill.progress)
  if (fill.next) await user.type(within(form).getByLabelText('Next Action'), fill.next)
  if (fill.due) await user.type(within(form).getByLabelText('Due Date'), fill.due)
  await user.click(within(form).getByRole('button', { name: '등록' }))
}

describe('Action 폼: 진행사항·Next Action 분리 입력', () => {
  // 진행사항만 입력한 Action은 Next Action·Due Date 칸이 "—"이고 종료 버튼이 없다.
  // 테스트 코드: AC-006
  it('진행사항만 등록하면 Next Action과 Due Date 칸이 대시로 보이고 종료 버튼이 없다', async () => {
    // given: Actions 탭의 현재 행 수
    const { user, table } = await openActions()
    const before = bodyRows(table).length

    // when: 진행사항만 입력해 등록한다
    await register(user, await openForm(user), { progress: '전화로만 확인' })

    // then: 맨 위에 새 행이 생기고 Next Action·Due Date는 "—"이며 종료 버튼이 없다
    await waitFor(() => expect(bodyRows(table)).toHaveLength(before + 1))
    const first = bodyRows(table)[0]!
    expect(first).toHaveTextContent('전화로만 확인')
    expect(within(first).getAllByText('—').length).toBeGreaterThanOrEqual(2)
    expect(within(first).queryByRole('button', { name: '종료(수행)' })).not.toBeInTheDocument()
  })

  // Next Action만 입력한 Action은 진행사항이 "—"이고 상태가 Open이다.
  // 테스트 코드: AC-007
  it('Next Action만 등록하면 상태가 Open이고 진행사항 칸이 대시로 보인다', async () => {
    // given: Actions 탭의 현재 행 수
    const { user, table } = await openActions()
    const before = bodyRows(table).length

    // when: Next Action과 Due Date만 입력해 등록한다
    await register(user, await openForm(user), { next: '견적 회신 받기', due: '2026-12-20' })

    // then: 맨 위 새 행의 상태가 Open이고 진행사항은 "—"이다
    await waitFor(() => expect(bodyRows(table)).toHaveLength(before + 1))
    const first = bodyRows(table)[0]!
    expect(first).toHaveTextContent('견적 회신 받기')
    expect(first).toHaveTextContent('Open')
    expect(within(first).getAllByText('—').length).toBeGreaterThanOrEqual(1)
  })

  // 진행사항과 Next Action이 모두 비면 안내 문구만 보이고 저장하지 않는다.
  // 테스트 코드: AC-008
  it('진행사항과 Next Action이 모두 비면 안내 문구를 보이고 아무것도 저장하지 않는다', async () => {
    // given: Actions 탭의 현재 행 수
    const { user, table } = await openActions()
    const before = bodyRows(table).length

    // when: 유형만 입력하고 등록한다
    await register(user, await openForm(user), {})

    // then: 안내 문구가 보이고 행 수는 그대로다
    expect(await screen.findByText('진행사항 또는 Next Action을 입력하세요.')).toBeVisible()
    expect(bodyRows(table)).toHaveLength(before)
  })

  // Next Action이 있는데 Due Date가 없으면 Due Date 안내 문구가 보인다.
  // 테스트 코드: AC-009
  it('Next Action만 입력하고 Due Date가 없으면 Due Date 안내 문구를 보인다', async () => {
    // given: Actions 탭
    const { user } = await openActions()

    // when: Next Action만 입력하고 등록한다
    await register(user, await openForm(user), { next: '다음 할 일' })

    // then: "Due Date를 입력하세요."가 보인다
    expect(await screen.findByText('Due Date를 입력하세요.')).toBeVisible()
  })

  // 진행사항만 있는 Action은 Due Date를 요구하지 않는다.
  it('진행사항만 입력하면 Due Date를 요구하지 않는다', async () => {
    // given: Actions 탭
    const { user } = await openActions()

    // when: 진행사항만 입력하고 등록한다
    await register(user, await openForm(user), { progress: '진행만' })

    // then: Due Date·입력 안내 문구가 모두 보이지 않는다
    await waitFor(() => expect(screen.queryByText('Due Date를 입력하세요.')).not.toBeInTheDocument())
    expect(screen.queryByText('진행사항 또는 Next Action을 입력하세요.')).not.toBeInTheDocument()
  })

  // Next Action을 모두 지우면 Due Date도 함께 비워진다.
  // 테스트 코드: AC-075
  it('Next Action을 모두 지우면 Due Date 입력도 비워진다', async () => {
    // given: 추가 팝업에서 Next Action과 Due Date를 입력했다
    const { user } = await openActions()
    const form = await openForm(user)
    await user.type(within(form).getByLabelText('Next Action'), '지울 계획')
    await user.type(within(form).getByLabelText('Due Date'), '2026-12-20')

    // when: Next Action을 모두 지운다
    await user.clear(within(form).getByLabelText('Next Action'))

    // then: Due Date 칸이 비어 있다
    expect(within(form).getByLabelText('Due Date')).toHaveValue('')
  })
})

describe('Action 표: 상태 열과 상태 버튼', () => {
  // Next Action이 Open인 행은 작성자에게 라벨과 종료(수행)·종료(미수행) 버튼 둘을 보인다.
  // 테스트 코드: NA-044
  it('shows Open and both close buttons to the author on an Open Next Action', async () => {
    // given: 김영업이 작성한 Open Action이 있는 Deal의 Actions 탭을 작성자가 연다.
    const { table } = await openActions()
    // when: 표의 첫 행을 본다.
    const first = bodyRows(table)[0]!

    // then: 상태 칸에 Open 라벨과 종료 버튼 둘이 보인다.
    expect(first).toHaveTextContent('Open')
    expect(within(first).getByRole('button', { name: '종료(수행)' })).toBeVisible()
    expect(within(first).getByRole('button', { name: '종료(미수행)' })).toBeVisible()
  })

  // 상태 버튼은 admin에게 보이고 다른 sales와 user에게는 라벨만 보인다.
  // 테스트 코드: NA-045
  it('shows the buttons to admin but not to another sales or the read-only user', async () => {
    // when: admin, 다른 sales(박영업), user가 각각 Actions 탭을 연다.
    const admin = await openActions('admin')
    // then: admin에게는 종료 버튼이 보인다.
    expect(within(bodyRows(admin.table)[0]!).getByRole('button', { name: '종료(수행)' })).toBeVisible()
    admin.unmount()

    const park = await openActions('sales', USER_ID.park)
    // then: 박영업에게는 버튼 없이 Open 라벨만 보인다.
    expect(within(bodyRows(park.table)[0]!).queryByRole('button', { name: '종료(수행)' })).not.toBeInTheDocument()
    expect(bodyRows(park.table)[0]).toHaveTextContent('Open')
    park.unmount()

    const viewer = await openActions('user')
    // then: user에게도 버튼이 없다.
    expect(within(bodyRows(viewer.table)[0]!).queryByRole('button', { name: '종료(수행)' })).not.toBeInTheDocument()
  })
})

describe('Next Action이 없는 행의 상태 칸', () => {
  // Next Action이 없는 진행사항만 행의 상태 칸은 "—"이고 버튼이 없다.
  // 테스트 코드: NA-044
  it('shows a dash and no button on the status cell of a progress-only action', async () => {
    // given: 작성자가 연 Actions 탭에 진행사항만 Action이 새로 생겼다(수행일시 오름차순으로 읽어 마지막 행에 온다).
    const code = await dealCodeOf(1)
    const { user, table } = await openActions()
    await gateway.actions.create(code, { type: { name: '미팅' }, progress: '전화로만 확인', nextAction: '', dueDate: '', memo: '' })
    // when: 수행일시 머리글을 눌러 목록을 다시 읽는다.
    await user.click(within(table).getByRole('button', { name: '수행일시' }))
    // then: 진행사항만 행의 상태 칸은 "—"이고 상태 버튼이 없다.
    await waitFor(() => expect(bodyRows(table).at(-1)).toHaveTextContent('전화로만 확인'))
    const statusCell = within(bodyRows(table).at(-1)!).getAllByRole('cell')[7]!
    expect(statusCell).toHaveTextContent('—')
    expect(within(statusCell).queryByRole('button')).not.toBeInTheDocument()
  })
})

describe('Next Action 종료 팝업', () => {
  // 종료(수행) 버튼은 메모 팝업을 거쳐 입력한 메모로 종료하고 행에 새 상태와 Memo가 보인다.
  // 테스트 코드: NA-047, NA-051
  it('opens a memo dialog for done and closes with the typed memo appended', async () => {
    // given: 작성자의 Open Action 행이 있다.
    const { user, table } = await openActions()
    // when: "종료(수행)"을 눌러 열린 팝업에 "문서 전달 완료"를 쓰고 "종료"를 누른다.
    await user.click(within(bodyRows(table)[0]!).getByRole('button', { name: '종료(수행)' }))

    const dialog = await screen.findByRole('dialog', { name: 'Next Action 종료(수행)' })
    await user.type(within(dialog).getByLabelText('Memo에 남길 내용(선택)'), '문서 전달 완료')
    await user.click(within(dialog).getByRole('button', { name: '종료' }))

    // then: 팝업이 닫히고 행이 종료(수행)과 메모를 보이며 "Open으로" 버튼이 생긴다.
    await waitFor(() => expect(screen.queryByRole('dialog')).not.toBeInTheDocument())
    await waitFor(() => expect(bodyRows(table)[0]).toHaveTextContent('종료(수행)'))
    expect(bodyRows(table)[0]).toHaveTextContent('문서 전달 완료')
    expect(within(bodyRows(table)[0]!).getByRole('button', { name: 'Open으로' })).toBeVisible()
  })

  // 종료(미수행) 팝업은 제목이 다르고 메모를 비운 채 종료할 수 있다.
  // 테스트 코드: NA-047
  it('uses the not-done title and allows closing with an empty memo', async () => {
    // given: 작성자의 Open Action 행이 있다.
    const { user, table } = await openActions()
    // when: "종료(미수행)"을 눌러 "Next Action 종료(미수행)" 팝업에서 메모 없이 "종료"를 누른다.
    await user.click(within(bodyRows(table)[0]!).getByRole('button', { name: '종료(미수행)' }))

    const dialog = await screen.findByRole('dialog', { name: 'Next Action 종료(미수행)' })
    await user.click(within(dialog).getByRole('button', { name: '종료' }))

    // then: 행이 종료(미수행)이 된다.
    await waitFor(() => expect(bodyRows(table)[0]).toHaveTextContent('종료(미수행)'))
  })

  // 팝업의 취소는 요청 없이 닫고 상태와 Memo를 바꾸지 않는다.
  // 테스트 코드: NA-048
  it('leaves the status unchanged on cancel', async () => {
    // given: 종료(수행) 팝업에 "버릴 메모"를 쓴 상태다.
    const { user, table } = await openActions()
    await user.click(within(bodyRows(table)[0]!).getByRole('button', { name: '종료(수행)' }))
    const dialog = await screen.findByRole('dialog', { name: 'Next Action 종료(수행)' })
    await user.type(within(dialog).getByLabelText('Memo에 남길 내용(선택)'), '버릴 메모')

    // when: "취소"를 누른다.
    await user.click(within(dialog).getByRole('button', { name: '취소' }))

    // then: 팝업이 닫히고 행은 Open 그대로이며 버린 메모가 없다.
    await waitFor(() => expect(screen.queryByRole('dialog')).not.toBeInTheDocument())
    expect(bodyRows(table)[0]).toHaveTextContent('Open')
    expect(bodyRows(table)[0]).not.toHaveTextContent('버릴 메모')
  })

  // 팝업에서 Esc를 누르면 요청 없이 닫고 상태를 바꾸지 않는다.
  // 테스트 코드: NA-048
  it('leaves the status unchanged on Escape', async () => {
    // given: 종료(수행) 팝업이 열려 있다.
    const { user, table } = await openActions()
    await user.click(within(bodyRows(table)[0]!).getByRole('button', { name: '종료(수행)' }))
    await screen.findByRole('dialog', { name: 'Next Action 종료(수행)' })

    // when: Esc를 누른다.
    fireEvent.keyDown(screen.getByRole('dialog'), { key: 'Escape' })

    // then: 팝업이 닫히고 행은 Open 그대로다.
    await waitFor(() => expect(screen.queryByRole('dialog')).not.toBeInTheDocument())
    expect(bodyRows(table)[0]).toHaveTextContent('Open')
  })

  // "Open으로"는 팝업 없이 바로 Open으로 되돌린다.
  // 테스트 코드: NA-049
  it('reopens a closed Next Action without a dialog', async () => {
    // given: 종료(수행)된 작성자의 Action 행이 있다.
    const { user, table } = await openActions()
    await user.click(within(bodyRows(table)[0]!).getByRole('button', { name: '종료(수행)' }))
    await user.click(within(await screen.findByRole('dialog')).getByRole('button', { name: '종료' }))
    await waitFor(() => expect(bodyRows(table)[0]).toHaveTextContent('종료(수행)'))

    // when: "Open으로"를 누른다.
    await user.click(within(bodyRows(table)[0]!).getByRole('button', { name: 'Open으로' }))

    // then: 팝업 없이 행이 Open이 된다.
    await waitFor(() => expect(bodyRows(table)[0]).toHaveTextContent('Open'))
    expect(screen.queryByRole('dialog')).not.toBeInTheDocument()
  })
})

describe('Action 검색: Next Action 상태 필터', () => {
  // Next Action 상태 검색 선택지는 전체·Open·종료(수행)·종료(미수행)·종료(전체) 다섯 개다.
  // 테스트 코드: NA-052
  it('offers the five choices', async () => {
    // when: Actions 탭을 연다.
    await openActions()

    const select = screen.getByLabelText('Next Action 상태')

    // then: 상태 선택지가 다섯 개다.
    expect(within(select).getAllByRole('option').map((o) => o.textContent)).toEqual([
      '전체',
      'Open',
      '종료(수행)',
      '종료(미수행)',
      '종료(전체)',
    ])
  })

  // 모든 Action이 Open이면 Open 검색은 행을 보이고 종료(전체) 검색은 빈 결과 문구를 보인다.
  // 테스트 코드: NA-054
  it('lists only Open actions for Open and none for closed when everything is open', async () => {
    // given: 모든 Action이 Open인 Deal이다.
    const { user, table } = await openActions()
    // when: Next Action 상태 "Open"으로 검색한다.
    await user.selectOptions(screen.getByLabelText('Next Action 상태'), 'Open')
    await user.click(screen.getByRole('button', { name: '검색' }))
    // then: 행이 보인다.
    await waitFor(() => expect(bodyRows(table).length).toBeGreaterThan(0))

    // when: 다시 "종료(전체)"로 검색한다.
    await user.selectOptions(screen.getByLabelText('Next Action 상태'), '종료(전체)')
    await user.click(screen.getByRole('button', { name: '검색' }))

    // then: "조건에 맞는 Action이 없습니다."가 보인다.
    expect(await screen.findByText('조건에 맞는 Action이 없습니다.')).toBeVisible()
  })
})

describe('Deal 상세 요약의 Next Action 상태', () => {
  // 기준 행을 종료(수행)하면 표와 요약 바 모두 새 상태 라벨을 보인다.
  // 테스트 코드: NA-051
  it('shows the status label of the basis Next Action and follows a close', async () => {
    // given: 기준 행이 Open인 Deal의 Actions 탭이다.
    const { user, table } = await openActions()
    const count = () => screen.getAllByText(/종료\(수행\)/).length
    expect(screen.getAllByText('Open').length).toBeGreaterThanOrEqual(2) // 표 + 요약

    // when: 그 행을 종료(수행)한다.
    await user.click(within(bodyRows(table)[0]!).getByRole('button', { name: '종료(수행)' }))
    await user.click(within(await screen.findByRole('dialog')).getByRole('button', { name: '종료' }))

    // then: 표와 요약 바 모두 "종료(수행)"을 보인다.
    await waitFor(() => expect(count()).toBeGreaterThanOrEqual(2))
  })
})

describe('Next Action 종료 실패', () => {
  // 서버가 거절하면 팝업이 열린 채 입력한 메모가 남고 팝업 안에 서버 문구가 보인다.
  // 테스트 코드: NA-050
  it('keeps the dialog open with the typed memo and shows the error when the server refuses (409)', async () => {
    // given: 종료 팝업에 "잃으면 안 되는 메모"를 쓰는 사이 그 Action이 다른 경로에서 이미 종료(수행)됐다.
    const { user, table } = await openActions()
    await user.click(within(bodyRows(table)[0]!).getByRole('button', { name: '종료(수행)' }))
    const dialog = await screen.findByRole('dialog', { name: 'Next Action 종료(수행)' })
    await user.type(within(dialog).getByLabelText('Memo에 남길 내용(선택)'), '잃으면 안 되는 메모')
    // 팝업이 열려 있는 동안 다른 경로에서 이미 같은 상태로 종료됐다(서버는 409 "이미 종료(수행) 상태입니다.").
    const [first] = await defaultMock.gateway.actions.list(await dealCodeOf(1), {})
    await defaultMock.gateway.actions.changeNextActionStatus(first!.id, { status: 'done', memo: '' })

    // when: "종료"를 누른다.
    await user.click(within(dialog).getByRole('button', { name: '종료' }))

    // then: 팝업 안에 "이미 종료(수행) 상태입니다."가 보이고 팝업과 메모가 그대로다.
    expect(await screen.findByText(/이미 종료\(수행\) 상태입니다\./)).toBeVisible()
    expect(screen.getByRole('dialog', { name: 'Next Action 종료(수행)' })).toBeVisible()
    expect(within(screen.getByRole('dialog')).getByLabelText('Memo에 남길 내용(선택)')).toHaveValue('잃으면 안 되는 메모')
  })

  // "Open으로"가 거절되면 팝업이 없으므로 탭의 오류 배너에 서버 문구가 보인다.
  // 테스트 코드: NA-050
  it('shows the server message in the tab banner when reopening is refused', async () => {
    // given: 작성자가 Action을 종료(수행)했고, 화면이 모르는 사이 다른 경로에서 이미 Open으로 되돌렸다.
    const code = await dealCodeOf(1)
    const { user, table } = await openActions()
    await user.click(within(bodyRows(table)[0]!).getByRole('button', { name: '종료(수행)' }))
    await user.click(within(await screen.findByRole('dialog')).getByRole('button', { name: '종료' }))
    await waitFor(() => expect(bodyRows(table)[0]).toHaveTextContent('종료(수행)'))
    const [first] = await gateway.actions.list(code, {})
    await gateway.actions.changeNextActionStatus(first!.id, { status: 'open', memo: '' })
    // when: 화면에 남아 있는 "Open으로"를 누른다.
    await user.click(within(bodyRows(table)[0]!).getByRole('button', { name: 'Open으로' }))
    // then: 탭의 오류 배너에 "이미 Open 상태입니다."가 보이고 팝업은 열리지 않는다.
    expect(await screen.findByRole('alert')).toHaveTextContent('이미 Open 상태입니다.')
    expect(screen.queryByRole('dialog')).not.toBeInTheDocument()
  })

  // 성공한 종료만 팝업을 닫는다.
  // 테스트 코드: NA-050
  it('closes the dialog only after a successful change', async () => {
    // given: 작성자의 Open Action 행이 있다.
    const { user, table } = await openActions()
    // when: "종료(수행)"을 누르고 팝업에서 "종료"를 누른다.
    await user.click(within(bodyRows(table)[0]!).getByRole('button', { name: '종료(수행)' }))
    await user.click(within(await screen.findByRole('dialog')).getByRole('button', { name: '종료' }))

    // then: 성공했으므로 팝업이 닫힌다.
    await waitFor(() => expect(screen.queryByRole('dialog')).not.toBeInTheDocument())
  })
})

describe('종료 상태 간 직접 전환', () => {
  async function closeFirst(user: View['user'], table: HTMLElement, label: '종료(수행)' | '종료(미수행)') {
    await user.click(within(bodyRows(table)[0]!).getByRole('button', { name: label }))
    await user.click(within(await screen.findByRole('dialog')).getByRole('button', { name: '종료' }))
    await waitFor(() => expect(screen.queryByRole('dialog')).not.toBeInTheDocument())
  }

  // 종료(수행) 행은 종료(미수행)과 "Open으로" 버튼만 보이고 종료(수행) 버튼은 없다.
  // 테스트 코드: NA-046
  it('offers the other closed status and "Open으로" on a done row, not the done button', async () => {
    // given: 작성자의 Action을 종료(수행)으로 바꿨다.
    const { user, table } = await openActions()
    // when: 작성자가 표를 본다.
    await closeFirst(user, table, '종료(수행)')

    const row = bodyRows(table)[0]!
    await waitFor(() => expect(within(row).getByRole('button', { name: 'Open으로' })).toBeVisible())

    // then: "종료(미수행)"·"Open으로"만 있고 "종료(수행)"은 없다.
    expect(within(row).getByRole('button', { name: '종료(미수행)' })).toBeVisible()
    expect(within(row).queryByRole('button', { name: '종료(수행)' })).not.toBeInTheDocument()
  })

  // 종료(미수행) 행은 종료(수행)과 "Open으로" 버튼만 보이고 종료(미수행) 버튼은 없다.
  // 테스트 코드: NA-046
  it('offers 종료(수행) and "Open으로" on a not-done row, not the not-done button', async () => {
    // given: 작성자의 Action을 종료(미수행)으로 바꿨다.
    const { user, table } = await openActions()
    // when: 작성자가 표를 본다.
    await closeFirst(user, table, '종료(미수행)')

    const row = bodyRows(table)[0]!
    await waitFor(() => expect(within(row).getByRole('button', { name: 'Open으로' })).toBeVisible())

    // then: "종료(수행)"·"Open으로"만 있고 "종료(미수행)"은 없다.
    expect(within(row).getByRole('button', { name: '종료(수행)' })).toBeVisible()
    expect(within(row).queryByRole('button', { name: '종료(미수행)' })).not.toBeInTheDocument()
  })

  // 종료(수행)에서 종료(미수행)으로 바로 전환할 때도 메모 팝업을 거치고 메모가 붙는다.
  // 테스트 코드: NA-047
  it('switches done to not-done through the memo dialog and appends the memo', async () => {
    // given: 종료(수행)된 작성자의 Action 행이 있다.
    const { user, table } = await openActions()
    await closeFirst(user, table, '종료(수행)')
    // when: "종료(미수행)"을 누르고 팝업에 "사실은 못 했음"을 써서 "종료"를 누른다.
    await user.click(await within(bodyRows(table)[0]!).findByRole('button', { name: '종료(미수행)' }))

    const dialog = await screen.findByRole('dialog', { name: 'Next Action 종료(미수행)' })
    await user.type(within(dialog).getByLabelText('Memo에 남길 내용(선택)'), '사실은 못 했음')
    await user.click(within(dialog).getByRole('button', { name: '종료' }))

    // then: 행이 종료(미수행)이 되고 메모가 보이며 팝업이 닫힌다.
    await waitFor(() => expect(bodyRows(table)[0]).toHaveTextContent('종료(미수행)'))
    expect(bodyRows(table)[0]).toHaveTextContent('사실은 못 했음')
    expect(screen.queryByRole('dialog')).not.toBeInTheDocument()
  })

  // 종료(미수행)에서 종료(수행)으로 바로 전환할 때도 메모 팝업을 거친다.
  // 테스트 코드: NA-047
  it('switches not-done to done through the memo dialog', async () => {
    // given: 종료(미수행)된 작성자의 Action 행이 있다.
    const { user, table } = await openActions()
    await closeFirst(user, table, '종료(미수행)')
    // when: "종료(수행)"을 누르고 팝업에서 메모 없이 "종료"를 누른다.
    await user.click(await within(bodyRows(table)[0]!).findByRole('button', { name: '종료(수행)' }))

    const dialog = await screen.findByRole('dialog', { name: 'Next Action 종료(수행)' })
    await user.click(within(dialog).getByRole('button', { name: '종료' }))

    // then: 행이 종료(수행)이 되고 "종료(미수행)" 전환 버튼이 보인다.
    await waitFor(() => expect(within(bodyRows(table)[0]!).getByRole('button', { name: '종료(미수행)' })).toBeVisible())
    expect(bodyRows(table)[0]).toHaveTextContent('종료(수행)')
  })

  // 종료 상태 사이 전환 팝업도 취소와 Esc로 상태를 바꾸지 않는다.
  // 테스트 코드: NA-048
  it('leaves the closed status on cancel and on Escape', async () => {
    // given: 종료(수행)된 행이 있다.
    const { user, table } = await openActions()
    await closeFirst(user, table, '종료(수행)')
    // when: "종료(미수행)" 팝업에서 "취소"를 누른다.
    await user.click(await within(bodyRows(table)[0]!).findByRole('button', { name: '종료(미수행)' }))
    await user.click(within(await screen.findByRole('dialog')).getByRole('button', { name: '취소' }))
    await waitFor(() => expect(screen.queryByRole('dialog')).not.toBeInTheDocument())
    // then: 종료(수행) 상태 그대로다.
    expect(within(bodyRows(table)[0]!).getByRole('button', { name: '종료(미수행)' })).toBeVisible()

    // when: 다시 팝업을 열고 Esc를 누른다.
    await user.click(within(bodyRows(table)[0]!).getByRole('button', { name: '종료(미수행)' }))
    fireEvent.keyDown(await screen.findByRole('dialog'), { key: 'Escape' })

    await waitFor(() => expect(screen.queryByRole('dialog')).not.toBeInTheDocument())
    // then: 여전히 종료(수행) 상태라 "종료(수행)" 버튼이 없다.
    expect(within(bodyRows(table)[0]!).queryByRole('button', { name: '종료(수행)' })).not.toBeInTheDocument()
  })

  // 다른 sales에게는 종료된 행에도 전환 버튼이 없다.
  // 테스트 코드: NA-045
  it('does not show switch buttons on a closed row to another sales', async () => {
    // given: 박영업이 연 Actions 탭에서 김영업이 작성한 Action이 종료(수행)됐다.
    const path = await detailPath(1, '?tab=actions')
    const park = await openActions('sales', USER_ID.park)
    const { gateway } = defaultMock
    const [first] = await gateway.actions.list(await dealCodeOf(1), {})
    await defaultMock.signInAs(USER_ID.kim)
    await gateway.actions.changeNextActionStatus(first!.id, { status: 'done', memo: '' })
    await defaultMock.signInAs(USER_ID.park)
    park.goTo('/deals')
    await screen.findByRole('heading', { name: /Deals/ })
    // when: 박영업이 표를 다시 본다.
    park.goTo(path)

    const table = await screen.findByRole('table', { name: 'Action 목록' })
    await waitFor(() => expect(bodyRows(table)[0]).toHaveTextContent('종료(수행)'))

    // then: 종료(수행) 라벨만 보이고 전환 버튼이 없다.
    const row = bodyRows(table)[0]!
    expect(within(row).queryByRole('button', { name: '종료(미수행)' })).not.toBeInTheDocument()
    expect(within(row).queryByRole('button', { name: 'Open으로' })).not.toBeInTheDocument()
  })
})
