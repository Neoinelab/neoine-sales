import { render, screen } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { useState } from 'react'
import { describe, expect, it } from 'vitest'
import type { ChartDraft } from './chartDraft'
import { ComboSeriesEditor } from './ComboSeriesEditor'

/**
 * 콤보 계열 설정 UI(명세 RC-R30). 계약(테스트가 정한 부분)
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

describe('ComboSeriesEditor: 콤보 계열 설정', () => {
  // 테스트 코드: RC-063
  it('값 열마다 한 줄에 종류와 보조 축을 보인다', () => {
    // when: 콤보 계열 편집기를 그린다 (전제: 값 열 3개, 마지막은 표식 꺾은선·보조 축)
    render(<Harness initial={{ ...LINE_AFTER_COLUMN, 4: { type: 'line_markers', secondary: true } }} />)

    // then: 줄마다 종류 이름과 보조 축 체크 상태가 설정과 같다
    expect(screen.getByLabelText('금액 종류')).toHaveDisplayValue('묶은 세로 막대')
    expect(screen.getByLabelText('건수 종류')).toHaveDisplayValue('꺾은선')
    expect(screen.getByLabelText('사용자 종류')).toHaveDisplayValue('표식이 있는 꺾은선')
    expect(screen.getByLabelText('금액 보조 축')).not.toBeChecked()
    expect(screen.getByLabelText('사용자 보조 축')).toBeChecked()
  })

  // 테스트 코드: RC-063
  it('계열 종류는 6가지를 고를 수 있다', () => {
    // when: 편집기를 그린다
    render(<Harness initial={LINE_AFTER_COLUMN} />)

    const options = Array.from((screen.getByLabelText('금액 종류') as HTMLSelectElement).options).map((o) => o.textContent)

    // then: 종류 선택지가 묶은 세로 막대·누적 세로 막대·꺾은선·표식이 있는 꺾은선·영역·누적 영역이다
    expect(options).toEqual(['묶은 세로 막대', '누적 세로 막대', '꺾은선', '표식이 있는 꺾은선', '영역', '누적 영역'])
  })

  // 테스트 코드: RC-064
  it('설정이 프리셋과 같으면 그 프리셋을, 아니면 사용자 지정 조합을 보인다', () => {
    // when: 프리셋과 같은 설정으로 편집기를 그린다
    const { unmount } = render(<Harness initial={LINE_AFTER_COLUMN} />)
    // then: 프리셋 선택이 "묶은 세로 막대 - 꺾은선"이다
    expect(screen.getByLabelText('콤보 프리셋')).toHaveDisplayValue('묶은 세로 막대 - 꺾은선')
    unmount()

    // when: 한 줄을 바꾼 설정으로 편집기를 다시 그린다
    render(<Harness initial={{ ...LINE_AFTER_COLUMN, 3: { type: 'area', secondary: false } }} />)
    // then: 프리셋 선택이 "사용자 지정 조합"이다
    expect(screen.getByLabelText('콤보 프리셋')).toHaveDisplayValue('사용자 지정 조합')
  })

  // 테스트 코드: RC-064
  it('프리셋 세 개와 사용자 지정 조합을 고를 수 있다', () => {
    // when: 편집기를 그린다
    render(<Harness initial={LINE_AFTER_COLUMN} />)

    const options = Array.from((screen.getByLabelText('콤보 프리셋') as HTMLSelectElement).options).map((o) => o.textContent)

    // then: 프리셋 선택지가 프리셋 3개와 사용자 지정 조합이다
    expect(options).toEqual(['묶은 세로 막대 - 꺾은선', '묶은 세로 막대 - 보조 축의 꺾은선', '누적 영역 - 묶은 세로 막대', '사용자 지정 조합'])
  })

  // 테스트 코드: RC-064
  it('프리셋을 고르면 모든 계열을 채운다', async () => {
    // given: 묶은 세로 막대 - 꺾은선 설정의 편집기를 그려 둔다
    const user = userEvent.setup()
    const seen: Value[] = []
    render(<Harness initial={LINE_AFTER_COLUMN} onChange={(v) => seen.push(v)} />)

    // when: "누적 영역 - 묶은 세로 막대" 프리셋을 고른다
    await user.selectOptions(screen.getByLabelText('콤보 프리셋'), '누적 영역 - 묶은 세로 막대')

    // then: 변경 값이 모든 값 열을 채운 설정이고 줄의 종류가 화면에도 반영된다
    expect(seen.at(-1)).toEqual({
      2: { type: 'stacked_area', secondary: false },
      3: { type: 'stacked_area', secondary: false },
      4: { type: 'column', secondary: false },
    })
    expect(screen.getByLabelText('금액 종류')).toHaveDisplayValue('누적 영역')
    expect(screen.getByLabelText('사용자 종류')).toHaveDisplayValue('묶은 세로 막대')
  })

  // 테스트 코드: RC-064
  it('둘째 프리셋은 꺾은선을 보조 축에 둔다', async () => {
    // given: 묶은 세로 막대 - 꺾은선 설정의 편집기를 그려 둔다
    const user = userEvent.setup()
    render(<Harness initial={LINE_AFTER_COLUMN} />)

    // when: "묶은 세로 막대 - 보조 축의 꺾은선" 프리셋을 고른다
    await user.selectOptions(screen.getByLabelText('콤보 프리셋'), '묶은 세로 막대 - 보조 축의 꺾은선')

    // then: 막대 줄은 기본 축, 꺾은선 줄은 보조 축이다
    expect(screen.getByLabelText('금액 보조 축')).not.toBeChecked()
    expect(screen.getByLabelText('건수 보조 축')).toBeChecked()
    expect(screen.getByLabelText('사용자 보조 축')).toBeChecked()
  })

  // 테스트 코드: RC-063
  it('고친 줄만 바뀌고 프리셋은 사용자 지정 조합이 된다', async () => {
    // given: 묶은 세로 막대 - 꺾은선 설정의 편집기를 그려 둔다
    const user = userEvent.setup()
    const seen: Value[] = []
    render(<Harness initial={LINE_AFTER_COLUMN} onChange={(v) => seen.push(v)} />)

    // when: 한 줄의 종류를 영역으로 바꾸고 다른 줄의 보조 축을 켠다
    await user.selectOptions(screen.getByLabelText('건수 종류'), '영역')
    await user.click(screen.getByLabelText('사용자 보조 축'))

    // then: 바꾼 두 줄만 달라진 설정이 전달되고 프리셋 선택이 사용자 지정 조합이다
    expect(seen.at(-1)).toEqual({
      2: { type: 'column', secondary: false },
      3: { type: 'area', secondary: false },
      4: { type: 'line', secondary: true },
    })
    expect(screen.getByLabelText('콤보 프리셋')).toHaveDisplayValue('사용자 지정 조합')
  })

  // 테스트 코드: RC-063
  it('안내 문구를 표 아래에 보인다', () => {
    // when: 안내 문구를 준 편집기를 그린다
    render(<Harness initial={LINE_AFTER_COLUMN} issue="모든 계열을 보조 축에 둘 수 없습니다" />)

    // then: 안내 문구가 보인다
    expect(screen.getByText('모든 계열을 보조 축에 둘 수 없습니다')).toBeVisible()
  })
})
