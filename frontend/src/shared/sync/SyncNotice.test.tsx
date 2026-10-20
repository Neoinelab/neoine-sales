import { render, screen } from '@testing-library/react'
import { describe, expect, it } from 'vitest'
import { SyncNotice } from './SyncNotice'

describe('SyncNotice', () => {
  it('keeps the single string behaviour', () => {
    const { rerender } = render(<SyncNotice notice="Status가 '계약완료'로 함께 변경되었습니다." />)
    expect(screen.getByRole('status')).toHaveTextContent("Status가 '계약완료'로 함께 변경되었습니다.")

    rerender(<SyncNotice notice="Status가 '계약완료'로 함께 변경되었습니다." draft />)
    expect(screen.getByRole('status')).toHaveTextContent("Status가 '계약완료'로 함께 변경됩니다. 저장하면 반영됩니다.")
  })

  it('joins several draft sentences and appends the save hint only once', () => {
    render(
      <SyncNotice
        draft
        notice={["Forecast가 'Commit'으로 함께 변경되었습니다.", null, "Status가 '제품소개'로 함께 변경되었습니다."]}
      />,
    )

    const text = screen.getByRole('status').textContent ?? ''
    expect(text).toBe("Forecast가 'Commit'으로 함께 변경됩니다. Status가 '제품소개'로 함께 변경됩니다. 저장하면 반영됩니다.")
    expect(text.split('저장하면 반영됩니다.')).toHaveLength(2)
  })

  it('renders nothing when every sentence is null or the list is empty', () => {
    const { container, rerender } = render(<SyncNotice notice={[null, null]} draft />)
    expect(container).toBeEmptyDOMElement()

    rerender(<SyncNotice notice={[]} draft />)
    expect(container).toBeEmptyDOMElement()
  })

  it('keeps the sentences as they are outside draft mode', () => {
    render(<SyncNotice notice={['첫 번째 되었습니다.', '두 번째 되었습니다.']} />)

    expect(screen.getByRole('status')).toHaveTextContent('첫 번째 되었습니다. 두 번째 되었습니다.')
  })
})
