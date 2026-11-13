import { screen, waitFor, within } from '@testing-library/react'
import { afterEach, describe, expect, it } from 'vitest'
import { gateway } from '../../../gateway'
import { resetMock } from '../../../test/fake/default'
import { defaultMock } from '../../../test/fake/default'
import { dealInput } from '../../../test/fake/testing'
import { renderAt } from '../../../test/mockApp'
import { dealCodeOf, detailPath } from '../../../test/detailTestUtils'
import { USER_ID } from '../../../test/fake/seed/ids'
import { ALL_DEALS } from '../list/testHelpers'

const DAY_MS = 86_400_000

describe('상세 Status 체류 표시 (Q3)', () => {
  afterEach(() => resetMock({ now: null }))

  // Status 옆에 'N일째'를 보이고 툴팁은 진입일(YYYY-MM-DD)이다.
  // 테스트 코드: RK-056
  it('shows "N일째" next to Status with the entry date in the tooltip', async () => {
    // given: 체류 일수가 있는 시드 Deal이다
    const code = await dealCodeOf(2)
    await defaultMock.signInAs(USER_ID.root)
    const deal = await gateway.deals.get(code)
    expect(deal.statusDays).toBeGreaterThan(0)

    // when: 상세를 연다
    await renderAt(await detailPath(2))

    // then: Status 옆에 '{statusDays}일째'가 보이고 툴팁은 진입일 YYYY-MM-DD 그대로다
    const bar = await screen.findByRole('region', { name: 'Deal 정보' })
    const stay = within(bar).getByText(`${deal.statusDays}일째`)
    expect(stay).toBeVisible()
    expect(deal.statusChangedOn).toMatch(/^\d{4}-\d{2}-\d{2}$/)
    expect(stay).toHaveAttribute('title', deal.statusChangedOn)
  })

  // 진입일은 날짜 그대로 보이고 시:분이 없다.
  // 테스트 코드: RK-056
  it('shows the tooltip as the entry date only, without a time', async () => {
    // given: Fake 시계를 2030-06-14T16:00Z로 맞추고 상세를 열었다
    resetMock({ now: '2030-06-14T16:00:00Z' })
    const code = await dealCodeOf(2) // 시드 code가 시계 날짜를 포함하므로 시계를 먼저 맞춘다
    const { client } = await renderAt(`/deals/${code}`, { role: 'admin' })
    const bar = await screen.findByRole('region', { name: 'Deal 정보' })
    await within(bar).findByText(/\d+일째/)
    // when: Status를 introduction으로 바꾸고 다시 읽는다
    await gateway.deals.applyChange(code, { change: { field: 'statusKey', value: 'introduction' } })
    await client.invalidateQueries()

    const deal = await gateway.deals.get(code)
    const stay = await within(bar).findByText('0일째')
    // then: 진입일은 서버 업무 날짜 '2030-06-14'이고 '0일째'의 툴팁도 그 날짜뿐이다(시각 없음)
    expect(deal.statusChangedOn).toBe('2030-06-14')
    expect(stay).toHaveAttribute('title', '2030-06-14')
  })

  // Status를 바꾸면 곧바로 '0일째'부터 다시 센다.
  // 테스트 코드: RK-056
  it('restarts from 0일째 right after the status changes', async () => {
    // given: admin이 Deal 상세를 열었고 'N일째'가 보인다
    const { client } = await renderAt(await detailPath(2), { role: 'admin' })
    const bar = await screen.findByRole('region', { name: 'Deal 정보' })
    await within(bar).findByText(/\d+일째/)

    // when: Status를 introduction으로 바꾸고 캐시를 무효화한다
    await gateway.deals.applyChange(await dealCodeOf(2), { change: { field: 'statusKey', value: 'introduction' } })
    await client.invalidateQueries()

    // then: '0일째'가 보인다
    await waitFor(() => expect(within(bar).getByText('0일째')).toBeVisible())
  })

  // Action이 없는 Deal도 Next Action 줄에 미업데이트 배지를 보인다.
  // 테스트 코드: RK-057
  it('shows the stale badge on a deal that has no action at all', async () => {
    // given: Action 없이 15일이 지난 Deal이 목록에 있다
    const { client, user } = await renderAt(ALL_DEALS, { role: 'admin' })
    await screen.findByRole('row', { name: /한빛은행 ITDR 도입/ })
    const created = await gateway.deals.create(dealInput(USER_ID.kim, { name: '액션 없는 Deal' }))
    defaultMock.clock.advance(15 * DAY_MS)
    await client.invalidateQueries()

    // when: 그 Deal의 상세를 연다
    await user.click(await screen.findByRole('link', { name: '액션 없는 Deal' }))

    const bar = await screen.findByRole('region', { name: 'Deal 정보' })
    // then: Next Action이 없고 '미업데이트' 배지와 '15일째'가 보인다
    expect(created.nextAction).toBeNull()
    expect(await within(bar).findByText('미업데이트')).toBeVisible()
    expect(within(bar).getByText('15일째')).toBeVisible()
  })
})
