import type { InlineControlContext } from './InlineEdit'

/** 인라인 수정용 여러 줄 입력: Enter는 저장(InlineEdit이 처리), Shift+Enter는 줄바꿈. */
export function ActionTextArea({ value, onChange, inputLabel }: InlineControlContext) {
  return (
    <textarea
      aria-label={inputLabel}
      value={value}
      rows={3}
      onChange={(e) => onChange(e.target.value)}
      onKeyDown={(e) => {
        // 줄바꿈은 위쪽 Enter 저장 처리에 닿지 않게 한다.
        if (e.key === 'Enter' && e.shiftKey) e.stopPropagation()
      }}
    />
  )
}
