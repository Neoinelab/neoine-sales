import { useState } from 'react'
import { useChangeMyPassword } from '../../data/me'
import { errorFields } from '../../data/errorFields'
import { ErrorBanner } from '../../shared/ui/ErrorBanner'
import { TextField } from '../../shared/ui/fields'
import { Notice } from '../../shared/ui/Notice'

const CONFIRM_MISMATCH = '새 비밀번호 확인이 일치하지 않습니다.'

/**
 * 비밀번호 변경(local 모드). 현재 비밀번호를 확인하고, 성공하면 이 기기를 뺀 다른 기기의 로그인이 끝난다.
 * 비밀번호가 든 요청 변수를 쿼리 캐시에 남기지 않도록 끝나는 즉시 mutation을 비우고, 결과는 화면 상태로만 둔다.
 */
export function PasswordForm() {
  const change = useChangeMyPassword()
  const [current, setCurrent] = useState('')
  const [next, setNext] = useState('')
  const [confirm, setConfirm] = useState('')
  const [mismatch, setMismatch] = useState(false)
  const [done, setDone] = useState(false)
  const [error, setError] = useState<unknown>(null)
  const invalid = errorFields(error)

  const clearSecrets = () => {
    setCurrent('')
    setNext('')
    setConfirm('')
  }

  function submit() {
    setDone(false)
    setError(null)
    if (next !== confirm) {
      setMismatch(true)
      return
    }
    setMismatch(false)
    change.mutate(
      { current, next },
      {
        onSuccess: () => {
          clearSecrets()
          setDone(true)
          change.reset()
        },
        onError: (failure) => {
          clearSecrets()
          setError(failure)
          change.reset()
        },
      },
    )
  }

  return (
    <form
      className="account-card"
      aria-label="비밀번호 변경"
      noValidate
      onSubmit={(e) => {
        e.preventDefault()
        submit()
      }}
    >
      <h3>비밀번호 변경</h3>
      {mismatch ? (
        <p role="alert" className="error">
          {CONFIRM_MISMATCH}
        </p>
      ) : (
        <ErrorBanner error={error} />
      )}
      {done && (
        <Notice kind="success" onClose={() => setDone(false)}>
          비밀번호를 바꿨습니다. 다른 기기의 로그인이 종료되었습니다.
        </Notice>
      )}
      <TextField label="현재 비밀번호" name="current_password" type="password" autoComplete="current-password" value={current} onChange={setCurrent} invalid={invalid.includes('current_password')} />
      <TextField label="새 비밀번호" name="new_password" type="password" autoComplete="new-password" value={next} onChange={setNext} invalid={invalid.includes('new_password')} />
      <TextField label="새 비밀번호 확인" name="new_password_confirm" type="password" autoComplete="new-password" value={confirm} onChange={setConfirm} />
      <div className="actions">
        <button type="submit" className="primary" disabled={change.isPending}>
          비밀번호 변경
        </button>
      </div>
    </form>
  )
}
