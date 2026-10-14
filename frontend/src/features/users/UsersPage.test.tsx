import { screen, waitFor, within } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { afterEach, describe, expect, it, vi } from 'vitest'
import { formatDateTime } from '../../shared/format'
import { ME_ADMIN, RESIGNED_ROW, USER_ROWS, userRef, type UserRow } from '../../test/authFixtures'
import { mockApi, problem, renderApp } from '../../test/utils'
import { UsersPage } from './UsersPage'

type Row = UserRow
const page = (items: Row[]) => ({ body: { items, offset: 0, limit: 50 } })
const ROOT = USER_ROWS[0] as Row
const KIM = USER_ROWS[1] as Row
const NEW_USER: Row = {
  id: 'u-3',
  login_id: 'lee',
  role: 'user',
  display_name: null,
  email: null,
  created_at: '2026-03-01T00:00:00Z',
  created_by: userRef('u-1', '최관리'),
  last_login_at: null,
  status: 'active',
  deleted_at: null,
  delete_reason: null,
}

afterEach(() => vi.restoreAllMocks())

const rowOf = (loginId: string) => screen.getByRole('row', { name: new RegExp(`^${loginId} `) })

describe('UsersPage list (UI-7)', () => {
  it('lists id, role, name, created, creator and last login', async () => {
    mockApi({ 'GET /api/v1/users': page(USER_ROWS), 'GET /api/v1/auth/me': { body: ME_ADMIN } })

    renderApp(<UsersPage />)

    await screen.findByText('kim')
    const headers = screen.getAllByRole('columnheader').map((h) => h.textContent)
    for (const name of ['아이디', '역할', '이름', '등록일', '등록자', '마지막 로그인']) {
      expect(headers).toContain(name)
    }
    const root = rowOf('root')
    for (const text of ['admin', '최관리', '설정관리', formatDateTime(ROOT.created_at), formatDateTime(ROOT.last_login_at as string)]) {
      expect(root).toHaveTextContent(text)
    }
    expect(rowOf('kim')).toHaveTextContent('sales')
    expect(rowOf('kim')).toHaveTextContent('김영업')
  })

  it('has no password column or password field anywhere', async () => {
    mockApi({ 'GET /api/v1/users': page(USER_ROWS), 'GET /api/v1/auth/me': { body: ME_ADMIN } })

    renderApp(<UsersPage />)

    await screen.findByText('kim')
    expect(screen.queryByLabelText(/비밀번호/)).not.toBeInTheDocument()
    expect(screen.queryByRole('columnheader', { name: /비밀번호/ })).not.toBeInTheDocument()
  })

  it('has no edit button on any row', async () => {
    mockApi({ 'GET /api/v1/users': page(USER_ROWS), 'GET /api/v1/auth/me': { body: ME_ADMIN } })

    renderApp(<UsersPage />)

    await screen.findByText('kim')
    expect(screen.queryByRole('button', { name: '수정' })).not.toBeInTheDocument()
  })

  it('shows the empty message when there are no users', async () => {
    mockApi({ 'GET /api/v1/users': page([]), 'GET /api/v1/auth/me': { body: ME_ADMIN } })

    renderApp(<UsersPage />)

    expect(await screen.findByText('등록된 사용자가 없습니다.')).toBeInTheDocument()
  })

  it('shows the server message when the list cannot be loaded', async () => {
    mockApi({ 'GET /api/v1/users': problem(403, 'forbidden', '이 작업을 수행할 권한이 없습니다'), 'GET /api/v1/auth/me': { body: ME_ADMIN } })

    renderApp(<UsersPage />)

    expect(await screen.findByRole('alert')).toHaveTextContent('이 작업을 수행할 권한이 없습니다')
  })
})

describe('UsersPage add (UI-7)', () => {
  it('registers an AD id with the chosen role and refreshes the list', async () => {
    let users = [ROOT, KIM]
    const requests = mockApi({
      'GET /api/v1/auth/me': { body: ME_ADMIN },
      'GET /api/v1/users': () => page(users),
      'POST /api/v1/users': () => {
        users = [...users, NEW_USER]
        return { status: 201, body: NEW_USER }
      },
    })
    renderApp(<UsersPage />)
    await screen.findByText('kim')
    const roles = Array.from(screen.getByLabelText('역할').querySelectorAll('option')).map((o) => o.value)
    expect(roles.sort()).toEqual(['admin', 'sales', 'user'])

    await userEvent.type(screen.getByLabelText('AD 아이디'), 'lee')
    await userEvent.selectOptions(screen.getByLabelText('역할'), 'user')
    await userEvent.click(screen.getByRole('button', { name: '추가' }))

    expect(await screen.findByRole('row', { name: /^lee / })).toBeInTheDocument()
    const post = requests.find((r) => r.method === 'POST')
    expect(post?.path).toBe('/api/v1/users')
    expect(post?.body).toEqual({ login_id: 'lee', role: 'user' })
    expect(post?.headers.get('x-requested-with')).toBe('neoine-web')
    expect(screen.getByLabelText('AD 아이디')).toHaveValue('')
  })

  it('shows the server message and keeps the input when the id already exists', async () => {
    mockApi({
      'GET /api/v1/auth/me': { body: ME_ADMIN },
      'GET /api/v1/users': page(USER_ROWS),
      'POST /api/v1/users': problem(409, 'already-exists', '이미 등록된 사용자입니다: kim'),
    })
    renderApp(<UsersPage />)
    await screen.findByText('kim')

    await userEvent.type(screen.getByLabelText('AD 아이디'), 'kim')
    await userEvent.click(screen.getByRole('button', { name: '추가' }))

    expect(await screen.findByRole('alert')).toHaveTextContent('이미 등록된 사용자입니다: kim')
    expect(screen.getByLabelText('AD 아이디')).toHaveValue('kim')
  })

  it('does not send an empty id', async () => {
    const requests = mockApi({ 'GET /api/v1/auth/me': { body: ME_ADMIN }, 'GET /api/v1/users': page(USER_ROWS) })
    renderApp(<UsersPage />)
    await screen.findByText('kim')

    await userEvent.click(screen.getByRole('button', { name: '추가' }))

    expect(requests.some((r) => r.method === 'POST')).toBe(false)
  })
})

describe('UsersPage delete (UI-7)', () => {
  it('deletes after confirmation and refreshes the list at once', async () => {
    let users = [ROOT, KIM]
    const requests = mockApi({
      'GET /api/v1/auth/me': { body: ME_ADMIN },
      'GET /api/v1/users': () => page(users),
      'DELETE /api/v1/users/u-2': () => {
        users = [ROOT]
        return { body: { outcome: 'deleted' } }
      },
    })
    const confirm = vi.spyOn(window, 'confirm').mockReturnValue(true)
    renderApp(<UsersPage />)
    await screen.findByText('kim')

    await userEvent.click(within(rowOf('kim')).getByRole('button', { name: '삭제' }))

    await waitFor(() => expect(screen.queryByRole('row', { name: /^kim / })).not.toBeInTheDocument())
    expect(confirm).toHaveBeenCalledWith(expect.stringContaining('kim'))
    expect(confirm).toHaveBeenCalledWith(
      expect.stringContaining('연결된 데이터가 있으면 퇴사 처리되고, 없으면 완전히 삭제됩니다'),
    )
    const del = requests.find((r) => r.method === 'DELETE')
    expect(del?.path).toBe('/api/v1/users/u-2')
    expect(del?.headers.get('x-requested-with')).toBe('neoine-web')
  })

  it('does nothing when the confirmation is declined', async () => {
    const requests = mockApi({ 'GET /api/v1/auth/me': { body: ME_ADMIN }, 'GET /api/v1/users': page(USER_ROWS) })
    vi.spyOn(window, 'confirm').mockReturnValue(false)
    renderApp(<UsersPage />)
    await screen.findByText('kim')

    await userEvent.click(within(rowOf('kim')).getByRole('button', { name: '삭제' }))

    expect(requests.some((r) => r.method === 'DELETE')).toBe(false)
    expect(rowOf('kim')).toBeInTheDocument()
  })

  it('shows the server message when the last admin cannot be deleted', async () => {
    mockApi({
      'GET /api/v1/auth/me': { body: { ...ME_ADMIN, user_id: 'u-other', subject: 'other-admin' } },
      'GET /api/v1/users': page(USER_ROWS),
      'DELETE /api/v1/users/u-1': problem(409, 'invalid-state', '마지막 관리자는 삭제할 수 없습니다'),
    })
    vi.spyOn(window, 'confirm').mockReturnValue(true)
    renderApp(<UsersPage />)
    await screen.findByText('kim')

    await userEvent.click(within(rowOf('root')).getByRole('button', { name: '삭제' }))

    expect(await screen.findByRole('alert')).toHaveTextContent('마지막 관리자는 삭제할 수 없습니다')
    expect(rowOf('root')).toBeInTheDocument()
  })

  it('hides the delete button on the row of the signed-in user', async () => {
    mockApi({ 'GET /api/v1/auth/me': { body: ME_ADMIN }, 'GET /api/v1/users': page(USER_ROWS) })

    renderApp(<UsersPage />)

    await screen.findByText('kim')
    await waitFor(() => expect(within(rowOf('root')).queryByRole('button', { name: '삭제' })).not.toBeInTheDocument())
    expect(await within(rowOf('kim')).findByRole('button', { name: '삭제' })).toBeInTheDocument()
  })

  it('shows the server message when the server refuses to delete oneself', async () => {
    mockApi({
      'GET /api/v1/auth/me': { body: { ...ME_ADMIN, user_id: 'u-nobody', subject: 'nobody' } },
      'GET /api/v1/users': page(USER_ROWS),
      'DELETE /api/v1/users/u-2': problem(409, 'invalid-state', '자기 자신은 삭제할 수 없습니다'),
    })
    vi.spyOn(window, 'confirm').mockReturnValue(true)
    renderApp(<UsersPage />)
    await screen.findByText('kim')

    await userEvent.click(within(rowOf('kim')).getByRole('button', { name: '삭제' }))

    expect(await screen.findByRole('alert')).toHaveTextContent('자기 자신은 삭제할 수 없습니다')
  })
})

describe('UsersPage delete outcome', () => {
  const deleteKim = async (outcome: 'deleted' | 'resigned') => {
    mockApi({
      'GET /api/v1/auth/me': { body: ME_ADMIN },
      'GET /api/v1/users': page(USER_ROWS),
      'DELETE /api/v1/users/u-2': { body: { outcome } },
    })
    vi.spyOn(window, 'confirm').mockReturnValue(true)
    renderApp(<UsersPage />)
    await screen.findByText('kim')
    await userEvent.click(within(rowOf('kim')).getByRole('button', { name: '삭제' }))
  }

  it('says the user was deleted when nothing was linked', async () => {
    await deleteKim('deleted')

    expect(await screen.findByRole('status')).toHaveTextContent('삭제되었습니다')
  })

  it('says the user was processed as resigned when data was linked', async () => {
    await deleteKim('resigned')

    expect(await screen.findByRole('status')).toHaveTextContent('퇴사 처리되었습니다')
  })

  it('clears the previous result message when the next delete fails', async () => {
    mockApi({
      'GET /api/v1/auth/me': { body: { ...ME_ADMIN, user_id: 'u-other', subject: 'other-admin' } },
      'GET /api/v1/users': page(USER_ROWS),
      'DELETE /api/v1/users/u-2': { body: { outcome: 'resigned' } },
      'DELETE /api/v1/users/u-1': problem(409, 'invalid-state', '마지막 관리자는 삭제할 수 없습니다'),
    })
    vi.spyOn(window, 'confirm').mockReturnValue(true)
    renderApp(<UsersPage />)
    await screen.findByText('kim')
    await userEvent.click(within(rowOf('kim')).getByRole('button', { name: '삭제' }))
    await screen.findByRole('status')

    await userEvent.click(within(rowOf('root')).getByRole('button', { name: '삭제' }))

    expect(await screen.findByRole('alert')).toHaveTextContent('마지막 관리자는 삭제할 수 없습니다')
    expect(screen.queryByRole('status')).not.toBeInTheDocument()
  })

  it('does not send a reason of its own (the server default is resigned)', async () => {
    const requests = mockApi({
      'GET /api/v1/auth/me': { body: ME_ADMIN },
      'GET /api/v1/users': page(USER_ROWS),
      'DELETE /api/v1/users/u-2': { body: { outcome: 'deleted' } },
    })
    vi.spyOn(window, 'confirm').mockReturnValue(true)
    renderApp(<UsersPage />)
    await screen.findByText('kim')
    await userEvent.click(within(rowOf('kim')).getByRole('button', { name: '삭제' }))

    await screen.findByRole('status')
    expect(requests.find((r) => r.method === 'DELETE')!.query.has('reason')).toBe(false)
  })
})

describe('UsersPage status filter and resigned rows', () => {
  const usersByStatus = (r: { query: URLSearchParams }) => {
    const status = r.query.get('status')
    if (status === 'resigned') return page([RESIGNED_ROW])
    if (status === 'all') return page([...USER_ROWS, RESIGNED_ROW])
    return page(USER_ROWS)
  }

  it('lists active users by default and sends status=active', async () => {
    const requests = mockApi({ 'GET /api/v1/auth/me': { body: ME_ADMIN }, 'GET /api/v1/users': usersByStatus })

    renderApp(<UsersPage />)

    await screen.findByText('kim')
    expect(screen.getByLabelText('상태')).toHaveValue('active')
    expect(requests.find((r) => r.path === '/api/v1/users')!.query.get('status')).toBe('active')
    expect(screen.queryByText('old')).not.toBeInTheDocument()
  })

  it('offers 재직, 퇴사 and 전체 and can list only the resigned', async () => {
    const requests = mockApi({ 'GET /api/v1/auth/me': { body: ME_ADMIN }, 'GET /api/v1/users': usersByStatus })
    renderApp(<UsersPage />)
    await screen.findByText('kim')
    const labels = Array.from(screen.getByLabelText('상태').querySelectorAll('option')).map((o) => o.textContent)
    expect(labels).toEqual(['재직', '퇴사', '전체'])

    await userEvent.selectOptions(screen.getByLabelText('상태'), 'resigned')

    expect(await screen.findByText('old')).toBeInTheDocument()
    expect(screen.queryByText('kim')).not.toBeInTheDocument()
    expect(requests.filter((r) => r.path === '/api/v1/users').at(-1)!.query.get('status')).toBe('resigned')
  })

  it('shows a resigned row with 이름(퇴사), the resignation time and reason, and no delete button', async () => {
    mockApi({ 'GET /api/v1/auth/me': { body: ME_ADMIN }, 'GET /api/v1/users': usersByStatus })
    renderApp(<UsersPage />)
    await screen.findByText('kim')

    await userEvent.selectOptions(screen.getByLabelText('상태'), 'all')

    await screen.findByText('old')
    const row = rowOf('old')
    expect(row).toHaveTextContent('이퇴사(퇴사)')
    expect(row).toHaveTextContent(formatDateTime(RESIGNED_ROW.deleted_at as string))
    expect(row).toHaveTextContent('퇴사')
    expect(within(row).queryByRole('button')).not.toBeInTheDocument()
    expect(within(rowOf('kim')).getByRole('button', { name: '삭제' })).toBeInTheDocument()
  })

  it('shows "-" for resignation columns of active users', async () => {
    mockApi({ 'GET /api/v1/auth/me': { body: ME_ADMIN }, 'GET /api/v1/users': usersByStatus })
    renderApp(<UsersPage />)

    await screen.findByText('kim')

    expect(within(rowOf('kim')).getAllByText('-').length).toBeGreaterThanOrEqual(2)
  })
})
