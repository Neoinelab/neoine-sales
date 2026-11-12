import { fireEvent, screen } from '@testing-library/react'
import { describe, expect, it } from 'vitest'
import { renderAt } from '../../../test/mockApp'
import { detailPath } from '../../../test/detailTestUtils'

async function openSearch() {
  const view = await renderAt(await detailPath(1, '?tab=actions'), { role: 'sales' })
  await screen.findByRole('heading', { level: 1, name: '한빛은행 ITDR 도입' })
  await screen.findByRole('table', { name: 'Action 목록' })
  return { ...view, keyword: screen.getByLabelText('키워드') }
}

describe('Actions 검색: 키워드 길이', () => {
  // 키워드 칸은 100자까지만 입력된다.
  // 테스트 코드: NA-060
  it('limits the keyword input to 100 characters', async () => {
    // when: Actions 탭의 키워드 칸을 본다.
    const { keyword } = await openSearch()

    // then: 입력 길이 제한이 100이다.
    expect(keyword).toHaveAttribute('maxlength', '100')
  })

  // 100자 키워드로 검색하면 오류 없이 빈 결과 문구가 나온다.
  // 테스트 코드: NA-060
  it('searches with a 100 character keyword and shows the empty result, not an error', async () => {
    // given: 키워드 칸에 100자를 썼다.
    const { user, keyword } = await openSearch()
    fireEvent.change(keyword, { target: { value: 'k'.repeat(100) } })

    // when: "검색"을 누른다.
    await user.click(screen.getByRole('button', { name: '검색' }))

    // then: "조건에 맞는 Action이 없습니다."가 나오고 오류 배너는 없다.
    expect(await screen.findByText('조건에 맞는 Action이 없습니다.')).toBeVisible()
    expect(screen.queryByRole('alert')).not.toBeInTheDocument()
  })
})
