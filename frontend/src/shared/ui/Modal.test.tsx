import { render, screen } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { useState } from 'react'
import { describe, expect, it, vi } from 'vitest'
import { ConfirmDialog } from './ConfirmDialog'
import { Modal } from './Modal'

describe('Modal', () => {
  it('opens as a labelled modal dialog and moves focus into it', () => {
    render(
      <Modal title="매출 확정" onClose={() => {}}>
        <input aria-label="금액" />
      </Modal>,
    )

    const dialog = screen.getByRole('dialog', { name: '매출 확정' })
    expect(dialog).toHaveAttribute('aria-modal', 'true')
    expect(dialog).toContainElement(document.activeElement as HTMLElement)
    expect(screen.getByLabelText('금액')).toHaveFocus()
  })

  it('closes on Escape', async () => {
    const onClose = vi.fn()
    render(
      <Modal title="제목" onClose={onClose}>
        <button type="button">내용</button>
      </Modal>,
    )

    await userEvent.keyboard('{Escape}')

    expect(onClose).toHaveBeenCalledTimes(1)
  })

  it('keeps Tab focus inside the dialog', async () => {
    render(
      <>
        <button type="button">바깥</button>
        <Modal title="제목" onClose={() => {}}>
          <button type="button">첫째</button>
          <button type="button">둘째</button>
        </Modal>
      </>,
    )

    await userEvent.tab()
    await userEvent.tab()
    await userEvent.tab()

    expect(screen.getByRole('dialog')).toContainElement(document.activeElement as HTMLElement)
  })

  it('returns focus to the opener when closed', async () => {
    function Host() {
      const [open, setOpen] = useState(false)
      return (
        <>
          <button type="button" onClick={() => setOpen(true)}>
            열기
          </button>
          {open && (
            <Modal title="제목" onClose={() => setOpen(false)}>
              <button type="button">내용</button>
            </Modal>
          )}
        </>
      )
    }
    render(<Host />)
    await userEvent.click(screen.getByRole('button', { name: '열기' }))
    expect(screen.getByRole('dialog')).toBeInTheDocument()

    await userEvent.keyboard('{Escape}')

    expect(screen.queryByRole('dialog')).not.toBeInTheDocument()
    expect(screen.getByRole('button', { name: '열기' })).toHaveFocus()
  })
})

describe('ConfirmDialog', () => {
  it('shows the message and calls the handlers', async () => {
    const onConfirm = vi.fn()
    const onCancel = vi.fn()
    render(
      <ConfirmDialog title="삭제" message="삭제할까요?" confirmLabel="삭제" danger onConfirm={onConfirm} onCancel={onCancel} />,
    )

    expect(screen.getByRole('dialog', { name: '삭제' })).toBeInTheDocument()
    expect(screen.getByText('삭제할까요?')).toBeInTheDocument()
    await userEvent.click(screen.getByRole('button', { name: '삭제' }))
    expect(onConfirm).toHaveBeenCalledTimes(1)
    await userEvent.click(screen.getByRole('button', { name: '취소' }))
    expect(onCancel).toHaveBeenCalledTimes(1)
  })

  it('cancels on Escape and disables confirm while busy', async () => {
    const onCancel = vi.fn()
    render(<ConfirmDialog title="확인" message="진행?" busy onConfirm={() => {}} onCancel={onCancel} />)

    expect(screen.getByRole('button', { name: '확인' })).toBeDisabled()
    await userEvent.keyboard('{Escape}')
    expect(onCancel).toHaveBeenCalled()
  })

  it('can disable confirm until the caller allows it', () => {
    render(<ConfirmDialog title="확인" message="m" confirmDisabled onConfirm={() => {}} onCancel={() => {}} />)

    expect(screen.getByRole('button', { name: '확인' })).toBeDisabled()
  })
})
