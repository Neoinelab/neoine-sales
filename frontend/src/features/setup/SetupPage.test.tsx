import { screen } from '@testing-library/react'
import { afterEach, describe, expect, it, vi } from 'vitest'
import { openFreshSetup } from '../../test/localAccounts'

afterEach(() => vi.restoreAllMocks())

describe('최초 설정 화면 (BDD 밖)', () => {
  // 최초 설정 화면에는 UI 목업 배지가 없다(실제 서버 게이트웨이로 동작한다는 표시).
  it('shows no mock badge', async () => {
    // when: /setup을 연다 (전제: 최초 설정이 처음 상태다)
    await openFreshSetup()

    // then: "UI 목업" 문구가 없다
    expect(screen.queryByText(/UI 목업/)).not.toBeInTheDocument()
  })
})
