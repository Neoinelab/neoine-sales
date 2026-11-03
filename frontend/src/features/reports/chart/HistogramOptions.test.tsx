import { render, screen } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { useState } from 'react'
import { describe, expect, it } from 'vitest'
import type { ChartDraft } from './chartDraft'
import { HistogramOptions } from './HistogramOptions'

/**
 * 히스토그램 구간 설정 UI(Excel 확장 AC10). 계약(테스트가 정한 부분)
 * - props: `{ value: ChartDraft['histogram'], onChange(next), issues?: Partial<Record<'bin_mode' | 'bin_count' | 'bin_width' | 'overflow' | 'underflow', string>> }`.
 * - 칸(getByLabelText): select "구간 방식"(자동·구간 수·구간 너비), "구간 수", "구간 너비", "오버플로 구간", "언더플로 구간".
 * - 쓰지 않는 칸은 disabled이고 이유가 `title`이다: 자동 → 구간 수·구간 너비, 구간 수 방식 → 구간 너비, 구간 너비 방식 → 구간 수.
 *   오버플로·언더플로 칸은 방식과 무관하게 쓸 수 있다.
 * - `issues[part]`는 그 칸 옆에 글자로 보이고 칸은 `aria-invalid`다.
 */

type Value = ChartDraft['histogram']
const AUTO: Value = { mode: 'auto', count: '', width: '', overflow: '', underflow: '' }

function Harness({ initial = AUTO, issues, onChange }: { initial?: Value; issues?: Record<string, string>; onChange?: (v: Value) => void }) {
  const [value, setValue] = useState<Value>(initial)
  return (
    <HistogramOptions
      value={value}
      issues={issues}
      onChange={(next) => {
        setValue(next)
        onChange?.(next)
      }}
    />
  )
}

const field = (label: string) => screen.getByLabelText(label)

describe('HistogramOptions', () => {
  it('shows auto mode with the count and width fields disabled and a reason on each', () => {
    render(<Harness />)

    expect(field('구간 방식')).toHaveDisplayValue('자동')
    expect(field('구간 수')).toBeDisabled()
    expect(field('구간 너비')).toBeDisabled()
    expect(field('구간 수')).toHaveAttribute('title', expect.stringMatching(/\S/))
    expect(field('구간 너비')).toHaveAttribute('title', expect.stringMatching(/\S/))
    expect(field('오버플로 구간')).toBeEnabled()
    expect(field('언더플로 구간')).toBeEnabled()
  })

  it('offers the three bin modes', () => {
    render(<Harness />)

    const options = Array.from((field('구간 방식') as HTMLSelectElement).options).map((o) => o.textContent)

    expect(options).toEqual(['자동', '구간 수', '구간 너비'])
  })

  it('enables only the count field in count mode and only the width field in width mode', async () => {
    const user = userEvent.setup()
    render(<Harness />)

    await user.selectOptions(field('구간 방식'), '구간 수')
    expect(field('구간 수')).toBeEnabled()
    expect(field('구간 너비')).toBeDisabled()

    await user.selectOptions(field('구간 방식'), '구간 너비')
    expect(field('구간 수')).toBeDisabled()
    expect(field('구간 너비')).toBeEnabled()
  })

  it('reports the chosen mode and the typed numbers as text', async () => {
    const user = userEvent.setup()
    const seen: Value[] = []
    render(<Harness onChange={(v) => seen.push(v)} />)

    await user.selectOptions(field('구간 방식'), '구간 수')
    await user.type(field('구간 수'), '8')
    await user.type(field('오버플로 구간'), '100.5')
    await user.type(field('언더플로 구간'), '-5')

    expect(seen.at(-1)).toEqual({ mode: 'count', count: '8', width: '', overflow: '100.5', underflow: '-5' })
  })

  it('keeps the typed texts of the unused fields when the mode changes', async () => {
    const user = userEvent.setup()
    render(<Harness initial={{ ...AUTO, mode: 'count', count: '8' }} />)

    await user.selectOptions(field('구간 방식'), '구간 너비')
    await user.selectOptions(field('구간 방식'), '구간 수')

    expect(field('구간 수')).toHaveValue('8')
  })

  it('shows the issue next to its field and marks the field invalid', () => {
    render(<Harness initial={{ ...AUTO, mode: 'count', count: '0' }} issues={{ bin_count: '구간 수는 1~100의 정수입니다' }} />)

    expect(screen.getByText('구간 수는 1~100의 정수입니다')).toBeVisible()
    expect(field('구간 수')).toHaveAttribute('aria-invalid', 'true')
    expect(field('구간 너비')).not.toHaveAttribute('aria-invalid')
  })

  it('shows the overflow order issue at the overflow field', () => {
    render(<Harness initial={{ ...AUTO, overflow: '10', underflow: '10' }} issues={{ overflow: '오버플로 구간은 언더플로 구간보다 커야 합니다' }} />)

    expect(screen.getByText('오버플로 구간은 언더플로 구간보다 커야 합니다')).toBeVisible()
    expect(field('오버플로 구간')).toHaveAttribute('aria-invalid', 'true')
  })
})
