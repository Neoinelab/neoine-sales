import { screen, within } from '@testing-library/react'
import { describe, expect, it } from 'vitest'
import { renderAt } from '../../../test/mockApp'
import { ALL_DEALS, rowOf } from './testHelpers'

// 목록의 BANT 열은 제거되었다(deal-list-columns-plan AC1). 열 구조·BANT 없음 검증은 DealsPage.columns.test.tsx.
// 여기에는 BANT 열과 무관하게 남는 계약(정렬 가능 헤더, 필터에 BANT 없음)만 둔다.

describe('목록 헤더 정렬', () => {
  // 기존 정렬 머리글은 계속 정렬 버튼이다
  // 테스트 코드: DL-089
  it('keeps the existing sortable headers sortable', async () => {
    // given: 목록 머리글
    await renderAt(ALL_DEALS)

    // when: 머리글을 확인한다
    await rowOf(/한빛은행 ITDR 도입/)

    // then: 기존 정렬 열이 정렬 버튼이다
    for (const name of ['Deal', '금액(단위:원)', 'Expected Close', '최종 업데이트']) {
      expect(within(screen.getByRole('columnheader', { name })).getByRole('button')).toBeVisible()
    }
  })
})

describe('목록 필터에는 BANT Label 선택이 없다', () => {
  // 필터 영역에 BANT Label 선택이 없다
  // 테스트 코드: DL-072
  it('has no Budget, Authority, Need or Timeline Label select in the filter area', async () => {
    // given: 목록 필터 바
    await renderAt(ALL_DEALS)
    await rowOf(/한빛은행 ITDR 도입/)

    // when: 필터 영역을 확인한다
    const filters = screen.getByRole('search', { name: 'Deal 필터' })

    // then: Budget·Authority·Need·Timeline 선택이 없다
    for (const name of ['Budget Label', 'Authority Label', 'Need Label', 'Timeline Label']) {
      expect(within(filters).queryByLabelText(name)).not.toBeInTheDocument()
    }
    expect(within(filters).queryAllByLabelText(/Label$/)).toEqual([])
  })

  // 예전 BANT 키가 있어도 전체를 보이고 화면이 동작한다
  // 테스트 코드: DL-072
  it('lists every deal and keeps the page working with old BANT keys in the URL', async () => {
    // given: 예전 BANT 키가 든 주소
    const { location } = await renderAt('/deals?year=all&budget=1&authority=2&need=3&timeline=4')

    // when: 그 주소를 연다
    await rowOf(/한빛은행 ITDR 도입/)

    // then: 키를 무시하고 전체를 보인다
    expect(screen.queryByText(/조건에 맞는 Deal이 없습니다/)).not.toBeInTheDocument()
    expect(screen.queryByRole('alert')).not.toBeInTheDocument()
    expect(location()).toContain('budget=1') // URL은 건드리지 않는다
    expect(screen.getAllByRole('row').length).toBeGreaterThan(1)
  })

  // 예전 BANT 키는 활성 필터로 세지 않는다
  // 테스트 코드: DL-072
  it('does not treat the old BANT keys as an active filter for the empty message', async () => {
    // when: 그 주소를 연다 (전제: 결과 없는 예전 BANT 키 주소)
    await renderAt('/deals?year=all&budget=1&authority=2&need=3&timeline=4', { seed: 'empty' })

    // then: '등록된 Deal이 없습니다.' 쪽 문구를 쓴다
    expect(await screen.findByText('등록된 Deal이 없습니다.')).toBeVisible()
    expect(screen.queryByText('조건에 맞는 Deal이 없습니다.')).not.toBeInTheDocument()
  })
})
