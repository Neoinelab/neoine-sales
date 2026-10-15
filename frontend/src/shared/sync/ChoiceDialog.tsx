import { useId, useState } from 'react'
import { Modal } from '../ui/Modal'

export interface ChoiceOption {
  value: string
  label: string
}

interface ChoiceDialogProps {
  /** SyncPlan.prompt */
  prompt: string
  options: readonly ChoiceOption[]
  /** 미리 선택할 값. null이면 선택 전까지 `확인` 비활성. */
  defaultValue: string | null
  error?: string | null
  onConfirm: (value: string) => void
  onCancel: () => void
}

/** "함께 바꿀 값 선택" 팝업: 라디오 목록. 선택 후에만 `확인`이 활성, 취소는 변경 없음. */
export function ChoiceDialog({ prompt, options, defaultValue, error, onConfirm, onCancel }: ChoiceDialogProps) {
  const promptId = useId()
  const [choice, setChoice] = useState<string | null>(defaultValue)

  return (
    <Modal
      title="함께 바꿀 값 선택"
      onClose={onCancel}
      footer={
        <>
          <button type="button" onClick={onCancel}>
            취소
          </button>
          <button type="button" className="primary" disabled={choice === null} onClick={() => choice !== null && onConfirm(choice)}>
            확인
          </button>
        </>
      }
    >
      <p id={promptId}>{prompt}</p>
      <div role="radiogroup" aria-labelledby={promptId} className="choice-list">
        {options.map((option) => (
          <label key={option.value} className="choice">
            <input type="radio" name="sync-choice" checked={choice === option.value} onChange={() => setChoice(option.value)} />
            {option.label}
          </label>
        ))}
      </div>
      {error && (
        <p role="alert" className="field-error">
          {error}
        </p>
      )}
    </Modal>
  )
}
