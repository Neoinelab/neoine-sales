import { screen, waitFor, within } from '@testing-library/react'
import { describe, expect, it } from 'vitest'
import { gateway } from '../../../gateway'
import { renderAt } from '../../../test/mockApp'
import { dataRows, rowOf } from './testHelpers'

/** 정렬 버튼이 있는 10개 머리글(BANT·Next Action 제외). */
const SORTABLE = ['Deal', '담당자', '고객사', '파트너사', 'Vendor', 'Status', 'Forecast', '금액(단위:천원)', 'Expected Close', '최종 업데이트']
const NOT_SORTABLE = ['BANT', 'Next Action']

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

describe('목록 머리글 정렬 (AC-1)', () => {
  it('BANT와 Next Action을 뺀 10개 헤더만 정렬 버튼이다', async () => {
    await renderAt('/deals')
    await rowOf(/한빛은행 ITDR 도입/)

    const headers = screen.getAllByRole('columnheader')
    const withButton = headers.filter((h) => within(h).queryByRole('button') !== null).map((h) => h.textContent?.trim())
    expect(withButton).toEqual(SORTABLE)
    for (const name of SORTABLE) expect(within(screen.getByRole('columnheader', { name })).getByRole('button')).toBeVisible()
    for (const name of NOT_SORTABLE) {
      const header = screen.getByRole('columnheader', { name })
      expect(within(header).queryByRole('button')).not.toBeInTheDocument()
      expect(header).not.toHaveAttribute('aria-sort')
    }
  })
})

describe('목록 머리글 정렬 토글 (AC-2)', () => {
  it.each(NEW_COLUMNS)('%s 헤더를 누르면 오름차순, 다시 누르면 내림차순이고 표시·aria-sort·URL이 맞다', async (label, sort) => {
    const { user, location } = await renderAt('/deals')
    await rowOf(/한빛은행 ITDR 도입/)

    await user.click(screen.getByRole('button', { name: label }))
    await waitFor(() => expect(screen.getByRole('columnheader', { name: label })).toHaveAttribute('aria-sort', 'ascending'))
    expect(location()).toBe(`/deals?sort=${sort}&order=asc`)
    expect(screen.getByRole('button', { name: label })).toHaveAttribute('data-dir', 'asc')

    await user.click(screen.getByRole('button', { name: label }))
    await waitFor(() => expect(screen.getByRole('columnheader', { name: label })).toHaveAttribute('aria-sort', 'descending'))
    expect(location()).toBe(`/deals?sort=${sort}&order=desc`)
    expect(screen.getByRole('button', { name: label })).toHaveAttribute('data-dir', 'desc')
  })

  it('정렬 중인 열에만 방향 표시와 aria-sort가 있다', async () => {
    const { user } = await renderAt('/deals')
    await rowOf(/한빛은행 ITDR 도입/)

    await user.click(screen.getByRole('button', { name: '담당자' }))
    await waitFor(() => expect(screen.getByRole('columnheader', { name: '담당자' })).toHaveAttribute('aria-sort', 'ascending'))

    for (const name of SORTABLE.filter((n) => n !== '담당자')) {
      const header = screen.getByRole('columnheader', { name })
      expect(header).not.toHaveAttribute('aria-sort')
      expect(within(header).getByRole('button')).not.toHaveAttribute('data-dir')
    }
  })

  it('다른 열로 옮기면 그 열의 기본 방향으로 시작하고 이전 열 표시는 사라진다', async () => {
    const { user, location } = await renderAt('/deals?sort=owner&order=desc')
    await rowOf(/한빛은행 ITDR 도입/)

    await user.click(screen.getByRole('button', { name: '금액(단위:천원)' }))

    await waitFor(() => expect(screen.getByRole('columnheader', { name: '금액(단위:천원)' })).toHaveAttribute('aria-sort', 'descending'))
    expect(screen.getByRole('columnheader', { name: '담당자' })).not.toHaveAttribute('aria-sort')
    expect(location()).toBe('/deals?sort=revenueAmount&order=desc')
  })

  it('정렬을 바꾸면 첫 페이지로 돌아간다', async () => {
    const { user, location } = await renderAt('/deals?page=2')
    await screen.findByRole('button', { name: '이전' })

    await user.click(screen.getByRole('button', { name: '고객사' }))

    await waitFor(() => expect(location()).toBe('/deals?sort=customer&order=asc'))
  })

  it('URL의 새 정렬 값을 머리글 표시로 복원한다', async () => {
    await renderAt('/deals?sort=vendor&order=desc')

    expect(await screen.findByRole('columnheader', { name: 'Vendor' })).toHaveAttribute('aria-sort', 'descending')
  })
})

describe('새 정렬이 행 순서에 반영된다 (AC-2·4)', () => {
  it.each(NEW_COLUMNS)('%s 정렬 오름차순·내림차순은 게이트웨이 정렬 결과와 같은 순서로 행을 보인다', async (label, sort) => {
    const { user } = await renderAt('/deals')
    await rowOf(/한빛은행 ITDR 도입/)
    const initial = rowNames()
    const expectedAsc = (await gateway.deals.list({ sort, order: 'asc', limit: 20 })).items.map((d) => d.name)
    const expectedDesc = (await gateway.deals.list({ sort, order: 'desc', limit: 20 })).items.map((d) => d.name)
    expect(expectedAsc).not.toEqual(initial) // 기본 정렬과 달라야 정렬이 일어났음을 알 수 있다

    await user.click(screen.getByRole('button', { name: label }))
    await waitFor(() => expect(rowNames()).toEqual(expectedAsc))

    await user.click(screen.getByRole('button', { name: label }))
    await waitFor(() => expect(rowNames()).toEqual(expectedDesc))
  })

  it('파트너가 없는 Deal은 오름차순·내림차순 모두 마지막에 있다', async () => {
    const { user } = await renderAt('/deals?mine=1') // 한 페이지에 모두 보이는 조건
    await rowOf(/한빛은행 ITDR 도입/)
    const partnerColumn = screen.getAllByRole('columnheader').findIndex((h) => h.textContent?.trim() === '파트너사')
    const partnerCells = () => dataRows().map((row) => within(row).getAllByRole('cell')[partnerColumn]?.textContent?.trim())

    await user.click(screen.getByRole('button', { name: '파트너사' }))
    await waitFor(() => expect(screen.getByRole('columnheader', { name: '파트너사' })).toHaveAttribute('aria-sort', 'ascending'))
    const asc = partnerCells()
    await user.click(screen.getByRole('button', { name: '파트너사' }))
    await waitFor(() => expect(screen.getByRole('columnheader', { name: '파트너사' })).toHaveAttribute('aria-sort', 'descending'))
    const desc = partnerCells()

    for (const cells of [asc, desc]) {
      const firstEmpty = cells.findIndex((text) => text === '—')
      expect(firstEmpty).toBeGreaterThan(0)
      expect(cells.slice(firstEmpty).every((text) => text === '—')).toBe(true)
    }
  })
})
