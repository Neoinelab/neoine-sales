import { render, screen, waitFor } from '@testing-library/react'
import { MemoryRouter, useLocation } from 'react-router'
import { describe, expect, it } from 'vitest'
import { useLocationNotice } from './useLocationNotice'

function Probe() {
  const [notice] = useLocationNotice()
  const location = useLocation()
  return (
    <div>
      <p data-testid="notice">{notice ?? '없음'}</p>
      <p data-testid="state">{JSON.stringify(location.state)}</p>
      <p data-testid="url">{location.pathname + location.search}</p>
    </div>
  )
}

function renderWith(entry: Parameters<typeof MemoryRouter>[0]['initialEntries']) {
  return render(
    <MemoryRouter initialEntries={entry}>
      <Probe />
    </MemoryRouter>,
  )
}

describe('useLocationNotice', () => {
  // 테스트 코드: UI-055
  it('이동 상태의 알림을 돌려주고 기록 상태는 비우되 주소는 그대로 둔다', async () => {
    // given: 이동 상태 {notice}로 연 /deals?q=a
    renderWith([{ pathname: '/deals', search: '?q=a', state: { notice: '삭제되었습니다.' } }])
    // then: 알림이 보인다
    expect(screen.getByTestId('notice')).toHaveTextContent('삭제되었습니다.')
    // when: 기록 상태가 비워지기를 기다린다
    await waitFor(() => expect(screen.getByTestId('state')).toHaveTextContent('null'))
    // then: 알림은 남아 있고 주소는 그대로다
    expect(screen.getByTestId('notice')).toHaveTextContent('삭제되었습니다.')
    expect(screen.getByTestId('url')).toHaveTextContent('/deals?q=a')
  })

  // 테스트 코드: UI-055
  it('알림이 문자열이 아니면 알림이 없다', () => {
    // when: {notice: 3} 상태로 연다
    renderWith([{ pathname: '/deals', state: { notice: 3 } }])
    // then: 알림이 없다
    expect(screen.getByTestId('notice')).toHaveTextContent('없음')
  })

  // 테스트 코드: UI-055
  it('이동 상태가 없으면 알림이 없다', () => {
    // when: 상태 없이 연다
    renderWith(['/deals'])
    // then: 알림이 없다
    expect(screen.getByTestId('notice')).toHaveTextContent('없음')
  })
})
