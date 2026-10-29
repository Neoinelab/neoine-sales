import { useState } from 'react'
import { useSaveSetupDirectory } from '../../data/setup'
import { DEFAULT_DIRECTORY_FORM, inputFromForm, validateForm, type DirectoryFormValues } from '../../shared/directory/directoryForm'
import { DirectoryFields } from '../../shared/directory/DirectoryFields'
import { directoryErrorMessage } from '../../shared/directory/messages'
import { ErrorBanner } from '../../shared/ui/ErrorBanner'

/** 1단계: AD 서버 등록. 실패해도 입력 값은 유지한다. */
export function DirectoryStep({ onSaved }: { onSaved: () => void }) {
  const [values, setValues] = useState<DirectoryFormValues>(DEFAULT_DIRECTORY_FORM)
  const save = useSaveSetupDirectory()
  const [invalid, setInvalid] = useState<string | null>(null)
  return (
    <form
      className="setup-card"
      noValidate
      onSubmit={(e) => {
        e.preventDefault()
        const problem = validateForm(values, 'setup')
        setInvalid(problem)
        if (problem === null) save.mutate(inputFromForm(values), { onSuccess: onSaved })
      }}
    >
      <h2>AD 서버 등록</h2>
      <p className="hint">로그인에 사용할 회사 AD 서버를 등록합니다.</p>
      <ErrorBanner error={invalid ?? save.error} format={(e) => (typeof e === 'string' ? e : directoryErrorMessage(e))} />
      <DirectoryFields values={values} onChange={setValues} />
      <div className="actions">
        <button type="submit" className="primary" disabled={save.isPending}>
          AD 서버 등록
        </button>
      </div>
    </form>
  )
}
