import { useLabels } from '../../../data/labels'
import { BANT_CATEGORIES, BANT_CATEGORY_NAMES } from '../../../shared/model/constants'
import { ComboBox } from '../../../shared/ui/ComboBox'
import { ErrorBanner } from '../../../shared/ui/ErrorBanner'
import type { SectionProps } from './sectionTypes'

export const BANT_UNKNOWN_HINT = '목록에 없는 Label입니다. 저장하면 새 Label로 추가됩니다.'

/**
 * ⑥ BANT: 항목마다 Label 이름을 입력한다(클릭하면 그 구분의 후보, 타이핑하면 부분 일치). 비워 두면 선택 안 함.
 * 목록에 없는 이름은 저장할 때 서버가 그 구분의 새 Label로 만든다. 기존 Label의 이름 수정·삭제는 Admin > Deal 관리에 있다.
 * Label 목록을 못 읽으면 입력을 막고(저장은 기존 선택을 그대로 둔다) 오류를 보인다.
 */
export function BantSection({ state, set, errors }: SectionProps) {
  const labels = useLabels()
  const all = labels.data ?? []
  const failed = labels.error !== null

  return (
    <section className="form-section" aria-labelledby="sec-bant">
      <h2 id="sec-bant">BANT</h2>
      <fieldset className="bant-fieldset">
        <legend className="kv-visually-hidden">BANT</legend>
        <ErrorBanner error={labels.error} />
        <div className="kv-grid">
          {BANT_CATEGORIES.map((category) => {
            const options = all.filter((l) => l.category === category).map((l) => ({ value: l.name, id: l.id }))
            const typed = state.bant[category].trim().toLowerCase()
            const unknown = typed !== '' && !options.some((o) => o.value.toLowerCase() === typed)
            return (
              <div key={category} className="kv-row">
                <ComboBox
                  label={BANT_CATEGORY_NAMES[category]}
                  name={`bant-${category}`}
                  value={state.bant[category]}
                  onChange={(text) => set('bant', { ...state.bant, [category]: text })}
                  options={options}
                  placeholder="비워 두면 선택 안 함"
                  disabled={failed}
                  error={errors.bant?.[category]}
                  hint={unknown ? BANT_UNKNOWN_HINT : undefined}
                />
              </div>
            )
          })}
        </div>
      </fieldset>
    </section>
  )
}
