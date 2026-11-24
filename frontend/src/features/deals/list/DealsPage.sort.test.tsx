import { screen, waitFor, within } from '@testing-library/react'
import { describe, expect, it } from 'vitest'
import { gateway } from '../../../gateway'
import { renderAt } from '../../../test/mockApp'
import { ALL_DEALS, dataRows, rowOf } from './testHelpers'

/** 정렬 버튼이 있는 10개 머리글(Next Action·Due·Next Action 상태 제외). */
const SORTABLE = ['Deal', '담당자', '고객사', '파트너사', 'Vendor', 'Status', 'Forecast', '금액(단위:원)', 'Expected Close', '최종 업데이트']
const NOT_SORTABLE = ['Next Action', 'Due Date', 'Next Action 상태']

/** 새로 정렬할 수 있게 된 5개 열: 머리글, URL sort 값. */
const NEW_COLUMNS = [
  ['담당자', 'owner'],
  ['고객사', 'customer'],
  ['파트너사', 'partner'],
  ['Vendor', 'vendor'],
  ['Forecast', 'forecastKey'],
] as const

function rowNames(): string[] {
  return dataRows().map((row) => within(row).getAllByRole('link')[0]?.textContent ?? '')
}

describe('목록 머리글 정렬', () => {
  // 정렬 버튼은 10개 머리글뿐이다
  // 테스트 코드: DL-089
  it('Next Action·Due·Next Action 상태를 뺀 10개 헤더만 정렬 버튼이다', async () => {
    // given: 목록 머리글
    await renderAt(ALL_DEALS)
    await rowOf(/한빛은행 ITDR 도입/)

    const headers = screen.getAllByRole('columnheader')
    // when: 머리글을 확인한다
    const withButton = headers.filter((h) => within(h).queryByRole('button') !== null).map((h) => h.textContent?.trim())
    // then: Next Action 세 열을 뺀 10열만 정렬 버튼이다
    expect(withButton).toEqual(SORTABLE)
    for (const name of SORTABLE) expect(within(screen.getByRole('columnheader', { name })).getByRole('button')).toBeVisible()
    for (const name of NOT_SORTABLE) {
      const header = screen.getByRole('columnheader', { name })
      expect(within(header).queryByRole('button')).not.toBeInTheDocument()
      expect(header).not.toHaveAttribute('aria-sort')
    }
  })
})

describe('목록 머리글 정렬 토글', () => {
  // 머리글을 누르면 오름차순, 다시 누르면 내림차순이고 표시·aria-sort·URL이 맞다
  // 테스트 코드: DL-089
  it.each(NEW_COLUMNS)('%s 헤더를 누르면 오름차순, 다시 누르면 내림차순이고 표시·aria-sort·URL이 맞다', async (label, sort) => {
    // given: 정렬이 없는 목록
    const { user, location } = await renderAt(ALL_DEALS)
    await rowOf(/한빛은행 ITDR 도입/)

    // when: 머리글을 누른다
    await user.click(screen.getByRole('button', { name: label }))
    // then: 오름차순의 aria-sort·방향 표시·URL이 맞다
    await waitFor(() => expect(screen.getByRole('columnheader', { name: label })).toHaveAttribute('aria-sort', 'ascending'))
    expect(location()).toBe(`/deals?year=all&sort=${sort}&order=asc`)
    expect(screen.getByRole('button', { name: label })).toHaveAttribute('data-dir', 'asc')

    // when: 머리글을 한 번 더 누른다
    await user.click(screen.getByRole('button', { name: label }))
    // then: 내림차순의 aria-sort·방향 표시·URL이 맞다
    await waitFor(() => expect(screen.getByRole('columnheader', { name: label })).toHaveAttribute('aria-sort', 'descending'))
    expect(location()).toBe(`/deals?year=all&sort=${sort}&order=desc`)
    expect(screen.getByRole('button', { name: label })).toHaveAttribute('data-dir', 'desc')
  })

  // 정렬 중인 열에만 방향 표시와 aria-sort가 있다
  // 테스트 코드: DL-089
  it('정렬 중인 열에만 방향 표시와 aria-sort가 있다', async () => {
    // given: 담당자로 정렬한 목록
    const { user } = await renderAt(ALL_DEALS)
    await rowOf(/한빛은행 ITDR 도입/)

    // when: 머리글을 확인한다
    await user.click(screen.getByRole('button', { name: '담당자' }))
    // then: 다른 열에는 aria-sort와 방향 표시가 없다
    await waitFor(() => expect(screen.getByRole('columnheader', { name: '담당자' })).toHaveAttribute('aria-sort', 'ascending'))

    for (const name of SORTABLE.filter((n) => n !== '담당자')) {
      const header = screen.getByRole('columnheader', { name })
      expect(header).not.toHaveAttribute('aria-sort')
      expect(within(header).getByRole('button')).not.toHaveAttribute('data-dir')
    }
  })

  // 다른 열로 옮기면 그 열의 자연 방향으로 시작한다
  // 테스트 코드: DL-089
  it('다른 열로 옮기면 그 열의 기본 방향으로 시작하고 이전 열 표시는 사라진다', async () => {
    // given: 한 열로 정렬한 목록
    const { user, location } = await renderAt('/deals?year=all&sort=owner&order=desc')
    await rowOf(/한빛은행 ITDR 도입/)

    // when: 다른 열을 누른다
    await user.click(screen.getByRole('button', { name: '금액(단위:원)' }))

    // then: 새 열이 자연 방향이고 이전 열 표시는 사라진다
    await waitFor(() => expect(screen.getByRole('columnheader', { name: '금액(단위:원)' })).toHaveAttribute('aria-sort', 'descending'))
    expect(screen.getByRole('columnheader', { name: '담당자' })).not.toHaveAttribute('aria-sort')
    expect(location()).toBe('/deals?year=all&sort=revenueAmount&order=desc')
  })

  // 정렬을 바꾸면 1페이지로 돌아간다
  // 테스트 코드: DL-089
  it('정렬을 바꾸면 첫 페이지로 돌아간다', async () => {
    // given: 2페이지를 보던 목록
    const { user, location } = await renderAt('/deals?year=all&page=2')
    await screen.findByRole('button', { name: '이전' })

    // when: 머리글을 누른다
    await user.click(screen.getByRole('button', { name: '고객사' }))

    // then: page 키가 사라진다
    await waitFor(() => expect(location()).toBe('/deals?year=all&sort=customer&order=asc'))
  })

  // URL의 정렬 값을 머리글 표시로 복원한다
  // 테스트 코드: DL-089
  it('URL의 새 정렬 값을 머리글 표시로 복원한다', async () => {
    // when: 그 주소를 연다 (전제: 정렬이 든 주소)
    await renderAt('/deals?year=all&sort=vendor&order=desc')

    // then: 머리글에 방향이 표시된다
    expect(await screen.findByRole('columnheader', { name: 'Vendor' })).toHaveAttribute('aria-sort', 'descending')
  })
})

describe('새 정렬이 행 순서에 반영된다', () => {
  // 정렬하면 행이 서버 순서대로 보인다
  // 테스트 코드: DL-090
  it.each(NEW_COLUMNS)('%s 정렬 오름차순·내림차순은 게이트웨이 정렬 결과와 같은 순서로 행을 보인다', async (label, sort) => {
    // given: 정렬 전 목록
    const { user } = await renderAt(ALL_DEALS)
    await rowOf(/한빛은행 ITDR 도입/)
    const initial = rowNames()
    const expectedAsc = (await gateway.deals.list({ sort, order: 'asc', limit: 20 })).items.map((d) => d.name)
    const expectedDesc = (await gateway.deals.list({ sort, order: 'desc', limit: 20 })).items.map((d) => d.name)
    expect(expectedAsc).not.toEqual(initial) // 기본 정렬과 달라야 정렬이 일어났음을 알 수 있다

    // when: 머리글을 누른다
    await user.click(screen.getByRole('button', { name: label }))
    // then: 행 순서가 서버 오름차순 결과와 같다
    await waitFor(() => expect(rowNames()).toEqual(expectedAsc))

    // when: 머리글을 한 번 더 누른다
    await user.click(screen.getByRole('button', { name: label }))
    // then: 행 순서가 서버 내림차순 결과와 같다
    await waitFor(() => expect(rowNames()).toEqual(expectedDesc))
  })

  // 파트너 없는 Deal은 어느 방향이든 끝에 있다
  // 테스트 코드: DL-090
  it('파트너가 없는 Deal은 오름차순·내림차순 모두 마지막에 있다', async () => {
    // given: 파트너 없는 Deal이 섞인 목록
    const { user } = await renderAt('/deals?mine=1') // 한 페이지에 모두 보이는 조건
    await rowOf(/한빛은행 ITDR 도입/)
    const partnerColumn = screen.getAllByRole('columnheader').findIndex((h) => h.textContent?.trim() === '파트너사')
    const partnerCells = () => dataRows().map((row) => within(row).getAllByRole('cell')[partnerColumn]?.textContent?.trim())

    // when: 파트너사로 오름차순 정렬한다
    await user.click(screen.getByRole('button', { name: '파트너사' }))
    await waitFor(() => expect(screen.getByRole('columnheader', { name: '파트너사' })).toHaveAttribute('aria-sort', 'ascending'))
    const asc = partnerCells()
    // when: 파트너사로 내림차순 정렬한다
    await user.click(screen.getByRole('button', { name: '파트너사' }))
    await waitFor(() => expect(screen.getByRole('columnheader', { name: '파트너사' })).toHaveAttribute('aria-sort', 'descending'))
    const desc = partnerCells()

    // then: 두 방향 모두 '—' 칸이 끝에 모여 있다
    for (const cells of [asc, desc]) {
      const firstEmpty = cells.findIndex((text) => text === '—')
      expect(firstEmpty).toBeGreaterThan(0)
      expect(cells.slice(firstEmpty).every((text) => text === '—')).toBe(true)
    }
  })
})
