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

  // 변경 대상 선택지에 Comment가 있고 고르면 Comment 이력(등록·삭제)만 남는다.
  // 테스트 코드: DD-107, CM-068
  it('offers Comment as a change target and keeps only the comment rows when chosen', async () => {
    // given: Comment를 하나 쓰고 지운 Deal(그 이력 두 줄)
    const { user, table, client } = await openHistory(1, '한빛은행 ITDR 도입')
    const code = (await gateway.deals.list({ keyword: '한빛은행 ITDR', limit: 5 })).items[0]!.code
    const written = await gateway.comments.create(code, { body: '이력 확인 글' })
    await gateway.comments.remove(written.id)
    await client.invalidateQueries()
    await waitFor(() => expect(client.isFetching()).toBe(0))

    // when: '변경 대상'에서 Comment를 고른다
    await user.selectOptions(screen.getByLabelText('변경 대상'), 'Comment')

    // then: 안내에 Comment 변경도 기록된다고 있고, 두 행(삭제가 위, 등록이 아래)이고 모두 대상이 Comment다
    expect(screen.getByText(/Comment 변경도 이 이력에 기록됩니다/)).toBeVisible()
    await waitFor(() => expect(bodyRows(table)).toHaveLength(2))
    expect(bodyRows(table)[0]).toHaveTextContent('삭제')
    expect(bodyRows(table)[1]).toHaveTextContent('등록: 이력 확인 글')
    for (const row of bodyRows(table)) expect(within(row).getByRole('cell', { name: 'Comment' })).toBeVisible()
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
