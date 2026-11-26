import { useState } from 'react'
import { render, screen } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { describe, expect, it } from 'vitest'
import { DirectoryFields } from './DirectoryFields'
import { DEFAULT_DIRECTORY_FORM } from './directoryForm'

function Form() {
  const [values, setValues] = useState(DEFAULT_DIRECTORY_FORM)
  return <DirectoryFields values={values} onChange={setValues} />
}

describe('AD 접속 정보', () => {
  it('shows five connection fields without persistent credential fields', () => {
    const { container } = render(<Form />)
    expect(container.querySelectorAll('input,select')).toHaveLength(5)
    expect(screen.queryByLabelText(/바인드/)).not.toBeInTheDocument()
  })
  it('updates default ports when security changes', async () => {
    const user = userEvent.setup()
    render(<Form />)
    await user.selectOptions(screen.getByLabelText(/보안 연결/), 'starttls')
    expect(screen.getByLabelText(/포트/)).toHaveValue(389)
    await user.clear(screen.getByLabelText(/포트/))
    await user.type(screen.getByLabelText(/포트/), '3269')
    await user.selectOptions(screen.getByLabelText(/보안 연결/), 'ssl')
    expect(screen.getByLabelText(/포트/)).toHaveValue(3269)
  })
})
