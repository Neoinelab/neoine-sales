import { render, screen } from '@testing-library/react'
import { describe, expect, it } from 'vitest'
import { SyncNotice } from './SyncNotice'

describe('SyncNotice', () => {
  it('문장 하나를 그대로 보이고 초안일 때는 저장 안내를 붙인다', () => {
    // when: 문장 하나로 안내를 그린다
    const { rerender } = render(<SyncNotice notice="Status가 '계약완료'로 함께 변경되었습니다." />)
    // then: 문장이 그대로 보인다
    expect(screen.getByRole('status')).toHaveTextContent("Status가 '계약완료'로 함께 변경되었습니다.")

    // when: 초안 모드로 다시 그린다
    rerender(<SyncNotice notice="Status가 '계약완료'로 함께 변경되었습니다." draft />)
    // then: 문장이 '변경됩니다'로 바뀌고 저장 안내가 붙는다
    expect(screen.getByRole('status')).toHaveTextContent("Status가 '계약완료'로 함께 변경됩니다. 저장하면 반영됩니다.")
  })

  it('초안 문장 여러 개를 이어 붙이고 저장 안내는 한 번만 붙인다', () => {
    // when: 문장 둘(사이에 null)을 초안 모드로 그린다
    render(
      <SyncNotice
        draft
        notice={["Forecast가 'Commit'으로 함께 변경되었습니다.", null, "Status가 '제품소개'로 함께 변경되었습니다."]}
      />,
    )

    // then: 문장이 이어지고 저장 안내는 한 번뿐이다
    const text = screen.getByRole('status').textContent ?? ''
    expect(text).toBe("Forecast가 'Commit'으로 함께 변경됩니다. Status가 '제품소개'로 함께 변경됩니다. 저장하면 반영됩니다.")
    expect(text.split('저장하면 반영됩니다.')).toHaveLength(2)
  })

  it('문장이 모두 null이거나 목록이 비면 아무것도 그리지 않는다', () => {
    // when: 문장이 모두 null인 안내를 그린다
    const { container, rerender } = render(<SyncNotice notice={[null, null]} draft />)
    // then: 비어 있다
    expect(container).toBeEmptyDOMElement()

    // when: 빈 목록으로 다시 그린다
    rerender(<SyncNotice notice={[]} draft />)
    // then: 비어 있다
    expect(container).toBeEmptyDOMElement()
  })

  it('초안이 아니면 문장을 그대로 둔다', () => {
    // when: 초안이 아닌 모드로 문장 둘을 그린다
    render(<SyncNotice notice={['첫 번째 되었습니다.', '두 번째 되었습니다.']} />)

    // then: 문장이 바뀌지 않고 이어서 보인다
    expect(screen.getByRole('status')).toHaveTextContent('첫 번째 되었습니다. 두 번째 되었습니다.')
  })
})
