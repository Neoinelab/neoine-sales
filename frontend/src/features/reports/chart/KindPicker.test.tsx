import { render, screen, within } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { describe, expect, it, vi } from 'vitest'
import type { ReportChartKind } from '../../../shared/model/reportTypes'
import { KindPicker } from './KindPicker'

/**
 * 2단 종류 선택(명세 RC-R27). 계약(테스트가 정한 부분)
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

describe('KindPicker: 분류와 하위 종류', () => {
  // 테스트 코드: RC-054
  it('분류 13개를 Excel 대화상자 순서로 보이고 고른 종류의 분류를 선택 상태로 둔다', () => {
    // when: 꺾은선형의 누적 꺾은선을 고른 상태로 그린다
    setup('stacked_line')

    // then: 13개 분류가 순서대로 있고 꺾은선형만 선택되어 있다
    expect(within(screen.getByRole('radiogroup', { name: '차트 분류' })).getAllByRole('radio')).toHaveLength(13)
    FAMILIES.forEach((name, i) => expect(screen.getAllByRole('radio')[i]).toHaveAccessibleName(name))
    expect(radio('꺾은선형')).toBeChecked()
    expect(radio('세로 막대형')).not.toBeChecked()
  })

  // 테스트 코드: RC-054
  it('꺾은선형은 하위 종류 6개만 보이고 고른 종류가 눌린 상태다', () => {
    // when: 표식이 있는 누적 꺾은선을 고른 상태로 그린다
    setup('stacked_line_markers')

    // then: 하위 종류 6개가 순서대로 있고 고른 종류만 눌린 상태이며 다른 분류 종류는 없다
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

  // 테스트 코드: RC-054
  it('종류가 하나뿐인 분류는 하위 종류 하나만 보인다', () => {
    // when: 트리맵을 고른 상태로 그린다
    setup('treemap')

    // then: 하위 종류가 트리맵 하나뿐이다
    expect(subKinds().map((b) => b.textContent)).toEqual(['트리맵'])
  })

  // 테스트 코드: RC-054
  it('하위 종류 버튼을 누르면 그 종류로 바꾼다', async () => {
    // given: 묶은 세로 막대를 고른 상태로 그려 둔다
    const { onChange, user } = setup('bar')

    // when: 100% 누적 세로 막대 버튼을 누른다
    await user.click(screen.getByRole('button', { name: '100% 누적 세로 막대' }))

    // then: 그 종류로 변경 알림이 한 번 온다
    expect(onChange).toHaveBeenCalledWith('stacked_100_bar')
  })

  // 테스트 코드: RC-054
  it('분류를 고르면 그 분류의 첫 하위 종류로 바꾼다', async () => {
    // given: 묶은 세로 막대를 고른 상태
    const { onChange, user } = setup('bar')

    // when: 꺾은선형과 분산형 분류를 차례로 고른다
    await user.click(radio('꺾은선형'))
    await user.click(radio('분산형(X, Y) 또는 거품형'))

    // then: 꺾은선과 분산형(표식만)으로 변경 알림이 온다
    expect(onChange.mock.calls.map((c) => c[0])).toEqual(['line', 'scatter'])
  })
})

describe('KindPicker: 그룹핑에 따른 잠금', () => {
  // 테스트 코드: RC-055
  it('그룹 컬럼이 2개이면 그룹 하나만 쓰는 분류는 이유와 함께 잠긴다', () => {
    // when: 그룹 2개 상태로 그린다
    setup('bar', 2)

    // then: 원형·분산형·폭포·깔때기·콤보 분류는 비활성이고 이유가 title에 있으며 나머지 분류는 활성이다
    for (const name of ['원형', '분산형(X, Y) 또는 거품형', '폭포', '깔때기', '콤보']) {
      expect(radio(name)).toBeDisabled()
      expect(radio(name)).toHaveAttribute('title', '그룹핑 컬럼이 1개 이하일 때 쓸 수 있습니다')
    }
    for (const name of ['세로 막대형', '가로 막대형', '꺾은선형', '영역형', '방사형', '트리맵', '선버스트', '히스토그램']) expect(radio(name)).toBeEnabled()
  })

  // 테스트 코드: RC-055
  it('일부만 쓸 수 있는 분류에서는 맞지 않는 하위 종류만 잠긴다', () => {
    // when: 그룹 2개 상태로 히스토그램 분류를 그린다
    setup('histogram', 2)

    // then: 히스토그램은 활성, 파레토는 비활성이고 이유가 title에 있다
    expect(screen.getByRole('button', { name: '히스토그램' })).toBeEnabled()
    expect(screen.getByRole('button', { name: '파레토' })).toBeDisabled()
    expect(screen.getByRole('button', { name: '파레토' })).toHaveAttribute('title', '그룹핑 컬럼이 1개 이하일 때 쓸 수 있습니다')
  })

  // 테스트 코드: RC-055
  it('그룹핑이 없으면 히스토그램 분류만 쓸 수 있고 나머지는 이유를 보인다', () => {
    // when: 그룹 0개 상태로 그린다
    setup('histogram', 0)

    // then: 히스토그램 분류만 활성이고 나머지는 "그룹핑한 결과로 만들 수 있습니다" 이유로 잠기며 파레토도 잠긴다
    expect(radio('히스토그램')).toBeEnabled()
    for (const name of FAMILIES.filter((f) => f !== '히스토그램')) {
      expect(radio(name)).toBeDisabled()
      expect(radio(name)).toHaveAttribute('title', '그룹핑한 결과로 만들 수 있습니다')
    }
    expect(screen.getByRole('button', { name: '히스토그램' })).toBeEnabled()
    expect(screen.getByRole('button', { name: '파레토' })).toBeDisabled()
    expect(screen.getByRole('button', { name: '파레토' })).toHaveAttribute('title', '그룹핑한 결과로 만들 수 있습니다')
  })

  // 테스트 코드: RC-055
  it('잠긴 분류를 눌러도 바뀌지 않는다', async () => {
    // given: 그룹 2개 상태로 그려 둔다
    const { onChange, user } = setup('bar', 2)

    // when: 잠긴 원형 분류를 누른다
    await user.click(radio('원형'))

    // then: 변경 알림이 없다
    expect(onChange).not.toHaveBeenCalled()
  })

  // 테스트 코드: RC-055
  it('그룹 컬럼이 정확히 1개이면 모든 분류를 쓸 수 있다', () => {
    // when: 그룹 1개 상태로 그린다
    setup('bar', 1)

    // then: 13개 분류가 모두 활성이다
    for (const name of FAMILIES) expect(radio(name)).toBeEnabled()
  })
})

describe('KindPicker: 키보드', () => {
  // 테스트 코드: RC-056
  it('화살표 키로 분류를 옮기면 그 분류의 첫 하위 종류로 바꾼다', async () => {
    const { onChange, user } = setup('bar')
    // given: 세로 막대형 분류에 포커스가 있는 상태
    radio('세로 막대형').focus()

    // when: 아래 화살표를 누른다
    await user.keyboard('{ArrowDown}')

    // then: 가로 막대의 첫 종류인 묶은 가로 막대로 바뀐다
    expect(onChange).toHaveBeenLastCalledWith('horizontal_bar')
  })

  // 테스트 코드: RC-056
  it('Enter와 Space로 하위 종류를 고른다', async () => {
    // given: 누적 세로 막대 버튼에 포커스가 있는 상태
    const { onChange, user } = setup('bar')
    const button = screen.getByRole('button', { name: '누적 세로 막대' })

    button.focus()
    // when: Enter와 Space를 누른다
    await user.keyboard('{Enter}')
    await user.keyboard(' ')

    // then: 두 번 모두 누적 세로 막대로 변경 알림이 온다
    expect(onChange.mock.calls.map((c) => c[0])).toEqual(['stacked_bar', 'stacked_bar'])
  })

  // 테스트 코드: RC-056
  it('Tab으로 하위 종류 버튼에 도달한다', async () => {
    const { user } = setup('bar')
    // given: 세로 막대형 분류에 포커스가 있는 상태
    radio('세로 막대형').focus()

    // when: Tab을 누른다
    await user.tab()

    // then: 포커스가 하위 종류 버튼 중 하나에 있다
    expect(subKinds()).toContain(document.activeElement)
  })
})
