import { fireEvent, screen } from '@testing-library/react'
import { describe, expect, it } from 'vitest'
import { renderAt } from '../../../test/mockApp'
import { detailPath } from '../../../test/detailTestUtils'

async function openSearch() {
  const view = await renderAt(await detailPath(1), { role: 'sales' })
  await screen.findByRole('heading', { level: 1, name: '한빛은행 ITDR 도입' })
  await screen.findByRole('table', { name: 'Action 목록' })
  return { ...view, keyword: screen.getByLabelText('키워드') }
}

describe('Actions 검색: 키워드 길이 (Q6 c, 서버 max_length=100)', () => {
  it('limits the keyword input to 100 characters', async () => {
    const { keyword } = await openSearch()

    expect(keyword).toHaveAttribute('maxlength', '100')
  })

  it('searches with a 100 character keyword and shows the empty result, not an error', async () => {
    const { user, keyword } = await openSearch()
    fireEvent.change(keyword, { target: { value: 'k'.repeat(100) } })

    await user.click(screen.getByRole('button', { name: '검색' }))

    expect(await screen.findByText('조건에 맞는 Action이 없습니다.')).toBeVisible()
    expect(screen.queryByRole('alert')).not.toBeInTheDocument()
  })
})
