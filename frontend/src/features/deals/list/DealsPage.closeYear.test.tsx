import { screen, waitFor, within } from '@testing-library/react'
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'
import { gateway } from '../../../gateway'
import { resetMock } from '../../../test/fake/default'
import { USER_ID } from '../../../test/fake/seed/ids'
import { dealInput } from '../../../test/fake/testing'
import { renderAt } from '../../../test/mockApp'
import { ALL_DEALS, dataRows, findFilterBar, toggleQuarter } from './testHelpers'

/** Deal 목록 연도 선택 상자 이름 "Close 연도"(DL-R24). 기준일 2026-10-15. */
beforeEach(() => resetMock({ now: '2026-10-15T09:00:00+09:00' }))
afterEach(() => {
  vi.restoreAllMocks()
  resetMock({ now: null })
})

describe('Deal 목록 Close 연도 선택 상자', () => {
  // 연도 선택 상자는 "Close 연도"이고 이름이 "연도"뿐인 상자는 없다
  // 테스트 코드: DL-107
  it('names the year select "Close 연도" and has no select named only "연도"', async () => {
    // given: admin 로그인, 앱 시계 2026-10-15
    // when: Deal 목록을 연다
    await renderAt(ALL_DEALS)
    const bar = await findFilterBar()

    // then: "Close 연도" 선택 상자가 있고 이름이 "연도"뿐인 선택 상자는 없다
    expect(await screen.findByLabelText('Close 연도')).toBeVisible()
    expect(bar.queryByLabelText('연도')).not.toBeInTheDocument()
  })

  // 2027을 고르면 URL과 목록이 Expected Close 2027년 Deal만 보인다
  // 테스트 코드: DL-107
  it('filters by the Expected Close year and writes year=2027 to the URL', async () => {
    // given: Expected Close가 2026-03-10·2027-05-01인 Deal 각 1건
    const { user, location, client } = await renderAt('/deals?year=all&q=클로즈연도')
    await screen.findByRole('search', { name: 'Deal 필터' })
    await gateway.deals.create(
      dealInput(USER_ID.kim, {
        name: '클로즈연도 2026건',
        revenueDate: '2026-03-10',
      }),
    )
    await gateway.deals.create(
      dealInput(USER_ID.kim, {
        name: '클로즈연도 2027건',
        revenueDate: '2027-05-01',
      }),
    )
    await client.invalidateQueries()
    await screen.findByRole('row', { name: /클로즈연도 2026건/ })

    // when: "Close 연도"에서 2027을 고른다
    await user.selectOptions(screen.getByLabelText('Close 연도'), '2027')

    // then: URL이 year=2027이고 2027년 Deal만 보인다
    await waitFor(() => expect(screen.queryByRole('row', { name: /클로즈연도 2026건/ })).not.toBeInTheDocument())
    expect(location()).toContain('year=2027')
    expect(dataRows()).toHaveLength(1)
    expect(within(dataRows()[0] as HTMLElement).getByText(/클로즈연도 2027건/)).toBeVisible()
  })

  // 전체에서 Q1을 고르면 Quarter 아래 올해(2026) 기준 안내가 나온다
  // 테스트 코드: DL-107
  it('shows "Close 연도가 전체이면 올해(2026) 기준입니다." when Q1 is checked with all years', async () => {
    // given: Close 연도 전체인 목록
    const { user } = await renderAt(ALL_DEALS)

    // when: Q1을 체크한다
    await toggleQuarter(user, 'Q1')

    // then: 안내 문구가 보인다
    expect(screen.getByText('Close 연도가 전체이면 올해(2026) 기준입니다.')).toBeVisible()
  })
})

describe('Dashboard·Forecast의 연도 선택 상자 이름', () => {
  // Dashboard는 "연도" 그대로다
  // 테스트 코드: DL-107
  it('keeps "연도" on the Dashboard', async () => {
    // given: Dashboard 화면
    // when: 연다
    await renderAt('/dashboard')

    // then: "연도"가 있고 "Close 연도"는 없다
    expect(await screen.findByLabelText('연도')).toBeVisible()
    expect(screen.queryByLabelText('Close 연도')).not.toBeInTheDocument()
  })

  // Forecast도 "연도" 그대로다
  // 테스트 코드: DL-107
  it('keeps "연도" on Forecast', async () => {
    // given: Forecast 화면
    // when: 연다
    await renderAt('/forecast')

    // then: "연도"가 있고 "Close 연도"는 없다
    expect(await screen.findByLabelText('연도')).toBeVisible()
    expect(screen.queryByLabelText('Close 연도')).not.toBeInTheDocument()
  })
})
