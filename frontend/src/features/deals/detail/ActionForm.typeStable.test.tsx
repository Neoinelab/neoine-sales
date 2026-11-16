import { screen, waitFor, within } from '@testing-library/react'
import { afterEach, describe, expect, it, vi } from 'vitest'
import { gateway } from '../../../gateway'
import { ApiError } from '../../../shared/api/problem'
import { detailPath } from '../../../test/detailTestUtils'
import { renderAt } from '../../../test/mockApp'

/**
 * Action 폼 유형 입력의 안정성(리뷰 후속): 유형 목록이 로딩 중이거나 실패했을 때는 "새 유형" 안내 대신 상태에 맞는 표시만 보인다.
 */
afterEach(() => vi.restoreAllMocks())

const HINT = '목록에 없는 유형입니다. 저장하면 새 유형으로 추가됩니다.'
const LOAD_ERROR = '유형 목록을 불러오지 못했습니다.'

async function openAddForm() {
  const view = await renderAt(await detailPath(1, '?tab=actions'), { role: 'sales' })
  await screen.findByRole('heading', { level: 1, name: '한빛은행 ITDR 도입' })
  await screen.findByRole('table', { name: 'Action 목록' })
  await view.user.click(screen.getByRole('button', { name: 'Action 추가' }))
  const form = screen.getByRole('form', { name: 'Action 추가' })
  return { ...view, form, type: within(form).getByLabelText('유형') }
}

describe('유형 목록이 로딩 중이거나 실패했을 때', () => {
  // 유형 목록을 읽는 중에는 새 유형 안내를 보이지 않는다.
  // 테스트 코드: AC-078
  it('does not hint that a typed type is new while the list is still loading', async () => {
    // given: 유형 목록이 끝나지 않게 한 추가 팝업
    vi.spyOn(gateway.actionTypes, 'list').mockImplementation(() => new Promise(() => undefined))
    const { user, type } = await openAddForm()

    // when: 유형을 입력한다
    await user.type(type, '미팅')

    // then: 새 유형 안내가 없다
    expect(screen.queryByText(HINT)).not.toBeInTheDocument()
  })

  // 유형 목록을 읽지 못하면 새 유형 안내 대신 오류 배너를 보인다.
  // 테스트 코드: AC-078
  it('shows an error alert instead of the new-type hint when the list cannot be read', async () => {
    // given: 유형 목록 읽기가 실패하도록 한 추가 팝업
    vi.spyOn(gateway.actionTypes, 'list').mockRejectedValue(
      new ApiError(500, { type: 'https://sales.neoine.test/problems/internal', title: 'x', status: 500, detail: LOAD_ERROR }),
    )
    const { user, form, type } = await openAddForm()

    // when: 유형을 입력한다
    await user.type(type, '미팅')

    // then: 폼 안에 오류 배너가 보인다
    await waitFor(() => expect(within(form).getByText(LOAD_ERROR).closest('[role="alert"]')).not.toBeNull())
    // then: 새 유형 안내가 없다
    expect(screen.queryByText(HINT)).not.toBeInTheDocument()
  })
})
