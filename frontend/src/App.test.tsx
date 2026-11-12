import { screen, waitFor, within } from '@testing-library/react'
import { describe, expect, it } from 'vitest'
import { logOutFromMenu, openUserMenu } from './test/localAccounts'
import { renderAt } from './test/mockApp'
import { DEFAULT_DEALS_URL_PATTERN } from './test/dealsUrl'

function mainMenu() {
  return within(screen.getByRole('navigation', { name: '주 메뉴' }))
}

describe('목업 표시 없음 (S1)', () => {
  // 로그인·최초 설정·셸·Admin 화면에 목업 표시가 없다.
  it.each([
    ['로그인 화면', '/login', null],
    ['최초 설정 화면', '/setup', null],
    ['셸(Deals)', '/deals', 'sales'],
    ['Admin 설정 화면', '/admin/integrations', 'admin'],
  ] as const)('%s에 목업 배지와 목업 메뉴가 없다', async (_name, url, role) => {
    // when: 그 화면을 연다
    await renderAt(url, { role })
    await waitFor(() => expect(screen.getAllByRole('heading').length).toBeGreaterThan(0))

    // then: 목업 배지·메뉴·문구가 없다
    expect(screen.queryByText(/UI 목업/)).not.toBeInTheDocument()
    expect(screen.queryByText(/메모리 저장/)).not.toBeInTheDocument()
    expect(screen.queryByRole('button', { name: '목업 메뉴' })).not.toBeInTheDocument()
    expect(screen.queryByText(/목업/)).not.toBeInTheDocument()
  })
})

describe('메뉴 (T-SHELL-04~05)', () => {
  // sales·user의 주 메뉴는 6개이고 Admin이 없다.
  // 테스트 코드: PL-060
  it.each(['sales', 'user'] as const)('%s의 주 메뉴는 여섯 개이고 Admin이 없다', async (role) => {
    // given: sales 또는 user로 로그인
    await renderAt('/deals', { role })
    await screen.findByRole('navigation', { name: '주 메뉴' })
    // when: 보호 화면을 연다
    const labels = mainMenu()
      .getAllByRole('link')
      .map((a) => a.textContent)
    // then: 주 메뉴 링크가 순서대로 여섯 개이고 Admin은 없다
    expect(labels).toEqual(['Deals', '계약관리', '파트너 Activity', 'Dashboard', 'Forecast', 'Reports'])
  })

  // admin의 주 메뉴는 끝에 Admin이 더해진다.
  // 테스트 코드: PL-061
  it('admin의 주 메뉴는 끝에 Admin이 더해진다', async () => {
    // given: admin으로 로그인
    await renderAt('/deals', { role: 'admin' })
    await screen.findByRole('navigation', { name: '주 메뉴' })
    // when: 보호 화면을 연다
    const labels = mainMenu()
      .getAllByRole('link')
      .map((a) => a.textContent)
    // then: 여섯 개 메뉴 끝에 Admin이 더해진다
    expect(labels).toEqual(['Deals', '계약관리', '파트너 Activity', 'Dashboard', 'Forecast', 'Reports', 'Admin'])
  })

  // 사용자 메뉴에 로그인한 이름과 역할이 보인다.
  it('사용자 메뉴에 로그인한 이름과 역할이 보인다', async () => {
    // given: sales(김영업)로 로그인한 Deals 화면
    const { user } = await renderAt('/deals', { role: 'sales' })
    // when: 사용자 메뉴를 연다
    await openUserMenu(user)
    // then: '김영업 (sales)'가 보인다
    expect(await screen.findByText('김영업 (sales)')).toBeVisible()
  })

  // 주 메뉴를 누르면 그 화면으로 간다.
  // 테스트 코드: PL-062
  it('주 메뉴를 누르면 그 화면으로 간다', async () => {
    // given: admin으로 로그인한 Deals 화면
    const { user, location } = await renderAt('/deals', { role: 'admin' })
    await screen.findByRole('navigation', { name: '주 메뉴' })
    // when: Forecast 메뉴를 누른다
    await user.click(mainMenu().getByRole('link', { name: 'Forecast' }))
    // then: 주소가 /forecast가 된다
    expect(location()).toBe('/forecast')
    // when: 이어서 Admin 메뉴를 누른다
    await user.click(mainMenu().getByRole('link', { name: 'Admin' }))
    // then: 주소가 /admin/users가 된다
    expect(location()).toBe('/admin/users')
  })
})

describe('Reports 화면 (T-SHELL-06)', () => {
  // /reports는 준비 중 화면이 아니라 빈 리포트 목록을 보인다.
  it('/reports는 준비 중 화면 대신 빈 리포트 목록을 보인다', async () => {
    // when: /reports를 연다
    await renderAt('/reports')
    // then: Reports 제목과 빈 목록 안내가 보이고 준비 중·목업 문구는 없다
    expect(await screen.findByRole('heading', { name: 'Reports' })).toBeVisible()
    expect(screen.getByText(/아직 저장한 리포트가 없습니다/)).toBeVisible()
    expect(screen.queryByText(/준비 중입니다/)).not.toBeInTheDocument()
    expect(document.body.textContent).not.toContain('목업')
  })
})

describe('Dashboard 화면', () => {
  // /dashboard는 준비 중 화면이 아니라 Dashboard를 보인다.
  // 테스트 코드: DSH-025
  it('준비 중 화면 대신 Dashboard를 보인다', async () => {
    // when: /dashboard를 연다
    await renderAt('/dashboard')
    // then: Dashboard 제목과 Status 탭(선택)·Forecast 탭이 보이고 준비 중·목업 문구는 없다
    expect(await screen.findByRole('heading', { level: 1, name: 'Dashboard' })).toBeVisible()
    expect(await screen.findByRole('tab', { name: 'Status' })).toHaveAttribute('aria-selected', 'true')
    expect(screen.getByRole('tab', { name: 'Forecast' })).toBeVisible()
    expect(screen.queryByText(/준비 중입니다/)).not.toBeInTheDocument()
    expect(document.body.textContent).not.toContain('목업')
  })

  // Dashboard는 모든 역할이 연다.
  // 테스트 코드: DSH-025
  it.each(['admin', 'sales', 'user'] as const)('%s 역할에게 열려 있다', async (role) => {
    // when: /dashboard를 연다
    await renderAt('/dashboard', { role })
    // then: Status 탭이 보인다
    expect(await screen.findByRole('tab', { name: 'Status' })).toBeVisible()
  })

  // 로그인하지 않은 방문자는 /dashboard에서 로그인 화면으로 간다.
  // 테스트 코드: PL-051, DSH-025
  it('로그인하지 않은 방문자가 /dashboard를 열면 로그인 화면으로 간다', async () => {
    // when: /dashboard를 연다 (전제: 로그인하지 않음, 최초 설정은 끝남)
    const { location } = await renderAt('/dashboard', { role: null })
    // then: 주소가 /login이 된다
    await waitFor(() => expect(location()).toBe('/login'))
  })
})

describe('가드와 리다이렉트 (T-SHELL-07~08)', () => {
  // 로그인하지 않은 방문자는 /deals에서 로그인 화면으로 간다.
  // 테스트 코드: PL-051
  it('로그인하지 않은 방문자가 /deals를 열면 로그인 화면으로 간다', async () => {
    // when: /deals를 연다 (전제: 로그인하지 않음, 최초 설정은 끝남)
    const { location } = await renderAt('/deals', { role: null })
    // then: 주소가 /login이 된다
    await waitFor(() => expect(location()).toBe('/login'))
  })

  // 첫 주소(/)는 Deals 목록으로 간다.
  // 테스트 코드: PL-053
  it('/는 Deals 목록으로 간다', async () => {
    // when: /를 연다 (전제: 로그인한 KIM)
    const { location } = await renderAt('/')
    // then: Deals 목록 주소(기본 조건 포함)가 된다
    await waitFor(() => expect(location()).toMatch(DEFAULT_DEALS_URL_PATTERN))
  })

  // sales·user는 Admin 화면에서 Deals 목록으로 간다.
  // 테스트 코드: PL-056
  it.each(['sales', 'user'] as const)('%s는 Admin 화면에서 Deals 목록으로 간다', async (role) => {
    // when: /admin/users를 연다 (전제: sales 또는 user로 로그인)
    const { location } = await renderAt('/admin/users', { role })
    // then: Deals 목록 주소가 된다
    await waitFor(() => expect(location()).toMatch(DEFAULT_DEALS_URL_PATTERN))
  })

  // admin이 /admin을 열면 사용자 관리로 간다.
  // 테스트 코드: PL-057
  it('admin이 /admin을 열면 사용자 관리로 간다', async () => {
    // when: /admin을 연다 (전제: admin으로 로그인)
    const { location } = await renderAt('/admin', { role: 'admin' })
    // then: 주소가 /admin/users다
    await waitFor(() => expect(location()).toBe('/admin/users'))
  })

  // Deal 등록·수정 화면은 sales·admin만 열고 user는 Deals 목록으로 간다.
  // 테스트 코드: PL-058
  it('Deal 등록·수정 화면은 sales와 admin만 열 수 있다', async () => {
    // when: sales가 /deals/new를 연다
    const sales = await renderAt('/deals/new', { role: 'sales' })
    await screen.findByRole('navigation', { name: '주 메뉴' })
    // then: 그 주소에 머문다
    expect(sales.location()).toBe('/deals/new')
    sales.unmount()

    // when: admin이 수정 화면 주소를 연다
    const admin = await renderAt('/deals/20261001-AB12/edit', { role: 'admin' })
    await screen.findByRole('navigation', { name: '주 메뉴' })
    // then: 그 주소에 머문다
    expect(admin.location()).toBe('/deals/20261001-AB12/edit')
    admin.unmount()

    // when: user가 /deals/new를 연다
    const viewer = await renderAt('/deals/new', { role: 'user' })
    // then: Deals 목록 주소가 된다
    await waitFor(() => expect(viewer.location()).toMatch(DEFAULT_DEALS_URL_PATTERN))
    viewer.unmount()

    // when: user가 수정 화면 주소를 연다
    const viewerEdit = await renderAt('/deals/20261001-AB12/edit', { role: 'user' })
    // then: Deals 목록 주소가 된다
    await waitFor(() => expect(viewerEdit.location()).toMatch(DEFAULT_DEALS_URL_PATTERN))
  })

  // Deal 상세·Forecast·Dashboard는 모든 역할이 연다.
  // 테스트 코드: PL-059
  it.each(['admin', 'sales', 'user'] as const)('%s는 Deal 상세·Forecast·Dashboard를 열 수 있다', async (role) => {
    for (const url of ['/deals/20261001-AB12', '/forecast', '/dashboard']) {
      // when: Deal 상세, Forecast, Dashboard 주소를 차례로 연다 (전제: admin·sales·user 각각)
      const opened = await renderAt(url, { role })
      await screen.findByRole('navigation', { name: '주 메뉴' })
      // then: 주소가 그대로이고 화면 틀이 보인다
      expect(opened.location()).toBe(url)
      opened.unmount()
    }
  })

  // 옛 사용자 관리·설정 주소는 Admin 새 주소로 간다.
  // 테스트 코드: PL-055
  it.each([
    ['/users', '/admin/users'],
    ['/settings', '/admin/integrations'],
  ])('옛 주소 %s는 admin에게 %s로 이동한다', async (from, to) => {
    // when: 옛 주소를 연다
    const { location } = await renderAt(from, { role: 'admin' })
    // then: Admin 새 주소가 된다
    await waitFor(() => expect(location()).toBe(to))
  })

  // 정의되지 않은 주소와 폐지된 주소는 Deals 목록으로 간다.
  // 테스트 코드: PL-054
  it.each(['/customers', '/partners', '/actions', '/nowhere'])('폐지된 주소 %s는 Deals 목록으로 간다', async (url) => {
    // when: 정의되지 않은 주소를 연다 (전제: 로그인한 기본 사용자)
    const { location } = await renderAt(url)
    // then: Deals 목록 주소가 된다
    await waitFor(() => expect(location()).toMatch(DEFAULT_DEALS_URL_PATTERN))
  })

  // 로그아웃하면 로그인 화면으로 간다.
  it('로그아웃하면 로그인 화면으로 간다', async () => {
    // given: sales로 로그인한 Deals 화면
    const { user, location } = await renderAt('/deals', { role: 'sales' })
    // when: 사용자 메뉴에서 로그아웃한다
    await logOutFromMenu(user)
    // then: 주소가 /login이 된다
    await waitFor(() => expect(location()).toBe('/login'))
  })
})
