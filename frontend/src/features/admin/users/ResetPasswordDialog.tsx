import { useId, useState } from 'react'
import { useResetUserPassword } from '../../../data/users'
import { errorFields } from '../../../data/errorFields'
import type { User } from '../../../shared/model/types'
import { ErrorBanner } from '../../../shared/ui/ErrorBanner'
import { TextField } from '../../../shared/ui/fields'
import { Modal } from '../../../shared/ui/Modal'

const CONFIRM_MISMATCH = '새 비밀번호 확인이 일치하지 않습니다.'

interface Props {
  user: User
  onDone: (user: User) => void
  onCancel: () => void
}

/**
 * 관리자가 사용자의 비밀번호를 정하는 대화상자(local 모드). 첫 로그인 시 변경 강제는 없고, 재설정하면 그 사용자의 로그인이 모두 끝난다.
 * 비밀번호가 든 요청 변수는 끝나는 즉시 mutation을 비워 쿼리 캐시에 남기지 않는다.
 */
export function ResetPasswordDialog({ user, onDone, onCancel }: Props) {
  const formId = useId()
  const reset = useResetUserPassword()
  const [password, setPassword] = useState('')
  const [confirm, setConfirm] = useState('')
  const [mismatch, setMismatch] = useState(false)
  const [error, setError] = useState<unknown>(null)
  const invalid = errorFields(error)

  function submit() {
    setError(null)
    if (password !== confirm) {
      setMismatch(true)
      return
    }
    setMismatch(false)
    reset.mutate(
      { id: user.id, password },
      {
        onSuccess: () => {
          reset.reset()
          onDone(user)
        },
        onError: (failure) => {
          setPassword('')
          setConfirm('')
          setError(failure)
          reset.reset()
        },
      },
    )
  }

  return (
    <Modal
      title="비밀번호 재설정"
      onClose={onCancel}
      footer={
        <>
          <button type="button" onClick={onCancel}>
            취소
          </button>
          <button type="submit" form={formId} className="primary" disabled={reset.isPending}>
            재설정
          </button>
        </>
      }
    >
      <form
        id={formId}
        noValidate
        className="admin-grid"
        onSubmit={(e) => {
          e.preventDefault()
          submit()
        }}
      >
        <p>{`${user.loginId} (${user.name}) 사용자의 비밀번호를 새로 정합니다.`}</p>
        <p className="hint">재설정하면 그 사용자의 로그인이 모두 종료됩니다. 새 비밀번호는 직접 전달하세요.</p>
        {mismatch ? (
          <p role="alert" className="error">
            {CONFIRM_MISMATCH}
          </p>
        ) : (
          <ErrorBanner error={error} />
        )}
        <TextField label="새 비밀번호" name="new_password" type="password" autoComplete="new-password" value={password} onChange={setPassword} invalid={invalid.includes('password')} />
        <TextField label="새 비밀번호 확인" name="new_password_confirm" type="password" autoComplete="new-password" value={confirm} onChange={setConfirm} />
      </form>
    </Modal>
  )
}
