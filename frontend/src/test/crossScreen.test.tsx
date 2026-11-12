import { screen, waitFor, within } from '@testing-library/react'
import { describe, expect, it } from 'vitest'
import { ALL_DEALS } from '../features/deals/list/testHelpers'
import { listMemoryKey } from '../shared/model/dealListMemory'
import { USER_ID } from './fake/seed/ids'
import { renderAt } from './mockApp'
// App은 DashboardPage를 React.lazy로 불러오므로 청크 로딩이 findBy 기본 대기(1초)를 넘기지 않게 미리 읽어 둔다 (Dashboard).
import '../features/dashboard/DashboardPage'

type Rendered = Awaited<ReturnType<typeof renderAt>>

/** 상단 메뉴 링크로 이동한다(같은 앱·같은 쿼리 캐시 안에서 화면을 오가며 반영을 본다). */
async function goTo(user: Rendered['user'], menu: string) {
  await user.click(within(screen.getByRole('navigation', { name: '주 메뉴' })).getByRole('link', { name: menu }))
}

/** 목록 밖에서 시작해 메뉴로 Deals에 들어가는 테스트가 전체 Deal을 보도록, 기억한 목록 조건을 '연도 전체'로 둔다(기억이 없으면 기본 조건 올해가 붙는다). */
function rememberAllDeals(userId: number = USER_ID.root) {
  window.sessionStorage.setItem(listMemoryKey(userId), 'year=all')
}

async function renameCode(user: Rendered['user'], rowName: RegExp, next: string) {
  const row = within(await screen.findByRole('row', { name: rowName }))
  await user.click(row.getByRole('button', { name: '이름 수정' }))
  const input = screen.getByLabelText('코드 이름')
  await user.clear(input)
  await user.type(input, next)
  await user.click(screen.getByRole('button', { name: '저장' }))
  await screen.findByRole('row', { name: new RegExp(next) })
}

describe('Admin 변경이 다른 화면에 반영된다 (6-a Status/Forecast 이름)', () => {
  // Admin이 Status 이름을 바꾸면 Deals 필터·목록 행·상세에 새 이름이 보인다.
  it('shows a renamed Status in the Deals filter, the list rows and the detail', async () => {
    // given: admin이 Admin 화면에서 '가격협상' Status를 '가격 협의'로 바꿨다
    rememberAllDeals()
    const { user } = await renderAt('/admin/deal', { role: 'admin' })
    await renameCode(user, /가격협상/, '가격 협의')

    // when: Deals 목록을 연다
    await goTo(user, 'Deals')
    // then: 필터 선택지에 '가격 협의'만 있고 옛 이름은 없다
    const filter = await screen.findByLabelText('Status')
    await within(filter).findByRole('option', { name: '가격 협의' })
    expect(within(filter).queryByRole('option', { name: '가격협상' })).not.toBeInTheDocument()
    // when: 새 이름으로 필터한다
    await user.selectOptions(filter, '가격 협의')
    // then: 목록 행에 '가격 협의'가 보인다
    await waitFor(() => expect(screen.getByText('총 4건')).toBeVisible())
    const buttons = screen.getAllByRole('button', { name: /Status 편집/ })
    expect(buttons.length).toBeGreaterThan(0)
    for (const b of buttons) expect(b).toHaveTextContent('가격 협의')

    // when: 첫 Deal 상세를 연다
    const dealLink = screen.getAllByRole('link').find((a) => /^\/deals\/\d{8}-/.test(a.getAttribute('href') ?? ''))
    await user.click(dealLink!)
    // then: 상세 Status에 '가격 협의'가 보인다
    const statusButton = await screen.findByRole('button', { name: 'Status 수정' })
    expect(statusButton).toHaveTextContent('가격 협의')
    // when: Status 편집을 연다
    await user.click(statusButton)
    // then: 선택지와 선택 값이 '가격 협의'다
    const detailStatus = await screen.findByLabelText('Status')
    await within(detailStatus).findByRole('option', { name: '가격 협의' })
    expect(detailStatus).toHaveDisplayValue('가격 협의')
  })

  // Admin이 Forecast 이름을 바꾸면 Forecast 화면과 Deals 목록에 새 이름이 보인다.
  it('shows a renamed Forecast in the Forecast screen and the Deals list', async () => {
    // given: admin이 Commit Forecast 코드를 '확정예상'으로 바꿨다
    rememberAllDeals()
    const { user } = await renderAt('/admin/deal', { role: 'admin' })
    await user.click(await screen.findByRole('tab', { name: 'Forecast 코드' }))
    await renameCode(user, /Commit/, '확정예상')

    // when: Forecast 화면을 연다
    await goTo(user, 'Forecast')
    // then: Forecast 열 머리글에 '확정예상'이 보이고 옛 이름은 없다
    expect(await screen.findByRole('columnheader', { name: /확정예상/ })).toBeVisible()
    expect(screen.queryByRole('columnheader', { name: /^Commit/ })).not.toBeInTheDocument()

    // when: Deals 목록에서 Forecast 필터 패널을 연다
    await goTo(user, 'Deals')
    const bar = within(await screen.findByRole('search', { name: 'Deal 필터' }))
    await user.click(await bar.findByRole('button', { name: /^Forecast / }))
    const panel = within(await screen.findByRole('group', { name: 'Forecast' }))
    // then: 옛 이름 선택지가 없다
    expect(panel.queryByRole('checkbox', { name: 'Commit' })).not.toBeInTheDocument()
    // when: 새 이름 '확정예상'으로 필터한다
    await user.click(await panel.findByRole('checkbox', { name: '확정예상' }))
    // then: 목록 행에 '확정예상'이 보인다
    await waitFor(() => expect(screen.getAllByRole('button', { name: /Forecast 편집/ }).length).toBeGreaterThan(0))
    for (const b of screen.getAllByRole('button', { name: /Forecast 편집/ })) expect(b).toHaveTextContent('확정예상')
  })
})

describe('contacts 수정이 Deal 화면에 반영된다 (6-b)', () => {
  // 연락처를 고치면 그 연락처를 쓰는 Deal의 Quick View와 상세에 새 값이 보인다
  // 테스트 코드: CT-087
  it('shows the edited title in the list quick view and in the deal detail', async () => {
    // given: Deal이 쓰는 연락처 '정민수'를 admin이 관리 화면에서 연다
    rememberAllDeals()
    const { user } = await renderAt('/admin/contacts', { role: 'admin' })
    const keyword = await screen.findByLabelText('검색어')
    await user.type(keyword, '정민수')
    await user.click(screen.getByRole('button', { name: '검색' }))
    const row = within(await screen.findByRole('row', { name: /정민수/ }))
    await user.click(row.getByRole('button', { name: '수정' }))
    const title = await screen.findByLabelText('직급')
    // when: 직급을 '이사'로 바꿔 저장한다
    await user.clear(title)
    await user.type(title, '이사')
    await user.click(screen.getByRole('button', { name: '저장' }))
    // then: 수정 폼이 닫힌다
    await waitFor(() => expect(screen.queryByRole('form', { name: '연락처 수정' })).not.toBeInTheDocument())

    // when: Deals 목록에서 해당 Deal을 검색해 빠른 보기를 연다
    await goTo(user, 'Deals')
    await user.type(await screen.findByLabelText('키워드'), '한빛은행 ITDR')
    await user.click(screen.getByRole('button', { name: '검색' }))
    const deal = await screen.findByRole('row', { name: /한빛은행 ITDR 도입/ })
    await user.click(within(deal).getByRole('button', { name: /빠른 보기/ }))
    // then: Quick View에 '이사'가 보인다
    expect(await screen.findByText(/정민수.*이사/)).toBeVisible()

    // when: Deal 상세를 연다
    await user.click(screen.getByRole('link', { name: '한빛은행 ITDR 도입' }))
    await screen.findByRole('heading', { level: 1, name: '한빛은행 ITDR 도입' })
    // then: 연락처 카드에 '이사'가 보인다
    const card = (await screen.findAllByText('정민수'))[0]!.closest('dl')!
    expect(within(card).getByText('직급').nextElementSibling).toHaveTextContent('이사')
  })
})

describe('Label 관리에서 만든 Label이 Deal 폼에 나타난다 (6-c)', () => {
  // BANT Label 관리에서 만든 Label이 Deal 등록 폼에 나타난다.
  it('offers a new Budget label in the Deal registration form', async () => {
    // given: admin이 Budget에 '분기 예산' Label을 추가했다
    const { user } = await renderAt('/admin/deal', { role: 'admin' })
    await user.click(await screen.findByRole('tab', { name: 'BANT Label' }))
    const budget = within(await screen.findByRole('region', { name: 'Budget' }))
    await user.type(budget.getByLabelText('새 Label 이름'), '분기 예산')
    await user.click(budget.getByRole('button', { name: '추가' }))
    await screen.findByText('분기 예산')

    // when: Deal 등록 폼에서 Budget 선택을 연다
    await goTo(user, 'Deals')
    await user.click(await screen.findByRole('link', { name: '+ Deal 등록' }))
    await user.click(await screen.findByRole('combobox', { name: 'Budget' }))
    // then: '분기 예산' 선택지가 보인다
    await screen.findByRole('option', { name: '분기 예산' })
  })
})

describe('Reports 메뉴 (Reports)', () => {
  // 메뉴에서 Reports를 열면 준비 중 화면이 아니라 빈 목록이 나온다.
  it('opens the empty report list from the menu instead of a coming soon page', async () => {
    // given: Deals 목록을 연 상태
    const { user, location } = await renderAt(ALL_DEALS)
    await screen.findByRole('row', { name: /한빛은행 ITDR 도입/ })
    // when: 메뉴에서 Reports를 누른다
    await goTo(user, 'Reports')
    // then: 주소가 /reports이고 제목과 빈 목록 안내가 보이며 준비 중 문구는 없다
    expect(location()).toBe('/reports')
    expect(await screen.findByRole('heading', { level: 1, name: 'Reports' })).toBeVisible()
    expect(screen.getByText(/아직 저장한 리포트가 없습니다/)).toBeVisible()
    expect(screen.queryByText(/준비 중입니다/)).not.toBeInTheDocument()
  })
})

describe('Dashboard 메뉴', () => {
  // 메뉴에서 Dashboard를 열면 준비 중 화면이 아니라 Dashboard가 나온다.
  // 테스트 코드: DSH-025
  it('메뉴에서 Dashboard를 열면 준비 중 화면 대신 Dashboard가 나온다', async () => {
    // given: Deals 목록을 연 상태
    const { user, location } = await renderAt(ALL_DEALS)
    await screen.findByRole('row', { name: /한빛은행 ITDR 도입/ })
    // when: 메뉴에서 Dashboard를 누른다
    await goTo(user, 'Dashboard')
    // then: 주소가 /dashboard이고 제목과 Status 탭이 보이며 준비 중 문구는 없다
    expect(location()).toBe('/dashboard')
    expect(await screen.findByRole('heading', { level: 1, name: 'Dashboard' })).toBeVisible()
    expect(await screen.findByRole('tab', { name: 'Status' })).toBeVisible()
    expect(screen.queryByText(/준비 중입니다/)).not.toBeInTheDocument()
  })
})

describe('Admin의 Action 유형 변경이 Deal 상세에 반영된다', () => {
  async function openFirstDeal(user: Rendered['user']) {
    await goTo(user, 'Deals')
    const dealLink = (await screen.findAllByRole('link')).find((a) => /^\/deals\/\d{8}-/.test(a.getAttribute('href') ?? ''))
    await user.click(dealLink!)
    await user.click(await screen.findByRole('tab', { name: 'Actions' }))
    await screen.findByRole('table', { name: 'Action 목록' })
  }

  // Deal 관리에서 추가한 Action 유형이 Action 폼의 후보로 나온다.
  it('offers a type added in Deal management as a candidate in the Action form', async () => {
    // given: admin이 Action 유형 '웨비나'를 추가했다
    rememberAllDeals()
    const { user } = await renderAt('/admin/deal?tab=action-type', { role: 'admin' })
    const add = await screen.findByRole('form', { name: 'Action 유형 추가' })
    await user.type(within(add).getByLabelText('새 유형 이름'), '웨비나')
    await user.click(within(add).getByRole('button', { name: '추가' }))
    await screen.findByText('웨비나')

    // when: 첫 Deal의 Action 추가 폼에서 유형 목록을 연다
    await openFirstDeal(user)
    await user.click(await screen.findByRole('button', { name: 'Action 추가' }))
    const dialog = await screen.findByRole('dialog', { name: 'Action 추가' })
    await user.click(within(within(dialog).getByRole('form', { name: 'Action 추가' })).getByLabelText('유형'))

    // then: '웨비나'가 후보로 보인다
    expect(within(await screen.findByRole('listbox', { name: '유형' })).getByRole('option', { name: '웨비나' })).toBeVisible()
  })

  // Action 유형 이름을 바꾸면 Deal의 Actions 표에 새 이름이 보인다.
  it('shows a renamed type in the Actions table of a deal', async () => {
    // given: admin이 Action 유형 '협상'을 '가격 협상'으로 바꿨다
    rememberAllDeals()
    const { user } = await renderAt('/admin/deal?tab=action-type', { role: 'admin' })
    const row = within(await screen.findByRole('row', { name: /협상/ }))
    await user.click(row.getByRole('button', { name: '이름 수정' }))
    const input = screen.getByLabelText('유형 이름')
    await user.clear(input)
    await user.type(input, '가격 협상')
    await user.click(screen.getByRole('button', { name: '저장' }))
    await screen.findByRole('row', { name: /가격 협상/ })

    // when: Deal 상세의 Actions 탭을 연다
    await goTo(user, 'Deals')
    await user.click(await screen.findByRole('link', { name: '한빛은행 ITDR 도입' }))
    await user.click(await screen.findByRole('tab', { name: 'Actions' }))
    const table = await screen.findByRole('table', { name: 'Action 목록' })

    // then: 표에 '가격 협상'이 보이고 옛 이름은 없다
    expect(await within(table).findByText('가격 협상')).toBeVisible()
    expect(within(table).queryByText('협상')).not.toBeInTheDocument()
  })
})
