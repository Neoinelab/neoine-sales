import { screen, within } from '@testing-library/react'
import { describe, expect, it } from 'vitest'
import { renderAt } from '../../test/mockApp'

describe('상단 메뉴 순서 (계약관리 AC1)', () => {
  it.each(['admin', 'sales', 'user'] as const)('puts 계약관리 right after Deals for %s', async (role) => {
    await renderAt('/deals', { role })

    const nav = await screen.findByRole('navigation', { name: '주 메뉴' })

    const links = within(nav).getAllByRole('link')
    expect(links[0]).toHaveTextContent('Deals')
    expect(links[1]).toHaveTextContent('계약관리')
    expect(links[1]).toHaveAttribute('href', '/contracts')
  })
})

describe('상단 브랜드', () => {
  // 테스트 코드: PL-073
  it('상단 브랜드는 salesX 로고 이미지로 홈에 연결된다', async () => {
    // given: 로그인한 sales 사용자의 보호 화면
    await renderAt('/deals', { role: 'sales' })

    // when: 상단 브랜드 영역을 본다
    const logo = await screen.findByRole('img', { name: 'salesX' })

    // then: salesX 로고가 홈 링크 안에 있고 이전 브랜드 문구는 없다
    expect(logo).toHaveAttribute('src', '/images/salesX.png')
    expect(logo.closest('a')).toHaveAttribute('href', '/')
    expect(screen.queryByText('NEOINE 영업관리')).not.toBeInTheDocument()
  })
})
