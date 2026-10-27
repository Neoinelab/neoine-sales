// 디자이너는 React.lazy 청크이므로 링크를 눌러 열기 전에 미리 읽어 둔다.
import './designer/ReportDesignerPage'
import { screen, waitFor, within } from '@testing-library/react'
import { describe, expect, it } from 'vitest'
import { mockControl } from '../../test/fake/default'
import { renderAt } from '../../test/mockApp'
import { addColumn, openDesigner, openList, resultTable, runQuery, saveDialog, setupReportClock, typeName } from '../../test/reportScreen'
import { BROKEN_DEFINITION, KIM_LIST_ORDER, MINE_PRIVATE, MINE_PUBLIC, OLD_PUBLIC, PARK_PRIVATE, PARK_PUBLIC, SAVED_SAMPLES, savedReport } from '../../test/savedReports'

setupReportClock()

describe('Reports 목록 (AC1)', () => {
  it.each(['admin', 'sales', 'user'] as const)('shows the empty list and the new report link for %s', async (role) => {
    const { user, location } = await renderAt('/reports', { role })

    expect(await screen.findByRole('heading', { level: 1, name: 'Reports' })).toBeVisible()
    expect(screen.getByText(/아직 저장한 리포트가 없습니다/)).toBeVisible()
    expect(screen.queryByText(/준비 중입니다/)).not.toBeInTheDocument()
    const link = screen.getByRole('link', { name: '+ 새 리포트' })
    expect(link).toHaveAttribute('href', '/reports/new')

    await user.click(link)

    expect(location()).toBe('/reports/new')
    expect(await screen.findByRole('heading', { level: 1, name: '새 리포트' })).toBeVisible()
  })

  it('sends an anonymous visitor to the login page', async () => {
    const { location } = await renderAt('/reports', { role: null })

    await waitFor(() => expect(location()).toBe('/login'))
  })

  it('sends an anonymous visitor of the designer to the login page', async () => {
    const { location } = await renderAt('/reports/new', { role: null })

    await waitFor(() => expect(location()).toBe('/login'))
  })
})

describe('user 역할의 디자이너 (AC2)', () => {
  it('lets the user role open the designer and run a query', async () => {
    const { user, location } = await openDesigner({ role: 'user' })
    await addColumn(user, 'Deal code')

    await runQuery(user)

    expect(location()).toBe('/reports/new')
    const table = await screen.findByRole('table', { name: '조회 결과' })
    expect(resultTable()).toBe(table)
    expect(screen.getByRole('cell', { name: 'Deal code 1' })).toBeVisible()
  })

  it('has no permission gate for the user role and offers a save button that waits for a result', async () => {
    const { user } = await openDesigner({ role: 'user' })

    expect(screen.queryByText(/권한/)).not.toBeInTheDocument()
    expect(screen.getByRole('button', { name: '저장' })).toBeDisabled()

    await addColumn(user, 'Deal code')
    await runQuery(user)
    await screen.findByRole('table', { name: '조회 결과' })

    expect(screen.getByRole('button', { name: '저장' })).toBeEnabled()
  })
})

const rowOf = (name: string): HTMLElement => {
  const row = screen.getByRole('link', { name }).closest('tr')
  if (!row) throw new Error(`행 없음: ${name}`)
  return row
}
const nameLinks = (): string[] =>
  within(screen.getByRole('table', { name: '리포트 목록' }))
    .getAllByRole('row')
    .slice(1)
    .map((row) => within(row).getAllByRole('link')[0]?.textContent ?? '')
/** 현재 주소의 쿼리를 이름→값으로 읽는다(쿼리 키 순서에 기대지 않는다). */
const paramsOf = (location: () => string): Record<string, string> => Object.fromEntries(new URLSearchParams(location().split('?')[1] ?? ''))
const searchBox = (): HTMLElement => screen.getByRole('textbox', { name: '이름·설명 검색' })
const scopeSelect = (): HTMLElement => screen.getByRole('combobox', { name: '리포트 범위' })
/** 행 메뉴 항목(링크·버튼·menuitem 어느 역할이든 이름으로 찾는다). */
const menuItem = (name: string): HTMLElement | null =>
  screen.queryByRole('menuitem', { name }) ?? screen.queryByRole('link', { name }) ?? screen.queryByRole('button', { name })
const hrefOf = (name: string): string | null => menuItem(name)?.closest('a')?.getAttribute('href') ?? null
const openMenu = async (user: Awaited<ReturnType<typeof openList>>['user'], name: string) => {
  await user.click(within(rowOf(name)).getByRole('button', { name: `${name} 메뉴` }))
}

describe('Reports 저장 목록 (AC12, S1)', () => {
  it('lists visible reports with tags owner and updated time', async () => {
    await openList()

    expect(screen.getByRole('heading', { level: 1, name: 'Reports' })).toBeVisible()
    for (const header of ['이름', '설명', '데이터', '만든 사람', '최종 수정']) {
      expect(screen.getByRole('columnheader', { name: header })).toBeVisible()
    }
    expect(nameLinks()).toEqual(KIM_LIST_ORDER)
    expect(screen.queryByRole('link', { name: PARK_PRIVATE.name })).not.toBeInTheDocument()
    expect(screen.queryByText(/아직 저장한 리포트가 없습니다/)).not.toBeInTheDocument()

    const mine = rowOf(MINE_PUBLIC.name)
    expect(within(mine).getByText('Lost 제외, 올해 Expected Close')).toBeVisible()
    expect(within(mine).getByText('Deal')).toBeVisible()
    expect(within(mine).queryByText('Actions')).not.toBeInTheDocument()
    expect(within(mine).queryByText('비공개')).not.toBeInTheDocument()
    expect(within(mine).getByText('김영업')).toBeVisible()
    expect(within(mine).getByText('2026-10-24 17:20')).toBeVisible()
    expect(within(mine).queryByText(/수정:/)).not.toBeInTheDocument()

    const park = rowOf(PARK_PUBLIC.name)
    expect(within(park).getByText('Deal')).toBeVisible()
    expect(within(park).getByText('Actions')).toBeVisible()
    expect(within(park).getByText('박영업')).toBeVisible()
    expect(within(park).getByText(/수정: 김영업/)).toBeVisible()

    expect(within(rowOf(MINE_PRIVATE.name)).getByText('비공개')).toBeVisible()
    expect(within(rowOf(OLD_PUBLIC.name)).getByText('강퇴사(퇴사)')).toBeVisible()
  })

  it('links each name to the view page', async () => {
    const { user, location } = await openList()

    expect(screen.getByRole('link', { name: MINE_PUBLIC.name })).toHaveAttribute('href', '/reports/11')

    await user.click(screen.getByRole('link', { name: MINE_PUBLIC.name }))

    expect(location()).toBe('/reports/11')
  })

  it('shows every report including the private ones of others to an admin', async () => {
    await openList({ role: 'admin' })

    expect(nameLinks()).toHaveLength(5)
    expect(within(rowOf(PARK_PRIVATE.name)).getByText('비공개')).toBeVisible()
  })

  it('keeps the new report link for every role', async () => {
    await openList({ role: 'user' })

    expect(screen.getByRole('link', { name: '+ 새 리포트' })).toHaveAttribute('href', '/reports/new')
  })

  it('filters by search and mine and keeps them in the url', async () => {
    const { user, location } = await openList()

    await user.type(searchBox(), 'VENDOR')

    await waitFor(() => expect(nameLinks()).toEqual([MINE_PUBLIC.name]))
    expect(location().split('?')[0]).toBe('/reports')
    expect(paramsOf(location)).toEqual({ q: 'VENDOR' })

    await user.clear(searchBox())
    await user.selectOptions(scopeSelect(), '내가 만든 리포트')

    await waitFor(() => expect(nameLinks()).toEqual([MINE_PUBLIC.name, MINE_PRIVATE.name]))
    expect(paramsOf(location)).toEqual({ mine: '1' })

    await user.type(searchBox(), '점검')

    await waitFor(() => expect(nameLinks()).toEqual([MINE_PRIVATE.name]))
    expect(paramsOf(location)).toEqual({ q: '점검', mine: '1' })

    await user.selectOptions(scopeSelect(), '전체 리포트')
    await user.clear(searchBox())

    await waitFor(() => expect(nameLinks()).toEqual(KIM_LIST_ORDER))
    expect(paramsOf(location)).toEqual({})
  })

  it('restores the search and mine from the url', async () => {
    await openList({ path: '/reports?q=%ED%8C%8C%EC%9D%B4%ED%94%84&mine=1' })

    expect(searchBox()).toHaveValue('파이프')
    expect(scopeSelect()).toHaveDisplayValue('내가 만든 리포트')
    expect(nameLinks()).toEqual([MINE_PUBLIC.name])
  })

  it('searches the description too and ignores case', async () => {
    const { user } = await openList()

    await user.type(searchBox(), 'expected close')

    await waitFor(() => expect(nameLinks()).toEqual([MINE_PUBLIC.name]))
  })

  it('shows no report when nothing matches', async () => {
    const { user } = await openList()

    await user.type(searchBox(), '없는말입니다')

    await waitFor(() => expect(screen.queryByRole('link', { name: MINE_PUBLIC.name })).not.toBeInTheDocument())
    expect(screen.queryByRole('link', { name: PARK_PUBLIC.name })).not.toBeInTheDocument()
    expect(screen.getByRole('link', { name: '+ 새 리포트' })).toBeVisible()
  })
})

describe('행 메뉴 (AC12, S3)', () => {
  const MENU = ['열기', '편집', '복제', '삭제'] as const
  const has = (item: (typeof MENU)[number]): boolean => menuItem(item) !== null

  it.each([
    ['sales on a report of their own', 'sales', MINE_PUBLIC.name, ['열기', '편집', '복제', '삭제']],
    ['sales on a private report of their own', 'sales', MINE_PRIVATE.name, ['열기', '편집', '복제', '삭제']],
    ['sales on a public report of someone else', 'sales', PARK_PUBLIC.name, ['열기', '편집', '복제']],
    ['sales on the public report of a resigned owner', 'sales', OLD_PUBLIC.name, ['열기', '편집', '복제']],
    ['user on a public report of someone else', 'user', MINE_PUBLIC.name, ['열기', '편집', '복제']],
    ['admin on the private report of someone else', 'admin', PARK_PRIVATE.name, ['열기', '편집', '복제', '삭제']],
    ['admin on a public report of someone else', 'admin', MINE_PUBLIC.name, ['열기', '편집', '복제', '삭제']],
  ] as const)('shows edit and delete in the row menu only when allowed: %s', async (_name, role, report, expected) => {
    const { user } = await openList({ role })

    await openMenu(user, report)

    expect(MENU.filter(has)).toEqual(expected)
  })

  it('opens and closes the menu with aria state, links the items and returns focus on Escape', async () => {
    const { user } = await openList()
    const button = within(rowOf(MINE_PUBLIC.name)).getByRole('button', { name: `${MINE_PUBLIC.name} 메뉴` })
    expect(button).toHaveAttribute('aria-haspopup', 'menu')
    expect(button).toHaveAttribute('aria-expanded', 'false')

    await user.click(button)

    expect(button).toHaveAttribute('aria-expanded', 'true')
    expect(hrefOf('열기')).toBe('/reports/11')
    expect(hrefOf('편집')).toBe('/reports/11/edit')

    await user.keyboard('{Escape}')

    expect(button).toHaveAttribute('aria-expanded', 'false')
    expect(menuItem('편집')).toBeNull()
    expect(button).toHaveFocus()
  })

  it('closes the menu on an outside click', async () => {
    const { user } = await openList()
    await openMenu(user, MINE_PUBLIC.name)

    await user.click(screen.getByRole('heading', { level: 1, name: 'Reports' }))

    expect(menuItem('편집')).toBeNull()
  })

  it('goes to the editor from the edit item', async () => {
    const { user, location } = await openList()
    await openMenu(user, PARK_PUBLIC.name)

    await user.click(menuItem('편집') as HTMLElement)

    expect(location()).toBe('/reports/13/edit')
  })
})

describe('삭제 (AC17, S4)', () => {
  it('deletes after confirmation and removes the row', async () => {
    const { user } = await openList()
    await openMenu(user, MINE_PUBLIC.name)
    await user.click(menuItem('삭제') as HTMLElement)

    const dialog = await screen.findByRole('dialog', { name: '리포트 삭제' })
    expect(dialog).toHaveTextContent(`‘${MINE_PUBLIC.name}’ 리포트를 삭제할까요? 되돌릴 수 없습니다.`)
    expect(mockControl.savedReportRequests()).toEqual([])

    await user.click(within(dialog).getByRole('button', { name: '삭제' }))

    await waitFor(() => expect(screen.queryByRole('link', { name: MINE_PUBLIC.name })).not.toBeInTheDocument())
    expect(screen.queryByRole('dialog')).not.toBeInTheDocument()
    expect(mockControl.savedReportRequests()).toEqual([{ op: 'remove', id: 11 }])
    expect(nameLinks()).toEqual([PARK_PUBLIC.name, MINE_PRIVATE.name, OLD_PUBLIC.name])
  })

  it('keeps the report when the confirmation is cancelled', async () => {
    const { user } = await openList()
    await openMenu(user, MINE_PUBLIC.name)
    await user.click(menuItem('삭제') as HTMLElement)

    await user.click(within(await screen.findByRole('dialog', { name: '리포트 삭제' })).getByRole('button', { name: '취소' }))

    expect(screen.queryByRole('dialog')).not.toBeInTheDocument()
    expect(screen.getByRole('link', { name: MINE_PUBLIC.name })).toBeVisible()
    expect(mockControl.savedReportRequests()).toEqual([])
  })

  it('shows the empty guide once the last visible report is deleted', async () => {
    const { user } = await renderAt('/reports', { savedReports: [MINE_PUBLIC] })
    await screen.findByRole('link', { name: MINE_PUBLIC.name })
    await openMenu(user, MINE_PUBLIC.name)
    await user.click(menuItem('삭제') as HTMLElement)

    await user.click(within(await screen.findByRole('dialog', { name: '리포트 삭제' })).getByRole('button', { name: '삭제' }))

    expect(await screen.findByText(/아직 저장한 리포트가 없습니다/)).toBeVisible()
  })
})

describe('복제 (AC10, S5)', () => {
  it('copies from the row menu and opens the copy in the editor', async () => {
    const { user, location } = await openList()
    await openMenu(user, MINE_PUBLIC.name)
    await user.click(menuItem('복제') as HTMLElement)

    const dialog = await saveDialog()
    expect(within(dialog).getByRole('textbox', { name: '이름' })).toHaveValue(`${MINE_PUBLIC.name} 복사본`)
    expect(within(dialog).getByRole('combobox', { name: '공개 범위' })).toHaveValue('public')

    await user.click(within(dialog).getByRole('button', { name: '저장' }))

    await waitFor(() => expect(location()).toBe('/reports/16/edit'))
    // 편집 화면은 lazy 청크라 첫 로딩이 기본 대기(1초)를 넘길 수 있다.
    expect(await screen.findByRole('heading', { level: 1, name: `${MINE_PUBLIC.name} 복사본` }, { timeout: 5000 })).toBeVisible()
    expect(mockControl.savedReportRequests()).toEqual([
      { op: 'copy', id: 11, body: expect.objectContaining({ name: `${MINE_PUBLIC.name} 복사본`, visibility: 'public' }) },
    ])
  })

  it('copies a public report of someone else as the report of the viewer with the chosen visibility', async () => {
    const { user, location } = await openList()
    await openMenu(user, PARK_PUBLIC.name)
    await user.click(menuItem('복제') as HTMLElement)
    const dialog = await saveDialog()
    await typeName(user, dialog, '내 복사본')
    await user.selectOptions(within(dialog).getByRole('combobox', { name: '공개 범위' }), '나만 보기')

    await user.click(within(dialog).getByRole('button', { name: '저장' }))

    await waitFor(() => expect(location()).toBe('/reports/16/edit'))
    expect(mockControl.savedReportRequests()[0]).toMatchObject({ op: 'copy', id: 13, body: { name: '내 복사본', visibility: 'private' } })
  })

  it('shows a duplicate name next to the name field and stays on the list', async () => {
    const { user, location } = await openList()
    await openMenu(user, MINE_PUBLIC.name)
    await user.click(menuItem('복제') as HTMLElement)
    const dialog = await saveDialog()
    await typeName(user, dialog, MINE_PRIVATE.name)

    await user.click(within(dialog).getByRole('button', { name: '저장' }))

    expect(await within(dialog).findByText('같은 이름의 리포트가 이미 있습니다.')).toBeVisible()
    expect(location()).toBe('/reports')
    expect(screen.getByRole('dialog', { name: '리포트 저장' })).toBeVisible()
  })

  it('shows the server violation inside the dialog when the source no longer fits the catalog', async () => {
    const broken = savedReport({ id: 20, name: '깨진 정의', definition: BROKEN_DEFINITION })
    const { user, location } = await openList({ savedReports: [...SAVED_SAMPLES, broken] })
    await openMenu(user, broken.name)
    await user.click(menuItem('복제') as HTMLElement)
    const dialog = await saveDialog()

    await user.click(within(dialog).getByRole('button', { name: '저장' }))

    expect(await within(dialog).findByRole('alert')).toHaveTextContent(/허용되지 않은 필드입니다: deal\.nope/)
    expect(screen.getByRole('dialog', { name: '리포트 저장' })).toBeVisible()
    expect(location()).toBe('/reports')
  })

  it('closes the copy dialog without sending anything on cancel', async () => {
    const { user } = await openList()
    await openMenu(user, MINE_PUBLIC.name)
    await user.click(menuItem('복제') as HTMLElement)

    await user.click(within(await saveDialog()).getByRole('button', { name: '취소' }))

    expect(screen.queryByRole('dialog')).not.toBeInTheDocument()
    expect(mockControl.savedReportRequests()).toEqual([])
  })
})
