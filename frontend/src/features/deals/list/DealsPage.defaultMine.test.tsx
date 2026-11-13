import { act, screen, waitFor, within } from '@testing-library/react'
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'
import { gateway } from '../../../gateway'
import { listMemoryKey } from '../../../shared/model/dealListMemory'
import { resetMock } from '../../../test/fake/default'
import { USER_ID } from '../../../test/fake/seed/ids'
import { SEED_PASSWORD } from '../../../test/fake/seed/users'
import { renderAt } from '../../../test/mockApp'
import { dataRows, rowOf } from './testHelpers'
// Dashboard에서 시작하는 테스트가 있다. App은 DashboardPage를 React.lazy로 불러오므로 청크 로딩이 findBy 기본 대기(1초)를 넘기지 않게 미리 읽어 둔다.
import '../../dashboard/DashboardPage'

/**
 * sales의 기본 조건 = 올해 + 내 딜만(`year=<올해>&mine=1`). 조건이 하나도 없는 주소로 들어오거나 초기화할 때만 적용한다.
 * 시드 Deal 날짜는 기준일 상대값이라 앱 시계를 고정한다. 화면 테스트의 기본 로그인 역할은 sales(KIM)다.
 */
const NOW = '2026-10-15T09:00:00+09:00'
const MINE_DEFAULT = '/deals?year=2026&mine=1'

beforeEach(() => resetMock({ now: NOW }))
afterEach(() => {
  vi.restoreAllMocks()
  resetMock({ now: null })
})

const mainMenu = () => within(screen.getByRole('navigation', { name: '주 메뉴' }))
const mineBox = () => screen.getByRole('checkbox', { name: '내 딜만' })
const settle = () =>
  act(async () => {
    await new Promise((resolve) => setTimeout(resolve, 30))
  })

describe('sales의 조건 없는 진입', () => {
  // sales의 조건 없는 /deals는 올해 + 내 딜만 주소로 바뀌고 mine 없는 요청은 나가지 않는다
  // 테스트 코드: DL-101
  it('replaces the bare list url with this year and my deals only, and never asks the server without mine', async () => {
    // given: 게이트웨이 list를 관찰한다 (전제: 조건 기억 없음, 앱 시계 2026-10-15의 KIM)
    const list = vi.spyOn(gateway.deals, 'list')

    // when: 조건 없는 /deals로 들어간다
    const { location } = await renderAt('/deals')
    await screen.findByText(/총 \d+건/)

    // then: 주소가 /deals?year=2026&mine=1이고 내 딜만이 체크되며, 모든 요청이 year 2026·mine true를 싣는다
    await waitFor(() => expect(location()).toBe(MINE_DEFAULT))
    expect(mineBox()).toBeChecked()
    expect(list.mock.calls.length).toBeGreaterThan(0)
    for (const [query] of list.mock.calls) expect(query).toMatchObject({ year: 2026, mine: true })
  })

  // 기본 조건 목록에는 KIM의 Deal만 보인다
  // 테스트 코드: DL-101
  it('lists only the deals of the signed-in sales', async () => {
    // when: 조건 없는 /deals로 들어간다 (전제: KIM·PARK의 올해 Deal이 있는 시드)
    await renderAt('/deals')

    // then: KIM의 Deal은 보이고 PARK의 Deal은 보이지 않는다
    expect(await rowOf(/한빛은행 ITDR 도입/)).toBeVisible()
    expect(screen.queryByRole('row', { name: /미래전자 EDR 교체/ })).not.toBeInTheDocument()
  })

  // 기본 조건 교체는 브라우저 이력에 남지 않는다
  // 테스트 코드: DL-101
  it('does not leave the bare list in the browser history', async () => {
    // given: Dashboard에서 시작한다
    const { user, location, goTo } = await renderAt('/dashboard')
    await screen.findByRole('heading', { name: 'Dashboard' })

    // when: 상단 메뉴 Deals를 눌러 들어온 뒤 뒤로 간다
    await user.click(mainMenu().getByRole('link', { name: 'Deals' }))
    await waitFor(() => expect(location()).toBe(MINE_DEFAULT))
    goTo(-1)

    // then: 조건 없는 주소가 아니라 /dashboard로 돌아간다
    await waitFor(() => expect(location()).toBe('/dashboard'))
  })

  // 루트 주소에서도 올해 + 내 딜만이다
  // 테스트 코드: DL-101
  it('applies the same default from the root address', async () => {
    // when: / 로 들어간다
    const { location } = await renderAt('/')

    // then: 주소가 /deals?year=2026&mine=1이 된다
    await waitFor(() => expect(location()).toBe(MINE_DEFAULT))
  })

  // 로그인 직후에도 올해 + 내 딜만이다
  // 테스트 코드: DL-101
  it('applies the same default right after a login', async () => {
    // given: 로그인 화면
    const { user, location } = await renderAt('/login', { role: null })
    await screen.findByRole('button', { name: '로그인' })

    // when: 영업 계정으로 로그인한다
    await user.type(screen.getByLabelText('아이디'), 'kim')
    await user.type(screen.getByLabelText('비밀번호'), SEED_PASSWORD)
    await user.click(screen.getByRole('button', { name: '로그인' }))

    // then: 주소가 /deals?year=2026&mine=1이 된다
    await waitFor(() => expect(location()).toBe(MINE_DEFAULT))
  })

  // 기억이 없으면 상단 메뉴 Deals도 올해 + 내 딜만이다
  // 테스트 코드: DL-101
  it('applies the same default from the top menu when nothing is remembered', async () => {
    // given: 기억된 목록 조건이 없는 Forecast 화면
    const { user, location } = await renderAt('/forecast')
    await screen.findByRole('heading', { name: 'Forecast' })

    // when: 상단 메뉴 Deals를 누른다
    await user.click(mainMenu().getByRole('link', { name: 'Deals' }))

    // then: 주소가 /deals?year=2026&mine=1이 된다
    await waitFor(() => expect(location()).toBe(MINE_DEFAULT))
  })

  // 기억이 없는 상세의 목록 링크도 올해 + 내 딜만이다
  // 테스트 코드: DL-101
  it('applies the same default to the back link of the detail page when nothing is remembered', async () => {
    // given: 기억이 없는 상세 화면
    const { user, location } = await renderAt('/deals/20000101-ZZZZ')

    // when: 'Deal 목록으로'를 누른다
    await user.click(await screen.findByRole('link', { name: 'Deal 목록으로' }))

    // then: 주소가 /deals?year=2026&mine=1이 된다
    await waitFor(() => expect(location()).toBe(MINE_DEFAULT))
  })
})

describe('sales의 초기화', () => {
  // 초기화는 올해 + 내 딜만으로 돌아가고 정렬은 지우며 그 조건을 기억한다
  // 테스트 코드: DL-102
  it('goes back to this year with my deals only as a new history entry and remembers it', async () => {
    // given: 다른 담당자·Status·정렬이 걸린 목록
    const start = `/deals?status=contract_completed&owner=${USER_ID.park}&sort=owner&order=asc`
    const { user, location, goTo } = await renderAt(start)
    await screen.findByText(/총 \d+건/)

    // when: 초기화 버튼을 누른다
    await user.click(screen.getByRole('button', { name: '초기화' }))

    // then: 주소가 올해 + 내 딜만이고 내 딜만만 체크되며 Status가 비고 정렬은 최종 업데이트 내림차순이다
    await waitFor(() => expect(location()).toBe(MINE_DEFAULT))
    expect(mineBox()).toBeChecked()
    expect(screen.getByLabelText('Status')).toHaveDisplayValue('전체')
    expect(screen.getByLabelText('연도')).toHaveDisplayValue('2026')
    expect(await screen.findByRole('columnheader', { name: '최종 업데이트' })).toHaveAttribute('aria-sort', 'descending')
    // then: 기억도 같은 조건이고 상단 메뉴 Deals 주소도 같다
    expect(window.sessionStorage.getItem(listMemoryKey(USER_ID.kim))).toBe('year=2026&mine=1')
    expect(mainMenu().getByRole('link', { name: 'Deals' })).toHaveAttribute('href', MINE_DEFAULT)

    // when: 뒤로 간다
    goTo(-1)

    // then: 초기화 전 조건으로 돌아간다
    await waitFor(() => expect(location()).toBe(start))
  })
})

describe('내 딜만 끄기', () => {
  // 내 딜만을 끄면 mine이 지워지고 기본 조건으로 되돌아가지 않는다
  // 테스트 코드: DL-103
  it('removes mine from the url without bringing the default back', async () => {
    // given: 기본 조건 목록 (전제: KIM·PARK의 올해 Deal이 있는 시드)
    const { user, location } = await renderAt(MINE_DEFAULT)
    await rowOf(/한빛은행 ITDR 도입/)
    expect(screen.queryByRole('row', { name: /미래전자 EDR 교체/ })).not.toBeInTheDocument()

    // when: 내 딜만 체크를 끈다
    await user.click(mineBox())

    // then: 주소가 /deals?year=2026이 되고 다시 mine이 붙지 않으며 PARK의 Deal도 보인다
    await waitFor(() => expect(location()).toBe('/deals?year=2026'))
    await settle()
    expect(location()).toBe('/deals?year=2026')
    expect(mineBox()).not.toBeChecked()
    expect(await rowOf(/미래전자 EDR 교체/)).toBeVisible()
  })

  // 끈 뒤 상세에 갔다 목록 링크로 돌아와도 mine이 붙지 않는다
  // 테스트 코드: DL-103
  it('keeps mine off after a detail round trip through the list link', async () => {
    // given: 내 딜만을 끈 목록에서 상세로 들어간 상태
    const { user, location } = await renderAt(MINE_DEFAULT)
    await rowOf(/한빛은행 ITDR 도입/)
    await user.click(mineBox())
    await waitFor(() => expect(location()).toBe('/deals?year=2026'))
    const link = within(await rowOf(/한빛은행 ITDR 도입/)).getByRole('link', { name: '한빛은행 ITDR 도입' })
    await user.click(link)
    await screen.findByRole('heading', { level: 1, name: '한빛은행 ITDR 도입' })

    // when: 상세의 목록 링크를 누른다
    await user.click(screen.getByRole('link', { name: '← 목록' }))

    // then: 주소가 /deals?year=2026 그대로다
    await waitFor(() => expect(location()).toBe('/deals?year=2026'))
    await settle()
    expect(location()).toBe('/deals?year=2026')
  })

  // 끈 뒤 다른 화면에 다녀와 상단 메뉴로 와도 mine이 붙지 않는다
  // 테스트 코드: DL-103
  it('keeps mine off when coming back through the top menu', async () => {
    // given: 내 딜만을 끈 목록에서 Forecast 화면으로 간 상태
    const { user, location } = await renderAt(MINE_DEFAULT)
    await rowOf(/한빛은행 ITDR 도입/)
    await user.click(mineBox())
    await waitFor(() => expect(location()).toBe('/deals?year=2026'))
    await user.click(mainMenu().getByRole('link', { name: 'Forecast' }))
    await screen.findByRole('heading', { name: 'Forecast' })

    // when: 상단 메뉴 Deals를 누른다
    await user.click(mainMenu().getByRole('link', { name: 'Deals' }))

    // then: 주소가 /deals?year=2026이다
    await waitFor(() => expect(location()).toBe('/deals?year=2026'))
    await settle()
    expect(location()).toBe('/deals?year=2026')
  })
})

describe('조건이 있는 주소와 기억된 조건', () => {
  // 조건이 있는 주소에는 내 딜만을 더하지 않는다
  // 테스트 코드: DL-104
  it.each([
    '/deals?year=2026&quarter=3&forecast=best%2Ccommit',
    '/deals?year=all',
    `/deals?owner=${USER_ID.park}`,
  ])('keeps %s as it is and sends no mine', async (url) => {
    // given: 게이트웨이 list를 관찰한다
    const list = vi.spyOn(gateway.deals, 'list')

    // when: 조건이 있는 주소로 들어간다
    const { location } = await renderAt(url)
    await screen.findByText(/총 \d+건/)
    await settle()

    // then: 주소가 그대로이고 내 딜만이 꺼져 있으며 어떤 요청에도 mine이 없다
    expect(location()).toBe(url)
    expect(mineBox()).not.toBeChecked()
    expect(list.mock.calls.length).toBeGreaterThan(0)
    for (const [query] of list.mock.calls) expect(query).not.toHaveProperty('mine')
  })

  // 기억된 조건이 있으면 상단 메뉴는 그 조건으로 가고 내 딜만을 더하지 않는다
  // 테스트 코드: DL-104
  it('goes to the remembered condition from the top menu without adding mine', async () => {
    // given: 기억된 조건 status=prospecting이 있고 목록이 아닌 화면
    window.sessionStorage.setItem(listMemoryKey(USER_ID.kim), 'status=prospecting')
    const { user, location } = await renderAt('/forecast')
    await screen.findByRole('heading', { name: 'Forecast' })

    // when: 상단 메뉴 Deals를 누른다
    await user.click(mainMenu().getByRole('link', { name: 'Deals' }))

    // then: 기억된 조건 주소 그대로이고 내 딜만은 꺼져 있다
    await waitFor(() => expect(location()).toBe('/deals?status=prospecting'))
    await settle()
    expect(location()).toBe('/deals?status=prospecting')
    expect(mineBox()).not.toBeChecked()
  })
})

describe('역할별 기본 조건', () => {
  // user의 기본 조건은 올해만이고 내 딜만이 꺼져 있다
  // 테스트 코드: DL-105
  it('gives a user this year only with my deals off', async () => {
    // given: 게이트웨이 list를 관찰한다 (전제: user 역할, 조건 기억 없음)
    const list = vi.spyOn(gateway.deals, 'list')

    // when: 조건 없는 /deals로 들어간다
    const { location } = await renderAt('/deals', { role: 'user' })
    await screen.findByText(/총 \d+건/)

    // then: 주소가 /deals?year=2026이고 내 딜만이 꺼진 채 올해 Deal이 보이며 요청에 mine이 없다
    await waitFor(() => expect(location()).toBe('/deals?year=2026'))
    expect(mineBox()).not.toBeChecked()
    expect(dataRows().length).toBeGreaterThan(0)
    for (const [query] of list.mock.calls) expect(query).not.toHaveProperty('mine')
  })

  // 담당 Deal이 없는 sales는 빈 조건 문구를 본다
  // 테스트 코드: DL-105
  it('shows the empty condition message to a sales who owns no deal', async () => {
    // when: 조건 없는 /deals로 들어간다 (전제: Deal이 하나도 없는 시드의 sales)
    const { location } = await renderAt('/deals', { seed: 'empty' })

    // then: 주소가 /deals?year=2026&mine=1이고 '조건에 맞는 Deal이 없습니다.'가 보인다
    await waitFor(() => expect(location()).toBe(MINE_DEFAULT))
    expect(await screen.findByText('조건에 맞는 Deal이 없습니다.')).toBeVisible()
    expect(screen.queryByText('등록된 Deal이 없습니다.')).not.toBeInTheDocument()
  })
})
