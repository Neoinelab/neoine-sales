import { render, screen } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { describe, expect, it, vi } from 'vitest'
import { Pager } from './Pager'

describe('Pager', () => {
  it('uses total to disable next on the last page', () => {
    render(<Pager offset={20} limit={20} total={40} onChange={() => {}} />)

    expect(screen.getByRole('button', { name: '다음' })).toBeDisabled()
    expect(screen.getByRole('button', { name: '이전' })).toBeEnabled()
  })

  it('enables next when more rows remain by total', async () => {
    const onChange = vi.fn()
    render(<Pager offset={0} limit={20} total={41} onChange={onChange} />)

    await userEvent.click(screen.getByRole('button', { name: '다음' }))

    expect(onChange).toHaveBeenCalledWith(20)
  })

  it('still works with count only (existing callers)', () => {
    render(<Pager offset={0} limit={20} count={20} onChange={() => {}} />)

    expect(screen.getByRole('button', { name: '다음' })).toBeEnabled()
  })
})
