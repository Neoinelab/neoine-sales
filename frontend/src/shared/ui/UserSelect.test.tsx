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
  it('기본으로는 재직 중인 영업 사용자만 묻는다', () => {
    // when: 기본 옵션으로 렌더한다 (전제: 사용자 옵션은 김영업뿐)
    render(<UserSelect label="Owner" name="owner" value="" onChange={() => {}} />)

    // then: 영업 역할로 묻고 안내 항목과 김영업이 있다
    expect(useUserOptions).toHaveBeenCalledWith({ role: 'sales' })
    expect(screen.getByRole('option', { name: '선택하세요' })).toBeInTheDocument()
    expect(screen.getByRole('option', { name: '김영업' })).toBeInTheDocument()
  })

  it('고른 사용자의 id를 알린다', async () => {
    // given: 값이 비어 있는 선택 상자
    const onChange = vi.fn()
    render(<UserSelect label="Owner" name="owner" value="" onChange={onChange} />)

    // when: 김영업을 고른다
    await userEvent.selectOptions(screen.getByLabelText('Owner'), String(USER_ID.kim))

    // then: 변경 콜백이 그 id 문자열을 받는다
    expect(onChange).toHaveBeenCalledWith(String(USER_ID.kim))
  })

  it('현재 담당자가 퇴사했으면 보이게 두되 고를 수는 없게 한다', () => {
    // when: 퇴사한 현재 담당자를 넘겨 렌더한다
    render(<UserSelect label="Owner" name="owner" value={String(USER_ID.lee)} onChange={() => {}} current={lee} />)

    // then: 퇴사 표시 항목이 비활성이고 선택 값은 그 사용자다
    const option = screen.getByRole('option', { name: '이퇴사(퇴사)' })
    expect(option).toBeDisabled()
    expect(screen.getByLabelText('Owner')).toHaveValue(String(USER_ID.lee))
  })

  it('검색 조건용으로는 퇴사자를 포함하고 첫 항목을 "전체"로 둔다', () => {
    // given: 재직자와 퇴사자가 모두 있는 사용자 옵션
    useUserOptions.mockReturnValue({ data: [kim, lee] })

    // when: 퇴사자 포함 옵션으로 렌더한다
    render(<UserSelect label="담당자" name="owner" value="" onChange={() => {}} includeResigned />)

    // then: 퇴사자 포함으로 묻고 "전체" 항목이 있으며 퇴사자를 고를 수 있다
    expect(useUserOptions).toHaveBeenCalledWith({ includeResigned: true })
    expect(screen.getByRole('option', { name: '전체' })).toBeInTheDocument()
    expect(screen.getByRole('option', { name: '이퇴사(퇴사)' })).toBeEnabled()
  })

  it('필수 오류 문구를 보여 준다', () => {
    // when: 오류 문구를 넘겨 렌더한다
    render(<UserSelect label="Owner" name="owner" value="" onChange={() => {}} error="Owner를 선택하세요." />)

    // then: 알림 영역에 오류 문구가 보인다
    expect(screen.getByRole('alert')).toHaveTextContent('Owner를 선택하세요.')
  })
})
