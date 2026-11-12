import { defaultMock } from '../../../test/fake/default'
import { screen, within } from '@testing-library/react'
import { afterEach, beforeEach, describe, expect, it } from 'vitest'
import { gateway } from '../../../gateway'
import { resetMock } from '../../../test/fake/default'
import { formatRelativeTime } from '../../../shared/format'
import { renderAt } from '../../../test/mockApp'
import { dealCodeOf } from '../../../test/detailTestUtils'
import { USER_ID } from '../../../test/fake/seed/ids'

const NOW = '2030-06-15T09:00:00+09:00'

beforeEach(() => resetMock({ now: NOW }))
afterEach(() => resetMock({ now: null }))

describe('상세와 mock 시계 (useToday)', () => {
  // 최종 업데이트가 mock 시계 기준 상대 시간으로 보이고 툴팁에 원래 시각이 있다.
  it('최종 업데이트를 상대 시간으로 보이고 툴팁에 시각을 담는다', async () => {
    // given: 관리자로 로그인한 상태의 Deal
    const code = await dealCodeOf(4)
    await defaultMock.signInAs(USER_ID.root)
    const deal = await gateway.deals.get(code)
    // when: 상세 화면을 연다 (전제: mock 시계 2030-06-15)
    await renderAt(`/deals/${code}`)
    const bar = await screen.findByRole('region', { name: 'Deal 정보' })
    const relative = formatRelativeTime(deal.lastUpdatedAt, NOW)
    // then: 'N일 전' 상대 시간이 보이고 title에 최종 업데이트 시각이 있다
    expect(relative).toMatch(/일 전$/)
    expect(within(bar).getByText(relative)).toHaveAttribute('title', deal.lastUpdatedAt)
  })

  // 현재 Next Action의 기한초과를 mock 시계 날짜로 판정해 표시한다.
  it('현재 Next Action의 기한초과를 mock 시계 날짜로 표시한다', async () => {
    // given: Action이 여러 개인 Deal
    const code = await dealCodeOf(3)
    // when: Action 탭을 연다 (전제: mock 시계 2030-06-15)
    await renderAt(`/deals/${code}?tab=actions`)
    const table = await screen.findByRole('table', { name: 'Action 목록' })
    const rows = within(table).getAllByRole('row').slice(1)
    // then: 첫 행만 기한초과로 표시되고 이전 행들은 표시되지 않는다
    expect(within(rows[0]!).getByText('기한초과')).toBeVisible()
    for (const older of rows.slice(1)) expect(within(older).queryByText('기한초과')).not.toBeInTheDocument()
  })
})
