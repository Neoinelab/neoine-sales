import { render, screen, within } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { describe, expect, it, vi } from 'vitest'
import type { ReportChartKind } from '../../../shared/model/reportTypes'
import { KindPicker } from './KindPicker'

/**
 * 2단 종류 선택(Excel 확장 AC1). 계약(테스트가 정한 부분)
 * - props: `{ kind, groupCount, onChange(kind) }`. `groupCount`는 지금 설계의 그룹핑 컬럼 수다.
 * - radiogroup "차트 분류": 분류 13개의 radio(이름은 분류 이름, 고른 종류의 분류가 checked).
 * - group "하위 종류": 고른 분류의 하위 종류 버튼(이름은 종류 이름, `aria-pressed`). 다른 분류의 종류는 그리지 않는다.
 * - 쓸 수 있는 그룹핑 수는 `minGroups <= groupCount <= maxGroups`. 쓸 수 없는 하위 종류 버튼은 disabled이고 이유가 `title`이다:
 *   그룹핑이 모자라면 "그룹핑한 결과로 만들 수 있습니다", 넘치면 "그룹핑 컬럼이 N개 이하일 때 쓸 수 있습니다"(N = 최대 수).
 *   하위 종류가 모두 쓸 수 없는 분류의 radio도 disabled이고 같은 이유가 `title`이다.
 * - 분류를 고르면 그 분류의 첫 번째로 쓸 수 있는 하위 종류로 `onChange`가 불린다.
 */

function setup(kind: ReportChartKind, groupCount = 1) {
  const onChange = vi.fn()
  const user = userEvent.setup()
  render(<KindPicker kind={kind} groupCount={groupCount} onChange={onChange} />)
  return { onChange, user }
}

const FAMILIES = ['세로 막대형', '가로 막대형', '꺾은선형', '원형', '영역형', '분산형(X, Y) 또는 거품형', '방사형', '트리맵', '선버스트', '히스토그램', '폭포', '깔때기', '콤보']
const radio = (name: string) => screen.getByRole('radio', { name })
const subKinds = () => within(screen.getByRole('group', { name: '하위 종류' })).getAllByRole('button')

describe('KindPicker: families and sub kinds', () => {
  it('lists the 13 families in the order of the Excel dialog and checks the family of the kind', () => {
    setup('stacked_line')

    expect(within(screen.getByRole('radiogroup', { name: '차트 분류' })).getAllByRole('radio')).toHaveLength(13)
    FAMILIES.forEach((name, i) => expect(screen.getAllByRole('radio')[i]).toHaveAccessibleName(name))
    expect(radio('꺾은선형')).toBeChecked()
    expect(radio('세로 막대형')).not.toBeChecked()
  })

  it('shows only the six sub kinds of the line family and marks the chosen one pressed', () => {
    setup('stacked_line_markers')

    expect(subKinds().map((b) => b.textContent)).toEqual([
      '꺾은선',
      '표식이 있는 꺾은선',
      '누적 꺾은선',
      '표식이 있는 누적 꺾은선',
      '100% 누적 꺾은선',
      '표식이 있는 100% 누적 꺾은선',
    ])
    expect(screen.getByRole('button', { name: '표식이 있는 누적 꺾은선' })).toHaveAttribute('aria-pressed', 'true')
    expect(screen.getByRole('button', { name: '꺾은선' })).toHaveAttribute('aria-pressed', 'false')
    expect(screen.queryByRole('button', { name: '묶은 세로 막대' })).not.toBeInTheDocument()
  })

  it('shows the single sub kind of a one kind family', () => {
    setup('treemap')

    expect(subKinds().map((b) => b.textContent)).toEqual(['트리맵'])
  })

  it('calls back with the sub kind that is pressed', async () => {
    const { onChange, user } = setup('bar')

    await user.click(screen.getByRole('button', { name: '100% 누적 세로 막대' }))

    expect(onChange).toHaveBeenCalledWith('stacked_100_bar')
  })

  it('calls back with the first sub kind of the family that is chosen', async () => {
    const { onChange, user } = setup('bar')

    await user.click(radio('꺾은선형'))
    await user.click(radio('분산형(X, Y) 또는 거품형'))

    expect(onChange.mock.calls.map((c) => c[0])).toEqual(['line', 'scatter'])
  })
})

describe('KindPicker: what the grouping allows', () => {
  it('disables the families that need at most one group column when there are two, with the reason', () => {
    setup('bar', 2)

    for (const name of ['원형', '분산형(X, Y) 또는 거품형', '폭포', '깔때기', '콤보']) {
      expect(radio(name)).toBeDisabled()
      expect(radio(name)).toHaveAttribute('title', '그룹핑 컬럼이 1개 이하일 때 쓸 수 있습니다')
    }
    for (const name of ['세로 막대형', '가로 막대형', '꺾은선형', '영역형', '방사형', '트리맵', '선버스트', '히스토그램']) expect(radio(name)).toBeEnabled()
  })

  it('disables only the sub kinds that do not fit inside a family that is partly usable', () => {
    setup('histogram', 2)

    expect(screen.getByRole('button', { name: '히스토그램' })).toBeEnabled()
    expect(screen.getByRole('button', { name: '파레토' })).toBeDisabled()
    expect(screen.getByRole('button', { name: '파레토' })).toHaveAttribute('title', '그룹핑 컬럼이 1개 이하일 때 쓸 수 있습니다')
  })

  it('allows only the histogram family without any grouping and says why for the rest', () => {
    setup('histogram', 0)

    expect(radio('히스토그램')).toBeEnabled()
    for (const name of FAMILIES.filter((f) => f !== '히스토그램')) {
      expect(radio(name)).toBeDisabled()
      expect(radio(name)).toHaveAttribute('title', '그룹핑한 결과로 만들 수 있습니다')
    }
    expect(screen.getByRole('button', { name: '히스토그램' })).toBeEnabled()
    expect(screen.getByRole('button', { name: '파레토' })).toBeDisabled()
    expect(screen.getByRole('button', { name: '파레토' })).toHaveAttribute('title', '그룹핑한 결과로 만들 수 있습니다')
  })

  it('does not call back when a disabled family is clicked', async () => {
    const { onChange, user } = setup('bar', 2)

    await user.click(radio('원형'))

    expect(onChange).not.toHaveBeenCalled()
  })

  it('enables everything that needs one group column when there is exactly one', () => {
    setup('bar', 1)

    for (const name of FAMILIES) expect(radio(name)).toBeEnabled()
  })
})

describe('KindPicker: keyboard (AC1)', () => {
  it('moves between the families with the arrow keys and calls back with the first sub kind', async () => {
    const { onChange, user } = setup('bar')
    radio('세로 막대형').focus()

    await user.keyboard('{ArrowDown}')

    expect(onChange).toHaveBeenLastCalledWith('horizontal_bar')
  })

  it('chooses a sub kind with Enter and with Space', async () => {
    const { onChange, user } = setup('bar')
    const button = screen.getByRole('button', { name: '누적 세로 막대' })

    button.focus()
    await user.keyboard('{Enter}')
    await user.keyboard(' ')

    expect(onChange.mock.calls.map((c) => c[0])).toEqual(['stacked_bar', 'stacked_bar'])
  })

  it('reaches the sub kind buttons with Tab', async () => {
    const { user } = setup('bar')
    radio('세로 막대형').focus()

    await user.tab()

    expect(subKinds()).toContain(document.activeElement)
  })
})
