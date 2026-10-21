import { render, screen } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { beforeEach, describe, expect, it, vi } from 'vitest'
import type { UserRef } from '../model/types'
import { UserSelect } from './UserSelect'
import { USER_ID } from '../../test/fake/seed/ids'

const kim: UserRef = { id: USER_ID.kim, name: '김영업', role: 'sales', status: 'active' }
const lee: UserRef = { id: USER_ID.lee, name: '이퇴사', role: 'sales', status: 'resigned' }

const useUserOptions = vi.hoisted(() => vi.fn())
vi.mock('../../data/users', () => ({ useUserOptions }))

beforeEach(() => {
  useUserOptions.mockReset()
  useUserOptions.mockReturnValue({ data: [kim] })
})

describe('UserSelect', () => {
  it('asks for active sales users only by default', () => {
    render(<UserSelect label="Owner" name="owner" value="" onChange={() => {}} />)

    expect(useUserOptions).toHaveBeenCalledWith({ role: 'sales' })
    expect(screen.getByRole('option', { name: '선택하세요' })).toBeInTheDocument()
    expect(screen.getByRole('option', { name: '김영업' })).toBeInTheDocument()
  })

  it('reports the chosen id', async () => {
    const onChange = vi.fn()
    render(<UserSelect label="Owner" name="owner" value="" onChange={onChange} />)

    await userEvent.selectOptions(screen.getByLabelText('Owner'), String(USER_ID.kim))

    expect(onChange).toHaveBeenCalledWith(String(USER_ID.kim))
  })

  it('keeps a resigned current owner visible but not selectable', () => {
    render(<UserSelect label="Owner" name="owner" value={String(USER_ID.lee)} onChange={() => {}} current={lee} />)

    const option = screen.getByRole('option', { name: '이퇴사(퇴사)' })
    expect(option).toBeDisabled()
    expect(screen.getByLabelText('Owner')).toHaveValue(String(USER_ID.lee))
  })

  it('includes resigned users with an "전체" first option for filters', () => {
    useUserOptions.mockReturnValue({ data: [kim, lee] })
    render(<UserSelect label="담당자" name="owner" value="" onChange={() => {}} includeResigned />)

    expect(useUserOptions).toHaveBeenCalledWith({ includeResigned: true })
    expect(screen.getByRole('option', { name: '전체' })).toBeInTheDocument()
    expect(screen.getByRole('option', { name: '이퇴사(퇴사)' })).toBeEnabled()
  })

  it('shows a required error message', () => {
    render(<UserSelect label="Owner" name="owner" value="" onChange={() => {}} error="Owner를 선택하세요." />)

    expect(screen.getByRole('alert')).toHaveTextContent('Owner를 선택하세요.')
  })
})
