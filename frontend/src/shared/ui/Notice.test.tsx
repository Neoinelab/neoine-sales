import { render, screen } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { describe, expect, it, vi } from 'vitest'
import { Notice } from './Notice'

describe('Notice', () => {
  it('announces info and success as status', () => {
    render(<Notice kind="success">저장되었습니다.</Notice>)

    expect(screen.getByRole('status')).toHaveTextContent('저장되었습니다.')
  })

  it('announces errors as alert', () => {
    render(<Notice kind="error">실패</Notice>)

    expect(screen.getByRole('alert')).toHaveTextContent('실패')
  })

  it('can be dismissed', async () => {
    const onClose = vi.fn()
    render(<Notice onClose={onClose}>내용</Notice>)

    await userEvent.click(screen.getByRole('button', { name: '닫기' }))

    expect(onClose).toHaveBeenCalled()
  })

  it('has no close button without onClose', () => {
    render(<Notice>내용</Notice>)

    expect(screen.queryByRole('button', { name: '닫기' })).not.toBeInTheDocument()
  })
})
