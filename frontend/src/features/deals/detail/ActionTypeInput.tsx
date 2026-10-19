import { useMemo, type Ref } from 'react'
import { useActionTypes } from '../../../data/actionTypes'
import { ComboBox } from '../../../shared/ui/ComboBox'
import { ErrorBanner } from '../../../shared/ui/ErrorBanner'

export const TYPE_UNKNOWN_HINT = '목록에 없는 유형입니다. 저장하면 새 유형으로 추가됩니다.'

interface ActionTypeInputProps {
  value: string
  onChange: (value: string) => void
  error?: string
  inputRef?: Ref<HTMLInputElement>
}

/** Action 유형 입력: 클릭하면 서버 순서의 후보, 타이핑하면 부분 일치, 없으면 직접 입력(저장 때 새 유형이 된다). */
export function ActionTypeInput({ value, onChange, error, inputRef }: ActionTypeInputProps) {
  const query = useActionTypes()
  const types = query.data
  const options = useMemo(() => (types ?? []).map((t) => ({ value: t.name, id: t.id })), [types])
  const typed = value.trim().toLowerCase()
  // 목록을 아직 못 읽었으면(로딩·실패) 새 유형인지 알 수 없으므로 안내하지 않는다.
  const unknown = types !== undefined && typed !== '' && !options.some((o) => o.value.toLowerCase() === typed)
  return (
    <>
      <ErrorBanner error={query.error} />
      <ComboBox
        label="유형"
        name="actionType"
        value={value}
        onChange={onChange}
        options={options}
        error={error}
        hint={unknown ? TYPE_UNKNOWN_HINT : undefined}
        inputRef={inputRef}
      />
    </>
  )
}
