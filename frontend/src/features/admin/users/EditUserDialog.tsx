import { useId, useState } from 'react'
import { useUpdateUser } from '../../../data/users'
import { errorFields } from '../../../data/errorFields'
import type { ProfileChange, User } from '../../../shared/model/types'
import { ErrorBanner } from '../../../shared/ui/ErrorBanner'
import { TextField } from '../../../shared/ui/fields'
import { Modal } from '../../../shared/ui/Modal'

interface Props {
  user: User
  /** 앱에서 직접 관리(local) 모드. 아니면(AD 연동) 이름·이메일은 AD 값이라 전화번호만 고칠 수 있다. */
  local: boolean
  onDone: (user: User) => void
  onCancel: () => void
}

export function EditUserDialog({ user, local, onDone, onCancel }: Props) {
  const formId = useId()
  const update = useUpdateUser()
  const [name, setName] = useState(user.name)
  const [email, setEmail] = useState(user.email ?? '')
  const [phone, setPhone] = useState(user.phone ?? '')
  const invalid = errorFields(update.error)

  const change: ProfileChange = {}
  if (local && name.trim() !== user.name) change.name = name.trim()
  if (local && email.trim() !== (user.email ?? '')) change.email = email.trim() === '' ? null : email.trim()
  if (phone.trim() !== (user.phone ?? '')) change.phone = phone.trim() === '' ? null : phone.trim()
  const dirty = Object.keys(change).length > 0

  return (
    <Modal
      title="정보 수정"
      onClose={onCancel}
      footer={
        <>
          <button type="button" onClick={onCancel}>
            취소
          </button>
          <button type="submit" form={formId} className="primary" disabled={!dirty || update.isPending}>
            저장
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
          update.mutate({ id: user.id, change }, { onSuccess: onDone })
        }}
      >
        <p>{`${user.loginId} 사용자의 정보를 고칩니다. 아이디와 역할은 여기서 바꿀 수 없습니다.`}</p>
        {!local && <p className="hint">이름·이메일은 AD에서 관리합니다. 전화번호만 고칠 수 있습니다.</p>}
        <ErrorBanner error={update.error} />
        <TextField label="이름" name="display_name" value={name} onChange={setName} disabled={!local} invalid={invalid.includes('display_name')} />
        <TextField label="이메일" name="email" type="email" value={email} onChange={setEmail} disabled={!local} invalid={invalid.includes('email')} />
        <TextField label="전화번호" name="phone" type="tel" value={phone} onChange={setPhone} invalid={invalid.includes('phone')} />
      </form>
    </Modal>
  )
}
