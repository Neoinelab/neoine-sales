import { render, screen } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { useState } from 'react'
import { describe, expect, it, vi } from 'vitest'
import { ConfirmDialog } from './ConfirmDialog'
import { Modal } from './Modal'

describe('Modal', () => {
  // 테스트 코드: UI-063
  it('className은 대화상자 클래스 뒤에 덧붙고 없으면 클래스가 그대로다', () => {
    // given: className이 있는 wide 모달, wide만 있는 모달, 속성 없는 모달
    // when: 각각 그린다
    render(
      <>
        <Modal title="넓은 창" wide className="x-size" onClose={() => {}}>
          <p>a</p>
        </Modal>
        <Modal title="보통 창" wide onClose={() => {}}>
          <p>b</p>
        </Modal>
        <Modal title="작은 창" onClose={() => {}}>
          <p>c</p>
        </Modal>
      </>,
    )
    // then: 클래스는 각각 modal wide x-size, modal wide, modal이고 모두 이름은 제목·aria-modal이다
    expect(screen.getByRole('dialog', { name: '넓은 창' })).toHaveAttribute('class', 'modal wide x-size')
    expect(screen.getByRole('dialog', { name: '보통 창' })).toHaveAttribute('class', 'modal wide')
    expect(screen.getByRole('dialog', { name: '작은 창' })).toHaveAttribute('class', 'modal')
    for (const name of ['넓은 창', '보통 창', '작은 창']) {
      expect(screen.getByRole('dialog', { name })).toHaveAttribute('aria-modal', 'true')
    }
  })

  // 테스트 코드: UI-042
  it('제목을 이름으로 가진 aria-modal 대화상자로 열리고 첫 칸에 포커스한다', () => {
    // given: 제목 "매출 확정"에 입력 칸 "금액"이 든 모달
    // when: 연다
    render(
      <Modal title="매출 확정" onClose={() => {}}>
        <input aria-label="금액" />
      </Modal>,
    )
    // then: 이름이 제목이고 aria-modal이며 "금액" 칸에 포커스가 있다
    const dialog = screen.getByRole('dialog', { name: '매출 확정' })
    expect(dialog).toHaveAttribute('aria-modal', 'true')
    expect(dialog).toContainElement(document.activeElement as HTMLElement)
    expect(screen.getByLabelText('금액')).toHaveFocus()
  })

  // 테스트 코드: UI-042
  it('data-autofocus가 붙은 칸이 첫 버튼보다 먼저 포커스를 받는다', () => {
    // given: 첫 버튼 뒤에 data-autofocus 칸이 있는 모달
    // when: 연다
    render(
      <Modal title="제목" onClose={() => {}}>
        <button type="button">첫 버튼</button>
        <input aria-label="먼저 입력" data-autofocus />
      </Modal>,
    )
    // then: data-autofocus 칸에 포커스가 있다
    expect(screen.getByLabelText('먼저 입력')).toHaveFocus()
  })

  // 테스트 코드: UI-042
  it('포커스 가능한 요소가 없으면 대화상자 자체가 포커스를 받는다', () => {
    // given: 글자만 있는 모달
    // when: 연다
    render(
      <Modal title="안내" onClose={() => {}}>
        <p>읽기만 합니다.</p>
      </Modal>,
    )
    // then: 대화상자 자체에 포커스가 있다
    expect(screen.getByRole('dialog', { name: '안내' })).toHaveFocus()
  })

  // 테스트 코드: UI-043
  it('Esc로 닫으면 연 버튼으로 포커스가 돌아오고 배경을 눌러도 닫히지 않는다', async () => {
    // given: "열기" 버튼으로 여는 모달
    const onClose = vi.fn()
    function Host() {
      const [open, setOpen] = useState(false)
      return (
        <>
          <button type="button" onClick={() => setOpen(true)}>
            열기
          </button>
          {open && (
            <Modal
              title="제목"
              onClose={() => {
                onClose()
                setOpen(false)
              }}
            >
              <button type="button">내용</button>
            </Modal>
          )}
        </>
      )
    }
    const { container } = render(<Host />)
    await userEvent.click(screen.getByRole('button', { name: '열기' }))
    expect(screen.getByRole('dialog')).toBeInTheDocument()
    // when: 배경을 누른다
    const backdrop = container.ownerDocument.querySelector('.modal-backdrop')
    if (!backdrop) throw new Error('배경이 없습니다.')
    await userEvent.click(backdrop)
    // then: onClose가 없고 대화상자가 남는다
    expect(onClose).not.toHaveBeenCalled()
    expect(screen.getByRole('dialog')).toBeInTheDocument()
    // when: Esc를 누른다
    await userEvent.keyboard('{Escape}')
    // then: onClose가 한 번 불려 사라지고 포커스는 "열기"로 돌아온다
    expect(onClose).toHaveBeenCalledTimes(1)
    expect(screen.queryByRole('dialog')).not.toBeInTheDocument()
    expect(screen.getByRole('button', { name: '열기' })).toHaveFocus()
  })

  // 테스트 코드: UI-044
  it('Tab을 눌러도 포커스가 모달 안에서만 돈다', async () => {
    // given: 바깥 버튼 "바깥"과 버튼 둘이 있는 모달
    render(
      <>
        <button type="button">바깥</button>
        <Modal title="제목" onClose={() => {}}>
          <button type="button">첫째</button>
          <button type="button">둘째</button>
        </Modal>
      </>,
    )
    // when: Tab을 세 번 누른다
    await userEvent.tab()
    await userEvent.tab()
    await userEvent.tab()
    // then: 포커스는 계속 모달 안이다
    expect(screen.getByRole('dialog')).toContainElement(document.activeElement as HTMLElement)
  })

  // 테스트 코드: UI-044
  it('첫 요소에서 Shift+Tab은 마지막 요소로 돈다', async () => {
    // given: 버튼 둘이 있는 모달(첫째에 포커스)
    render(
      <Modal title="제목" onClose={() => {}}>
        <button type="button">첫째</button>
        <button type="button">둘째</button>
      </Modal>,
    )
    expect(screen.getByRole('button', { name: '첫째' })).toHaveFocus()
    // when: Shift+Tab을 누른다
    await userEvent.tab({ shift: true })
    // then: 마지막 요소 "둘째"로 간다
    expect(screen.getByRole('button', { name: '둘째' })).toHaveFocus()
  })

  // 테스트 코드: UI-044
  it('포커스 가능한 요소가 없는 모달에서는 Tab으로 포커스가 대화상자 밖으로 나가지 않는다', async () => {
    // given: 바깥 버튼과 글자만 있는 모달
    render(
      <>
        <button type="button">바깥</button>
        <Modal title="안내" onClose={() => {}}>
          <p>읽기만 합니다.</p>
        </Modal>
      </>,
    )
    // when: Tab을 누른다
    await userEvent.tab()
    // then: 포커스가 대화상자에 남는다
    expect(screen.getByRole('dialog', { name: '안내' })).toHaveFocus()
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

  // 테스트 코드: UI-045
  it('Esc는 맨 위 모달만 받는다', async () => {
    // given: 바깥 모달 위에 안쪽 모달이 열려 있다
    const onOuter = vi.fn()
    const onInner = vi.fn()
    render(<Stacked onOuter={onOuter} onInner={onInner} />)
    await openInner()
    // when: Esc를 누른다
    await userEvent.keyboard('{Escape}')
    // then: 안쪽만 닫히고 바깥 onClose는 없다
    expect(onInner).toHaveBeenCalledTimes(1)
    expect(onOuter).not.toHaveBeenCalled()
    expect(screen.queryByRole('dialog', { name: '안쪽' })).not.toBeInTheDocument()
    expect(screen.getByRole('dialog', { name: '바깥' })).toBeInTheDocument()
  })

  // 테스트 코드: UI-045
  it('안쪽이 사라진 뒤의 Esc는 바깥 모달이 받는다', async () => {
    // given: 바깥 모달 위에 안쪽 모달이 열려 있다
    const onOuter = vi.fn()
    render(<Stacked onOuter={onOuter} onInner={() => {}} />)
    await openInner()
    // when: Esc를 누른다
    await userEvent.keyboard('{Escape}')
    // then: 바깥 onClose는 아직 없다
    expect(onOuter).not.toHaveBeenCalled()
    // when: Esc를 한 번 더 누른다
    await userEvent.keyboard('{Escape}')
    // then: 바깥 onClose가 한 번 불린다
    expect(onOuter).toHaveBeenCalledTimes(1)
  })

  // 테스트 코드: UI-045
  it('Tab은 맨 위 모달 안에서만 돈다', async () => {
    // given: 안쪽 모달이 열려 있고 "안쪽 첫째"에 포커스가 있다
    render(<Stacked onOuter={() => {}} onInner={() => {}} />)
    await openInner()
    expect(screen.getByRole('button', { name: '안쪽 첫째' })).toHaveFocus()
    // when: Tab을 누른다
    await userEvent.tab()
    // then: 안쪽 둘째(마지막)로 간다
    expect(screen.getByRole('button', { name: '안쪽 둘째' })).toHaveFocus()
    // when: Tab을 한 번 더 누른다
    await userEvent.tab()
    // then: 바깥으로 가지 않고 안쪽 첫째로 돈다
    expect(screen.getByRole('button', { name: '안쪽 첫째' })).toHaveFocus()
  })

  // 테스트 코드: UI-045
  it('맨 위 모달의 첫 요소에서 Shift+Tab은 그 모달의 마지막 요소로 돈다', async () => {
    // given: 안쪽 모달이 열려 있다
    render(<Stacked onOuter={() => {}} onInner={() => {}} />)
    await openInner()
    // when: Shift+Tab을 누른다
    await userEvent.tab({ shift: true })
    // then: 안쪽 둘째로 간다
    expect(screen.getByRole('button', { name: '안쪽 둘째' })).toHaveFocus()
  })

  // 테스트 코드: UI-045
  it('겹친 모달을 없앤 뒤 새 단일 모달도 Esc로 닫힌다', async () => {
    // given: 겹친 모달을 열었다가 모두 없앴다
    const first = render(<Stacked onOuter={() => {}} onInner={() => {}} />)
    await openInner()
    first.unmount()
    const onClose = vi.fn()
    render(
      <Modal title="새 모달" onClose={onClose}>
        <button type="button">내용</button>
      </Modal>,
    )
    // when: Esc를 누른다
    await userEvent.keyboard('{Escape}')
    // then: 새 모달 onClose가 한 번 불린다
    expect(onClose).toHaveBeenCalledTimes(1)
  })
})

describe('ConfirmDialog', () => {
  // 테스트 코드: UI-046
  it('문구를 보이고 확인·취소 버튼이 각각 핸들러를 부른다', async () => {
    // given: 제목 "삭제", 문구 "삭제할까요?", 확인 "삭제"인 danger 대화상자
    const onConfirm = vi.fn()
    const onCancel = vi.fn()
    render(
      <ConfirmDialog title="삭제" message="삭제할까요?" confirmLabel="삭제" danger onConfirm={onConfirm} onCancel={onCancel} />,
    )
    // then: 대화상자 이름과 문구가 보인다
    expect(screen.getByRole('dialog', { name: '삭제' })).toBeInTheDocument()
    expect(screen.getByText('삭제할까요?')).toBeInTheDocument()
    // when: "삭제"를 누른다
    await userEvent.click(screen.getByRole('button', { name: '삭제' }))
    // then: onConfirm이 한 번 불린다
    expect(onConfirm).toHaveBeenCalledTimes(1)
    // when: "취소"를 누른다
    await userEvent.click(screen.getByRole('button', { name: '취소' }))
    // then: onCancel이 한 번 불린다
    expect(onCancel).toHaveBeenCalledTimes(1)
  })

  // 테스트 코드: UI-046
  it('진행 중이면 확인만 꺼지고 Esc는 취소한다', async () => {
    // given: busy인 대화상자
    const onCancel = vi.fn()
    render(<ConfirmDialog title="확인" message="진행?" busy onConfirm={() => {}} onCancel={onCancel} />)
    // then: 확인은 비활성이고 취소는 활성이다
    expect(screen.getByRole('button', { name: '확인' })).toBeDisabled()
    expect(screen.getByRole('button', { name: '취소' })).toBeEnabled()
    // when: Esc를 누른다
    await userEvent.keyboard('{Escape}')
    // then: onCancel이 불린다
    expect(onCancel).toHaveBeenCalled()
  })

  // 테스트 코드: UI-046
  it('진행 중에도 취소 버튼을 누르면 onCancel을 부른다', async () => {
    // given: busy인 대화상자
    const onCancel = vi.fn()
    const onConfirm = vi.fn()
    render(<ConfirmDialog title="확인" message="진행?" busy onConfirm={onConfirm} onCancel={onCancel} />)
    // when: "취소"를 누른다
    await userEvent.click(screen.getByRole('button', { name: '취소' }))
    // then: onCancel이 한 번 불리고 onConfirm은 없다
    expect(onCancel).toHaveBeenCalledTimes(1)
    expect(onConfirm).not.toHaveBeenCalled()
  })

  // 테스트 코드: UI-046
  it('호출자가 허락할 때까지 확인이 꺼져 있다', () => {
    // given: confirmDisabled인 대화상자
    // when: 연다
    render(<ConfirmDialog title="확인" message="m" confirmDisabled onConfirm={() => {}} onCancel={() => {}} />)
    // then: 확인은 비활성, 취소는 활성이다
    expect(screen.getByRole('button', { name: '확인' })).toBeDisabled()
    expect(screen.getByRole('button', { name: '취소' })).toBeEnabled()
  })
})
