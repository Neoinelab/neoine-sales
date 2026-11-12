// 디자이너는 React.lazy 청크이므로 링크를 눌러 열기 전에 미리 읽어 둔다.
import './designer/ReportDesignerPage'
import { screen, waitFor, within } from '@testing-library/react'
import { describe, expect, it } from 'vitest'
import { mockControl } from '../../test/fake/default'
import { renderAt } from '../../test/mockApp'
import { addColumn, openDesigner, openList, resultTable, runQuery, saveDialog, setupReportClock, typeName } from '../../test/reportScreen'
import { BROKEN_DEFINITION, KIM_LIST_ORDER, MINE_PRIVATE, MINE_PUBLIC, OLD_PUBLIC, PARK_PRIVATE, PARK_PUBLIC, SAVED_SAMPLES, savedReport } from '../../test/savedReports'

setupReportClock()

describe('Reports 목록', () => {
  // 테스트 코드: RS-053
  it.each(['admin', 'sales', 'user'] as const)('%s 역할은 빈 목록과 새 리포트 링크를 본다', async (role) => {
    // given: 저장 리포트가 없는 Fake에 역할별로 로그인한다
    const { user, location } = await renderAt('/reports', { role })

    // when: /reports를 연다 / then: 제목, 빈 안내, 새 리포트 링크가 보인다
    expect(await screen.findByRole('heading', { level: 1, name: 'Reports' })).toBeVisible()
    expect(screen.getByText(/아직 저장한 리포트가 없습니다/)).toBeVisible()
    expect(screen.queryByText(/준비 중입니다/)).not.toBeInTheDocument()
    const link = screen.getByRole('link', { name: '+ 새 리포트' })
    expect(link).toHaveAttribute('href', '/reports/new')

    // when: 새 리포트 링크를 누른다
    await user.click(link)

    // then: 새 리포트 화면으로 간다
    expect(location()).toBe('/reports/new')
    expect(await screen.findByRole('heading', { level: 1, name: '새 리포트' })).toBeVisible()
  })

  it('로그인하지 않은 방문자는 목록에서 로그인 화면으로 간다', async () => {
    // when: 로그인하지 않고 /reports를 연다
    const { location } = await renderAt('/reports', { role: null })

    // then: /login으로 간다
    await waitFor(() => expect(location()).toBe('/login'))
  })

  it('로그인하지 않은 방문자는 디자이너에서 로그인 화면으로 간다', async () => {
    // when: 로그인하지 않고 /reports/new를 연다
    const { location } = await renderAt('/reports/new', { role: null })

    // then: /login으로 간다
    await waitFor(() => expect(location()).toBe('/login'))
  })
})

describe('user 역할의 디자이너', () => {
  it('user 역할도 디자이너를 열어 조회한다', async () => {
    // given: user 역할로 디자이너를 연다
    const { user, location } = await openDesigner({ role: 'user' })
    // when: 컬럼을 넣고 조회한다
    await addColumn(user, 'Deal code')

    await runQuery(user)

    // then: 화면에 머물며 결과 표가 보인다
    expect(location()).toBe('/reports/new')
    const table = await screen.findByRole('table', { name: '조회 결과' })
    expect(resultTable()).toBe(table)
    expect(screen.getByRole('cell', { name: 'Deal code 1' })).toBeVisible()
  })

  // 테스트 코드: RS-067
  it('user 역할에게 권한 안내는 없고 저장 버튼은 결과가 생길 때까지 꺼져 있다', async () => {
    // when: user 역할로 디자이너를 연다
    const { user } = await openDesigner({ role: 'user' })

    // then: 권한 안내가 없고 저장 버튼이 꺼져 있다
    expect(screen.queryByText(/권한/)).not.toBeInTheDocument()
    expect(screen.getByRole('button', { name: '저장' })).toBeDisabled()

    // when: 컬럼을 넣고 조회한다
    await addColumn(user, 'Deal code')
    await runQuery(user)
    await screen.findByRole('table', { name: '조회 결과' })

    // then: 저장 버튼이 켜진다
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

describe('Reports 저장 목록', () => {
  // 테스트 코드: RS-054
  it('볼 수 있는 리포트를 태그·만든 사람·최종 수정과 함께 서버 순서로 보인다', async () => {
    // when: 김영업으로 샘플 리포트 목록을 연다
    await openList()

    // then: 제목, 열 머리글, 서버 순서의 이름 링크가 보이고 남의 비공개는 없다
    expect(screen.getByRole('heading', { level: 1, name: 'Reports' })).toBeVisible()
    for (const header of ['이름', '설명', '데이터', '만든 사람', '최종 수정']) {
      expect(screen.getByRole('columnheader', { name: header })).toBeVisible()
    }
    expect(nameLinks()).toEqual(KIM_LIST_ORDER)
    expect(screen.queryByRole('link', { name: PARK_PRIVATE.name })).not.toBeInTheDocument()
    expect(screen.queryByText(/아직 저장한 리포트가 없습니다/)).not.toBeInTheDocument()

    // then: 내 공개 행에 설명·Deal 태그·만든 사람·수정 시각이 있고 비공개·수정자 표시는 없다
    const mine = rowOf(MINE_PUBLIC.name)
    expect(within(mine).getByText('Lost 제외, 올해 Expected Close')).toBeVisible()
    expect(within(mine).getByText('Deal')).toBeVisible()
    expect(within(mine).queryByText('Actions')).not.toBeInTheDocument()
    expect(within(mine).queryByText('비공개')).not.toBeInTheDocument()
    expect(within(mine).getByText('김영업')).toBeVisible()
    expect(within(mine).getByText('2026-10-24 17:20')).toBeVisible()
    expect(within(mine).queryByText(/수정:/)).not.toBeInTheDocument()

    // then: 박영업 행에 Deal·Actions 태그와 "수정: 김영업"이 있다
    const park = rowOf(PARK_PUBLIC.name)
    expect(within(park).getByText('Deal')).toBeVisible()
    expect(within(park).getByText('Actions')).toBeVisible()
    expect(within(park).getByText('박영업')).toBeVisible()
    expect(within(park).getByText(/수정: 김영업/)).toBeVisible()

    // then: 비공개 행에 "비공개", 퇴사자 행에 "(퇴사)" 표시가 있다
    expect(within(rowOf(MINE_PRIVATE.name)).getByText('비공개')).toBeVisible()
    expect(within(rowOf(OLD_PUBLIC.name)).getByText('강퇴사(퇴사)')).toBeVisible()
  })

  // 테스트 코드: RS-054
  it('이름은 보기 화면으로 가는 링크다', async () => {
    // when: 목록을 연다
    const { user, location } = await openList()

    // then: 이름 링크의 주소가 /reports/11이다
    expect(screen.getByRole('link', { name: MINE_PUBLIC.name })).toHaveAttribute('href', '/reports/11')

    // when: 이름을 누른다
    await user.click(screen.getByRole('link', { name: MINE_PUBLIC.name }))

    // then: 보기 화면 주소로 간다
    expect(location()).toBe('/reports/11')
  })

  // 테스트 코드: RS-055
  it('admin에게는 남의 비공개 리포트도 보인다', async () => {
    // when: admin으로 목록을 연다
    await openList({ role: 'admin' })

    // then: 5건이 모두 보이고 남의 비공개 행에 "비공개" 태그가 있다
    expect(nameLinks()).toHaveLength(5)
    expect(within(rowOf(PARK_PRIVATE.name)).getByText('비공개')).toBeVisible()
  })

  // 테스트 코드: RS-053
  it('user 역할도 새 리포트 링크가 있다', async () => {
    // when: user로 목록을 연다
    await openList({ role: 'user' })

    // then: 새 리포트 링크가 있다
    expect(screen.getByRole('link', { name: '+ 새 리포트' })).toHaveAttribute('href', '/reports/new')
  })

  // 테스트 코드: RS-056
  it('검색어와 "내가 만든 리포트"로 거르고 주소에 남긴다', async () => {
    // given: 목록을 연다
    const { user, location } = await openList()

    // when: 대문자 검색어를 입력한다
    await user.type(searchBox(), 'VENDOR')

    // then: 이름·설명에 맞는 리포트만 남고 주소에 q가 있다
    await waitFor(() => expect(nameLinks()).toEqual([MINE_PUBLIC.name]))
    expect(location().split('?')[0]).toBe('/reports')
    expect(paramsOf(location)).toEqual({ q: 'VENDOR' })

    // when: 검색어를 지우고 범위를 "내가 만든 리포트"로 바꾼다
    await user.clear(searchBox())
    await user.selectOptions(scopeSelect(), '내가 만든 리포트')

    // then: 내가 만든 것만 남고 주소에 mine=1이 있다
    await waitFor(() => expect(nameLinks()).toEqual([MINE_PUBLIC.name, MINE_PRIVATE.name]))
    expect(paramsOf(location)).toEqual({ mine: '1' })

    // when: 검색어를 더한다
    await user.type(searchBox(), '점검')

    // then: 둘 다 적용되어 주소에 q와 mine이 모두 있다
    await waitFor(() => expect(nameLinks()).toEqual([MINE_PRIVATE.name]))
    expect(paramsOf(location)).toEqual({ q: '점검', mine: '1' })

    // when: 범위를 전체로 돌리고 검색어를 지운다
    await user.selectOptions(scopeSelect(), '전체 리포트')
    await user.clear(searchBox())

    // then: 전체 목록으로 돌아오고 주소 필터가 비어 있다
    await waitFor(() => expect(nameLinks()).toEqual(KIM_LIST_ORDER))
    expect(paramsOf(location)).toEqual({})
  })

  // 테스트 코드: RS-056
  it('주소의 검색어와 범위를 새로 열어도 복원한다', async () => {
    // when: /reports?q=…&mine=1 주소로 목록을 연다
    await openList({ path: '/reports?q=%ED%8C%8C%EC%9D%B4%ED%94%84&mine=1' })

    // then: 검색어·범위가 복원되고 같은 결과만 보인다
    expect(searchBox()).toHaveValue('파이프')
    expect(scopeSelect()).toHaveDisplayValue('내가 만든 리포트')
    expect(nameLinks()).toEqual([MINE_PUBLIC.name])
  })

  // 테스트 코드: RS-056
  it('설명에서도 대소문자 없이 찾는다', async () => {
    // given: 목록을 연다
    const { user } = await openList()

    // when: 설명 일부를 소문자로 입력한다
    await user.type(searchBox(), 'expected close')

    // then: 그 설명의 리포트만 남는다
    await waitFor(() => expect(nameLinks()).toEqual([MINE_PUBLIC.name]))
  })

  // 테스트 코드: RS-056
  it('맞는 리포트가 없으면 안내를 보인다', async () => {
    // given: 목록을 연다
    const { user } = await openList()

    // when: 어디에도 없는 검색어를 입력한다
    await user.type(searchBox(), '없는말입니다')

    // then: 리포트 링크가 사라지고 새 리포트 링크는 남는다
    await waitFor(() => expect(screen.queryByRole('link', { name: MINE_PUBLIC.name })).not.toBeInTheDocument())
    expect(screen.queryByRole('link', { name: PARK_PUBLIC.name })).not.toBeInTheDocument()
    expect(screen.getByRole('link', { name: '+ 새 리포트' })).toBeVisible()
  })
})

describe('행 메뉴', () => {
  const MENU = ['열기', '편집', '복제', '삭제'] as const
  const has = (item: (typeof MENU)[number]): boolean => menuItem(item) !== null

  // 테스트 코드: RS-057
  it.each([
    ['sales on a report of their own', 'sales', MINE_PUBLIC.name, ['열기', '편집', '복제', '삭제']],
    ['sales on a private report of their own', 'sales', MINE_PRIVATE.name, ['열기', '편집', '복제', '삭제']],
    ['sales on a public report of someone else', 'sales', PARK_PUBLIC.name, ['열기', '편집', '복제']],
    ['sales on the public report of a resigned owner', 'sales', OLD_PUBLIC.name, ['열기', '편집', '복제']],
    ['user on a public report of someone else', 'user', MINE_PUBLIC.name, ['열기', '편집', '복제']],
    ['admin on the private report of someone else', 'admin', PARK_PRIVATE.name, ['열기', '편집', '복제', '삭제']],
    ['admin on a public report of someone else', 'admin', MINE_PUBLIC.name, ['열기', '편집', '복제', '삭제']],
  ] as const)('행 메뉴의 편집·삭제는 권한이 있을 때만 있다: %s', async (_name, role, report, expected) => {
    // given: 역할별로 목록을 연다
    const { user } = await openList({ role })

    // when: 리포트의 메뉴를 연다
    await openMenu(user, report)

    // then: 허용된 항목만 있다
    expect(MENU.filter(has)).toEqual(expected)
  })

  // 테스트 코드: RS-057
  it('메뉴는 aria 상태로 여닫히고 항목은 링크이며 Escape는 포커스를 단추로 돌린다', async () => {
    // when: 목록을 열고 내 리포트의 메뉴 단추를 찾는다
    const { user } = await openList()
    const button = within(rowOf(MINE_PUBLIC.name)).getByRole('button', { name: `${MINE_PUBLIC.name} 메뉴` })
    // then: 메뉴 단추는 aria-haspopup이 menu이고 닫혀 있다
    expect(button).toHaveAttribute('aria-haspopup', 'menu')
    expect(button).toHaveAttribute('aria-expanded', 'false')

    // when: 메뉴 단추를 누른다
    await user.click(button)

    // then: 열림 상태이고 열기·편집 항목이 링크 주소를 가진다
    expect(button).toHaveAttribute('aria-expanded', 'true')
    expect(hrefOf('열기')).toBe('/reports/11')
    expect(hrefOf('편집')).toBe('/reports/11/edit')

    // when: Escape를 누른다
    await user.keyboard('{Escape}')

    // then: 메뉴가 닫히고 포커스가 단추에 돌아온다
    expect(button).toHaveAttribute('aria-expanded', 'false')
    expect(menuItem('편집')).toBeNull()
    expect(button).toHaveFocus()
  })

  // 테스트 코드: RS-057
  it('바깥을 누르면 메뉴가 닫힌다', async () => {
    // given: 메뉴를 연 목록
    const { user } = await openList()
    await openMenu(user, MINE_PUBLIC.name)

    // when: 바깥(제목)을 누른다
    await user.click(screen.getByRole('heading', { level: 1, name: 'Reports' }))

    // then: 메뉴가 닫힌다
    expect(menuItem('편집')).toBeNull()
  })

  // 테스트 코드: RS-057
  it('편집 항목은 편집 화면으로 간다', async () => {
    // given: 남의 공개 리포트의 메뉴를 연 목록
    const { user, location } = await openList()
    await openMenu(user, PARK_PUBLIC.name)

    // when: 편집을 누른다
    await user.click(menuItem('편집') as HTMLElement)

    // then: /reports/13/edit로 간다
    expect(location()).toBe('/reports/13/edit')
  })
})

describe('삭제', () => {
  // 테스트 코드: RS-058
  it('확인 뒤 삭제하면 행이 사라진다', async () => {
    // when: 목록에서 내 리포트의 삭제를 누른다
    const { user } = await openList()
    await openMenu(user, MINE_PUBLIC.name)
    await user.click(menuItem('삭제') as HTMLElement)

    // then: 확인 창에 삭제 문구가 있고 아직 요청이 없다
    const dialog = await screen.findByRole('dialog', { name: '리포트 삭제' })
    expect(dialog).toHaveTextContent(`‘${MINE_PUBLIC.name}’ 리포트를 삭제할까요? 되돌릴 수 없습니다.`)
    expect(mockControl.savedReportRequests()).toEqual([])

    // when: 확인 창에서 삭제를 누른다
    await user.click(within(dialog).getByRole('button', { name: '삭제' }))

    // then: 행이 사라지고 창이 닫히며 삭제 요청이 한 번 기록된다
    await waitFor(() => expect(screen.queryByRole('link', { name: MINE_PUBLIC.name })).not.toBeInTheDocument())
    expect(screen.queryByRole('dialog')).not.toBeInTheDocument()
    expect(mockControl.savedReportRequests()).toEqual([{ op: 'remove', id: 11 }])
    expect(nameLinks()).toEqual([PARK_PUBLIC.name, MINE_PRIVATE.name, OLD_PUBLIC.name])
  })

  // 테스트 코드: RS-058
  it('확인 창을 취소하면 삭제 요청 없이 행이 남는다', async () => {
    // given: 삭제 확인 창을 연다
    const { user } = await openList()
    await openMenu(user, MINE_PUBLIC.name)
    await user.click(menuItem('삭제') as HTMLElement)

    // when: 취소를 누른다
    await user.click(within(await screen.findByRole('dialog', { name: '리포트 삭제' })).getByRole('button', { name: '취소' }))

    // then: 창이 닫히고 행이 남으며 요청이 없다
    expect(screen.queryByRole('dialog')).not.toBeInTheDocument()
    expect(screen.getByRole('link', { name: MINE_PUBLIC.name })).toBeVisible()
    expect(mockControl.savedReportRequests()).toEqual([])
  })

  // 테스트 코드: RS-058
  it('마지막 리포트를 지우면 빈 안내가 보인다', async () => {
    // given: 리포트가 하나뿐인 목록에서 삭제 확인 창을 연다
    const { user } = await renderAt('/reports', { savedReports: [MINE_PUBLIC] })
    await screen.findByRole('link', { name: MINE_PUBLIC.name })
    await openMenu(user, MINE_PUBLIC.name)
    await user.click(menuItem('삭제') as HTMLElement)

    // when: 삭제를 확인한다
    await user.click(within(await screen.findByRole('dialog', { name: '리포트 삭제' })).getByRole('button', { name: '삭제' }))

    // then: 빈 안내가 보인다
    expect(await screen.findByText(/아직 저장한 리포트가 없습니다/)).toBeVisible()
  })
})

describe('복제', () => {
  // 테스트 코드: RS-059
  it('행 메뉴에서 복제하면 새 리포트의 편집 화면이 열린다', async () => {
    // when: 목록에서 내 리포트의 복제를 누른다
    const { user, location } = await openList()
    await openMenu(user, MINE_PUBLIC.name)
    await user.click(menuItem('복제') as HTMLElement)

    // then: 이름이 "복사본"으로, 공개 범위가 공개로 시작한다
    const dialog = await saveDialog()
    expect(within(dialog).getByRole('textbox', { name: '이름' })).toHaveValue(`${MINE_PUBLIC.name} 복사본`)
    expect(within(dialog).getByRole('combobox', { name: '공개 범위' })).toHaveValue('public')

    // when: 저장한다
    await user.click(within(dialog).getByRole('button', { name: '저장' }))

    // then: 새 리포트의 편집 화면으로 가고 복제 요청이 한 번 기록된다
    await waitFor(() => expect(location()).toBe('/reports/16/edit'))
    // 편집 화면은 lazy 청크라 첫 로딩이 기본 대기(1초)를 넘길 수 있다.
    expect(await screen.findByRole('heading', { level: 1, name: `${MINE_PUBLIC.name} 복사본` }, { timeout: 5000 })).toBeVisible()
    expect(mockControl.savedReportRequests()).toEqual([
      { op: 'copy', id: 11, body: expect.objectContaining({ name: `${MINE_PUBLIC.name} 복사본`, visibility: 'public' }) },
    ])
  })

  // 테스트 코드: RS-059
  it('남의 공개 리포트를 복제하면 내 리포트가 되고 고른 공개 범위를 가진다', async () => {
    // given: 남의 공개 리포트의 복제 창을 연다
    const { user, location } = await openList()
    await openMenu(user, PARK_PUBLIC.name)
    await user.click(menuItem('복제') as HTMLElement)
    const dialog = await saveDialog()
    // when: 이름을 정하고 공개 범위를 "나만 보기"로 바꿔 저장한다
    await typeName(user, dialog, '내 복사본')
    await user.selectOptions(within(dialog).getByRole('combobox', { name: '공개 범위' }), '나만 보기')

    await user.click(within(dialog).getByRole('button', { name: '저장' }))

    // then: 편집 화면으로 가고 요청에 이름·비공개가 실린다
    await waitFor(() => expect(location()).toBe('/reports/16/edit'))
    expect(mockControl.savedReportRequests()[0]).toMatchObject({ op: 'copy', id: 13, body: { name: '내 복사본', visibility: 'private' } })
  })

  // 테스트 코드: RS-060
  it('이름이 겹치면 이름 칸 아래 문구를 보이고 목록에 머문다', async () => {
    // given: 복제 창에서 이미 있는 이름을 넣는다
    const { user, location } = await openList()
    await openMenu(user, MINE_PUBLIC.name)
    await user.click(menuItem('복제') as HTMLElement)
    const dialog = await saveDialog()
    await typeName(user, dialog, MINE_PRIVATE.name)

    // when: 저장한다
    await user.click(within(dialog).getByRole('button', { name: '저장' }))

    // then: 중복 문구가 보이고 주소·창이 그대로다
    expect(await within(dialog).findByText('같은 이름의 리포트가 이미 있습니다.')).toBeVisible()
    expect(location()).toBe('/reports')
    expect(screen.getByRole('dialog', { name: '리포트 저장' })).toBeVisible()
  })

  // 테스트 코드: RS-060
  it('원본이 지금 규칙과 맞지 않으면 대화상자 안에 서버 위반을 보인다', async () => {
    // given: 지금 카탈로그에 없는 필드를 쓰는 원본의 복제 창
    const broken = savedReport({ id: 20, name: '깨진 정의', definition: BROKEN_DEFINITION })
    const { user, location } = await openList({ savedReports: [...SAVED_SAMPLES, broken] })
    await openMenu(user, broken.name)
    await user.click(menuItem('복제') as HTMLElement)
    const dialog = await saveDialog()

    // when: 저장한다
    await user.click(within(dialog).getByRole('button', { name: '저장' }))

    // then: 창 안에 위반 문구가 보이고 주소는 그대로다
    expect(await within(dialog).findByRole('alert')).toHaveTextContent(/허용되지 않은 필드입니다: deal\.nope/)
    expect(screen.getByRole('dialog', { name: '리포트 저장' })).toBeVisible()
    expect(location()).toBe('/reports')
  })

  // 테스트 코드: RS-060
  it('복제 창을 취소하면 요청 없이 닫힌다', async () => {
    // given: 복제 창을 연다
    const { user } = await openList()
    await openMenu(user, MINE_PUBLIC.name)
    await user.click(menuItem('복제') as HTMLElement)

    // when: 취소를 누른다
    await user.click(within(await saveDialog()).getByRole('button', { name: '취소' }))

    // then: 창이 닫히고 요청이 없다
    expect(screen.queryByRole('dialog')).not.toBeInTheDocument()
    expect(mockControl.savedReportRequests()).toEqual([])
  })
})
