import { render, screen } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { useState } from 'react'
import { describe, expect, it } from 'vitest'
import type { ChartDraft } from './chartDraft'
import { HistogramOptions } from './HistogramOptions'

/**
 * 히스토그램 구간 설정 UI(명세 RC-R30). 계약(테스트가 정한 부분)
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

describe('HistogramOptions: 히스토그램 구간 설정', () => {
  // 테스트 코드: RC-061
  it('자동 방식에서는 구간 수·구간 너비 칸이 이유와 함께 잠긴다', () => {
    // when: 자동 방식의 구간 설정을 그린다
    render(<Harness />)

    // then: 구간 수·너비 칸은 비활성이고 이유(title)가 있으며 오버플로·언더플로 칸은 활성이다
    expect(field('구간 방식')).toHaveDisplayValue('자동')
    expect(field('구간 수')).toBeDisabled()
    expect(field('구간 너비')).toBeDisabled()
    expect(field('구간 수')).toHaveAttribute('title', expect.stringMatching(/\S/))
    expect(field('구간 너비')).toHaveAttribute('title', expect.stringMatching(/\S/))
    expect(field('오버플로 구간')).toBeEnabled()
    expect(field('언더플로 구간')).toBeEnabled()
  })

  // 테스트 코드: RC-061
  it('구간 방식은 자동·구간 수·구간 너비 세 가지다', () => {
    // when: 구간 설정을 그린다
    render(<Harness />)

    const options = Array.from((field('구간 방식') as HTMLSelectElement).options).map((o) => o.textContent)

    // then: 구간 방식 선택지가 세 가지다
    expect(options).toEqual(['자동', '구간 수', '구간 너비'])
  })

  // 테스트 코드: RC-061
  it('구간 수 방식에서는 구간 수 칸만, 구간 너비 방식에서는 너비 칸만 활성이다', async () => {
    // given: 자동 방식의 구간 설정을 그려 둔다
    const user = userEvent.setup()
    render(<Harness />)

    // when: 구간 수 방식을 고른다
    await user.selectOptions(field('구간 방식'), '구간 수')
    // then: 구간 수 칸만 활성이다
    expect(field('구간 수')).toBeEnabled()
    expect(field('구간 너비')).toBeDisabled()

    // when: 구간 너비 방식을 고른다
    await user.selectOptions(field('구간 방식'), '구간 너비')
    // then: 구간 너비 칸만 활성이다
    expect(field('구간 수')).toBeDisabled()
    expect(field('구간 너비')).toBeEnabled()
  })

  // 테스트 코드: RC-061
  it('고른 방식과 입력한 숫자를 글자로 알린다', async () => {
    // given: 자동 방식의 구간 설정을 그려 둔다
    const user = userEvent.setup()
    const seen: Value[] = []
    render(<Harness onChange={(v) => seen.push(v)} />)

    // when: 구간 수 방식을 고르고 구간 수·오버플로·언더플로를 입력한다
    await user.selectOptions(field('구간 방식'), '구간 수')
    await user.type(field('구간 수'), '8')
    await user.type(field('오버플로 구간'), '100.5')
    await user.type(field('언더플로 구간'), '-5')

    // then: 마지막 변경 값이 방식과 입력 글자를 그대로 담는다
    expect(seen.at(-1)).toEqual({ mode: 'count', count: '8', width: '', overflow: '100.5', underflow: '-5' })
  })

  // 테스트 코드: RC-061
  it('방식을 바꿔도 쓰지 않는 칸의 입력 글자는 지우지 않는다', async () => {
    // given: 구간 수 방식에 8을 입력한 구간 설정을 그려 둔다
    const user = userEvent.setup()
    render(<Harness initial={{ ...AUTO, mode: 'count', count: '8' }} />)

    // when: 구간 너비 방식으로 바꿨다가 구간 수 방식으로 되돌린다
    await user.selectOptions(field('구간 방식'), '구간 너비')
    await user.selectOptions(field('구간 방식'), '구간 수')

    // then: 구간 수 칸에 8이 그대로 있다
    expect(field('구간 수')).toHaveValue('8')
  })

  // 테스트 코드: RC-061
  it('안내는 해당 칸 옆에 보이고 칸은 잘못됨 상태다', () => {
    // when: 구간 수 안내를 준 구간 설정을 그린다
    render(<Harness initial={{ ...AUTO, mode: 'count', count: '0' }} issues={{ bin_count: '구간 수는 1~100의 정수입니다' }} />)

    // then: 안내 문구가 보이고 구간 수 칸만 aria-invalid다
    expect(screen.getByText('구간 수는 1~100의 정수입니다')).toBeVisible()
    expect(field('구간 수')).toHaveAttribute('aria-invalid', 'true')
    expect(field('구간 너비')).not.toHaveAttribute('aria-invalid')
  })

  // 테스트 코드: RC-061
  it('오버플로 순서 안내는 오버플로 칸에 붙는다', () => {
    // when: 오버플로 안내를 준 구간 설정을 그린다
    render(<Harness initial={{ ...AUTO, overflow: '10', underflow: '10' }} issues={{ overflow: '오버플로 구간은 언더플로 구간보다 커야 합니다' }} />)

    // then: 안내 문구가 보이고 오버플로 칸이 aria-invalid다
    expect(screen.getByText('오버플로 구간은 언더플로 구간보다 커야 합니다')).toBeVisible()
    expect(field('오버플로 구간')).toHaveAttribute('aria-invalid', 'true')
  })
})
