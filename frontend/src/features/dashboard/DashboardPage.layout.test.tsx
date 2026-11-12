import { screen, within } from '@testing-library/react'
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'
import { resetMock } from '../../test/fake/default'
import { renderAt } from '../../test/mockApp'
import { NOW } from './testHelpers'

/** 화면 배치: 탭이 최상단에 오고 검색 조건은 각 탭 패널 위쪽에 들어간다. */

beforeEach(() => resetMock({ now: NOW }))
afterEach(() => {
  vi.restoreAllMocks()
  resetMock({ now: null })
})

const follows = (a: Element, b: Element) => Boolean(a.compareDocumentPosition(b) & Node.DOCUMENT_POSITION_FOLLOWING)

describe('Dashboard 배치', () => {
  // 테스트 코드: DSH-025
  it.each(['status', 'forecast'])('%s 탭 패널 맨 위에 필터를 둔다', async (tab) => {
    // when: 탭을 연다
    await renderAt(`/dashboard?tab=${tab}`)

    // then: 필터 폼이 패널의 첫 제목보다 앞에 있다
    const panel = await screen.findByRole('tabpanel')
    const form = within(panel).getByRole('form', { name: 'Dashboard 필터' })
    const firstHeading = await within(panel).findAllByRole('heading', { level: 2 })
    expect(follows(form, firstHeading[0] as Element)).toBe(true)
  })

  // 테스트 코드: DSH-025
  it('제목 바로 아래에 탭이 있고 안내 줄은 탭 패널 안에 있다', async () => {
    // when: /dashboard를 연다
    await renderAt('/dashboard')

    // then: 탭 목록이 안내 줄보다 앞이고 안내 줄이 패널 안에 있으며 문구가 정확하다
    const tablist = await screen.findByRole('tablist', { name: 'Dashboard 보기' })
    const hint = await screen.findByText(/기간은 Expected Close 기준/)
    expect(follows(tablist, hint)).toBe(true)
    expect(within(screen.getByRole('tabpanel')).getByText(/기간은 Expected Close 기준/)).toBeVisible()
    expect(hint).toHaveTextContent(/^기간은 Expected Close 기준이며 금액 단위는 원입니다\. 기준일 \d{4}-\d{2}-\d{2}$/)
  })

  // 테스트 코드: DSH-025
  it.each(['Status', 'Forecast'])('%s 탭 이름 왼쪽에 장식용 아이콘이 있다', async (name) => {
    // when: /dashboard를 연다
    await renderAt('/dashboard')

    // then: 탭 안에 aria-hidden 아이콘이 이름보다 앞에 있다
    const tab = await screen.findByRole('tab', { name })
    const icon = tab.querySelector('svg')
    expect(icon).not.toBeNull()
    expect(icon).toHaveAttribute('aria-hidden', 'true')
    expect(follows(icon as Element, within(tab).getByText(name))).toBe(true)
  })

  // 테스트 코드: DSH-025
  it('공통 강조 탭 모양(tabs-prominent)을 쓴다', async () => {
    // when: /dashboard를 연다
    await renderAt('/dashboard')

    // then: 탭 목록의 부모가 tabs-prominent다
    expect((await screen.findByRole('tablist', { name: 'Dashboard 보기' })).parentElement).toHaveClass('tabs-prominent')
  })
})
