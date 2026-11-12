import { render, screen } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { describe, expect, it, vi } from 'vitest'
import { Notice } from './Notice'

describe('Notice', () => {
  // 테스트 코드: UI-054
  it('success 알림은 status로 알린다', () => {
    // when: success 알림을 그린다
    render(<Notice kind="success">저장되었습니다.</Notice>)
    // then: role이 status다
    expect(screen.getByRole('status')).toHaveTextContent('저장되었습니다.')
  })

  // 테스트 코드: UI-054
  it('error 알림은 alert로 알린다', () => {
    // when: error 알림을 그린다
    render(<Notice kind="error">실패</Notice>)
    // then: role이 alert다
    expect(screen.getByRole('alert')).toHaveTextContent('실패')
  })

  // 테스트 코드: UI-054
  it('onClose가 있으면 닫기 버튼으로 닫을 수 있다', async () => {
    // given: onClose가 있는 알림
    const onClose = vi.fn()
    render(<Notice onClose={onClose}>내용</Notice>)
    // when: "닫기"를 누른다
    await userEvent.click(screen.getByRole('button', { name: '닫기' }))
    // then: onClose가 불린다
    expect(onClose).toHaveBeenCalled()
  })

  // 테스트 코드: UI-054
  it('onClose가 없으면 닫기 버튼이 없다', () => {
    // when: onClose 없는 알림을 그린다
    render(<Notice>내용</Notice>)
    // then: 닫기 버튼이 없다
    expect(screen.queryByRole('button', { name: '닫기' })).not.toBeInTheDocument()
  })
})
