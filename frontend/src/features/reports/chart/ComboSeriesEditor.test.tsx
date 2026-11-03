import { render, screen } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { useState } from 'react'
import { describe, expect, it } from 'vitest'
import type { ChartDraft } from './chartDraft'
import { ComboSeriesEditor } from './ComboSeriesEditor'

/**
 * 콤보 계열 설정 UI(Excel 확장 AC14). 계약(테스트가 정한 부분)
 * - props: `{ columns: { uid, header }[], value: ChartDraft['comboTypes'], onChange(next), issue?: string }`. `columns`는 고른 값 열이 차트 순서대로다.
 * - select "콤보 프리셋": 프리셋 3개(묶은 세로 막대 - 꺾은선 / 묶은 세로 막대 - 보조 축의 꺾은선 / 누적 영역 - 묶은 세로 막대)와 "사용자 지정 조합".
 *   현재 설정이 프리셋과 같으면 그 프리셋을, 아니면 사용자 지정 조합을 보여 준다.
 * - 값 열마다 select "<머리글> 종류"(묶은 세로 막대·누적 세로 막대·꺾은선·표식이 있는 꺾은선·영역·누적 영역)와 checkbox "<머리글> 보조 축".
 * - 프리셋을 고르면 `onChange`가 모든 값 열의 설정을 채운 객체로 불린다. 한 칸을 바꾸면 나머지는 그대로다.
 * - `issue`는 표 아래에 글자로 보인다.
 */

type Value = ChartDraft['comboTypes']
const COLUMNS = [
  { uid: 2, header: '금액' },
  { uid: 3, header: '건수' },
  { uid: 4, header: '사용자' },
]
const LINE_AFTER_COLUMN: Value = {
  2: { type: 'column', secondary: false },
  3: { type: 'line', secondary: false },
  4: { type: 'line', secondary: false },
}

function Harness({ initial, issue, onChange }: { initial: Value; issue?: string; onChange?: (v: Value) => void }) {
  const [value, setValue] = useState<Value>(initial)
  return (
    <ComboSeriesEditor
      columns={COLUMNS}
      value={value}
      issue={issue}
      onChange={(next) => {
        setValue(next)
        onChange?.(next)
      }}
    />
  )
}

describe('ComboSeriesEditor', () => {
  it('shows one row per value column with its type and secondary axis', () => {
    render(<Harness initial={{ ...LINE_AFTER_COLUMN, 4: { type: 'line_markers', secondary: true } }} />)

    expect(screen.getByLabelText('금액 종류')).toHaveDisplayValue('묶은 세로 막대')
    expect(screen.getByLabelText('건수 종류')).toHaveDisplayValue('꺾은선')
    expect(screen.getByLabelText('사용자 종류')).toHaveDisplayValue('표식이 있는 꺾은선')
    expect(screen.getByLabelText('금액 보조 축')).not.toBeChecked()
    expect(screen.getByLabelText('사용자 보조 축')).toBeChecked()
  })

  it('offers the six series types', () => {
    render(<Harness initial={LINE_AFTER_COLUMN} />)

    const options = Array.from((screen.getByLabelText('금액 종류') as HTMLSelectElement).options).map((o) => o.textContent)

    expect(options).toEqual(['묶은 세로 막대', '누적 세로 막대', '꺾은선', '표식이 있는 꺾은선', '영역', '누적 영역'])
  })

  it('shows the preset that the current settings equal, and the custom mix otherwise', () => {
    const { unmount } = render(<Harness initial={LINE_AFTER_COLUMN} />)
    expect(screen.getByLabelText('콤보 프리셋')).toHaveDisplayValue('묶은 세로 막대 - 꺾은선')
    unmount()

    render(<Harness initial={{ ...LINE_AFTER_COLUMN, 3: { type: 'area', secondary: false } }} />)
    expect(screen.getByLabelText('콤보 프리셋')).toHaveDisplayValue('사용자 지정 조합')
  })

  it('offers the three presets and the custom mix', () => {
    render(<Harness initial={LINE_AFTER_COLUMN} />)

    const options = Array.from((screen.getByLabelText('콤보 프리셋') as HTMLSelectElement).options).map((o) => o.textContent)

    expect(options).toEqual(['묶은 세로 막대 - 꺾은선', '묶은 세로 막대 - 보조 축의 꺾은선', '누적 영역 - 묶은 세로 막대', '사용자 지정 조합'])
  })

  it('fills every series when a preset is chosen', async () => {
    const user = userEvent.setup()
    const seen: Value[] = []
    render(<Harness initial={LINE_AFTER_COLUMN} onChange={(v) => seen.push(v)} />)

    await user.selectOptions(screen.getByLabelText('콤보 프리셋'), '누적 영역 - 묶은 세로 막대')

    expect(seen.at(-1)).toEqual({
      2: { type: 'stacked_area', secondary: false },
      3: { type: 'stacked_area', secondary: false },
      4: { type: 'column', secondary: false },
    })
    expect(screen.getByLabelText('금액 종류')).toHaveDisplayValue('누적 영역')
    expect(screen.getByLabelText('사용자 종류')).toHaveDisplayValue('묶은 세로 막대')
  })

  it('puts the lines on the secondary axis with the second preset', async () => {
    const user = userEvent.setup()
    render(<Harness initial={LINE_AFTER_COLUMN} />)

    await user.selectOptions(screen.getByLabelText('콤보 프리셋'), '묶은 세로 막대 - 보조 축의 꺾은선')

    expect(screen.getByLabelText('금액 보조 축')).not.toBeChecked()
    expect(screen.getByLabelText('건수 보조 축')).toBeChecked()
    expect(screen.getByLabelText('사용자 보조 축')).toBeChecked()
  })

  it('changes only the row that is edited and switches the preset to the custom mix', async () => {
    const user = userEvent.setup()
    const seen: Value[] = []
    render(<Harness initial={LINE_AFTER_COLUMN} onChange={(v) => seen.push(v)} />)

    await user.selectOptions(screen.getByLabelText('건수 종류'), '영역')
    await user.click(screen.getByLabelText('사용자 보조 축'))

    expect(seen.at(-1)).toEqual({
      2: { type: 'column', secondary: false },
      3: { type: 'area', secondary: false },
      4: { type: 'line', secondary: true },
    })
    expect(screen.getByLabelText('콤보 프리셋')).toHaveDisplayValue('사용자 지정 조합')
  })

  it('shows the issue under the table', () => {
    render(<Harness initial={LINE_AFTER_COLUMN} issue="모든 계열을 보조 축에 둘 수 없습니다" />)

    expect(screen.getByText('모든 계열을 보조 축에 둘 수 없습니다')).toBeVisible()
  })
})
