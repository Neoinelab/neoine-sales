import { render } from '@testing-library/react'
import { describe, expect, it } from 'vitest'
import { AmountText } from './AmountText'

describe('AmountText', () => {
  // 테스트 코드: UI-029
  it('금액을 반올림 없는 콤마 숫자로 보인다', () => {
    // when: 1234567을 표시한다
    const { container } = render(<AmountText amount={1_234_567} />)
    // then: amount 클래스에 1,234,567이 보인다
    const span = container.querySelector('.amount')
    expect(span).toHaveTextContent('1,234,567')
  })
})
