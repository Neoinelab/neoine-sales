import { useState } from 'react'
import { useCreateUser } from '../../../data/users'
import type { Role } from '../../../shared/model/types'
import { ErrorBanner } from '../../../shared/ui/ErrorBanner'
import { SelectField, TextField } from '../../../shared/ui/fields'

const MISSING_MESSAGE = 'AD 아이디와 이름을 입력하세요.'

/** 로그인을 허용할 AD 계정을 이름·역할과 함께 등록한다(비밀번호는 AD가 확인한다). */
export function AddUserForm() {
  const create = useCreateUser()
  const [loginId, setLoginId] = useState('')
  const [name, setName] = useState('')
  const [role, setRole] = useState<Role>('sales')
  const [missing, setMissing] = useState(false)

  function submit() {
    if (loginId.trim() === '' || name.trim() === '') {
      setMissing(true)
      return
    }
    setMissing(false)
    create.mutate(
      { loginId: loginId.trim(), name: name.trim(), role },
      {
        onSuccess: () => {
          setLoginId('')
          setName('')
        },
      },
    )
  }

  return (
    <form
      className="admin-card"
      aria-label="사용자 등록"
      noValidate
      onSubmit={(e) => {
        e.preventDefault()
        submit()
      }}
    >
      <h3>사용자 등록</h3>
      {missing ? (
        <p role="alert" className="error">
          {MISSING_MESSAGE}
        </p>
      ) : (
        <ErrorBanner error={create.error} />
      )}
      <div className="admin-form-row">
        <TextField label="AD 아이디" name="login_id" value={loginId} onChange={setLoginId} />
        <TextField label="이름" name="name" value={name} onChange={setName} />
        <SelectField label="역할" name="role" value={role} onChange={(v) => setRole(v as Role)}>
          <option value="admin">admin</option>
          <option value="sales">sales</option>
          <option value="user">user</option>
        </SelectField>
        <button type="submit" className="primary" disabled={create.isPending}>
          추가
        </button>
      </div>
    </form>
  )
}
