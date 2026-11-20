import { AutoGrowTextArea } from './AutoGrowTextArea'
import type { InlineControlContext } from './InlineEdit'

/** 인라인 수정용 여러 줄 입력: Enter는 저장(InlineEdit이 처리), Shift+Enter는 줄바꿈. */
export function ActionTextArea({ value, onChange, inputLabel, startHeight }: InlineControlContext) {
  return <AutoGrowTextArea label={inputLabel} value={value} onChange={onChange} startHeight={startHeight} />
}
