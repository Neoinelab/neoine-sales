import { screen, waitFor, within } from '@testing-library/react'
import { describe, expect, it } from 'vitest'
import { renderAt } from '../../../test/mockApp'

type Rendered = Awaited<ReturnType<typeof renderAt>>

async function openStatus() {
  const view = await renderAt('/admin/deal', { role: 'admin' })
  await screen.findByRole('row', { name: /기회발굴/ })
  return view
}

async function openForecast() {
  const view = await openStatus()
  await view.user.click(screen.getByRole('tab', { name: 'Forecast 코드' }))
  await screen.findByRole('row', { name: /Pipeline/ })
  return view
}

/** 본문 행(헤더 제외)의 첫 번째 이름 칸 텍스트들. */
function names(): string[] {
  return screen
    .getAllByRole('row')
    .slice(1)
    .map((row) => within(row).getAllByRole('cell')[1]?.textContent ?? '')
}

function row(name: RegExp) {
  return within(screen.getByRole('row', { name }))
}

async function addCode(user: Rendered['user'], name: string) {
  await user.type(screen.getByLabelText('새 코드 이름'), name)
  await user.click(screen.getByRole('button', { name: '추가' }))
}

describe('Deal 관리 탭 (T-ADMIN-03)', () => {
  it('shows the five tabs, Vendor·Solution before the alert settings, and starts at Status codes', async () => {
    await openStatus()

    const tabs = within(screen.getByRole('tablist', { name: 'Deal 관리 항목' })).getAllByRole('tab')
    expect(tabs.map((t) => t.textContent)).toEqual(['Status 코드', 'Forecast 코드', 'BANT Label', 'Vendor·Solution', '경고 기준'])
    expect(screen.getByRole('tab', { name: 'Status 코드' })).toHaveAttribute('aria-selected', 'true')
  })

  it('explains that Won and 계약완료 stay in sync even when renamed', async () => {
    await openStatus()

    expect(screen.getByText(/Won과 계약완료는 이름을 바꿔도 같은 의미로 동기화됩니다/)).toBeInTheDocument()
  })
})

describe('Status 코드 목록 (T-ADMIN-03)', () => {
  it('lists the seven statuses in order with order, key and usage count', async () => {
    await openStatus()

    expect(names()).toEqual(['기회발굴', '제품소개', 'POC준비', 'POC완료', '기술평가', '가격협상', '계약완료'])
    for (const header of ['순서', '이름', '내부 코드', '사용 중 Deal']) {
      expect(screen.getByRole('columnheader', { name: header })).toBeInTheDocument()
    }
    const negotiation = row(/가격협상/)
    expect(negotiation.getByText('price_negotiation')).toBeInTheDocument()
    expect(negotiation.getByText('4')).toBeInTheDocument()
  })

  it('marks the system-linked 계약완료 as locked, with a disabled delete and a reason', async () => {
    await openStatus()

    const locked = row(/계약완료/)
    expect(locked.getByText('시스템 연결')).toBeInTheDocument()
    const del = locked.getByRole('button', { name: '삭제' })
    expect(del).toBeDisabled()
    expect(del).toHaveAccessibleDescription(/시스템과 연결된 코드는 삭제할 수 없습니다. 이름과 순서는 변경할 수 있습니다./)
    expect(row(/기회발굴/).getByText('시스템 연결')).toBeInTheDocument()
    expect(row(/제품소개/).queryByText('시스템 연결')).not.toBeInTheDocument()
  })
})

describe('Status 코드 이름 수정 (T-ADMIN-04)', () => {
  it('renames a code inline', async () => {
    const { user } = await openStatus()

    await user.click(row(/가격협상/).getByRole('button', { name: '이름 수정' }))
    const input = screen.getByLabelText('코드 이름')
    await user.clear(input)
    await user.type(input, '가격 협의')
    await user.click(screen.getByRole('button', { name: '저장' }))

    expect(await screen.findByRole('row', { name: /가격 협의/ })).toBeInTheDocument()
    expect(screen.queryByRole('row', { name: /가격협상/ })).not.toBeInTheDocument()
    expect(screen.queryByLabelText('코드 이름')).not.toBeInTheDocument()
  })

  it('lets the locked code be renamed as well', async () => {
    const { user } = await openStatus()

    await user.click(row(/계약완료/).getByRole('button', { name: '이름 수정' }))
    const input = screen.getByLabelText('코드 이름')
    await user.clear(input)
    await user.type(input, '계약성사')
    await user.keyboard('{Enter}')

    expect(await screen.findByRole('row', { name: /계약성사/ })).toBeInTheDocument()
    expect(row(/계약성사/).getByText('contract_completed')).toBeInTheDocument()
  })

  it('cancels the rename with Escape and keeps the name', async () => {
    const { user } = await openStatus()

    await user.click(row(/가격협상/).getByRole('button', { name: '이름 수정' }))
    await user.type(screen.getByLabelText('코드 이름'), '추가')
    await user.keyboard('{Escape}')

    expect(screen.queryByLabelText('코드 이름')).not.toBeInTheDocument()
    expect(screen.getByRole('row', { name: /가격협상/ })).toBeInTheDocument()
  })

  it('shows the server message for a duplicate name and keeps editing', async () => {
    const { user } = await openStatus()

    await user.click(row(/가격협상/).getByRole('button', { name: '이름 수정' }))
    const input = screen.getByLabelText('코드 이름')
    await user.clear(input)
    await user.type(input, '제품소개')
    await user.click(screen.getByRole('button', { name: '저장' }))

    expect(await screen.findByRole('alert')).toHaveTextContent('같은 이름의 코드가 이미 있습니다.')
    expect(screen.getByLabelText('코드 이름')).toHaveValue('제품소개')
  })

  it('shows the server message when the name is empty', async () => {
    const { user } = await openStatus()

    await user.click(row(/가격협상/).getByRole('button', { name: '이름 수정' }))
    await user.clear(screen.getByLabelText('코드 이름'))
    await user.click(screen.getByRole('button', { name: '저장' }))

    expect(await screen.findByRole('alert')).toHaveTextContent('이름을 입력하세요.')
  })
})

describe('Status 코드 순서 변경 (T-ADMIN-04)', () => {
  it('moves a code up and down', async () => {
    const { user } = await openStatus()

    await user.click(screen.getByRole('button', { name: '가격협상 위로 이동' }))

    await waitFor(() =>
      expect(names()).toEqual(['기회발굴', '제품소개', 'POC준비', 'POC완료', '가격협상', '기술평가', '계약완료']),
    )
    await user.click(screen.getByRole('button', { name: '가격협상 아래로 이동' }))
    await waitFor(() =>
      expect(names()).toEqual(['기회발굴', '제품소개', 'POC준비', 'POC완료', '기술평가', '가격협상', '계약완료']),
    )
  })

  it('disables moving the first code up and the last code down', async () => {
    await openStatus()

    expect(screen.getByRole('button', { name: '기회발굴 위로 이동' })).toBeDisabled()
    expect(screen.getByRole('button', { name: '계약완료 아래로 이동' })).toBeDisabled()
  })
})

describe('Status 코드 추가·삭제 (T-ADMIN-05)', () => {
  it('adds a code at the end with zero usage and clears the input', async () => {
    const { user } = await openStatus()

    await addCode(user, '내부검토')

    expect(await screen.findByRole('row', { name: /내부검토/ })).toBeInTheDocument()
    expect(names().at(-1)).toBe('내부검토')
    expect(row(/내부검토/).getByText('0')).toBeInTheDocument()
    expect(screen.getByLabelText('새 코드 이름')).toHaveValue('')
  })

  it('shows the server message for an empty new name', async () => {
    const { user } = await openStatus()

    await user.click(screen.getByRole('button', { name: '추가' }))

    expect(await screen.findByRole('alert')).toHaveTextContent('이름을 입력하세요.')
  })

  it('deletes an unused code after confirmation', async () => {
    const { user } = await openStatus()
    await addCode(user, '내부검토')
    await screen.findByRole('row', { name: /내부검토/ })

    await user.click(row(/내부검토/).getByRole('button', { name: '삭제' }))
    const dialog = within(await screen.findByRole('dialog', { name: '코드 삭제' }))
    await user.click(dialog.getByRole('button', { name: '삭제' }))

    await waitFor(() => expect(screen.queryByRole('row', { name: /내부검토/ })).not.toBeInTheDocument())
  })

  it('keeps the code when the delete confirmation is declined', async () => {
    const { user } = await openStatus()
    await addCode(user, '내부검토')
    await screen.findByRole('row', { name: /내부검토/ })

    await user.click(row(/내부검토/).getByRole('button', { name: '삭제' }))
    await user.click(within(await screen.findByRole('dialog')).getByRole('button', { name: '취소' }))

    expect(screen.getByRole('row', { name: /내부검토/ })).toBeInTheDocument()
  })

  it('refuses to delete a code that deals use and shows how many', async () => {
    const { user } = await openStatus()

    await user.click(row(/가격협상/).getByRole('button', { name: '삭제' }))
    await user.click(within(await screen.findByRole('dialog')).getByRole('button', { name: '삭제' }))

    expect(await screen.findByRole('alert')).toHaveTextContent('사용 중인 코드는 삭제할 수 없습니다. (Deal 4건)')
    expect(screen.queryByRole('dialog')).not.toBeInTheDocument()
    expect(screen.getByRole('row', { name: /가격협상/ })).toBeInTheDocument()
  })
})

describe('Forecast 코드 (T-ADMIN-03~05)', () => {
  it('lists the six forecasts with probability hints and the Open/Won/Lost kind', async () => {
    await openForecast()

    expect(names()).toEqual(['Pipeline', 'Best', 'Most Likely', 'Commit', 'Won', 'Lost'])
    expect(screen.getByRole('columnheader', { name: '확률 참고' })).toBeInTheDocument()
    expect(screen.getByRole('columnheader', { name: '구분' })).toBeInTheDocument()
    expect(row(/Pipeline/).getByText('0–50')).toBeInTheDocument()
    expect(row(/Pipeline/).getByText('Open')).toBeInTheDocument()
    expect(row(/Lost/).getByText('Lost', { selector: '.badge' })).toBeInTheDocument()
  })

  it('locks Won against deletion but allows renaming it', async () => {
    const { user } = await openForecast()

    expect(row(/^.*Won/).getByRole('button', { name: '삭제' })).toBeDisabled()
    expect(row(/Won/).getByText('시스템 연결')).toBeInTheDocument()
    await user.click(row(/Won/).getByRole('button', { name: '이름 수정' }))
    const input = screen.getByLabelText('코드 이름')
    await user.clear(input)
    await user.type(input, '수주')
    await user.click(screen.getByRole('button', { name: '저장' }))

    expect(await screen.findByRole('row', { name: /수주/ })).toBeInTheDocument()
  })

  it('refuses to delete a forecast that deals use', async () => {
    const { user } = await openForecast()

    await user.click(row(/Commit/).getByRole('button', { name: '삭제' }))
    await user.click(within(await screen.findByRole('dialog')).getByRole('button', { name: '삭제' }))

    expect(await screen.findByRole('alert')).toHaveTextContent(/사용 중인 코드는 삭제할 수 없습니다\. \(Deal \d+건\)/)
  })

  it('adds and reorders forecast codes independently from statuses', async () => {
    const { user } = await openForecast()

    await addCode(user, 'Upside')
    expect(await screen.findByRole('row', { name: /Upside/ })).toBeInTheDocument()
    await user.click(screen.getByRole('button', { name: 'Upside 위로 이동' }))

    await waitFor(() => expect(names().indexOf('Upside')).toBe(names().length - 2))
  })
})
