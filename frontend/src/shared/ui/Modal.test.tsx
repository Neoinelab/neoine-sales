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

describe('겹친 Modal', () => {
  /** 바깥 Modal 안에서 버튼으로 안쪽 Modal을 연다(실제 화면의 동기화 팝업처럼 나중에 마운트된다). */
  function Stacked({ onOuter, onInner }: { onOuter: () => void; onInner: () => void }) {
    const [innerOpen, setInnerOpen] = useState(false)
    return (
      <Modal title="바깥" onClose={onOuter}>
        {innerOpen && (
          <Modal
            title="안쪽"
            onClose={() => {
              onInner()
              setInnerOpen(false)
            }}
          >
            <button type="button">안쪽 첫째</button>
            <button type="button">안쪽 둘째</button>
          </Modal>
        )}
        <button type="button" onClick={() => setInnerOpen(true)}>
          안쪽 열기
        </button>
        <button type="button">바깥 끝</button>
      </Modal>
    )
  }

  async function openInner() {
    await userEvent.click(screen.getByRole('button', { name: '안쪽 열기' }))
    expect(screen.getByRole('dialog', { name: '안쪽' })).toBeInTheDocument()
  }

  it('only the top modal handles escape', async () => {
    const onOuter = vi.fn()
    const onInner = vi.fn()
    render(<Stacked onOuter={onOuter} onInner={onInner} />)
    await openInner()

    await userEvent.keyboard('{Escape}')

    expect(onInner).toHaveBeenCalledTimes(1)
    expect(onOuter).not.toHaveBeenCalled()
    expect(screen.queryByRole('dialog', { name: '안쪽' })).not.toBeInTheDocument()
    expect(screen.getByRole('dialog', { name: '바깥' })).toBeInTheDocument()
  })

  it('hands escape to the outer modal once the inner one is gone', async () => {
    const onOuter = vi.fn()
    render(<Stacked onOuter={onOuter} onInner={() => {}} />)
    await openInner()

    await userEvent.keyboard('{Escape}')
    expect(onOuter).not.toHaveBeenCalled()
    await userEvent.keyboard('{Escape}')

    expect(onOuter).toHaveBeenCalledTimes(1)
  })

  it('tab cycles inside the top modal only', async () => {
    render(<Stacked onOuter={() => {}} onInner={() => {}} />)
    await openInner()
    expect(screen.getByRole('button', { name: '안쪽 첫째' })).toHaveFocus()
    await userEvent.tab() // 안쪽 둘째(마지막)
    expect(screen.getByRole('button', { name: '안쪽 둘째' })).toHaveFocus()

    await userEvent.tab()

    expect(screen.getByRole('button', { name: '안쪽 첫째' })).toHaveFocus()
  })

  it('shift+tab from the first element of the top modal wraps to its last element', async () => {
    render(<Stacked onOuter={() => {}} onInner={() => {}} />)
    await openInner()

    await userEvent.tab({ shift: true })

    expect(screen.getByRole('button', { name: '안쪽 둘째' })).toHaveFocus()
  })

  it('does not leave the stack dirty after unmount: a later single modal still closes on escape', async () => {
    const first = render(<Stacked onOuter={() => {}} onInner={() => {}} />)
    await openInner()
    first.unmount()
    const onClose = vi.fn()
    render(
      <Modal title="새 모달" onClose={onClose}>
        <button type="button">내용</button>
      </Modal>,
    )

    await userEvent.keyboard('{Escape}')

    expect(onClose).toHaveBeenCalledTimes(1)
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
