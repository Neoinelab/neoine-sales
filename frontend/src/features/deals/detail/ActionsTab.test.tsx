import { screen, waitFor, within } from '@testing-library/react'
import { describe, expect, it } from 'vitest'
import { renderAt } from '../../../test/mockApp'
import { detailPath } from '../../../test/detailTestUtils'

/** 유형 자동완성 입력에 글자를 입력한다(목록 선택 없이 직접 입력). */
async function typeAction(user: Awaited<ReturnType<typeof renderAt>>['user'], form: HTMLElement, text: string) {
  await user.type(within(form).getByLabelText('유형'), text)
}

async function openActions(no: number, title: string, role: 'sales' | 'admin' | 'user' = 'sales') {
  const view = await renderAt(await detailPath(no), { role })
  await screen.findByRole('heading', { level: 1, name: title })
  const table = await screen.findByRole('table', { name: 'Action 목록' })
  return { ...view, table }
}

function bodyRows(table: HTMLElement) {
  return within(table).getAllByRole('row').slice(1)
}

describe('Actions 탭 목록 (T-ACTION-01)', () => {
  it('lists actions newest first with the columns the plan asks for', async () => {
    const { table } = await openActions(1, '한빛은행 ITDR 도입')
    const headers = within(table).getAllByRole('columnheader').map((h) => h.textContent)
    expect(headers).toEqual([
      '수행일시',
      '담당자',
      '등록 시점 Status·Forecast',
      '유형',
      '진행사항',
      'Next Action',
      'Due Date',
      'Memo',
      '관리',
    ])
    const first = bodyRows(table)[0]
    expect(first).toHaveTextContent('최종 가격 협의')
    expect(first).toHaveTextContent('계약서 초안 검토')
    expect(first).toHaveTextContent('가격협상')
    expect(first).toHaveTextContent('Commit')
    expect(bodyRows(table)[1]).toHaveTextContent('임원 보고용 ROI 자료 전달')
  })

  it('marks the overdue due date of the current next action', async () => {
    const { table } = await openActions(3, '미래전자 EDR 교체')
    expect(within(bodyRows(table)[0]!).getByText('기한초과')).toBeVisible()
  })

  it('shows the registered-time status of older actions, which can differ from the current one', async () => {
    const { table } = await openActions(1, '한빛은행 ITDR 도입')
    const rows = bodyRows(table)
    const oldest = rows[rows.length - 1]!
    expect(oldest).toHaveTextContent('POC완료')
    expect(oldest).not.toHaveTextContent('가격협상')
  })
})

describe('Next Action 업데이트 등록 (T-ACTION-02~05)', () => {
  it('opens the form with the previous update as a read-only reference and an empty type', async () => {
    const { user } = await openActions(1, '한빛은행 ITDR 도입')
    await user.click(screen.getByRole('button', { name: 'Next Action 업데이트' }))
    const form = screen.getByRole('form', { name: 'Next Action 업데이트' })
    expect(within(form).getByLabelText('유형')).toHaveDisplayValue('')
    expect(within(form).getByLabelText('Status')).toHaveDisplayValue('가격협상')
    const previous = screen.getByRole('complementary', { name: '이전 Update' })
    expect(previous).toHaveTextContent('최종 가격 협의')
    expect(previous).toHaveTextContent('계약서 초안 검토')
    expect(within(form).getByText(/담당자: 김영업/)).toBeVisible()
  })

  it('fills the progress with the previous next action', async () => {
    const { user } = await openActions(1, '한빛은행 ITDR 도입')
    await user.click(screen.getByRole('button', { name: 'Next Action 업데이트' }))
    await user.click(screen.getByRole('button', { name: '이전 Next Action을 진행사항에 채우기' }))
    expect(screen.getByLabelText('진행사항')).toHaveValue('계약서 초안 검토')
  })

  it('registers an action at the top of the list and refreshes the summary bar', async () => {
    const { user, table } = await openActions(1, '한빛은행 ITDR 도입')
    await user.click(screen.getByRole('button', { name: 'Next Action 업데이트' }))
    const form = screen.getByRole('form', { name: 'Next Action 업데이트' })
    await typeAction(user, form, '미팅')
    await user.type(within(form).getByLabelText('진행사항'), '법무팀 계약 검토 미팅')
    await user.type(within(form).getByLabelText('Next Action'), '날인본 수령')
    await user.type(within(form).getByLabelText('Due Date'), '2026-12-20')
    await user.type(within(form).getByLabelText('Memo'), '법무 의견 반영')
    await user.click(within(form).getByRole('button', { name: '등록' }))
    await waitFor(() => expect(bodyRows(table)[0]).toHaveTextContent('법무팀 계약 검토 미팅'))
    expect(bodyRows(table)[0]).toHaveTextContent('날인본 수령')
    expect(bodyRows(table)[0]).toHaveTextContent('2026-12-20')
    expect(screen.queryByRole('form', { name: 'Next Action 업데이트' })).not.toBeInTheDocument()
    const bar = screen.getByRole('region', { name: 'Deal 정보' })
    expect(within(bar).getByText(/날인본 수령/)).toBeVisible()
    expect(screen.getByText('Action이 등록되었습니다.')).toBeVisible()
  })

  it('shows each missing-field message and focuses the type first (AC-27)', async () => {
    const { user } = await openActions(1, '한빛은행 ITDR 도입')
    await user.click(screen.getByRole('button', { name: 'Next Action 업데이트' }))
    const form = screen.getByRole('form', { name: 'Next Action 업데이트' })
    await user.click(within(form).getByRole('button', { name: '등록' }))
    expect(within(form).getByText('유형을 입력하세요.')).toBeVisible()
    expect(within(form).getByText('진행사항을 입력하세요.')).toBeVisible()
    expect(within(form).getByText('Next Action을 입력하세요.')).toBeVisible()
    expect(within(form).getByText('Due Date를 입력하세요.')).toBeVisible()
    expect(within(form).getByRole('combobox', { name: '유형' })).toHaveFocus()
  })

  it('accepts a past due date', async () => {
    const { user, table } = await openActions(2, '대한제조 MFA 확대')
    await user.click(screen.getByRole('button', { name: 'Next Action 업데이트' }))
    const form = screen.getByRole('form', { name: 'Next Action 업데이트' })
    await typeAction(user, form, '기타')
    await user.type(within(form).getByLabelText('진행사항'), '지난 일정 정리')
    await user.type(within(form).getByLabelText('Next Action'), '후속 확인')
    await user.type(within(form).getByLabelText('Due Date'), '2026-01-05')
    await user.click(within(form).getByRole('button', { name: '등록' }))
    await waitFor(() => expect(bodyRows(table)[0]).toHaveTextContent('지난 일정 정리'))
  })

  it('cancels the form without registering anything', async () => {
    const { user, table } = await openActions(1, '한빛은행 ITDR 도입')
    const before = bodyRows(table).length
    await user.click(screen.getByRole('button', { name: 'Next Action 업데이트' }))
    await user.type(screen.getByLabelText('진행사항'), '버릴 내용')
    await user.click(screen.getByRole('button', { name: '취소' }))
    expect(screen.queryByRole('form', { name: 'Next Action 업데이트' })).not.toBeInTheDocument()
    expect(bodyRows(table)).toHaveLength(before)
  })

  it('stores the status at registration time when the status is changed in the form (sync popup)', async () => {
    const { user, table } = await openActions(1, '한빛은행 ITDR 도입')
    await user.click(screen.getByRole('button', { name: 'Next Action 업데이트' }))
    const form = screen.getByRole('form', { name: 'Next Action 업데이트' })
    await user.selectOptions(within(form).getByLabelText('Status'), '계약완료')
    const dialog = await screen.findByRole('dialog', { name: '매출 확정' })
    await user.clear(within(dialog).getByLabelText('매출금액(단위:천원, 실제 값)'))
    await user.type(within(dialog).getByLabelText('매출금액(단위:천원, 실제 값)'), '1850000')
    await user.clear(within(dialog).getByLabelText('매출일(실제 값)'))
    await user.type(within(dialog).getByLabelText('매출일(실제 값)'), '2026-11-20')
    await user.click(within(dialog).getByRole('button', { name: '확정' }))
    expect(await within(form).findByText(/저장하면 반영됩니다/)).toBeVisible()
    expect(within(form).getByLabelText('Status')).toHaveDisplayValue('계약완료')
    await typeAction(user, form, '계약')
    await user.type(within(form).getByLabelText('진행사항'), '계약 체결')
    await user.type(within(form).getByLabelText('Next Action'), '납품 일정 확인')
    await user.type(within(form).getByLabelText('Due Date'), '2026-12-01')
    await user.click(within(form).getByRole('button', { name: '등록' }))
    await waitFor(() => expect(bodyRows(table)[0]).toHaveTextContent('계약 체결'))
    expect(bodyRows(table)[0]).toHaveTextContent('계약완료')
    expect(bodyRows(table)[0]).toHaveTextContent('Won')
    const bar = screen.getByRole('region', { name: 'Deal 정보' })
    expect(within(bar).getByRole('button', { name: 'Status 수정' })).toHaveTextContent('계약완료')
  })

  it('keeps the status when the sync popup in the form is cancelled', async () => {
    const { user } = await openActions(1, '한빛은행 ITDR 도입')
    await user.click(screen.getByRole('button', { name: 'Next Action 업데이트' }))
    const form = screen.getByRole('form', { name: 'Next Action 업데이트' })
    await user.selectOptions(within(form).getByLabelText('Status'), '계약완료')
    const dialog = await screen.findByRole('dialog', { name: '매출 확정' })
    await user.click(within(dialog).getByRole('button', { name: '취소' }))
    await waitFor(() => expect(screen.queryByRole('dialog')).not.toBeInTheDocument())
    expect(within(form).getByLabelText('Status')).toHaveDisplayValue('가격협상')
    expect(within(form).queryByText(/저장하면 반영됩니다/)).not.toBeInTheDocument()
  })
})

describe('Action 수정·삭제 (T-ACTION-06~07)', () => {
  it('edits an older action, explains it goes to the history, and keeps the registered status', async () => {
    const { user, table } = await openActions(1, '한빛은행 ITDR 도입')
    const row = bodyRows(table)[1]!
    await user.click(within(row).getByRole('button', { name: '수정' }))
    const form = screen.getByRole('form', { name: 'Action 수정' })
    expect(within(form).getByText(/Deal History에 기록됩니다/)).toBeVisible()
    expect(within(form).queryByLabelText('Status')).not.toBeInTheDocument()
    const progress = within(form).getByLabelText('진행사항')
    expect(progress).toHaveValue('임원 보고용 ROI 자료 전달')
    await user.clear(progress)
    await user.type(progress, 'ROI 자료 수정본 전달')
    await user.click(within(form).getByRole('button', { name: '저장' }))
    await waitFor(() => expect(bodyRows(table)[1]).toHaveTextContent('ROI 자료 수정본 전달'))
    expect(screen.getByText('Action이 수정되었습니다.')).toBeVisible()
    await user.click(screen.getByRole('tab', { name: 'Deal History' }))
    const cells = await screen.findAllByRole('cell', { name: 'Action' })
    expect(cells.length).toBeGreaterThan(0)
    expect(screen.getAllByText(/수정: /).length).toBeGreaterThan(0)
  })

  it('shows the validation message when an edit empties a required field', async () => {
    const { user, table } = await openActions(1, '한빛은행 ITDR 도입')
    await user.click(within(bodyRows(table)[0]!).getByRole('button', { name: '수정' }))
    const form = screen.getByRole('form', { name: 'Action 수정' })
    await user.clear(within(form).getByLabelText('Next Action'))
    await user.click(within(form).getByRole('button', { name: '저장' }))
    expect(within(form).getByText('Next Action을 입력하세요.')).toBeVisible()
  })

  it('deletes an action after confirmation and refreshes the next action in the summary bar', async () => {
    const { user, table } = await openActions(1, '한빛은행 ITDR 도입')
    const before = bodyRows(table).length
    await user.click(within(bodyRows(table)[0]!).getByRole('button', { name: '삭제' }))
    const dialog = screen.getByRole('dialog', { name: 'Action 삭제' })
    expect(dialog).toHaveTextContent('Deal History에 기록됩니다')
    await user.click(within(dialog).getByRole('button', { name: '삭제' }))
    await waitFor(() => expect(bodyRows(table)).toHaveLength(before - 1))
    const bar = screen.getByRole('region', { name: 'Deal 정보' })
    await waitFor(() => expect(within(bar).queryByText(/계약서 초안 검토/)).not.toBeInTheDocument())
  })

  it('keeps the action when the delete is cancelled', async () => {
    const { user, table } = await openActions(1, '한빛은행 ITDR 도입')
    const before = bodyRows(table).length
    await user.click(within(bodyRows(table)[0]!).getByRole('button', { name: '삭제' }))
    await user.click(within(screen.getByRole('dialog', { name: 'Action 삭제' })).getByRole('button', { name: '취소' }))
    expect(bodyRows(table)).toHaveLength(before)
  })

  it('shows a viewer the actions without register, edit or delete controls', async () => {
    const { table } = await openActions(1, '한빛은행 ITDR 도입', 'user')
    expect(screen.queryByRole('button', { name: 'Next Action 업데이트' })).not.toBeInTheDocument()
    expect(within(table).queryByRole('button', { name: '수정' })).not.toBeInTheDocument()
    expect(within(table).queryByRole('button', { name: '삭제' })).not.toBeInTheDocument()
    expect(bodyRows(table).length).toBeGreaterThan(1)
  })
})

describe('Actions 검색 (T-ACTION-08~09)', () => {
  async function search() {
    const view = await openActions(1, '한빛은행 ITDR 도입')
    return { ...view, form: screen.getByRole('search', { name: 'Action 검색' }) }
  }

  it('offers the six conditions', async () => {
    const { form } = await search()
    for (const label of ['유형', '담당자', '키워드', '수행일 시작', '수행일 끝', '기한 시작', '기한 끝', '정렬']) {
      expect(within(form).getByLabelText(label)).toBeVisible()
    }
  })

  it('searches by keyword', async () => {
    const { user, form, table } = await search()
    await user.type(within(form).getByLabelText('키워드'), 'ROI')
    await user.click(within(form).getByRole('button', { name: '검색' }))
    await waitFor(() => expect(bodyRows(table)).toHaveLength(1))
    expect(bodyRows(table)[0]).toHaveTextContent('임원 보고용 ROI 자료 전달')
  })

  it('searches by type', async () => {
    const { user, form, table } = await search()
    await within(form).findByRole('option', { name: '이메일' })
    await user.selectOptions(within(form).getByLabelText('유형'), '이메일')
    await user.click(within(form).getByRole('button', { name: '검색' }))
    await waitFor(() => expect(bodyRows(table)[0]).toHaveTextContent('이메일'))
    for (const row of bodyRows(table)) expect(within(row).getAllByText('이메일').length).toBeGreaterThan(0)
  })

  it('searches by actor including resigned users', async () => {
    const { user, form } = await search()
    const actor = within(form).getByLabelText('담당자')
    await waitFor(() => expect(within(actor).getByRole('option', { name: '강퇴사(퇴사)' })).toBeInTheDocument())
    await user.selectOptions(actor, '강퇴사(퇴사)')
    await user.click(within(form).getByRole('button', { name: '검색' }))
    expect(await screen.findByText('조건에 맞는 Action이 없습니다.')).toBeVisible()
  })

  it('sorts by due date soonest first', async () => {
    const { user, form, table } = await search()
    await user.selectOptions(within(form).getByLabelText('정렬'), '기한 임박순')
    await user.click(within(form).getByRole('button', { name: '검색' }))
    await waitFor(() => {
      const dues = bodyRows(table).map((r) => /\d{4}-\d{2}-\d{2}/.exec(within(r).getAllByRole('cell')[6]?.textContent ?? '')?.[0] ?? '')
      expect(dues.length).toBeGreaterThan(1)
      expect([...dues].sort()).toEqual(dues)
    })
  })

  it('filters by a due date range and an acted date range', async () => {
    const { user, form } = await search()
    await user.type(within(form).getByLabelText('기한 시작'), '2100-01-01')
    await user.click(within(form).getByRole('button', { name: '검색' }))
    expect(await screen.findByText('조건에 맞는 Action이 없습니다.')).toBeVisible()
    await user.click(within(form).getByRole('button', { name: '초기화' }))
    expect(await screen.findByRole('table', { name: 'Action 목록' })).toBeVisible()
    await user.type(within(form).getByLabelText('수행일 끝'), '2000-01-01')
    await user.click(within(form).getByRole('button', { name: '검색' }))
    expect(await screen.findByText('조건에 맞는 Action이 없습니다.')).toBeVisible()
  })

  it('shows the reset result with every action again', async () => {
    const { user, form, table } = await search()
    const total = bodyRows(table).length
    await user.type(within(form).getByLabelText('키워드'), 'ROI')
    await user.click(within(form).getByRole('button', { name: '검색' }))
    await waitFor(() => expect(bodyRows(table)).toHaveLength(1))
    await user.click(within(form).getByRole('button', { name: '초기화' }))
    await waitFor(() => expect(bodyRows(table)).toHaveLength(total))
    expect(within(form).getByLabelText('키워드')).toHaveValue('')
  })
})

describe('Action 수정·삭제 버튼 권한 (AC-25, Q8)', () => {
  const EDIT_TITLE = '본인 Action 또는 admin만 수정할 수 있습니다.'
  const DELETE_TITLE = '본인 Action 또는 admin만 삭제할 수 있습니다.'

  async function openAs(userId: string) {
    const view = await renderAt(await detailPath(1), { userId })
    await screen.findByRole('heading', { level: 1, name: '한빛은행 ITDR 도입' })
    const table = await screen.findByRole('table', { name: 'Action 목록' })
    return { ...view, table }
  }

  it('enables edit and delete on every row of the owner who registered them', async () => {
    const { table } = await openAs('u-kim')

    const rows = bodyRows(table)
    expect(rows.length).toBeGreaterThan(1)
    for (const row of rows) {
      expect(within(row).getByRole('button', { name: '수정' })).toBeEnabled()
      expect(within(row).getByRole('button', { name: '삭제' })).toBeEnabled()
      expect(within(row).getByRole('button', { name: '수정' })).not.toHaveAttribute('title')
    }
  })

  it('disables both buttons with the reason as title on actions of another sales', async () => {
    const { table } = await openAs('u-park')

    const rows = bodyRows(table)
    expect(rows.length).toBeGreaterThan(1)
    for (const row of rows) {
      const edit = within(row).getByRole('button', { name: '수정' })
      const remove = within(row).getByRole('button', { name: '삭제' })
      expect(edit).toBeDisabled()
      expect(edit).toHaveAttribute('title', EDIT_TITLE)
      expect(remove).toBeDisabled()
      expect(remove).toHaveAttribute('title', DELETE_TITLE)
    }
  })

  it('still shows the manage column and the register button to that other sales', async () => {
    const { table } = await openAs('u-park')

    expect(within(table).getByRole('columnheader', { name: '관리' })).toBeVisible()
    expect(screen.getByRole('button', { name: 'Next Action 업데이트' })).toBeVisible()
  })

  it('does not open the edit form when a disabled edit button is clicked', async () => {
    const { user, table } = await openAs('u-park')

    await user.click(within(bodyRows(table)[0]!).getByRole('button', { name: '수정' }))

    expect(screen.queryByRole('form', { name: 'Action 수정' })).not.toBeInTheDocument()
  })

  it('enables both buttons on every row for admin, including actions of other users', async () => {
    const { table } = await openAs('u-root')

    for (const row of bodyRows(table)) {
      expect(within(row).getByRole('button', { name: '수정' })).toBeEnabled()
      expect(within(row).getByRole('button', { name: '삭제' })).toBeEnabled()
    }
  })

  it('enables only the rows of the viewer when rows of two different users are mixed', async () => {
    const { user, table } = await openAs('u-park')
    await user.click(screen.getByRole('button', { name: 'Next Action 업데이트' }))
    const form = screen.getByRole('form', { name: 'Next Action 업데이트' })
    await typeAction(user, form, '통화')
    await user.type(within(form).getByLabelText('진행사항'), '박영업 후속 연락')
    await user.type(within(form).getByLabelText('Next Action'), '미팅 일정 확정')
    await user.type(within(form).getByLabelText('Due Date'), '2026-12-20')
    await user.click(within(form).getByRole('button', { name: '등록' }))
    await waitFor(() => expect(bodyRows(table)[0]).toHaveTextContent('박영업 후속 연락'))

    const rows = bodyRows(table)
    expect(within(rows[0]!).getByRole('button', { name: '수정' })).toBeEnabled()
    expect(within(rows[0]!).getByRole('button', { name: '삭제' })).toBeEnabled()
    expect(within(rows[1]!).getByRole('button', { name: '수정' })).toBeDisabled()
    expect(within(rows[1]!).getByRole('button', { name: '삭제' })).toBeDisabled()
  })

  it('shows a user-role viewer no manage column at all', async () => {
    const { table } = await openAs('u-han')

    expect(within(table).queryByRole('columnheader', { name: '관리' })).not.toBeInTheDocument()
    expect(within(table).queryByRole('button', { name: '수정' })).not.toBeInTheDocument()
    expect(within(table).queryByRole('button', { name: '삭제' })).not.toBeInTheDocument()
  })
})
