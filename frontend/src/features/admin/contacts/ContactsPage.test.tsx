import { screen, waitFor, within } from '@testing-library/react'
import { afterEach, describe, expect, it, vi } from 'vitest'
import { gateway } from '../../../gateway'
import { renderAt } from '../../../test/mockApp'

afterEach(() => vi.restoreAllMocks())

/** 게이트웨이가 실제로 던지는 ApiError 하나(로그아웃 상태의 me() → 401). 로그인 전에 얻는다. */
async function serverError(): Promise<unknown> {
  await gateway.auth.logout()
  return gateway.auth.me().catch((e: unknown) => e)
}

type Rendered = Awaited<ReturnType<typeof renderAt>>

async function openContacts() {
  const view = await renderAt('/admin/contacts', { role: 'admin' })
  await screen.findAllByRole('row', { name: /한빛은행/ })
  return view
}

function bodyRows() {
  return screen.getAllByRole('row').slice(1)
}

function rowOf(company: string, name: string) {
  return within(screen.getByRole('row', { name: new RegExp(`${company}.*${name}`) }))
}

async function search(user: Rendered['user'], keyword: string) {
  const box = screen.getByLabelText('검색어')
  await user.clear(box)
  await user.type(box, keyword)
  await user.click(screen.getByRole('button', { name: '검색' }))
}

async function fill(user: Rendered['user'], values: Partial<Record<'회사명' | '담당자명' | '직급' | '이메일' | '전화', string>>) {
  for (const [label, value] of Object.entries(values)) {
    const input = screen.getByLabelText(label)
    await user.clear(input)
    if (value) await user.type(input, value)
  }
}

describe('contacts 목록 (T-ADMIN-07)', () => {
  it('lists the first page with company, name, title, email, phone and linked deal count', async () => {
    await openContacts()

    for (const header of ['구분', '회사명', '담당자명', '직급', '이메일', '전화', '연결 Deal']) {
      expect(screen.getByRole('columnheader', { name: header })).toBeInTheDocument()
    }
    expect(bodyRows()).toHaveLength(20)
    const row = rowOf('한빛은행', '정민수')
    expect(row.getByText('과장')).toBeInTheDocument()
    expect(row.getByText(/@hanbit\.test$/)).toBeInTheDocument()
    expect(row.getByText('1')).toBeInTheDocument()
  })

  it('pages through all 24 contacts', async () => {
    const { user } = await openContacts()

    await user.click(screen.getByRole('button', { name: '다음' }))

    await waitFor(() => expect(bodyRows()).toHaveLength(4))
    expect(screen.getByRole('button', { name: '다음' })).toBeDisabled()
  })

  it('filters by kind', async () => {
    const { user } = await openContacts()

    await user.selectOptions(screen.getByLabelText('구분'), '파트너')

    await screen.findAllByRole('row', { name: /에이원시스템/ })
    await waitFor(() => expect(bodyRows()).toHaveLength(7))
    expect(screen.queryByRole('row', { name: /한빛은행/ })).not.toBeInTheDocument()
    expect(screen.getAllByText('파트너', { selector: 'td .badge' })).toHaveLength(7)
  })

  it('searches by keyword from the first page, also with Enter', async () => {
    const { user } = await openContacts()
    await user.click(screen.getByRole('button', { name: '다음' }))

    await user.clear(screen.getByLabelText('검색어'))
    await user.type(screen.getByLabelText('검색어'), '한빛{Enter}')

    await waitFor(() => expect(bodyRows()).toHaveLength(3))
    expect(screen.getByRole('row', { name: /임태호/ })).toBeInTheDocument()
  })

  it('shows the full list again when the keyword is emptied', async () => {
    const { user } = await openContacts()
    await search(user, '한빛')
    await waitFor(() => expect(bodyRows()).toHaveLength(3))

    await user.clear(screen.getByLabelText('검색어'))
    await user.click(screen.getByRole('button', { name: '검색' }))

    await waitFor(() => expect(bodyRows()).toHaveLength(20))
  })

  it('searches by email too', async () => {
    const { user } = await openContacts()

    await search(user, 'bae1@nuri')

    await waitFor(() => expect(bodyRows()).toHaveLength(1))
    expect(screen.getByRole('row', { name: /배성훈/ })).toBeInTheDocument()
  })

  it('shows an empty search message when nothing matches', async () => {
    const { user } = await openContacts()

    await search(user, '없는회사')

    expect(await screen.findByText('조건에 맞는 연락처가 없습니다.')).toBeInTheDocument()
  })

  it('shows the empty message without conditions when there are no contacts', async () => {
    vi.spyOn(gateway.contacts, 'list').mockResolvedValue({ items: [], total: 0, offset: 0, limit: 20 })
    await renderAt('/admin/contacts', { role: 'admin' })

    expect(await screen.findByText('등록된 연락처가 없습니다.')).toBeInTheDocument()
  })

  it('shows the message when the list cannot be loaded', async () => {
    vi.spyOn(gateway.contacts, 'list').mockRejectedValue(await serverError())
    await renderAt('/admin/contacts', { role: 'admin' })

    expect(await screen.findByRole('alert')).toHaveTextContent('로그인이 필요합니다.')
  })
})

describe('contacts 등록 (T-ADMIN-08)', () => {
  async function openCreate(user: Rendered['user']) {
    await user.click(screen.getByRole('button', { name: '연락처 등록' }))
    return screen.findByRole('form', { name: '연락처 등록' })
  }

  it('creates a customer contact without an email', async () => {
    const { user } = await openContacts()
    await openCreate(user)

    await user.selectOptions(screen.getByLabelText('연락처 구분'), '고객')
    await fill(user, { 회사명: '새솔물산', 담당자명: '홍길동', 직급: '대리' })
    await user.click(screen.getByRole('button', { name: '저장' }))

    await waitFor(() => expect(screen.queryByRole('form', { name: '연락처 등록' })).not.toBeInTheDocument())
    await search(user, '새솔물산')
    const row = within(await screen.findByRole('row', { name: /새솔물산/ }))
    expect(row.getByText('홍길동')).toBeInTheDocument()
    expect(row.getByText('0')).toBeInTheDocument()
  })

  it('creates a partner contact', async () => {
    const { user } = await openContacts()
    await openCreate(user)

    await user.selectOptions(screen.getByLabelText('연락처 구분'), '파트너')
    await fill(user, { 회사명: '새파트너', 담당자명: '김파트', 이메일: 'p@newpartner.test', 전화: '02-1234-5678' })
    await user.click(screen.getByRole('button', { name: '저장' }))

    await user.selectOptions(screen.getByLabelText('구분'), '파트너')
    expect(await screen.findByRole('row', { name: /새파트너/ })).toBeInTheDocument()
  })

  it('removes whitespace while typing and tells the user', async () => {
    const { user } = await openContacts()
    await openCreate(user)

    await user.type(screen.getByLabelText('회사명'), '새 솔 물산')

    expect(screen.getByLabelText('회사명')).toHaveValue('새솔물산')
    expect(screen.getByText('공백은 입력할 수 없습니다.')).toBeInTheDocument()
  })

  it('shows required messages and does not send a request when empty', async () => {
    const { user } = await openContacts()
    await openCreate(user)
    const create = vi.spyOn(gateway.contacts, 'create')

    await user.click(screen.getByRole('button', { name: '저장' }))

    expect(screen.getByText('회사명을 입력하세요.')).toBeInTheDocument()
    expect(screen.getByText('담당자명을 입력하세요.')).toBeInTheDocument()
    expect(create).not.toHaveBeenCalled()
  })

  it('shows the email format message', async () => {
    const { user } = await openContacts()
    await openCreate(user)

    await fill(user, { 회사명: '새솔물산', 담당자명: '홍길동', 이메일: 'nope' })
    await user.click(screen.getByRole('button', { name: '저장' }))

    expect(screen.getByText('이메일 형식이 올바르지 않습니다.')).toBeInTheDocument()
  })

  it('shows the server message for a contact that already exists', async () => {
    const { user } = await openContacts()
    await openCreate(user)

    await fill(user, { 회사명: '미래전자', 담당자명: '권나연' })
    await user.click(screen.getByRole('button', { name: '저장' }))

    expect(await screen.findByRole('alert')).toHaveTextContent('이미 등록된 연락처입니다.')
    expect(screen.getByRole('form', { name: '연락처 등록' })).toBeInTheDocument()
  })

  it('closes the form with cancel', async () => {
    const { user } = await openContacts()
    await openCreate(user)

    await user.click(screen.getByRole('button', { name: '취소' }))

    expect(screen.queryByRole('form', { name: '연락처 등록' })).not.toBeInTheDocument()
  })
})

describe('contacts 수정 (T-ADMIN-09)', () => {
  it('tells how many deals will reflect the change and saves it', async () => {
    const { user } = await openContacts()

    await user.click(rowOf('한빛은행', '정민수').getByRole('button', { name: '수정' }))

    const form = await screen.findByRole('form', { name: '연락처 수정' })
    expect(within(form).getByText('이 연락처를 쓰는 1개 Deal에 모두 반영됩니다.')).toBeInTheDocument()
    expect(screen.getByLabelText('회사명')).toHaveValue('한빛은행')
    expect(screen.getByLabelText('담당자명')).toHaveValue('정민수')
    await fill(user, { 직급: '부장' })
    await user.click(screen.getByRole('button', { name: '저장' }))

    await waitFor(() => expect(screen.queryByRole('form', { name: '연락처 수정' })).not.toBeInTheDocument())
    expect(await within(await screen.findByRole('row', { name: /정민수/ })).findByText('부장')).toBeInTheDocument()
  })

  it('does not show the sharing notice when no deal uses the contact', async () => {
    const { user } = await openContacts()
    await user.click(screen.getByRole('button', { name: '연락처 등록' }))
    await fill(user, { 회사명: '새솔물산', 담당자명: '홍길동' })
    await user.click(screen.getByRole('button', { name: '저장' }))
    await search(user, '새솔물산')

    await user.click(within(await screen.findByRole('row', { name: /새솔물산/ })).getByRole('button', { name: '수정' }))

    await screen.findByRole('form', { name: '연락처 수정' })
    expect(screen.queryByText(/Deal에 모두 반영됩니다/)).not.toBeInTheDocument()
  })

  it('blocks whitespace on edit too', async () => {
    const { user } = await openContacts()
    await user.click(rowOf('한빛은행', '정민수').getByRole('button', { name: '수정' }))
    await screen.findByRole('form', { name: '연락처 수정' })

    await fill(user, { 담당자명: '정 민 수' })

    expect(screen.getByLabelText('담당자명')).toHaveValue('정민수')
    expect(screen.getByText('공백은 입력할 수 없습니다.')).toBeInTheDocument()
  })
})

describe('contacts 삭제 (T-ADMIN-10)', () => {
  async function createAndFind(user: Rendered['user']) {
    await user.click(screen.getByRole('button', { name: '연락처 등록' }))
    await fill(user, { 회사명: '새솔물산', 담당자명: '홍길동' })
    await user.click(screen.getByRole('button', { name: '저장' }))
    await search(user, '새솔물산')
    return screen.findByRole('row', { name: /새솔물산/ })
  }

  it('refuses to delete a contact that deals use and says how many', async () => {
    const { user } = await openContacts()

    await user.click(rowOf('한빛은행', '정민수').getByRole('button', { name: '삭제' }))
    await user.click(within(await screen.findByRole('dialog', { name: '연락처 삭제' })).getByRole('button', { name: '삭제' }))

    expect(await screen.findByRole('alert')).toHaveTextContent('연결된 Deal이 1건 있어 삭제할 수 없습니다.')
    expect(screen.queryByRole('dialog')).not.toBeInTheDocument()
    expect(screen.getByRole('row', { name: /정민수/ })).toBeInTheDocument()
  })

  it('deletes a contact nobody uses after confirmation', async () => {
    const { user } = await openContacts()
    const created = await createAndFind(user)

    await user.click(within(created).getByRole('button', { name: '삭제' }))
    await user.click(within(await screen.findByRole('dialog')).getByRole('button', { name: '삭제' }))

    await waitFor(() => expect(screen.queryByRole('row', { name: /새솔물산/ })).not.toBeInTheDocument())
  })

  it('does nothing when the confirmation is declined', async () => {
    const { user } = await openContacts()
    const created = await createAndFind(user)
    const remove = vi.spyOn(gateway.contacts, 'remove')

    await user.click(within(created).getByRole('button', { name: '삭제' }))
    await user.click(within(await screen.findByRole('dialog')).getByRole('button', { name: '취소' }))

    expect(remove).not.toHaveBeenCalled()
    expect(screen.getByRole('row', { name: /새솔물산/ })).toBeInTheDocument()
  })
})
