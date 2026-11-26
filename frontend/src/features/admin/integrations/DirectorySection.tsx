import { useId } from 'react'
import { useDirectorySettings, useSaveDirectory, useTestDirectory } from '../../../data/settings'
import { DirectoryConnectionForm } from '../../../shared/directory/DirectoryConnectionForm'
import { directoryErrorMessage } from '../../../shared/directory/messages'
import { formatDateTime } from '../../../shared/format'
import { userLabel } from '../../../shared/model/period'
import type { DirectoryTestInput } from '../../../shared/model/types'
import { ErrorBanner } from '../../../shared/ui/ErrorBanner'

export function DirectorySection() {
  const titleId = useId()
  const settings = useDirectorySettings()
  const save = useSaveDirectory()
  const test = useTestDirectory()
  const saved = settings.data
  async function testConnection(input: DirectoryTestInput) {
    try { return await test.mutateAsync(input) } finally { test.reset() }
  }
  return <section className="admin-card" aria-labelledby={titleId}>
    <header>
      <h3 id={titleId}>AD(LDAP) 서버 설정</h3>
      {saved && <>
        <p className="hint">{`마지막 수정: ${saved.updatedBy ? userLabel(saved.updatedBy) : '-'} · ${formatDateTime(saved.updatedAt)}`}</p>
        <p className="hint">{`설정 버전 ${saved.revision}`}</p>
      </>}
    </header>
    <ErrorBanner error={settings.error} format={directoryErrorMessage} />
    {settings.isPending && <p className="hint">불러오는 중…</p>}
    {settings.isSuccess && <DirectoryConnectionForm saved={saved ?? null} test={testConnection} save={(input) => save.mutateAsync({ input, expectedRevision: saved?.revision ?? null })} />}
  </section>
}
