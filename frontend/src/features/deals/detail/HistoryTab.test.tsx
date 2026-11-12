import { screen, waitFor, within } from '@testing-library/react'
import { describe, expect, it } from 'vitest'
import { gateway } from '../../../gateway'
import { renderAt } from '../../../test/mockApp'
import { detailPath } from '../../../test/detailTestUtils'

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
  // 이력 표는 변경 시각·변경자·변경 대상·변경 전·변경 후를 최신순으로 보인다.
  // 테스트 코드: DD-106
  it('shows when, who, what, before and after, newest first', async () => {
    // when: Deal History 탭을 연다 (전제: 파트너를 교체한 Deal)
    const { table } = await openHistory(17, '누리통신 MFA')
    // then: 머리글 다섯 개가 순서대로 있고 파트너 행에 전후 파트너가 보인다
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

  // 퇴사한 변경자는 '이름(퇴사)'로 보인다.
  // 테스트 코드: DD-106
  it('shows a resigned user as 이름(퇴사)', async () => {
    // when: Deal History 탭을 연다 (전제: 퇴사자가 변경한 이력이 있는 Deal)
    const { table } = await openHistory(1, '한빛은행 ITDR 도입')
    // then: '강퇴사(퇴사)'가 표에 보인다
    expect(within(table).getAllByText('강퇴사(퇴사)').length).toBeGreaterThan(0)
  })

  // 변경 대상으로 거르면 그 구분의 행만 남는다.
  // 테스트 코드: DD-107
  it('filters by the change target', async () => {
    // given: 여러 구분의 이력이 있는 Deal
    const { user, table } = await openHistory(1, '한빛은행 ITDR 도입')
    const total = bodyRows(table).length
    // when: '변경 대상'에서 첨부 파일을 고른다
    await user.selectOptions(screen.getByLabelText('변경 대상'), '첨부 파일')
    // then: 행 수가 줄고 모든 행의 대상이 '첨부 파일'이다
    await waitFor(() => expect(bodyRows(table).length).toBeLessThan(total))
    for (const row of bodyRows(table)) expect(within(row).getByRole('cell', { name: '첨부 파일' })).toBeVisible()
  })

  // 결과가 없는 구분은 '변경 이력이 없습니다.'를 보인다.
  // 테스트 코드: DD-107
  it('tells there is no history for a filter without results', async () => {
    // given: 파트너 이력이 없는 Deal
    const { user } = await openHistory(2, '대한제조 MFA 확대')
    // when: '변경 대상'에서 파트너를 고른다
    await user.selectOptions(screen.getByLabelText('변경 대상'), '파트너')
    // then: '변경 이력이 없습니다.'가 보인다
    expect(await screen.findByText('변경 이력이 없습니다.')).toBeVisible()
  })

  // 이력은 읽기 전용이고 20행씩 페이지로 나뉜다.
  // 테스트 코드: DD-108
  it('is read only and paginates by 20 rows', async () => {
    // given: 변경을 25번 더 쌓은 Deal
    const { user, client, table } = await openHistory(1, '한빛은행 ITDR 도입')
    expect(screen.queryByRole('button', { name: '수정' })).not.toBeInTheDocument()
    // 20건을 넘기도록 변경을 쌓는다(화면 밖에서 같은 게이트웨이로).
    const code = (await gateway.deals.list({ keyword: '한빛은행 ITDR', limit: 5 })).items[0]!.code
    for (let i = 0; i < 25; i += 1) {
      await gateway.deals.applyChange(code, { change: { field: 'revenueAmount', value: 1_000_000_000 + i * 1000 } })
    }
    await client.invalidateQueries()
    const pager = await screen.findByRole('navigation', { name: '페이지' })
    await waitFor(() => expect(within(pager).getByRole('button', { name: '다음' })).toBeEnabled())
    expect(bodyRows(table)).toHaveLength(20)
    // when: Deal History 탭을 열고 다음 페이지로 간다
    await user.click(within(pager).getByRole('button', { name: '다음' }))
    // then: 수정 버튼이 없고 첫 페이지가 20행이며 다음 페이지가 더 적은 행이다
    expect(bodyRows(table).length).toBeGreaterThan(0)
    expect(bodyRows(table).length).toBeLessThan(20)
  })
})
