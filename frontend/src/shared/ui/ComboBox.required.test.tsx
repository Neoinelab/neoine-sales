import { render, screen } from '@testing-library/react'
import { useState } from 'react'
import { describe, expect, it } from 'vitest'
import { ComboBox } from './ComboBox'

function Host({ label, required }: { label: string; required?: boolean }) {
  const [value, setValue] = useState('')
  return <ComboBox label={label} name="company" value={value} onChange={setValue} options={[{ value: '한빛상사' }]} required={required} />
}

describe('ComboBox 필수 표시', () => {
  // required 콤보박스는 입력 칸 required 속성과 루트 required 클래스를 가진다
  // 테스트 코드: UI-062
  it('puts the required attribute on the input and the required class on the root only for a required combobox', () => {
    // when: 화면을 그린다 (전제: 라벨 "고객 회사명" required 콤보박스와 라벨 "파트너 회사명" 콤보박스)
    render(
      <>
        <Host label="고객 회사명" required />
        <Host label="파트너 회사명" />
      </>,
    )
    const required = screen.getByRole('combobox', { name: '고객 회사명' })
    const plain = screen.getByRole('combobox', { name: '파트너 회사명' })

    // then: 첫 칸은 입력 칸에 required 속성, 루트에 required 클래스가 있고 둘째 칸에는 둘 다 없다. 라벨 글자는 그대로다
    expect(required).toBeRequired()
    expect(required.closest('.field')).toHaveClass('required')
    expect(plain).not.toBeRequired()
    expect(plain.closest('.field')).not.toHaveClass('required')
    expect(screen.getByText('고객 회사명')).toBeVisible()
  })
})
