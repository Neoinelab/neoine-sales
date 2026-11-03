import { describe, expect, it } from 'vitest'
import { COMBO_PRESETS, comboPresetOf } from './combo'

/**
 * 콤보 프리셋(Excel 확장 "설계 6"): 화면 바로가기일 뿐 저장하지 않는다. 프리셋을 고르면 계열별 설정이 채워지고,
 * 현재 설정이 어느 프리셋과 같은지는 `comboPresetOf`가 계산해 "사용자 지정 조합"과 구분한다.
 * 계약: `COMBO_PRESETS`는 `{ key, label, apply(count) }[]`이고 `apply(count)`는 값 열 수만큼의 `{ type, secondary }[]`다.
 */

const column = { type: 'column', secondary: false } as const
const line = { type: 'line', secondary: false } as const
const lineSecondary = { type: 'line', secondary: true } as const
const area = { type: 'stacked_area', secondary: false } as const

describe('combo presets', () => {
  it('lists the three presets with their Excel names (the custom mix is not a preset)', () => {
    expect(COMBO_PRESETS.map((p) => p.label)).toEqual(['묶은 세로 막대 - 꺾은선', '묶은 세로 막대 - 보조 축의 꺾은선', '누적 영역 - 묶은 세로 막대'])
  })

  it('fills column then lines for the first preset', () => {
    expect(COMBO_PRESETS[0]?.apply(3)).toEqual([column, line, line])
  })

  it('fills column then lines on the secondary axis for the second preset', () => {
    expect(COMBO_PRESETS[1]?.apply(3)).toEqual([column, lineSecondary, lineSecondary])
  })

  it('makes all but the last series stacked areas and the last one a column for the third preset', () => {
    expect(COMBO_PRESETS[2]?.apply(3)).toEqual([area, area, column])
    expect(COMBO_PRESETS[2]?.apply(2)).toEqual([area, column])
  })

  it('never puts every series on the secondary axis', () => {
    for (const preset of COMBO_PRESETS) {
      for (const count of [2, 3, 10]) expect(preset.apply(count).every((s) => s.secondary)).toBe(false)
    }
  })

  it.each([2, 3, 10])('recognizes what a preset filled for %s series', (count) => {
    for (const preset of COMBO_PRESETS) expect(comboPresetOf(preset.apply(count))).toBe(preset.key)
  })

  it('calls anything else a custom mix', () => {
    expect(comboPresetOf([column, { type: 'line_markers', secondary: false }])).toBe('custom')
    expect(comboPresetOf([line, column])).toBe('custom')
    expect(comboPresetOf([column, lineSecondary, line])).toBe('custom')
  })
})
