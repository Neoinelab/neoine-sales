import { AutoGrowTextArea } from './AutoGrowTextArea'
import type { InlineControlContext } from './InlineEdit'

/** 인라인 수정용 여러 줄 입력: Enter·Shift+Enter 모두 줄바꿈이고 저장은 InlineEdit의 "저장" 버튼(saveButtons)이 한다. */
export function ActionTextArea({ value, onChange, inputLabel, startHeight, busy }: InlineControlContext) {
  return <AutoGrowTextArea label={inputLabel} value={value} onChange={onChange} startHeight={startHeight} disabled={busy} />
}
