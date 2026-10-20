import { fireEvent, screen, waitFor, within } from '@testing-library/react'
import { describe, expect, it } from 'vitest'
import { defaultMock } from '../../../test/fake/default'
import { dealCodeOf, detailPath } from '../../../test/detailTestUtils'
import { renderAt } from '../../../test/mockApp'

type View = Awaited<ReturnType<typeof renderAt>>

async function openActions(role: 'sales' | 'admin' | 'user' = 'sales', userId?: string) {
  const view = await renderAt(await detailPath(1), userId ? { userId } : { role })
  await screen.findByRole('heading', { level: 1, name: '한빛은행 ITDR 도입' })
  const table = await screen.findByRole('table', { name: 'Action 목록' })
  return { ...view, table }
}

const bodyRows = (table: HTMLElement) => within(table).getAllByRole('row').slice(1)

async function openForm(user: View['user']) {
  await user.click(screen.getByRole('button', { name: 'Next Action 업데이트' }))
  return screen.getByRole('form', { name: 'Next Action 업데이트' })
}

async function register(user: View['user'], form: HTMLElement, fill: { progress?: string; next?: string; due?: string }) {
  await user.type(within(form).getByLabelText('유형'), '미팅')
  if (fill.progress) await user.type(within(form).getByLabelText('진행사항'), fill.progress)
  if (fill.next) await user.type(within(form).getByLabelText('Next Action'), fill.next)
  if (fill.due) await user.type(within(form).getByLabelText('Due Date'), fill.due)
  await user.click(within(form).getByRole('button', { name: '등록' }))
}

describe('Action 폼: 진행사항·Next Action 분리 입력 (AC-20)', () => {
  it('saves a progress-only action and shows dashes for the empty Next Action and Due Date', async () => {
    const { user, table } = await openActions()
    const before = bodyRows(table).length

    await register(user, await openForm(user), { progress: '전화로만 확인' })

    await waitFor(() => expect(bodyRows(table)).toHaveLength(before + 1))
    const first = bodyRows(table)[0]!
    expect(first).toHaveTextContent('전화로만 확인')
    expect(within(first).getAllByText('—').length).toBeGreaterThanOrEqual(2)
    expect(within(first).queryByRole('button', { name: '종료(수행)' })).not.toBeInTheDocument()
  })

  it('saves a Next-Action-only action as Open with a dash for the progress', async () => {
    const { user, table } = await openActions()
    const before = bodyRows(table).length

    await register(user, await openForm(user), { next: '견적 회신 받기', due: '2026-12-20' })

    await waitFor(() => expect(bodyRows(table)).toHaveLength(before + 1))
    const first = bodyRows(table)[0]!
    expect(first).toHaveTextContent('견적 회신 받기')
    expect(first).toHaveTextContent('Open')
    expect(within(first).getAllByText('—').length).toBeGreaterThanOrEqual(1)
  })

  it('asks for progress or Next Action when both are empty and saves nothing', async () => {
    const { user, table } = await openActions()
    const before = bodyRows(table).length

    await register(user, await openForm(user), {})

    expect(await screen.findByText('진행사항 또는 Next Action을 입력하세요.')).toBeVisible()
    expect(bodyRows(table)).toHaveLength(before)
  })

  it('requires the Due Date only when there is a Next Action', async () => {
    const { user } = await openActions()

    await register(user, await openForm(user), { next: '다음 할 일' })

    expect(await screen.findByText('Due Date를 입력하세요.')).toBeVisible()
  })

  it('does not ask for the Due Date of a progress-only action', async () => {
    const { user } = await openActions()

    await register(user, await openForm(user), { progress: '진행만' })

    await waitFor(() => expect(screen.queryByText('Due Date를 입력하세요.')).not.toBeInTheDocument())
    expect(screen.queryByText('진행사항 또는 Next Action을 입력하세요.')).not.toBeInTheDocument()
  })

  it('clears the Due Date input when the Next Action is erased', async () => {
    const { user } = await openActions()
    const form = await openForm(user)
    await user.type(within(form).getByLabelText('Next Action'), '지울 계획')
    await user.type(within(form).getByLabelText('Due Date'), '2026-12-20')

    await user.clear(within(form).getByLabelText('Next Action'))

    expect(within(form).getByLabelText('Due Date')).toHaveValue('')
  })
})

describe('Action 표: 상태 열과 상태 버튼 (AC-21)', () => {
  it('shows Open and both close buttons to the author on an Open Next Action', async () => {
    const { table } = await openActions()
    const first = bodyRows(table)[0]!

    expect(first).toHaveTextContent('Open')
    expect(within(first).getByRole('button', { name: '종료(수행)' })).toBeVisible()
    expect(within(first).getByRole('button', { name: '종료(미수행)' })).toBeVisible()
  })

  it('shows the buttons to admin but not to another sales or the read-only user', async () => {
    const admin = await openActions('admin')
    expect(within(bodyRows(admin.table)[0]!).getByRole('button', { name: '종료(수행)' })).toBeVisible()
    admin.unmount()

    const park = await openActions('sales', 'u-park')
    expect(within(bodyRows(park.table)[0]!).queryByRole('button', { name: '종료(수행)' })).not.toBeInTheDocument()
    expect(bodyRows(park.table)[0]).toHaveTextContent('Open')
    park.unmount()

    const viewer = await openActions('user')
    expect(within(bodyRows(viewer.table)[0]!).queryByRole('button', { name: '종료(수행)' })).not.toBeInTheDocument()
  })
})

describe('Next Action 종료 팝업 (AC-22)', () => {
  it('opens a memo dialog for done and closes with the typed memo appended', async () => {
    const { user, table } = await openActions()
    await user.click(within(bodyRows(table)[0]!).getByRole('button', { name: '종료(수행)' }))

    const dialog = await screen.findByRole('dialog', { name: 'Next Action 종료(수행)' })
    await user.type(within(dialog).getByLabelText('Memo에 남길 내용(선택)'), '문서 전달 완료')
    await user.click(within(dialog).getByRole('button', { name: '종료' }))

    await waitFor(() => expect(screen.queryByRole('dialog')).not.toBeInTheDocument())
    await waitFor(() => expect(bodyRows(table)[0]).toHaveTextContent('종료(수행)'))
    expect(bodyRows(table)[0]).toHaveTextContent('문서 전달 완료')
    expect(within(bodyRows(table)[0]!).getByRole('button', { name: 'Open으로' })).toBeVisible()
  })

  it('uses the not-done title and allows closing with an empty memo', async () => {
    const { user, table } = await openActions()
    await user.click(within(bodyRows(table)[0]!).getByRole('button', { name: '종료(미수행)' }))

    const dialog = await screen.findByRole('dialog', { name: 'Next Action 종료(미수행)' })
    await user.click(within(dialog).getByRole('button', { name: '종료' }))

    await waitFor(() => expect(bodyRows(table)[0]).toHaveTextContent('종료(미수행)'))
  })

  it('leaves the status unchanged on cancel', async () => {
    const { user, table } = await openActions()
    await user.click(within(bodyRows(table)[0]!).getByRole('button', { name: '종료(수행)' }))
    const dialog = await screen.findByRole('dialog', { name: 'Next Action 종료(수행)' })
    await user.type(within(dialog).getByLabelText('Memo에 남길 내용(선택)'), '버릴 메모')

    await user.click(within(dialog).getByRole('button', { name: '취소' }))

    await waitFor(() => expect(screen.queryByRole('dialog')).not.toBeInTheDocument())
    expect(bodyRows(table)[0]).toHaveTextContent('Open')
    expect(bodyRows(table)[0]).not.toHaveTextContent('버릴 메모')
  })

  it('leaves the status unchanged on Escape', async () => {
    const { user, table } = await openActions()
    await user.click(within(bodyRows(table)[0]!).getByRole('button', { name: '종료(수행)' }))
    await screen.findByRole('dialog', { name: 'Next Action 종료(수행)' })

    fireEvent.keyDown(screen.getByRole('dialog'), { key: 'Escape' })

    await waitFor(() => expect(screen.queryByRole('dialog')).not.toBeInTheDocument())
    expect(bodyRows(table)[0]).toHaveTextContent('Open')
  })

  it('reopens a closed Next Action without a dialog', async () => {
    const { user, table } = await openActions()
    await user.click(within(bodyRows(table)[0]!).getByRole('button', { name: '종료(수행)' }))
    await user.click(within(await screen.findByRole('dialog')).getByRole('button', { name: '종료' }))
    await waitFor(() => expect(bodyRows(table)[0]).toHaveTextContent('종료(수행)'))

    await user.click(within(bodyRows(table)[0]!).getByRole('button', { name: 'Open으로' }))

    await waitFor(() => expect(bodyRows(table)[0]).toHaveTextContent('Open'))
    expect(screen.queryByRole('dialog')).not.toBeInTheDocument()
  })
})

describe('Action 검색: Next Action 상태 필터 (AC-24)', () => {
  it('offers the five choices', async () => {
    await openActions()

    const select = screen.getByLabelText('Next Action 상태')

    expect(within(select).getAllByRole('option').map((o) => o.textContent)).toEqual([
      '전체',
      'Open',
      '종료(수행)',
      '종료(미수행)',
      '종료(전체)',
    ])
  })

  it('lists only Open actions for Open and none for closed when everything is open', async () => {
    const { user, table } = await openActions()
    await user.selectOptions(screen.getByLabelText('Next Action 상태'), 'Open')
    await user.click(screen.getByRole('button', { name: '검색' }))
    await waitFor(() => expect(bodyRows(table).length).toBeGreaterThan(0))

    await user.selectOptions(screen.getByLabelText('Next Action 상태'), '종료(전체)')
    await user.click(screen.getByRole('button', { name: '검색' }))

    expect(await screen.findByText('조건에 맞는 Action이 없습니다.')).toBeVisible()
  })
})

describe('Deal 상세 요약의 Next Action 상태 (AC-23)', () => {
  it('shows the status label of the basis Next Action and follows a close', async () => {
    const { user, table } = await openActions()
    const count = () => screen.getAllByText(/종료\(수행\)/).length
    expect(screen.getAllByText('Open').length).toBeGreaterThanOrEqual(2) // 표 + 요약

    await user.click(within(bodyRows(table)[0]!).getByRole('button', { name: '종료(수행)' }))
    await user.click(within(await screen.findByRole('dialog')).getByRole('button', { name: '종료' }))

    await waitFor(() => expect(count()).toBeGreaterThanOrEqual(2))
  })
})

describe('Next Action 종료 실패 (리뷰 Minor 1)', () => {
  it('keeps the dialog open with the typed memo and shows the error when the server refuses (409)', async () => {
    const { user, table } = await openActions()
    await user.click(within(bodyRows(table)[0]!).getByRole('button', { name: '종료(수행)' }))
    const dialog = await screen.findByRole('dialog', { name: 'Next Action 종료(수행)' })
    await user.type(within(dialog).getByLabelText('Memo에 남길 내용(선택)'), '잃으면 안 되는 메모')
    // 팝업이 열려 있는 동안 다른 경로에서 이미 같은 상태로 종료됐다(서버는 409 "이미 종료(수행) 상태입니다.").
    const [first] = await defaultMock.gateway.actions.list(await dealCodeOf(1), {})
    await defaultMock.gateway.actions.changeNextActionStatus(first!.id, { status: 'done', memo: '' })

    await user.click(within(dialog).getByRole('button', { name: '종료' }))

    expect(await screen.findByText(/이미 종료\(수행\) 상태입니다\./)).toBeVisible()
    expect(screen.getByRole('dialog', { name: 'Next Action 종료(수행)' })).toBeVisible()
    expect(within(screen.getByRole('dialog')).getByLabelText('Memo에 남길 내용(선택)')).toHaveValue('잃으면 안 되는 메모')
  })

  it('closes the dialog only after a successful change', async () => {
    const { user, table } = await openActions()
    await user.click(within(bodyRows(table)[0]!).getByRole('button', { name: '종료(수행)' }))
    await user.click(within(await screen.findByRole('dialog')).getByRole('button', { name: '종료' }))

    await waitFor(() => expect(screen.queryByRole('dialog')).not.toBeInTheDocument())
  })
})

describe('종료 상태 간 직접 전환 (사용자 결정 2026-10-20)', () => {
  async function closeFirst(user: View['user'], table: HTMLElement, label: '종료(수행)' | '종료(미수행)') {
    await user.click(within(bodyRows(table)[0]!).getByRole('button', { name: label }))
    await user.click(within(await screen.findByRole('dialog')).getByRole('button', { name: '종료' }))
    await waitFor(() => expect(screen.queryByRole('dialog')).not.toBeInTheDocument())
  }

  it('offers the other closed status and "Open으로" on a done row, not the done button', async () => {
    const { user, table } = await openActions()
    await closeFirst(user, table, '종료(수행)')

    const row = bodyRows(table)[0]!
    await waitFor(() => expect(within(row).getByRole('button', { name: 'Open으로' })).toBeVisible())

    expect(within(row).getByRole('button', { name: '종료(미수행)' })).toBeVisible()
    expect(within(row).queryByRole('button', { name: '종료(수행)' })).not.toBeInTheDocument()
  })

  it('offers 종료(수행) and "Open으로" on a not-done row, not the not-done button', async () => {
    const { user, table } = await openActions()
    await closeFirst(user, table, '종료(미수행)')

    const row = bodyRows(table)[0]!
    await waitFor(() => expect(within(row).getByRole('button', { name: 'Open으로' })).toBeVisible())

    expect(within(row).getByRole('button', { name: '종료(수행)' })).toBeVisible()
    expect(within(row).queryByRole('button', { name: '종료(미수행)' })).not.toBeInTheDocument()
  })

  it('switches done to not-done through the memo dialog and appends the memo', async () => {
    const { user, table } = await openActions()
    await closeFirst(user, table, '종료(수행)')
    await user.click(await within(bodyRows(table)[0]!).findByRole('button', { name: '종료(미수행)' }))

    const dialog = await screen.findByRole('dialog', { name: 'Next Action 종료(미수행)' })
    await user.type(within(dialog).getByLabelText('Memo에 남길 내용(선택)'), '사실은 못 했음')
    await user.click(within(dialog).getByRole('button', { name: '종료' }))

    await waitFor(() => expect(bodyRows(table)[0]).toHaveTextContent('종료(미수행)'))
    expect(bodyRows(table)[0]).toHaveTextContent('사실은 못 했음')
    expect(screen.queryByRole('dialog')).not.toBeInTheDocument()
  })

  it('switches not-done to done through the memo dialog', async () => {
    const { user, table } = await openActions()
    await closeFirst(user, table, '종료(미수행)')
    await user.click(await within(bodyRows(table)[0]!).findByRole('button', { name: '종료(수행)' }))

    const dialog = await screen.findByRole('dialog', { name: 'Next Action 종료(수행)' })
    await user.click(within(dialog).getByRole('button', { name: '종료' }))

    await waitFor(() => expect(within(bodyRows(table)[0]!).getByRole('button', { name: '종료(미수행)' })).toBeVisible())
    expect(bodyRows(table)[0]).toHaveTextContent('종료(수행)')
  })

  it('leaves the closed status on cancel and on Escape', async () => {
    const { user, table } = await openActions()
    await closeFirst(user, table, '종료(수행)')
    await user.click(await within(bodyRows(table)[0]!).findByRole('button', { name: '종료(미수행)' }))
    await user.click(within(await screen.findByRole('dialog')).getByRole('button', { name: '취소' }))
    await waitFor(() => expect(screen.queryByRole('dialog')).not.toBeInTheDocument())
    expect(within(bodyRows(table)[0]!).getByRole('button', { name: '종료(미수행)' })).toBeVisible()

    await user.click(within(bodyRows(table)[0]!).getByRole('button', { name: '종료(미수행)' }))
    fireEvent.keyDown(await screen.findByRole('dialog'), { key: 'Escape' })

    await waitFor(() => expect(screen.queryByRole('dialog')).not.toBeInTheDocument())
    expect(within(bodyRows(table)[0]!).queryByRole('button', { name: '종료(수행)' })).not.toBeInTheDocument()
  })

  it('does not show switch buttons on a closed row to another sales', async () => {
    const path = await detailPath(1)
    const park = await openActions('sales', 'u-park')
    const { gateway } = defaultMock
    const [first] = await gateway.actions.list(await dealCodeOf(1), {})
    await gateway.auth.quickLogin('u-kim')
    await gateway.actions.changeNextActionStatus(first!.id, { status: 'done', memo: '' })
    await gateway.auth.quickLogin('u-park')
    park.goTo('/deals')
    await screen.findByRole('heading', { name: /Deals/ })
    park.goTo(path)

    const table = await screen.findByRole('table', { name: 'Action 목록' })
    await waitFor(() => expect(bodyRows(table)[0]).toHaveTextContent('종료(수행)'))

    const row = bodyRows(table)[0]!
    expect(within(row).queryByRole('button', { name: '종료(미수행)' })).not.toBeInTheDocument()
    expect(within(row).queryByRole('button', { name: 'Open으로' })).not.toBeInTheDocument()
  })
})
