import { useSaveSetupDirectory, useTestSetupDirectory } from '../../data/setup'
import { DirectoryConnectionForm } from '../../shared/directory/DirectoryConnectionForm'
import type { DirectoryTestInput } from '../../shared/model/types'

export function DirectoryStep({ onSaved, onBack }: { onSaved: () => void; onBack: () => void }) {
  const save = useSaveSetupDirectory()
  const test = useTestSetupDirectory()
  async function testConnection(input: DirectoryTestInput) {
    try { return await test.mutateAsync(input) } finally { test.reset() }
  }
  return <DirectoryConnectionForm setup onBack={onBack} test={testConnection} save={async (input) => {
    await save.mutateAsync(input)
    onSaved()
  }} />
}
