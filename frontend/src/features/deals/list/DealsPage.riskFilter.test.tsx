import { screen, waitFor, within } from '@testing-library/react'
import { describe, expect, it } from 'vitest'
import { gateway } from '../../../gateway'
import { DEFAULT_DEALS_URL_PATTERN } from '../../../test/dealsUrl'
import { renderAt } from '../../../test/mockApp'
import { ALL_DEALS, dataRows, rowOf } from './testHelpers'

function rowNames(): string[] {
  return dataRows().map((row) => within(row).getAllByRole('link')[0]?.textContent ?? '')
}

async function expectedNames(filter: { overdue?: boolean; stale?: boolean }): Promise<string[]> {
  const page = await gateway.deals.list({ ...filter, limit: 20 })
  return page.items.map((d) => d.name)
}

const overdueBox = () => screen.getByRole('checkbox', { name: '기한초과' })
const staleBox = () => screen.getByRole('checkbox', { name: '미업데이트' })

describe('Deals 필터: 기한초과·미업데이트 (AC-9)', () => {
  it('has the two checkboxes, off by default', async () => {
    await renderAt(ALL_DEALS)
    await rowOf(/한빛은행 ITDR 도입/)

    expect(overdueBox()).not.toBeChecked()
    expect(staleBox()).not.toBeChecked()
  })

  it('기한초과 체크는 overdue=1을 URL에 쓰고 첫 페이지로 가며 해당 Deal만 보인다', async () => {
    const { user, location } = await renderAt('/deals?year=all&page=2')
    await screen.findByRole('button', { name: '이전' })
    const expected = await expectedNames({ overdue: true })
    expect(expected.length).toBeGreaterThan(0)

    await user.click(overdueBox())

    await waitFor(() => expect(rowNames()).toEqual(expected))
    expect(location()).toBe('/deals?year=all&overdue=1')
    expect(location()).not.toContain('page=')
    expect(overdueBox()).toBeChecked()
    expect(dataRows().length).toBeLessThan(20)
  })

  it('미업데이트 체크는 stale=1을 URL에 쓰고 해당 Deal만 보인다', async () => {
    const { user, location } = await renderAt(ALL_DEALS)
    await rowOf(/한빛은행 ITDR 도입/)
    const expected = await expectedNames({ stale: true })
    expect(expected.length).toBeGreaterThan(0)

    await user.click(staleBox())

    await waitFor(() => expect(rowNames()).toEqual(expected))
    expect(location()).toBe('/deals?year=all&stale=1')
    expect(staleBox()).toBeChecked()
  })

  it('둘 다 켜면 어느 하나라도 해당하는 Deal이 보인다', async () => {
    const { user, location } = await renderAt(ALL_DEALS)
    await rowOf(/한빛은행 ITDR 도입/)
    const either = await expectedNames({ overdue: true, stale: true })
    const onlyOverdue = await expectedNames({ overdue: true })
    expect(either.length).toBeGreaterThanOrEqual(onlyOverdue.length)

    await user.click(overdueBox())
    await user.click(staleBox())

    await waitFor(() => expect(rowNames()).toEqual(either))
    expect(location()).toContain('overdue=1')
    expect(location()).toContain('stale=1')
  })

  it('체크를 끄면 키가 지워지고 전체 목록으로 돌아간다', async () => {
    const { user, location } = await renderAt('/deals?year=all&overdue=1')
    await waitFor(() => expect(overdueBox()).toBeChecked())

    await user.click(overdueBox())

    await waitFor(() => expect(location()).toBe('/deals?year=all'))
    await waitFor(() => expect(dataRows()).toHaveLength(20))
    expect(overdueBox()).not.toBeChecked()
  })

  it('URL의 overdue=1·stale=1을 체크 상태로 복원한다', async () => {
    await renderAt('/deals?overdue=1&stale=1')

    await waitFor(() => expect(overdueBox()).toBeChecked())
    expect(staleBox()).toBeChecked()
  })

  it('알 수 없는 값(overdue=yes)은 체크되지 않고 조회에도 쓰이지 않는다', async () => {
    await renderAt('/deals?overdue=yes&stale=0')
    await rowOf(/한빛은행 ITDR 도입/)

    expect(overdueBox()).not.toBeChecked()
    expect(staleBox()).not.toBeChecked()
    expect(dataRows()).toHaveLength(20)
  })

  it('초기화하면 두 체크가 꺼지고 URL이 기본 조건 주소가 된다', async () => {
    const { user, location } = await renderAt('/deals?overdue=1&stale=1')
    await waitFor(() => expect(overdueBox()).toBeChecked())

    await user.click(screen.getByRole('button', { name: '초기화' }))

    await waitFor(() => expect(location()).toMatch(DEFAULT_DEALS_URL_PATTERN))
    expect(overdueBox()).not.toBeChecked()
    expect(staleBox()).not.toBeChecked()
  })

  it('다른 조건과 AND로 결합한다', async () => {
    const { user, location } = await renderAt('/deals?mine=1')
    await rowOf(/한빛은행 ITDR 도입/)
    const mineRisky = (await gateway.deals.list({ mine: true, overdue: true, stale: true, limit: 20 })).items.map((d) => d.name)
    expect(mineRisky.length).toBeGreaterThan(0)

    await user.click(overdueBox())
    await user.click(staleBox())

    await waitFor(() => expect(rowNames()).toEqual(mineRisky))
    expect(location()).toContain('mine=1')
  })

  it('overdue만 있는 URL도 활성 필터로 본다(빈 목록 문구)', async () => {
    await renderAt('/deals?overdue=1', { seed: 'empty' })

    expect(await screen.findByText('조건에 맞는 Deal이 없습니다.')).toBeVisible()
  })
})
