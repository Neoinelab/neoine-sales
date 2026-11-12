import { render, screen } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { describe, expect, it, vi } from 'vitest'
import { Pager } from './Pager'

describe('Pager', () => {
  // 테스트 코드: UI-048
  it('total이 있으면 마지막 페이지에서 다음이 꺼진다', () => {
    // given: offset 20·limit 20·total 40(마지막 페이지)
    // when: 그린다
    render(<Pager offset={20} limit={20} total={40} onChange={() => {}} />)
    // then: 다음은 비활성, 이전은 활성이다
    expect(screen.getByRole('button', { name: '다음' })).toBeDisabled()
    expect(screen.getByRole('button', { name: '이전' })).toBeEnabled()
  })

  // 테스트 코드: UI-047
  it('첫 페이지에서는 이전이 꺼지고 다음을 누르면 다음 offset을 알린다', async () => {
    // given: offset 0·limit 20·total 41
    const onChange = vi.fn()
    render(<Pager offset={0} limit={20} total={41} onChange={onChange} />)
    // then: 이전은 비활성이고 "1 페이지"와 이름 "페이지"의 nav가 보인다
    expect(screen.getByRole('button', { name: '이전' })).toBeDisabled()
    expect(screen.getByText('1 페이지')).toBeInTheDocument()
    expect(screen.getByRole('navigation', { name: '페이지' })).toBeInTheDocument()
    // when: 다음을 누른다
    await userEvent.click(screen.getByRole('button', { name: '다음' }))
    // then: onChange(20)이다
    expect(onChange).toHaveBeenCalledWith(20)
  })

  // 테스트 코드: UI-047
  it('이전을 누르면 한 페이지 앞의 offset을 알리고 페이지 번호를 보인다', async () => {
    // given: offset 40·limit 20·total 100
    const onChange = vi.fn()
    render(<Pager offset={40} limit={20} total={100} onChange={onChange} />)
    // then: "3 페이지"가 보인다
    expect(screen.getByText('3 페이지')).toBeInTheDocument()
    // when: 이전을 누른다
    await userEvent.click(screen.getByRole('button', { name: '이전' }))
    // then: onChange(20)이다
    expect(onChange).toHaveBeenCalledWith(20)
  })

  // 테스트 코드: UI-048
  it('total이 없으면 받은 건수가 limit만큼일 때 다음이 켜진다', () => {
    // given: offset 0·limit 20·count 20(total 없음)
    // when: 그린다
    render(<Pager offset={0} limit={20} count={20} onChange={() => {}} />)
    // then: 다음이 활성이다
    expect(screen.getByRole('button', { name: '다음' })).toBeEnabled()
  })

  // 테스트 코드: UI-048
  it('total이 없고 받은 건수가 limit보다 적으면 마지막 페이지다', () => {
    // given: offset 0·limit 20·count 7
    // when: 그린다
    render(<Pager offset={0} limit={20} count={7} onChange={() => {}} />)
    // then: 다음이 비활성이다
    expect(screen.getByRole('button', { name: '다음' })).toBeDisabled()
  })
})
