import { screen, waitFor, within } from '@testing-library/react'
import { afterEach, describe, expect, it } from 'vitest'
import { gateway } from '../../../gateway'
import { resetMock } from '../../../test/fake/default'
import { defaultMock } from '../../../test/fake/default'
import { dealInput } from '../../../test/fake/testing'
import { renderAt } from '../../../test/mockApp'
import { formatDateTime } from '../../../shared/format'
import { dealCodeOf, detailPath } from '../../../test/detailTestUtils'

const DAY_MS = 86_400_000

describe('상세 Status 체류 표시 (AC-13, Q3)', () => {
  afterEach(() => resetMock({ now: null }))

  it('shows "N일째" next to Status with the entry time in the tooltip', async () => {
    const code = await dealCodeOf(2)
    await gateway.auth.quickLogin('u-root')
    const deal = await gateway.deals.get(code)
    expect(deal.statusDays).toBeGreaterThan(0)

    await renderAt(await detailPath(2))

    const bar = await screen.findByRole('region', { name: 'Deal 정보' })
    const stay = within(bar).getByText(`${deal.statusDays}일째`)
    expect(stay).toBeVisible()
    expect(stay).toHaveAttribute('title', formatDateTime(deal.statusChangedAt))
    expect(stay.getAttribute('title')).not.toBe(deal.statusChangedAt)
  })

  it('shows the tooltip in local time when the change time was serialized in UTC', async () => {
    // KST 2030-06-15 01:00 = UTC 2030-06-14 16:00. 원문 ISO가 아니라 로컬 표시여야 한다.
    resetMock({ now: '2030-06-14T16:00:00Z' })
    const code = await dealCodeOf(2) // 시드 code가 시계 날짜를 포함하므로 시계를 먼저 맞춘다
    const { client } = await renderAt(`/deals/${code}`, { role: 'admin' })
    const bar = await screen.findByRole('region', { name: 'Deal 정보' })
    await within(bar).findByText(/\d+일째/)
    await gateway.deals.applyChange(code, { change: { field: 'statusKey', value: 'introduction' } })
    await client.invalidateQueries()

    const deal = await gateway.deals.get(code)
    const stay = await within(bar).findByText('0일째')
    expect(stay).toHaveAttribute('title', formatDateTime(deal.statusChangedAt))
    expect(stay.getAttribute('title')).not.toMatch(/T\d{2}:\d{2}/)
  })

  it('restarts from 0일째 right after the status changes', async () => {
    const { client } = await renderAt(await detailPath(2), { role: 'admin' })
    const bar = await screen.findByRole('region', { name: 'Deal 정보' })
    await within(bar).findByText(/\d+일째/)

    await gateway.deals.applyChange(await dealCodeOf(2), { change: { field: 'statusKey', value: 'introduction' } })
    await client.invalidateQueries()

    await waitFor(() => expect(within(bar).getByText('0일째')).toBeVisible())
  })

  it('shows the stale badge on a deal that has no action at all', async () => {
    const { client, user } = await renderAt('/deals', { role: 'admin' })
    await screen.findByRole('row', { name: /한빛은행 ITDR 도입/ })
    const created = await gateway.deals.create(dealInput('u-kim', { name: '액션 없는 Deal' }))
    defaultMock.clock.advance(15 * DAY_MS)
    await client.invalidateQueries()

    await user.click(await screen.findByRole('link', { name: '액션 없는 Deal' }))

    const bar = await screen.findByRole('region', { name: 'Deal 정보' })
    expect(created.nextAction).toBeNull()
    expect(await within(bar).findByText('미업데이트')).toBeVisible()
    expect(within(bar).getByText('15일째')).toBeVisible()
  })
})
