import { describe, expect, it } from 'vitest'
import { COMBO_PRESETS, comboPresetOf } from './combo'

/**
 * 콤보 프리셋(명세 RC-R30): 화면 바로가기일 뿐 저장하지 않는다. 프리셋을 고르면 계열별 설정이 채워지고,
 * 현재 설정이 어느 프리셋과 같은지는 `comboPresetOf`가 계산해 "사용자 지정 조합"과 구분한다.
 * 계약: `COMBO_PRESETS`는 `{ key, label, apply(count) }[]`이고 `apply(count)`는 값 열 수만큼의 `{ type, secondary }[]`다.
 */

const column = { type: 'column', secondary: false } as const
const line = { type: 'line', secondary: false } as const
const lineSecondary = { type: 'line', secondary: true } as const
const area = { type: 'stacked_area', secondary: false } as const

describe('콤보 프리셋', () => {
  // 테스트 코드: RC-064
  it('프리셋은 세 가지이고 사용자 지정 조합은 프리셋이 아니다', () => {
    // when: 프리셋 이름을 모은다
    const actual = COMBO_PRESETS.map((p) => p.label)
    // then: Excel 이름 세 개뿐이다
    expect(actual).toEqual(['묶은 세로 막대 - 꺾은선', '묶은 세로 막대 - 보조 축의 꺾은선', '누적 영역 - 묶은 세로 막대'])
  })

  // 테스트 코드: RC-064
  it('첫째 프리셋은 막대 하나에 나머지는 꺾은선이다', () => {
    // when: 첫째 프리셋을 값 3개에 적용한다
    const actual = COMBO_PRESETS[0]?.apply(3)

    // then: 막대, 꺾은선, 꺾은선이다
    expect(actual).toEqual([column, line, line])
  })

  // 테스트 코드: RC-064
  it('둘째 프리셋은 꺾은선을 보조 축에 둔다', () => {
    // when: 둘째 프리셋을 값 3개에 적용한다
    const actual = COMBO_PRESETS[1]?.apply(3)

    // then: 막대, 보조 축 꺾은선 둘이다
    expect(actual).toEqual([column, lineSecondary, lineSecondary])
  })

  // 테스트 코드: RC-064
  it('셋째 프리셋은 마지막만 막대이고 나머지는 누적 영역이다', () => {
    // when: 셋째 프리셋을 값 3개와 2개에 적용한다
    const actual = COMBO_PRESETS[2]?.apply(3)
    const actual2 = COMBO_PRESETS[2]?.apply(2)
    // then: 누적 영역 + 마지막 막대다
    expect(actual).toEqual([area, area, column])
    expect(actual2).toEqual([area, column])
  })

  // 테스트 코드: RC-064
  it('어느 프리셋도 모든 계열을 보조 축에 두지 않는다', () => {
    // when: 모든 프리셋을 값 2·3·10개에 적용한다
    const allSecondary = COMBO_PRESETS.flatMap((preset) => [2, 3, 10].map((count) => preset.apply(count).every((s) => s.secondary)))
    // then: 전부 보조 축인 경우가 없다
    expect(allSecondary).not.toContain(true)
  })

  // 테스트 코드: RC-064
  it.each([2, 3, 10])('프리셋이 채운 설정은 그 프리셋으로 알아본다 (%s개)', (count) => {
    // when: 프리셋이 채운 설정으로 프리셋을 알아본다
    const recognized = COMBO_PRESETS.map((preset) => comboPresetOf(preset.apply(count)))
    // then: 같은 프리셋이다
    expect(recognized).toEqual(COMBO_PRESETS.map((preset) => preset.key))
  })

  // 테스트 코드: RC-064
  it('그 밖의 설정은 사용자 지정 조합이다', () => {
    // when: 프리셋과 다른 설정 세 가지의 프리셋을 알아본다
    const actual = comboPresetOf([column, { type: 'line_markers', secondary: false }])
    const actual2 = comboPresetOf([line, column])
    const actual3 = comboPresetOf([column, lineSecondary, line])
    // then: 모두 custom이다
    expect(actual).toBe('custom')
    expect(actual2).toBe('custom')
    expect(actual3).toBe('custom')
  })
})
