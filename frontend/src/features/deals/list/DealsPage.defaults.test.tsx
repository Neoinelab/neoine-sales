import { act, screen, waitFor, within } from '@testing-library/react'
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'
import { gateway } from '../../../gateway'
import { listMemoryKey } from '../../../shared/model/dealListMemory'
import { defaultDealsUrl } from '../../../test/dealsUrl'
import { resetMock } from '../../../test/fake/default'
import { USER_ID } from '../../../test/fake/seed/ids'
import { SEED_PASSWORD } from '../../../test/fake/seed/users'
import { renderAt } from '../../../test/mockApp'
import { clearQuarter, dataRows, quarterButton, rowOf } from './testHelpers'
// 기록 테스트는 /dashboard에서 시작한다. App은 DashboardPage를 React.lazy로 불러오므로 청크 로딩이 findBy 기본 대기(1초)를 넘기지 않게 미리 읽어 둔다.
import '../../dashboard/DashboardPage'

/**
 * 기본 조건 = 연도 전체(`year=all`), Quarter 없음, 정렬은 최종 업데이트 최신순(admin 기준. sales는 여기에 내 딜만이 더해진다).
 * 조건이 하나도 없는 주소로 목록에 들어오거나 초기화할 때만 적용한다(DL-R19, 2026-11-13: 예전 기본은 올해).
 * 시드 날짜는 기준일 상대값이라 기준일을 고정한다. 앱 시계는 기본 조건에 영향이 없다.
 */
const NOW = '2026-10-15T09:00:00+09:00'

beforeEach(() => resetMock({ now: NOW }))
afterEach(() => {
  vi.restoreAllMocks()
  resetMock({ now: null })
})

const optionNames = (select: HTMLElement) => within(select).getAllByRole('option').map((o) => o.textContent)
/** 이 파일의 기본 조건 테스트는 admin(연도 전체)이다. sales의 '올해 + 내 딜만'은 DealsPage.defaultMine.test.tsx(DL-101~105). */
const ADMIN = { role: 'admin' } as const
const mainMenu = () => within(screen.getByRole('navigation', { name: '주 메뉴' }))

describe('조건 없는 목록 진입', () => {
  // 조건 없는 /deals는 연도 전체 기본 조건 주소로 바뀌고 최종 업데이트 최신순으로 보인다
  // 테스트 코드: DL-055
  it('replaces the bare list url with all years and no quarter', async () => {
    // when: 조건 없는 /deals로 들어간다 (전제: 서버 시계 2026-10-15의 로그인한 admin)
    const { location } = await renderAt('/deals', ADMIN)

    // then: 주소가 /deals?year=all로 바뀌고 연도 전체·Quarter 전체·월 전체·월 선택지 13개가 보인다
    await waitFor(() => expect(location()).toBe('/deals?year=all'))
    expect(await screen.findByLabelText('연도')).toHaveDisplayValue('전체')
    expect(quarterButton('전체')).toBeInTheDocument()
    expect(screen.getByLabelText('월')).toHaveDisplayValue('전체')
    expect(optionNames(screen.getByLabelText('월'))).toHaveLength(13)
  })

  // 기본 조건 목록 요청에는 연도·분기가 없고 정렬은 최종 업데이트 내림차순이다
  // 테스트 코드: DL-055
  it('never asks the server with a year or quarter and sorts by last update descending', async () => {
    // given: 게이트웨이 list를 관찰한다
    const list = vi.spyOn(gateway.deals, 'list')

    await renderAt('/deals', ADMIN)
    // when: 조건 없는 /deals로 들어간다
    await screen.findByText(/총 \d+건/)

    // then: 모든 요청이 연도·분기 없이 최종 업데이트 내림차순(정렬 생략 = 기본)이다
    expect(list.mock.calls.length).toBeGreaterThan(0)
    for (const [query] of list.mock.calls) {
      expect(query).not.toHaveProperty('year')
      expect(query).not.toHaveProperty('quarters')
      expect(query.sort ?? 'lastUpdatedAt').toBe('lastUpdatedAt')
      expect(query.order ?? 'desc').toBe('desc')
    }
  })

  // 기본 조건 목록은 모든 연도의 Deal을 최종 업데이트 최신순으로 보인다
  // 테스트 코드: DL-055
  it('lists the deals of every year by last update, newest first', async () => {
    // given: 2026·2027년 매출 Deal이 모두 있고 최종 업데이트일이 서로 다른 Fake
    const all = await gateway.deals.list({ limit: 200 })
    const years = new Set(all.items.map((d) => d.revenueDate.slice(0, 4)))
    expect(years.has('2026')).toBe(true)
    expect(years.has('2027')).toBe(true)
    const expected = await gateway.deals.list({ limit: 20, sort: 'lastUpdatedAt', order: 'desc' })

    // when: 조건 없는 /deals로 들어간다
    await renderAt('/deals', ADMIN)

    // then: '총 N건'이 전체 Deal 수이고 행이 최종 업데이트 최신순이며 머리글이 내림차순이다
    expect(await screen.findByText(`총 ${all.total}건`)).toBeVisible()
    const names = dataRows().map((row) => row.textContent ?? '')
    expect(names).toHaveLength(expected.items.length)
    expected.items.forEach((deal, i) => expect(names[i]).toContain(deal.name))
    expect(screen.getByRole('columnheader', { name: '최종 업데이트' })).toHaveAttribute('aria-sort', 'descending')
  })

  // 빈 값·공백 값은 없는 조건으로 보고 기본 조건이 된다
  // 테스트 코드: DL-055
  it('treats an empty value and a blank value as no condition', async () => {
    // when: /deals?q=&solution=%20로 들어간다 (전제: 값이 비었거나 공백뿐인 q·solution 키 주소)
    const { location } = await renderAt('/deals?q=&solution=%20', ADMIN)

    // then: 주소가 /deals?year=all로 바뀐다
    await waitFor(() => expect(location()).toBe('/deals?year=all'))
  })

  // 기본 조건은 정렬을 이어받고 page·모르는 키를 버린다
  // 테스트 코드: DL-056
  it('keeps the sort and drops the page and unknown keys when it fills the default', async () => {
    // when: /deals?sort=owner&order=asc&page=3&outcome=open으로 들어간다 (전제: 정렬·page·예전 outcome 키만 있는 주소)
    const { location } = await renderAt('/deals?sort=owner&order=asc&page=3&outcome=open', ADMIN)

    // then: 주소가 정렬만 남은 기본 조건이 되고 담당자 머리글이 오름차순이다
    await waitFor(() => expect(location()).toBe('/deals?year=all&sort=owner&order=asc'))
    expect(await screen.findByRole('columnheader', { name: '담당자' })).toHaveAttribute('aria-sort', 'ascending')
  })

  // 기본 조건 교체는 브라우저 이력에 남지 않는다
  // 테스트 코드: DL-056
  it('does not leave the bare list in the browser history', async () => {
    // given: Dashboard에서 시작한다
    const { user, location, goTo } = await renderAt('/dashboard', ADMIN)
    await screen.findByRole('heading', { name: 'Dashboard' })

    // when: 상단 메뉴 Deals를 눌러 들어온 뒤 뒤로 간다
    await user.click(mainMenu().getByRole('link', { name: 'Deals' }))
    // then: 조건 없는 주소가 아니라 /dashboard로 돌아간다
    await waitFor(() => expect(location()).toBe('/deals?year=all'))
    goTo(-1)

    await waitFor(() => expect(location()).toBe('/dashboard'))
  })
})

describe('앱 시계와 무관', () => {
  // 기본 조건은 앱 시계의 연말·새해 경계에서도 연도 전체다
  // 테스트 코드: DL-055
  it.each(['2030-06-15T09:00:00+09:00', '2027-01-01T00:10:00+09:00', '2026-12-31T23:50:00+09:00'])(
    'is the same all-years url with the app clock %s',
    async (now) => {
      // given: 서버 시계를 연말·새해 경계 시각으로 둔다
      resetMock({ now })

      // when: 조건 없는 /deals로 들어간다
      const { location } = await renderAt('/deals', ADMIN)

      // then: 주소가 시계와 무관하게 /deals?year=all이다
      await waitFor(() => expect(location()).toBe('/deals?year=all'))
      expect(location()).toBe(defaultDealsUrl(now, '', 'admin'))
    },
  )
})

describe('여러 진입점', () => {
  // 루트 주소에서도 기본 조건이 적용된다
  // 테스트 코드: DL-057
  it('applies the default from the root address', async () => {
    // when: / 로 들어간다 (전제: 로그인한 admin)
    const { location } = await renderAt('/', ADMIN)

    // then: 주소가 /deals?year=all이 된다
    await waitFor(() => expect(location()).toBe('/deals?year=all'))
  })

  // 로그인 직후에도 기본 조건이 적용된다
  // 테스트 코드: DL-057
  it('applies the default right after a login', async () => {
    // given: 로그인 화면
    const { user, location } = await renderAt('/login', { role: null })
    await screen.findByRole('button', { name: '로그인' })

    // when: 아이디·비밀번호로 로그인한다
    await user.type(screen.getByLabelText('아이디'), 'root')
    await user.type(screen.getByLabelText('비밀번호'), SEED_PASSWORD)
    await user.click(screen.getByRole('button', { name: '로그인' }))

    // then: 주소가 /deals?year=all이 된다
    await waitFor(() => expect(location()).toBe('/deals?year=all'))
  })

  // 기억이 없으면 상단 메뉴 Deals도 기본 조건이다
  // 테스트 코드: DL-057
  it('applies the default when the top menu has no remembered condition', async () => {
    // given: 기억된 목록 조건이 없는 Forecast 화면
    const { user, location } = await renderAt('/forecast', ADMIN)
    await screen.findByRole('heading', { name: 'Forecast' })
    expect(mainMenu().getByRole('link', { name: 'Deals' })).toHaveAttribute('href', '/deals')

    // when: 상단 메뉴 Deals를 누른다
    await user.click(mainMenu().getByRole('link', { name: 'Deals' }))

    // then: 주소가 /deals?year=all이 된다
    await waitFor(() => expect(location()).toBe('/deals?year=all'))
  })

  // 예전 outcome만 기억돼 있으면 기본 조건이다
  // 테스트 코드: DL-057
  it('applies the default when the remembered search has only an old outcome', async () => {
    // given: 예전 outcome 키만 기억돼 있고 없는 Deal의 상세 화면
    window.sessionStorage.setItem(listMemoryKey(USER_ID.root), 'outcome=open')
    const { user, location } = await renderAt('/deals/20000101-ZZZZ', ADMIN)
    const back = await screen.findByRole('link', { name: 'Deal 목록으로' })
    expect(back).toHaveAttribute('href', '/deals')

    // when: 상세의 'Deal 목록으로'를 누른다
    await user.click(back)

    // then: 주소가 /deals?year=all이 된다
    await waitFor(() => expect(location()).toBe('/deals?year=all'))
  })

  // 기억이 없는 상세의 목록 링크도 기본 조건이다
  // 테스트 코드: DL-057
  it('applies the default to the back link of the detail page when nothing is remembered', async () => {
    // given: 기억이 없는 상세 화면
    const { user, location } = await renderAt('/deals/20000101-ZZZZ', ADMIN)

    // when: 'Deal 목록으로'를 누른다
    await user.click(await screen.findByRole('link', { name: 'Deal 목록으로' }))

    // then: 주소가 /deals?year=all이 된다
    await waitFor(() => expect(location()).toBe('/deals?year=all'))
  })
})

describe('초기화', () => {
  // 초기화는 연도 전체 기본 조건으로 새 이력을 만들고 정렬도 지우며 기억한다
  // 테스트 코드: DL-070
  it('goes to all years as a new history entry and remembers it', async () => {
    // given: 연도 전체·Status·정렬이 걸린 목록
    const start = '/deals?year=all&status=contract_completed&sort=name&order=asc'
    const { user, location, goTo } = await renderAt(start, ADMIN)
    await screen.findByRole('row', { name: /청명대학교 SSO\/MFA/ })

    // when: 초기화 버튼을 누른다
    await user.click(screen.getByRole('button', { name: '초기화' }))

    // then: 주소·칸이 연도 전체 기본 조건이 되고 정렬은 최종 업데이트 내림차순, 기억도 year=all이며 뒤로 가면 이전 조건이다
    await waitFor(() => expect(location()).toBe('/deals?year=all'))
    expect(screen.getByLabelText('Status')).toHaveDisplayValue('전체')
    expect(screen.getByLabelText('연도')).toHaveDisplayValue('전체')
    expect(quarterButton('전체')).toBeInTheDocument()
    expect(await screen.findByRole('columnheader', { name: '최종 업데이트' })).toHaveAttribute('aria-sort', 'descending')
    expect(window.sessionStorage.getItem(listMemoryKey(USER_ID.root))).toBe('year=all')

    goTo(-1)

    await waitFor(() => expect(location()).toBe(start))
  })
})

describe('조건이 있는 주소는 그대로', () => {
  // 조건이 있는 주소는 바뀌지 않는다
  // 테스트 코드: DL-055
  it.each(['/deals?overdue=1', '/deals?quarter=4', '/deals?month=3', '/deals?status=contract_completed'])('keeps %s as it is', async (url) => {
    // given: 조건이 하나 있는 주소
    const { location } = await renderAt(url)
    await screen.findByText(/총 \d+건/)
    // when: 그 주소로 들어간다
    await act(async () => {
      await new Promise((resolve) => setTimeout(resolve, 30))
    })

    // then: 주소가 그대로이고 연도는 전체다
    expect(location()).toBe(url)
    expect(screen.getByLabelText('연도')).toHaveDisplayValue('전체')
  })

  // 조건이 있는 주소는 연도·분기를 덧붙여 조회하지 않는다
  // 테스트 코드: DL-055
  it('does not ask the server with an added period for an address that has a condition', async () => {
    // given: 기한초과 조건만 있는 주소
    const list = vi.spyOn(gateway.deals, 'list')

    await renderAt('/deals?overdue=1')
    // when: 그 주소로 들어간다
    await screen.findByText(/총 \d+건/)

    // then: 모든 요청에 year·quarter가 없다
    for (const [query] of list.mock.calls) {
      expect(query).not.toHaveProperty('year')
      expect(query).not.toHaveProperty('quarter')
    }
  })
})

describe('필터 바에서 마지막 조건을 지울 때', () => {
  // 마지막 조건을 지우면 기본 연도 대신 연도 전체로 남는다
  // 테스트 코드: DL-069
  it('keeps all years instead of bringing the default year back', async () => {
    // given: 기한초과 조건 하나만 켜진 목록
    const { user, location } = await renderAt('/deals?overdue=1')
    await waitFor(() => expect(screen.getByRole('checkbox', { name: '기한초과' })).toBeChecked())

    // when: 기한초과 체크를 끈다
    await user.click(screen.getByRole('checkbox', { name: '기한초과' }))

    // then: 주소가 /deals?year=all로 남고 연도 칸은 전체다
    await waitFor(() => expect(location()).toBe('/deals?year=all'))
    await act(async () => {
      await new Promise((resolve) => setTimeout(resolve, 30))
    })
    expect(location()).toBe('/deals?year=all')
    expect(screen.getByLabelText('연도')).toHaveDisplayValue('전체')
  })
})

describe('연도 전체', () => {
  // 연도·Quarter를 모두 지워도 연도 전체로 남는다
  // 테스트 코드: DL-069
  it('keeps all years when year and quarter are both cleared', async () => {
    // given: 연도 2026·Q4가 걸린 목록
    const { user, location } = await renderAt('/deals?year=2026&quarter=4')
    await screen.findByRole('row', { name: /한빛은행 ITDR 도입/ })

    // when: 연도를 전체로 바꾼다
    await user.selectOptions(screen.getByLabelText('연도'), '전체')
    // then: 주소가 year=all&quarter=4가 된다
    await waitFor(() => expect(location()).toBe('/deals?year=all&quarter=4'))
    // when: Quarter를 해제한다
    await clearQuarter(user)

    // then: 주소가 year=all이고 전체 Deal이 첫 페이지 20건으로 보인다
    await waitFor(() => expect(location()).toBe('/deals?year=all'))
    await act(async () => {
      await new Promise((resolve) => setTimeout(resolve, 30))
    })
    expect(location()).toBe('/deals?year=all')
    const all = await gateway.deals.list({ limit: 1 })
    expect(await screen.findByText(`총 ${all.total}건`)).toBeVisible()
    expect(dataRows()).toHaveLength(20)
  })

  // 연도 전체는 서버에 연도를 보내지 않는다
  // 테스트 코드: DL-082
  it('sends no year when all years are chosen', async () => {
    // given: 연도 2026·Q4가 걸린 목록
    const list = vi.spyOn(gateway.deals, 'list')
    const { user } = await renderAt('/deals?year=2026&quarter=4')
    await screen.findByText(/총 \d+건/)

    // when: 연도를 전체로 바꾼다
    await user.selectOptions(screen.getByLabelText('연도'), '전체')

    // then: 마지막 요청에 year가 없고 분기만 있다
    await waitFor(() => expect(list.mock.calls.at(-1)?.[0]).toEqual({ offset: 0, limit: 20, quarters: [4] }))
  })

  // 상세에 다녀와도 연도 전체가 복원된다
  // 테스트 코드: DL-082
  it('restores all years after a detail round trip', async () => {
    // given: 연도 전체 목록에서 상세로 들어간 상태
    const { user, location } = await renderAt('/deals?year=all')
    const first = await rowOf(/한빛은행 ITDR 도입/)
    const link = within(first).getByRole('link', { name: '한빛은행 ITDR 도입' })
    const name = link.textContent ?? ''
    await user.click(link)
    await screen.findByRole('heading', { level: 1, name })

    // when: 상세의 목록 링크를 누른다
    await user.click(screen.getByRole('link', { name: '← 목록' }))

    // then: 주소가 year=all로 돌아오고 연도 칸이 전체다
    await waitFor(() => expect(location()).toBe('/deals?year=all'))
    expect(await screen.findByLabelText('연도')).toHaveDisplayValue('전체')
  })

  // 다른 화면에 다녀와 상단 메뉴로 와도 연도 전체가 복원된다
  // 테스트 코드: DL-082
  it('restores all years from the top menu after leaving the list', async () => {
    // given: 연도 전체 목록에서 Forecast 화면으로 간 상태
    const { user, location } = await renderAt('/deals?year=all')
    await screen.findByText(/총 \d+건/)
    await user.click(mainMenu().getByRole('link', { name: 'Forecast' }))
    await screen.findByRole('heading', { name: 'Forecast' })

    // when: 상단 메뉴 Deals를 누른다
    await user.click(mainMenu().getByRole('link', { name: 'Deals' }))

    // then: 주소가 year=all이다
    await waitFor(() => expect(location()).toBe('/deals?year=all'))
  })
})
