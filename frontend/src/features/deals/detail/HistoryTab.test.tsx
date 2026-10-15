import { screen, waitFor, within } from '@testing-library/react'
import { describe, expect, it } from 'vitest'
import { gateway } from '../../../gateway'
import { renderAt } from '../../../test/mockApp'
import { detailPath } from './detailTestUtils'

async function openHistory(no: number, title: string) {
  const view = await renderAt(await detailPath(no, '?tab=history'))
  await screen.findByRole('heading', { level: 1, name: title })
  const table = await screen.findByRole('table', { name: 'Deal History' })
  return { ...view, table }
}

function bodyRows(table: HTMLElement) {
  return within(table).getAllByRole('row').slice(1)
}

describe('Deal History 탭 (T-DETAIL / DL-11)', () => {
  it('shows when, who, what, before and after, newest first', async () => {
    const { table } = await openHistory(17, '누리통신 MFA')
    expect(within(table).getAllByRole('columnheader').map((h) => h.textContent)).toEqual([
      '변경 시각',
      '변경자',
      '변경 대상',
      '변경 전',
      '변경 후',
    ])
    const partner = bodyRows(table).find((r) => within(r).queryByRole('cell', { name: '파트너' }))
    expect(partner).toBeDefined()
    expect(partner).toHaveTextContent('코어테크')
    expect(partner).toHaveTextContent('에이원시스템')
  })

  it('shows a resigned user as 이름(퇴사)', async () => {
    const { table } = await openHistory(1, '한빛은행 ITDR 도입')
    expect(within(table).getAllByText('강퇴사(퇴사)').length).toBeGreaterThan(0)
  })

  it('filters by the change target', async () => {
    const { user, table } = await openHistory(1, '한빛은행 ITDR 도입')
    const total = bodyRows(table).length
    await user.selectOptions(screen.getByLabelText('변경 대상'), '첨부 파일')
    await waitFor(() => expect(bodyRows(table).length).toBeLessThan(total))
    for (const row of bodyRows(table)) expect(within(row).getByRole('cell', { name: '첨부 파일' })).toBeVisible()
  })

  it('tells there is no history for a filter without results', async () => {
    const { user } = await openHistory(2, '대한제조 MFA 확대')
    await user.selectOptions(screen.getByLabelText('변경 대상'), '파트너')
    expect(await screen.findByText('변경 이력이 없습니다.')).toBeVisible()
  })

  it('is read only and paginates by 20 rows', async () => {
    const { user, client, table } = await openHistory(1, '한빛은행 ITDR 도입')
    expect(screen.queryByRole('button', { name: '수정' })).not.toBeInTheDocument()
    // 20건을 넘기도록 변경을 쌓는다(화면 밖에서 같은 게이트웨이로).
    const code = (await gateway.deals.list({ keyword: '한빛은행 ITDR', limit: 5 })).items[0]!.code
    for (let i = 0; i < 25; i += 1) {
      await gateway.deals.applyChange(code, { change: { field: 'revenueAmount', value: 1_000_000_000 + i } })
    }
    await client.invalidateQueries()
    const pager = await screen.findByRole('navigation', { name: '페이지' })
    await waitFor(() => expect(within(pager).getByRole('button', { name: '다음' })).toBeEnabled())
    expect(bodyRows(table)).toHaveLength(20)
    await user.click(within(pager).getByRole('button', { name: '다음' }))
    expect(bodyRows(table).length).toBeGreaterThan(0)
    expect(bodyRows(table).length).toBeLessThan(20)
  })
})
