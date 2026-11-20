import { DateInput } from '../../../shared/ui/DateInput'
import { AutoGrowTextArea } from './AutoGrowTextArea'
import { decodePair, encodePair } from './actionEdit'
import type { InlineControlContext } from './InlineEdit'

/** Next Action과 Due Date를 한 번에 고치는 입력기. 칸 사이 이동은 저장이 아니고 Enter로 둘을 함께 저장한다. */
export function ActionNextPairInput({ value, onChange, commit, startHeight }: InlineControlContext) {
  const { next, due } = decodePair(value)
  return (
    <>
      <AutoGrowTextArea
        label="Next Action"
        value={next}
        startHeight={startHeight}
        // Next Action을 모두 지우면 Due Date도 비운다(Next Action 없이 Due Date는 저장할 수 없다).
        onChange={(v) => onChange(encodePair(v, v.trim() === '' ? '' : due))}
      />
      <DateInput
        aria-label="Due Date"
        value={due}
        onChange={(v) => onChange(encodePair(next, v))}
        onEnter={(v) => commit(encodePair(next, v))}
        onPicked={(v) => commit(encodePair(next, v))}
      />
    </>
  )
}
