import { useState, type KeyboardEvent } from 'react'
import { useCreateLabel } from '../../../data/labels'
import { BANT_CATEGORY_NAMES, BANT_LABEL_MAX_LENGTH, type BantCategory } from '../../../shared/model/constants'

interface NewLabelInputProps {
  category: BantCategory
  /** 만든 Label의 id. 호출처가 그 항목에 바로 선택한다. */
  onCreated: (labelId: string) => void
  onCancel: () => void
}

/** BANT 항목 안에서 즉석으로 Label을 만든다. 중복(같은 구분, 대소문자 무시)은 서버(게이트웨이) 문구로 거부된다. */
export function NewLabelInput({ category, onCreated, onCancel }: NewLabelInputProps) {
  const create = useCreateLabel()
  const [name, setName] = useState('')
  const [error, setError] = useState<string | null>(null)
  const title = BANT_CATEGORY_NAMES[category]

  async function submit() {
    const trimmed = name.trim()
    if (trimmed === '') return setError('Label 이름을 입력하세요.')
    if (Array.from(trimmed).length > BANT_LABEL_MAX_LENGTH) {
      return setError(`Label 이름은 ${BANT_LABEL_MAX_LENGTH}자 이내로 입력하세요.`)
    }
    setError(null)
    try {
      const label = await create.mutateAsync({ category, name: trimmed })
      onCreated(label.id)
    } catch (failure) {
      setError(failure instanceof Error ? failure.message : 'Label을 만들지 못했습니다.')
    }
  }

  // Enter는 폼 저장이 아니라 Label 만들기, Esc는 입력 닫기.
  function onKeyDown(event: KeyboardEvent<HTMLInputElement>) {
    if (event.key === 'Enter') {
      event.preventDefault()
      void submit()
    } else if (event.key === 'Escape') {
      event.preventDefault()
      onCancel()
    }
  }

  return (
    <div className="new-label">
      <div className="field">
        <label>
          <span>{title} 새 Label 이름</span>
          <input
            value={name}
            maxLength={BANT_LABEL_MAX_LENGTH + 10}
            aria-invalid={error ? true : undefined}
            onChange={(e) => setName(e.target.value)}
            onKeyDown={onKeyDown}
          />
        </label>
        {error && (
          <p role="alert" className="field-error">
            {error}
          </p>
        )}
      </div>
      <button type="button" className="primary" disabled={create.isPending} onClick={() => void submit()}>
        만들기
      </button>
      <button type="button" aria-label="새 Label 취소" onClick={onCancel}>
        취소
      </button>
    </div>
  )
}
