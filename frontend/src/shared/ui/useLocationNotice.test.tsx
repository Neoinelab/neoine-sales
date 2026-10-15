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
  it('returns the notice from location.state and clears the history state keeping the url', async () => {
    renderWith([{ pathname: '/deals', search: '?q=a', state: { notice: '삭제되었습니다.' } }])
    expect(screen.getByTestId('notice')).toHaveTextContent('삭제되었습니다.')
    await waitFor(() => expect(screen.getByTestId('state')).toHaveTextContent('null'))
    expect(screen.getByTestId('notice')).toHaveTextContent('삭제되었습니다.')
    expect(screen.getByTestId('url')).toHaveTextContent('/deals?q=a')
  })

  it('ignores a state without a string notice', () => {
    renderWith([{ pathname: '/deals', state: { notice: 3 } }])
    expect(screen.getByTestId('notice')).toHaveTextContent('없음')
  })

  it('returns nothing without a state', () => {
    renderWith(['/deals'])
    expect(screen.getByTestId('notice')).toHaveTextContent('없음')
  })
})
