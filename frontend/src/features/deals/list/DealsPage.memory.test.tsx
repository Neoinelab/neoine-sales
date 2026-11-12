import { screen, waitFor, within } from '@testing-library/react'
import { afterEach, beforeEach, describe, expect, it } from 'vitest'
import { listMemoryKey } from '../../../shared/model/dealListMemory'
import { resetMock } from '../../../test/fake/default'
import { renderAt } from '../../../test/mockApp'
import { dealCodeOf } from '../../../test/detailTestUtils'
import { defaultDealsUrl } from '../../../test/dealsUrl'
import { ALL_DEALS, dataRows, quarterButton, rowOf } from './testHelpers'
import { USER_ID } from '../../../test/fake/seed/ids'

/**
 * DL-06 목록 조회 조건 유지(P5): 화면 안 링크·버튼으로 목록에 돌아오면 직전의 필터·정렬·페이지가 그대로다.
 * 시드(샘플 픽스처) 기준: mine=1&status=contract_completed 는 김영업의 청명대학교 SSO/MFA·도담건설 MFA 2건.
 */

const CONDITION = '/deals?mine=1&status=contract_completed&sort=name&order=asc'
const PAGED = '/deals?year=all&sort=revenueAmount&order=desc&page=2'
/** 초기화·빈 진입이 쓰는 기준일(앱 시계). 시드 Deal 날짜는 이 시각 기준 상대값이다. */
const NOW = '2026-10-15T09:00:00+09:00'
const NOT_FOUND = '/deals/20000101-ZZZZ'
const QINGMYEONG = /청명대학교 SSO\/MFA/

type View = Awaited<ReturnType<typeof renderAt>>

/** 조건 목록에서 청명대학교 SSO/MFA의 상세 화면까지 들어간다. */
async function openDetailFrom(url: string): Promise<View> {
  const view = await renderAt(url)
  const row = await rowOf(QINGMYEONG)
  await view.user.click(within(row).getByRole('link', { name: '청명대학교 SSO/MFA' }))
  await screen.findByRole('heading', { level: 1, name: '청명대학교 SSO/MFA' })
  return view
}

async function expectConditionList(view: View, url: string) {
  await screen.findByRole('row', { name: QINGMYEONG })
  expect(view.location()).toBe(url)
  expect(screen.getByLabelText('Status')).toHaveDisplayValue('계약완료')
  expect(screen.getByRole('columnheader', { name: 'Deal' })).toHaveAttribute('aria-sort', 'ascending')
  expect(dataRows()).toHaveLength(2)
}

describe('상세에서 목록으로', () => {
  // 상세의 목록 링크는 조건·정렬이 걸린 목록으로 돌아간다
  // 테스트 코드: DL-096
  it('back link on detail returns to the filtered sorted page', async () => {
    // when: 상세의 목록 링크를 누른다 (전제: 조건·정렬이 걸린 목록에서 상세로 들어간 상태)
    const view = await openDetailFrom(CONDITION)

    // then: 같은 조건·정렬의 목록이다
    expect(screen.getByRole('link', { name: '← 목록' })).toHaveAttribute('href', CONDITION)
    await view.user.click(screen.getByRole('link', { name: '← 목록' }))

    await expectConditionList(view, CONDITION)
  })

  // 상세의 목록 링크는 페이지 번호도 유지한다
  // 테스트 코드: DL-096
  it('back link on detail keeps the page number', async () => {
    // given: 2페이지에서 상세로 들어간 상태
    const view = await renderAt(PAGED)
    await screen.findByRole('button', { name: '이전' })
    const firstRow = dataRows()[0] as HTMLElement
    const link = within(firstRow).getAllByRole('link')[0] as HTMLElement
    const name = link.textContent ?? ''
    await view.user.click(link)
    await screen.findByRole('heading', { level: 1, name })

    await view.user.click(screen.getByRole('link', { name: '← 목록' }))

    // when: 목록 링크를 누른다
    await screen.findByRole('button', { name: '이전' })

    // then: 2페이지이다
    expect(view.location()).toBe(PAGED)
    expect(dataRows()).toHaveLength(4)
    expect(screen.getByRole('columnheader', { name: '금액(단위:원)' })).toHaveAttribute('aria-sort', 'descending')
  })

  // 빠른 보기의 상세 링크를 다녀와도 조건이 유지된다
  // 테스트 코드: DL-096
  it('quick view detail link round trip keeps conditions', async () => {
    // given: 조건이 걸린 목록의 빠른 보기
    const view = await renderAt(CONDITION)
    const row = await rowOf(QINGMYEONG)
    await view.user.click(within(row).getByRole('button', { name: /빠른 보기/ }))
    await view.user.click(within(screen.getByRole('region', { name: /빠른 보기/ })).getByRole('link', { name: '상세 보기' }))
    await screen.findByRole('heading', { level: 1, name: '청명대학교 SSO/MFA' })

    // when: 상세 보기를 갔다가 돌아온다
    await view.user.click(screen.getByRole('link', { name: '← 목록' }))

    // then: 같은 조건이다
    await expectConditionList(view, CONDITION)
  })

  // 상세→수정→저장→상세를 거쳐도 조건이 남는다
  // 테스트 코드: DL-096
  it('conditions survive detail edit save detail chain', async () => {
    // given: 조건이 걸린 목록
    const view = await openDetailFrom(CONDITION)
    const code = view.location().replace('/deals/', '')
    view.goTo(`/deals/${code}/edit`)
    await screen.findByRole('heading', { name: 'Deal 수정' })
    await screen.findByLabelText('Deal Name')

    // when: 상세에서 수정·저장 후 목록으로 간다
    await view.user.click(screen.getByRole('button', { name: '저장' }))

    // then: 같은 조건이다
    await waitFor(() => expect(view.location()).toBe(`/deals/${code}`))

    await view.user.click(await screen.findByRole('link', { name: '← 목록' }))

    await expectConditionList(view, CONDITION)
  })

  // 브라우저 뒤로 가기도 URL을 복원한다
  // 테스트 코드: DL-096
  it('browser back still restores the url', async () => {
    // given: 상세에 다녀온 상태
    const view = await openDetailFrom(CONDITION)

    // when: 뒤로 가기를 한다
    view.goTo(-1)

    // then: 목록 URL이 복원된다
    await expectConditionList(view, CONDITION)
  })
})

describe('삭제와 등록·수정 취소', () => {
  // Deal 삭제 뒤 기억된 목록으로 가고 알림은 한 번만 보인다
  // 테스트 코드: DL-099
  it('deleting a deal returns to remembered list with notice once', async () => {
    // given: 조건이 걸린 목록에서 들어간 상세
    const code = await dealCodeOf(11)
    const view = await openDetailFrom(CONDITION)
    await view.user.click(screen.getByRole('button', { name: 'Deal 삭제' }))
    const dialog = await screen.findByRole('dialog', { name: 'Deal 삭제' })
    await view.user.type(within(dialog).getByLabelText('Deal code 확인'), code)

    // when: Deal을 삭제한다
    await view.user.click(within(dialog).getByRole('button', { name: '삭제' }))

    // then: 기억된 목록으로 이동하고 알림이 한 번 보인다
    expect(await screen.findByText(`Deal ${code}이(가) 삭제되었습니다.`)).toBeVisible()
    expect(view.location()).toBe(CONDITION)
    expect(screen.getByLabelText('Status')).toHaveDisplayValue('계약완료')

    await view.user.click(screen.getByRole('link', { name: 'Forecast' }))
    await screen.findByRole('heading', { name: 'Forecast' })
    await view.user.click(screen.getByRole('link', { name: 'Deals' }))
    await screen.findByRole('heading', { name: 'Deals' })
    await screen.findByRole('row', { name: /도담건설 MFA/ })
    expect(screen.queryByText(`Deal ${code}이(가) 삭제되었습니다.`)).not.toBeInTheDocument()
  })

  // 새 Deal 폼의 취소는 기억된 목록으로 간다
  // 테스트 코드: DL-099
  it('cancel on new deal form returns to remembered list', async () => {
    // given: 조건이 걸린 목록에서 들어간 새 Deal 폼
    const view = await renderAt(CONDITION)
    await screen.findByRole('row', { name: QINGMYEONG })
    await view.user.click(screen.getByRole('link', { name: '+ Deal 등록' }))
    await screen.findByRole('heading', { name: 'Deal 등록' })

    // when: 취소한다
    await view.user.click(screen.getByRole('button', { name: '취소' }))

    // then: 기억된 목록이다
    await expectConditionList(view, CONDITION)
  })

  // 수정 폼의 취소는 상세로 돌아간다(DE)
  it('cancel on edit form still returns to detail', async () => {
    // given: 상세에서 연 수정 폼
    const view = await openDetailFrom(CONDITION)
    const code = view.location().replace('/deals/', '')
    view.goTo(`/deals/${code}/edit`)
    await screen.findByRole('heading', { name: 'Deal 수정' })

    // when: 취소한다
    await view.user.click(screen.getByRole('button', { name: '취소' }))

    // then: 상세 화면이다
    expect(view.location()).toBe(`/deals/${code}`)
  })
})

describe('오류 화면의 목록 링크', () => {
  // 상세 오류 화면의 목록 링크는 기억된 목록이다
  // 테스트 코드: DL-099
  it('detail error page link uses the remembered list', async () => {
    // given: 기억된 조건과 없는 Deal 상세
    const view = await renderAt(CONDITION)
    await screen.findByRole('row', { name: QINGMYEONG })

    // when: 오류 화면의 링크를 확인한다
    view.goTo(NOT_FOUND)

    // then: 기억된 목록 주소다
    expect(await screen.findByRole('alert')).toHaveTextContent('Deal을 찾을 수 없습니다.')
    expect(screen.getByRole('link', { name: 'Deal 목록으로' })).toHaveAttribute('href', CONDITION)
  })

  // 수정 오류 화면의 목록 링크도 기억된 목록이다
  // 테스트 코드: DL-099
  it('edit error page link uses the remembered list', async () => {
    // given: 기억된 조건과 없는 Deal 수정
    const view = await renderAt(CONDITION)
    await screen.findByRole('row', { name: QINGMYEONG })

    // when: 오류 화면의 링크를 확인한다
    view.goTo(`${NOT_FOUND}/edit`)

    // then: 기억된 목록 주소다
    expect(await screen.findByRole('alert')).toHaveTextContent('Deal을 찾을 수 없습니다.')
    expect(screen.getByRole('link', { name: '목록으로' })).toHaveAttribute('href', CONDITION)
  })
})

describe('상단 메뉴와 초기화', () => {
  // 상단 메뉴 Deals는 기억된 목록을 연다
  // 테스트 코드: DL-097
  it('top menu deals opens remembered list', async () => {
    // given: 기억된 목록 조건이 있는 상태
    const adminList = '/deals?status=contract_completed&sort=name&order=asc'
    const view = await renderAt(adminList, { role: 'admin' })
    await screen.findByRole('row', { name: QINGMYEONG })

    // when: 다른 화면에서 상단 메뉴 Deals를 누른다
    await view.user.click(screen.getByRole('link', { name: 'Admin' }))

    // then: 기억된 조건의 목록이다
    await waitFor(() => expect(view.location()).toMatch(/^\/admin/))

    await view.user.click(screen.getByRole('link', { name: 'Deals' }))

    await screen.findByRole('row', { name: QINGMYEONG })
    expect(view.location()).toBe(adminList)
    expect(screen.getByLabelText('Status')).toHaveDisplayValue('계약완료')
  })

  // 초기화는 기억된 조건을 기본 조건으로 바꾼다
  // 테스트 코드: DL-098
  it('reset replaces the remembered conditions with the default period', async () => {
    // given: 조건이 기억된 목록
    resetMock({ now: NOW })
    const view = await renderAt(CONDITION)
    await screen.findByRole('row', { name: QINGMYEONG })

    // when: 초기화를 누른다
    await view.user.click(screen.getByRole('button', { name: '초기화' }))

    // then: 기억이 올해 기본 조건이다
    await waitFor(() => expect(view.location()).toBe(defaultDealsUrl(NOW)))
    await screen.findByRole('row', { name: /한빛은행 ITDR 도입/ })
    await view.user.click(within(await rowOf(/한빛은행 ITDR 도입/)).getByRole('link', { name: '한빛은행 ITDR 도입' }))
    await screen.findByRole('heading', { level: 1, name: '한빛은행 ITDR 도입' })

    expect(screen.getByRole('link', { name: '← 목록' })).toHaveAttribute('href', defaultDealsUrl(NOW))
    resetMock({ now: null })
  })
})

describe('탭·사용자 단위 기억', () => {
  // 다른 사용자는 이전 사용자의 조건을 물려받지 않는다
  // 테스트 코드: DL-098
  it('another user does not inherit conditions', async () => {
    // given: 한 사용자의 기억
    const first = await renderAt(CONDITION)
    await screen.findByRole('row', { name: QINGMYEONG })
    first.unmount()

    // when: 다른 사용자로 로그인한다
    // u-kim의 기억이 sessionStorage에 남은 채, u-park는 목록이 아닌 화면에서 시작한다(단일 키 구현이면 u-kim 조건이 보인다).
    await renderAt(NOT_FOUND, { userId: USER_ID.park })

    // then: 기본 조건이다
    expect(await screen.findByRole('alert')).toHaveTextContent('Deal을 찾을 수 없습니다.')

    expect(screen.getByRole('link', { name: 'Deals' })).toHaveAttribute('href', '/deals')
    expect(screen.getByRole('link', { name: 'Deal 목록으로' })).toHaveAttribute('href', '/deals')
  })

  // 새로고침해도 같은 사용자는 조건이 유지된다
  // 테스트 코드: DL-098
  it('the same user keeps conditions after a reload', async () => {
    // given: 기억된 조건
    const first = await renderAt(CONDITION)
    await screen.findByRole('row', { name: QINGMYEONG })
    first.unmount()

    // when: 새로고침한다
    const view = await renderAt('/deals/20000101-ZZZZ')

    // then: 같은 조건이 남는다
    expect(await screen.findByRole('alert')).toHaveTextContent('Deal을 찾을 수 없습니다.')
    expect(screen.getByRole('link', { name: 'Deal 목록으로' })).toHaveAttribute('href', CONDITION)
    expect(view.location()).toBe(NOT_FOUND)
  })
})

describe('목록에 머무는 동안 상단 메뉴 (리뷰 Major)', () => {
  const deals = () => screen.getByRole('link', { name: 'Deals' })

  beforeEach(() => resetMock({ now: NOW }))
  afterEach(() => resetMock({ now: null }))

  // 초기화 직후 메뉴 Deals 링크는 기본 조건이다
  // 테스트 코드: DL-097
  it('menu deals href is the default list right after reset', async () => {
    // given: 초기화한 목록
    const view = await renderAt(CONDITION)
    await screen.findByRole('row', { name: QINGMYEONG })

    await view.user.click(screen.getByRole('button', { name: '초기화' }))

    // when: 메뉴 링크를 확인한다
    await screen.findByRole('row', { name: /한빛은행 ITDR 도입/ })

    // then: 기본 조건 주소다
    expect(view.location()).toBe(defaultDealsUrl(NOW))
    expect(deals()).toHaveAttribute('href', defaultDealsUrl(NOW))
  })

  // 조건을 바꾸면 메뉴 Deals 링크가 즉시 따라간다
  // 테스트 코드: DL-097
  it('menu deals href follows a filter change immediately', async () => {
    // given: 목록 화면
    const view = await renderAt(ALL_DEALS)
    await screen.findByRole('row', { name: /한빛은행 ITDR 도입/ })

    await view.user.selectOptions(screen.getByLabelText('Status'), '계약완료')

    // when: 조건을 바꾼다
    await screen.findByRole('row', { name: QINGMYEONG })

    // then: 메뉴 링크가 지금 URL이다
    expect(view.location()).toBe('/deals?year=all&status=contract_completed')
    expect(deals()).toHaveAttribute('href', '/deals?year=all&status=contract_completed')
  })

  // 정렬을 바꾸면 메뉴 링크가 즉시 따라간다
  // 테스트 코드: DL-097
  it('menu deals href follows a sort change immediately', async () => {
    // given: 목록 화면
    const view = await renderAt(ALL_DEALS)
    await screen.findByRole('row', { name: /한빛은행 ITDR 도입/ })

    // when: 정렬을 바꾼다
    await view.user.click(screen.getByRole('button', { name: '금액(단위:원)' }))

    // then: 메뉴 링크가 지금 URL이다
    await waitFor(() => expect(screen.getByRole('columnheader', { name: '금액(단위:원)' })).toHaveAttribute('aria-sort', 'descending'))

    expect(view.location()).toContain('sort=revenueAmount')
    expect(deals()).toHaveAttribute('href', view.location())
  })

  // 페이지를 바꾸면 메뉴 링크가 즉시 따라간다
  // 테스트 코드: DL-097
  it('menu deals href follows a page change immediately', async () => {
    // given: 목록 화면
    const view = await renderAt(PAGED)

    // when: 페이지를 바꾼다
    await view.user.click(await screen.findByRole('button', { name: '이전' }))

    // then: 메뉴 링크가 지금 URL이다
    await waitFor(() => expect(view.location()).not.toContain('page=2'))

    expect(deals()).toHaveAttribute('href', view.location())
  })
})

describe('Quarter만 있는 조건의 기억', () => {
  beforeEach(() => resetMock({ now: '2026-10-15T09:00:00+09:00' }))
  afterEach(() => resetMock({ now: null }))

  // 분기만 있는 조건도 그대로 기억해 복원한다
  // 테스트 코드: DL-096
  it('remembers a quarter-only search as it is and restores it when coming back from a detail page', async () => {
    // when: 상세에 갔다가 돌아온다 (전제: 분기만 걸린 목록)
    const view = await renderAt('/deals?quarter=4')

    // then: 분기 조건이 그대로다
    await waitFor(() => expect(dataRows().length).toBeGreaterThan(0))
    expect(window.sessionStorage.getItem(listMemoryKey(USER_ID.kim))).toBe('quarter=4')

    const link = within(dataRows()[0] as HTMLElement).getAllByRole('link')[0] as HTMLElement
    const name = link.textContent ?? ''
    await view.user.click(link)
    await screen.findByRole('heading', { level: 1, name })
    expect(screen.getByRole('link', { name: '← 목록' })).toHaveAttribute('href', '/deals?quarter=4')
    await view.user.click(screen.getByRole('link', { name: '← 목록' }))

    await screen.findByRole('button', { name: '초기화' })
    expect(view.location()).toBe('/deals?quarter=4')
    expect(quarterButton('Q4')).toBeInTheDocument()
    expect(screen.getByLabelText('연도')).toHaveDisplayValue('전체')
  })
})

describe('최종 업데이트 기간 기억', () => {
  const UPDATED = '/deals?mine=1&status=contract_completed&updated_from=2000-01-01&updated_to=2099-12-31&sort=name&order=asc'

  // 상세에서 돌아와도 같은 최종 업데이트 기간이다
  // 테스트 코드: DL-096
  it('returns from detail to the same updated date range', async () => {
    // when: 목록으로 돌아온다 (전제: 기간이 걸린 목록에서 상세로 들어간 상태)
    const view = await openDetailFrom(UPDATED)

    // then: 같은 기간이다
    expect(screen.getByRole('link', { name: '← 목록' })).toHaveAttribute('href', UPDATED)
    await view.user.click(screen.getByRole('link', { name: '← 목록' }))

    await screen.findByRole('row', { name: QINGMYEONG })
    expect(view.location()).toBe(UPDATED)
    expect(screen.getByLabelText('최종 업데이트')).toHaveDisplayValue('직접 지정')
    expect(screen.getByLabelText('시작일')).toHaveValue('2000.01.01')
    expect(screen.getByLabelText('종료일')).toHaveValue('2099.12.31')
  })

  // 예전 Expected Close 기간(from·to)은 복원하지 않는다
  // 테스트 코드: DL-098
  it('does not restore the old expected-close period from and to', async () => {
    // when: 목록 링크를 확인한다 (전제: 예전 from·to가 기억된 상태)
    const view = await openDetailFrom(`${CONDITION}&from=2099-01-01&to=2099-12-31`)

    // then: from·to가 없다
    // 구 from/to는 조회에 쓰이지 않아 목록이 그대로 2건이고, 기억에도 남지 않는다.
    expect(screen.getByRole('link', { name: '← 목록' })).toHaveAttribute('href', CONDITION)
    await view.user.click(screen.getByRole('link', { name: '← 목록' }))
    await waitFor(() => expect(dataRows()).toHaveLength(2))
    expect(view.location()).toBe(CONDITION)
  })
})

describe('정렬·기한초과·미업데이트 기억', () => {
  const RISK_SORT = '/deals?overdue=1&stale=1&sort=owner&order=desc'

  // 담당자 정렬·경고 필터도 같게 돌아온다
  // 테스트 코드: DL-096
  it('returns from detail to the same owner sort and risk filters', async () => {
    // when: 상세에 갔다가 돌아온다 (전제: 담당자 정렬과 경고 필터가 걸린 목록)
    const view = await renderAt(RISK_SORT)

    // then: 같은 정렬·필터이다
    await waitFor(() => expect(dataRows().length).toBeGreaterThan(0))
    const link = within(dataRows()[0] as HTMLElement).getAllByRole('link')[0] as HTMLElement
    const name = link.textContent ?? ''
    await view.user.click(link)
    await screen.findByRole('heading', { level: 1, name })

    expect(screen.getByRole('link', { name: '← 목록' })).toHaveAttribute('href', RISK_SORT)
    await view.user.click(screen.getByRole('link', { name: '← 목록' }))

    await waitFor(() => expect(view.location()).toBe(RISK_SORT))
    expect(await screen.findByRole('columnheader', { name: '담당자' })).toHaveAttribute('aria-sort', 'descending')
    expect(screen.getByRole('checkbox', { name: '기한초과' })).toBeChecked()
    expect(screen.getByRole('checkbox', { name: '미업데이트' })).toBeChecked()
  })

  // 새 정렬과 경고 키를 sessionStorage에 저장한다
  // 테스트 코드: DL-098
  it('stores the new sort and the risk keys in session storage', async () => {
    // when: 화면에 머문다 (전제: 정렬·경고 필터가 걸린 목록)
    await renderAt(RISK_SORT)

    // then: 저장소에 그 키가 있다
    await waitFor(() => expect(window.sessionStorage.getItem(listMemoryKey(USER_ID.kim))).toBe('overdue=1&stale=1&sort=owner&order=desc'))
  })

  // 새 열 정렬 변경도 메뉴 링크가 즉시 따라간다
  // 테스트 코드: DL-097
  it('menu deals href follows a new-column sort change immediately', async () => {
    // given: 목록 화면
    const deals = () => screen.getByRole('link', { name: 'Deals' })
    const view = await renderAt(ALL_DEALS)
    await screen.findByRole('row', { name: /한빛은행 ITDR 도입/ })

    // when: 새 열로 정렬한다
    await view.user.click(screen.getByRole('button', { name: '담당자' }))

    // then: 메뉴 링크가 지금 URL이다
    await waitFor(() => expect(screen.getByRole('columnheader', { name: '담당자' })).toHaveAttribute('aria-sort', 'ascending'))

    expect(deals()).toHaveAttribute('href', '/deals?year=all&sort=owner&order=asc')
  })

  // 예전 BANT 키는 복원하지 않는다
  // 테스트 코드: DL-098
  it('does not restore old BANT keys that an earlier version stored', async () => {
    // given: 예전 BANT 키가 기억된 상태
    window.sessionStorage.setItem(listMemoryKey(USER_ID.kim), 'budget=1&need=3&stale=1')

    // when: 목록 링크를 확인한다
    await renderAt('/deals/20000101-ZZZZ')

    // then: BANT 키가 빠진 주소다
    // 목록 밖(없는 Deal 상세)에서 기억된 조건으로 돌아가는 링크를 본다. 목록 화면 안에서는 메뉴가 현재 URL을 따른다.
    expect(await screen.findByRole('alert')).toHaveTextContent('Deal을 찾을 수 없습니다.')

    expect(screen.getByRole('link', { name: 'Deal 목록으로' })).toHaveAttribute('href', '/deals?stale=1')
    expect(screen.getByRole('link', { name: 'Deals' })).toHaveAttribute('href', '/deals?stale=1')
  })
})
