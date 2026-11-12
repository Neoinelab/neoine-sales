import { screen, waitFor, within } from '@testing-library/react'
import { afterEach, describe, expect, it, vi } from 'vitest'
import { gateway } from '../../../gateway'
import { renderAt } from '../../../test/mockApp'

afterEach(() => vi.restoreAllMocks())

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

describe('Deal 관리 화면 틀', () => {
  // 탭 6개를 순서대로 보이고 Status 코드 탭에서 시작한다.
  // 테스트 코드: CD-047
  it('shows the six tabs, Vendor before the alert settings, and starts at Status codes', async () => {
    // given: admin으로 /admin/deal을 연다
    await openStatus()

    // then: 탭 목록 "Deal 관리 항목"이 정해진 순서이고 Status 코드가 선택되어 있다
    const tabs = within(screen.getByRole('tablist', { name: 'Deal 관리 항목' })).getAllByRole('tab')
    expect(tabs.map((t) => t.textContent)).toEqual(['Status 코드', 'Forecast 코드', 'BANT Label', 'Action 유형', 'Vendor', '경고 기준'])
    expect(screen.getByRole('tab', { name: 'Status 코드' })).toHaveAttribute('aria-selected', 'true')
  })

  // 주소의 tab 값으로 탭을 열고 모르는 값이면 Status 코드 탭이며, Status 코드 탭을 고르면 주소에 tab이 없다.
  // 테스트 코드: CD-048
  it('opens the tab named by ?tab=, falls back to Status codes, and drops tab for Status codes', async () => {
    // when: ?tab=forecast로 연다
    const forecast = await renderAt('/admin/deal?tab=forecast', { role: 'admin' })
    // then: Forecast 코드 탭이 선택되고 Forecast 표가 보인다
    expect(await screen.findByRole('table', { name: 'Forecast 코드' })).toBeInTheDocument()
    expect(screen.getByRole('tab', { name: 'Forecast 코드' })).toHaveAttribute('aria-selected', 'true')

    // when: Status 코드 탭을 고른다
    await forecast.user.click(screen.getByRole('tab', { name: 'Status 코드' }))
    // then: Status 표가 보이고 주소에는 tab이 없다
    expect(await screen.findByRole('table', { name: 'Status 코드' })).toBeInTheDocument()
    expect(forecast.location()).toBe('/admin/deal')
    forecast.unmount()

    // when: 모르는 tab 값으로 연다
    await renderAt('/admin/deal?tab=unknown', { role: 'admin' })
    // then: Status 코드 탭이 선택된다
    expect(await screen.findByRole('table', { name: 'Status 코드' })).toBeInTheDocument()
    expect(screen.getByRole('tab', { name: 'Status 코드' })).toHaveAttribute('aria-selected', 'true')
  })
})

describe('Status 코드 목록 (T-ADMIN-03)', () => {
  // Won·계약완료 동기화 안내를 보인다.
  // 테스트 코드: CD-049
  it('explains that Won and 계약완료 stay in sync even when renamed', async () => {
    // given: Status 코드 탭을 연다
    await openStatus()

    // then: 동기화 안내가 보인다
    expect(screen.getByText(/Won과 계약완료는 이름을 바꿔도 같은 의미로 동기화됩니다/)).toBeInTheDocument()
  })

  // Status 표는 7개를 순서대로 순서·이름·내부 코드·사용 건수와 함께 보인다.
  // 테스트 코드: CD-050
  it('lists the seven statuses in order with order, key and usage count', async () => {
    // given: Status 코드 탭을 연다
    await openStatus()

    // then: 이름이 기본 순서이고 머리글이 있으며 가격협상 행에 key와 사용 4가 보인다
    expect(names()).toEqual(['기회발굴', '제품소개', 'POC준비', 'POC완료', '기술평가', '가격협상', '계약완료'])
    for (const header of ['순서', '이름', '내부 코드', '사용 중 Deal']) {
      expect(screen.getByRole('columnheader', { name: header })).toBeInTheDocument()
    }
    const negotiation = row(/가격협상/)
    expect(negotiation.getByText('price_negotiation')).toBeInTheDocument()
    expect(negotiation.getByText('4')).toBeInTheDocument()
  })

  // 잠금 행은 "시스템 연결" 배지와 이유가 붙은 비활성 삭제 버튼을 가진다.
  // 테스트 코드: CD-051
  it('marks the system-linked 계약완료 as locked, with a disabled delete and a reason', async () => {
    // given: Status 코드 탭을 연다
    await openStatus()

    // then: 계약완료·기회발굴에 배지가 있고 계약완료의 삭제는 비활성이며 이유가 붙고 제품소개엔 배지가 없다
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
  // 이름을 표 안에서 바꾸면(저장) 새 이름이 보인다.
  // 테스트 코드: CD-053
  it('renames a code inline', async () => {
    // given: Status 코드 탭을 연다
    const { user } = await openStatus()

    // when: 가격협상의 이름을 "가격 협의"로 바꿔 저장한다
    await user.click(row(/가격협상/).getByRole('button', { name: '이름 수정' }))
    const input = screen.getByLabelText('코드 이름')
    await user.clear(input)
    await user.type(input, '가격 협의')
    await user.click(screen.getByRole('button', { name: '저장' }))

    // then: 새 이름 행이 보이고 옛 이름 행과 입력 칸은 사라진다
    expect(await screen.findByRole('row', { name: /가격 협의/ })).toBeInTheDocument()
    expect(screen.queryByRole('row', { name: /가격협상/ })).not.toBeInTheDocument()
    expect(screen.queryByLabelText('코드 이름')).not.toBeInTheDocument()
  })

  // 잠금 코드도 Enter로 이름을 바꿀 수 있고 key는 그대로다.
  // 테스트 코드: CD-053
  it('lets the locked code be renamed as well', async () => {
    // given: Status 코드 탭을 연다
    const { user } = await openStatus()

    // when: 계약완료의 이름을 "계약성사"로 바꾸고 Enter를 누른다
    await user.click(row(/계약완료/).getByRole('button', { name: '이름 수정' }))
    const input = screen.getByLabelText('코드 이름')
    await user.clear(input)
    await user.type(input, '계약성사')
    await user.keyboard('{Enter}')

    // then: "계약성사" 행이 보이고 내부 코드는 contract_completed 그대로다
    expect(await screen.findByRole('row', { name: /계약성사/ })).toBeInTheDocument()
    expect(row(/계약성사/).getByText('contract_completed')).toBeInTheDocument()
  })

  // Esc로 이름 수정을 그만두면 요청 없이 원래 이름이 남는다.
  // 테스트 코드: CD-054
  it('cancels the rename with Escape and keeps the name', async () => {
    // given: Status 코드 탭을 열고 가격협상 이름 수정을 시작해 글자를 더한다
    const { user } = await openStatus()
    const rename = vi.spyOn(gateway.codes, 'rename')
    await user.click(row(/가격협상/).getByRole('button', { name: '이름 수정' }))
    await user.type(screen.getByLabelText('코드 이름'), '추가')

    // when: Esc를 누른다
    await user.keyboard('{Escape}')

    // then: 요청 없이 입력 칸이 사라지고 "가격협상" 행이 그대로다
    expect(rename).not.toHaveBeenCalled()
    expect(screen.queryByLabelText('코드 이름')).not.toBeInTheDocument()
    expect(screen.getByRole('row', { name: /가격협상/ })).toBeInTheDocument()
  })

  // 중복 이름이면 서버 문구를 보이고 입력을 유지한다.
  // 테스트 코드: CD-055
  it('shows the server message for a duplicate name and keeps editing', async () => {
    // given: 가격협상 이름 수정을 시작한다
    const { user } = await openStatus()
    await user.click(row(/가격협상/).getByRole('button', { name: '이름 수정' }))
    const input = screen.getByLabelText('코드 이름')
    await user.clear(input)
    await user.type(input, '제품소개')

    // when: 저장한다
    await user.click(screen.getByRole('button', { name: '저장' }))

    // then: 오류 알림이 서버 문구이고 입력 칸 값은 "제품소개"다
    expect(await screen.findByRole('alert')).toHaveTextContent('같은 이름의 코드가 이미 있습니다.')
    expect(screen.getByLabelText('코드 이름')).toHaveValue('제품소개')
  })

  // 빈 이름으로 저장하면 서버 문구를 보인다.
  // 테스트 코드: CD-056
  it('shows the server message when the name is empty', async () => {
    // given: 가격협상 이름 수정을 시작해 입력을 비운다
    const { user } = await openStatus()
    await user.click(row(/가격협상/).getByRole('button', { name: '이름 수정' }))
    await user.clear(screen.getByLabelText('코드 이름'))

    // when: 저장한다
    await user.click(screen.getByRole('button', { name: '저장' }))

    // then: "이름을 입력하세요." 오류 알림이 보인다
    expect(await screen.findByRole('alert')).toHaveTextContent('이름을 입력하세요.')
  })
})

describe('Status 코드 순서 변경 (T-ADMIN-04)', () => {
  // ↑/↓로 코드를 이웃과 자리 바꾼다.
  // 테스트 코드: CD-057
  it('moves a code up and down', async () => {
    // given: Status 코드 탭을 연다
    const { user } = await openStatus()

    // when: 가격협상을 위로 이동한다
    await user.click(screen.getByRole('button', { name: '가격협상 위로 이동' }))

    // then: 가격협상이 기술평가 앞에 온다
    await waitFor(() =>
      expect(names()).toEqual(['기회발굴', '제품소개', 'POC준비', 'POC완료', '가격협상', '기술평가', '계약완료']),
    )

    // when: 가격협상을 아래로 이동한다
    await user.click(screen.getByRole('button', { name: '가격협상 아래로 이동' }))

    // then: 원래 순서로 돌아온다
    await waitFor(() =>
      expect(names()).toEqual(['기회발굴', '제품소개', 'POC준비', 'POC완료', '기술평가', '가격협상', '계약완료']),
    )
  })

  // 첫 행의 ↑와 마지막 행의 ↓는 비활성이다.
  // 테스트 코드: CD-058
  it('disables moving the first code up and the last code down', async () => {
    // given: Status 코드 탭을 연다
    await openStatus()

    // then: 첫 행의 위로 이동, 마지막 행의 아래로 이동이 비활성이다
    expect(screen.getByRole('button', { name: '기회발굴 위로 이동' })).toBeDisabled()
    expect(screen.getByRole('button', { name: '계약완료 아래로 이동' })).toBeDisabled()
  })
})

describe('Status 코드 추가·삭제 (T-ADMIN-05)', () => {
  // 코드를 추가하면 맨 끝에 사용 0으로 보이고 입력이 비워진다.
  // 테스트 코드: CD-059
  it('adds a code at the end with zero usage and clears the input', async () => {
    // given: Status 코드 탭을 연다
    const { user } = await openStatus()

    // when: "내부검토"를 추가한다
    await addCode(user, '내부검토')

    // then: 마지막 행이 "내부검토"이고 사용 0이며 입력 칸이 비어 있다
    expect(await screen.findByRole('row', { name: /내부검토/ })).toBeInTheDocument()
    expect(names().at(-1)).toBe('내부검토')
    expect(row(/내부검토/).getByText('0')).toBeInTheDocument()
    expect(screen.getByLabelText('새 코드 이름')).toHaveValue('')
  })

  // 빈 이름으로 추가하면 서버 문구를 보인다.
  // 테스트 코드: CD-060
  it('shows the server message for an empty new name', async () => {
    // given: Status 코드 탭을 연다
    const { user } = await openStatus()

    // when: 입력 없이 "추가"를 누른다
    await user.click(screen.getByRole('button', { name: '추가' }))

    // then: "이름을 입력하세요." 오류 알림이 보인다
    expect(await screen.findByRole('alert')).toHaveTextContent('이름을 입력하세요.')
  })

  // 쓰이지 않는 코드를 확인 뒤 삭제하면 표에서 사라진다.
  // 테스트 코드: CD-061
  it('deletes an unused code after confirmation', async () => {
    // given: "내부검토"를 추가했다
    const { user } = await openStatus()
    await addCode(user, '내부검토')
    await screen.findByRole('row', { name: /내부검토/ })

    // when: 그 행의 삭제를 누르고 대화상자 "코드 삭제"에서 삭제한다
    await user.click(row(/내부검토/).getByRole('button', { name: '삭제' }))
    const dialog = within(await screen.findByRole('dialog', { name: '코드 삭제' }))
    await user.click(dialog.getByRole('button', { name: '삭제' }))

    // then: "내부검토" 행이 사라진다
    await waitFor(() => expect(screen.queryByRole('row', { name: /내부검토/ })).not.toBeInTheDocument())
  })

  // 삭제 확인을 취소하면 코드가 남는다.
  // 테스트 코드: CD-062
  it('keeps the code when the delete confirmation is declined', async () => {
    // given: "내부검토"를 추가했다
    const { user } = await openStatus()
    await addCode(user, '내부검토')
    await screen.findByRole('row', { name: /내부검토/ })
    const remove = vi.spyOn(gateway.codes, 'remove')

    // when: 삭제를 누르고 대화상자에서 취소한다
    await user.click(row(/내부검토/).getByRole('button', { name: '삭제' }))
    await user.click(within(await screen.findByRole('dialog')).getByRole('button', { name: '취소' }))

    // then: 요청 없이 대화상자가 닫히고 "내부검토" 행이 남는다
    expect(remove).not.toHaveBeenCalled()
    expect(screen.queryByRole('dialog')).not.toBeInTheDocument()
    expect(screen.getByRole('row', { name: /내부검토/ })).toBeInTheDocument()
  })

  // Deal이 쓰는 Status 삭제는 거절 문구를 보이고 대화상자를 닫으며 행이 남는다.
  // 테스트 코드: CD-063
  it('refuses to delete a code that deals use and shows how many', async () => {
    // given: 가격협상을 쓰는 Deal 4건이 있다
    const { user } = await openStatus()

    // when: 가격협상을 삭제 확인한다
    await user.click(row(/가격협상/).getByRole('button', { name: '삭제' }))
    await user.click(within(await screen.findByRole('dialog')).getByRole('button', { name: '삭제' }))

    // then: "(Deal 4건)" 오류 알림이 보이고 대화상자가 닫히며 행이 남는다
    expect(await screen.findByRole('alert')).toHaveTextContent('사용 중인 코드는 삭제할 수 없습니다. (Deal 4건)')
    expect(screen.queryByRole('dialog')).not.toBeInTheDocument()
    expect(screen.getByRole('row', { name: /가격협상/ })).toBeInTheDocument()
  })
})

describe('오류 배너 (CD-R23)', () => {
  // 새 작업을 시작하면 이전 오류 배너가 사라진다.
  // 테스트 코드: CD-066
  it('clears the previous error when a new action starts', async () => {
    // given: 빈 이름으로 추가해 오류 알림이 보인다
    const { user } = await openStatus()
    await user.click(screen.getByRole('button', { name: '추가' }))
    expect(await screen.findByRole('alert')).toHaveTextContent('이름을 입력하세요.')

    // when: 다른 행의 "이름 수정"을 누른다
    await user.click(row(/제품소개/).getByRole('button', { name: '이름 수정' }))

    // then: 오류 알림이 사라진다
    expect(screen.queryByRole('alert')).not.toBeInTheDocument()
  })

  // 이동을 시작해도 이전 오류가 지워지고 이동이 성공하면 다시 생기지 않는다.
  // 테스트 코드: CD-066
  it('clears the previous error when a move starts and a successful move leaves none', async () => {
    // given: 빈 이름으로 추가해 오류 알림이 보인다
    const { user } = await openStatus()
    await user.click(screen.getByRole('button', { name: '추가' }))
    expect(await screen.findByRole('alert')).toBeInTheDocument()

    // when: 제품소개를 아래로 이동한다
    await user.click(screen.getByRole('button', { name: '제품소개 아래로 이동' }))

    // then: 오류 알림이 사라지고 이동은 반영된다
    await waitFor(() => expect(names().slice(0, 3)).toEqual(['기회발굴', 'POC준비', '제품소개']))
    expect(screen.queryByRole('alert')).not.toBeInTheDocument()
  })
})

describe('Forecast 코드 (T-ADMIN-03~05)', () => {
  // Forecast 표는 6개를 확률 참고·구분(Open/Won/Lost)과 함께 보인다.
  // 테스트 코드: CD-052
  it('lists the six forecasts with probability hints and the Open/Won/Lost kind', async () => {
    // given: Forecast 코드 탭을 연다
    await openForecast()

    // then: 이름 순서, 확률 참고·구분 머리글, Pipeline의 0–50과 Open, Lost 배지가 보인다
    expect(names()).toEqual(['Pipeline', 'Best', 'Most Likely', 'Commit', 'Won', 'Lost'])
    expect(screen.getByRole('columnheader', { name: '확률 참고' })).toBeInTheDocument()
    expect(screen.getByRole('columnheader', { name: '구분' })).toBeInTheDocument()
    expect(row(/Pipeline/).getByText('0–50')).toBeInTheDocument()
    expect(row(/Pipeline/).getByText('Open')).toBeInTheDocument()
    expect(row(/Lost/).getByText('Lost', { selector: '.badge' })).toBeInTheDocument()
  })

  // Won은 삭제할 수 없지만 이름은 바꿀 수 있다.
  // 테스트 코드: CD-065
  it('locks Won against deletion but allows renaming it', async () => {
    // given: Forecast 코드 탭을 연다
    const { user } = await openForecast()

    // then: Won 행의 삭제가 비활성이고 "시스템 연결"이 있다
    expect(row(/^.*Won/).getByRole('button', { name: '삭제' })).toBeDisabled()
    expect(row(/Won/).getByText('시스템 연결')).toBeInTheDocument()

    // when: Won의 이름을 "수주"로 바꾼다
    await user.click(row(/Won/).getByRole('button', { name: '이름 수정' }))
    const input = screen.getByLabelText('코드 이름')
    await user.clear(input)
    await user.type(input, '수주')
    await user.click(screen.getByRole('button', { name: '저장' }))

    // then: "수주" 행이 보인다
    expect(await screen.findByRole('row', { name: /수주/ })).toBeInTheDocument()
  })

  // Deal이 쓰는 Forecast 삭제는 거절 문구를 보이고 대화상자를 닫으며 행이 남는다.
  // 테스트 코드: CD-063
  it('refuses to delete a forecast that deals use', async () => {
    // given: Commit을 쓰는 Deal이 있는 Forecast 코드 탭
    const { user } = await openForecast()

    // when: Commit을 삭제 확인한다
    await user.click(row(/Commit/).getByRole('button', { name: '삭제' }))
    await user.click(within(await screen.findByRole('dialog')).getByRole('button', { name: '삭제' }))

    // then: Deal 건수가 든 거절 문구가 보이고 대화상자가 닫히며 행이 남는다
    expect(await screen.findByRole('alert')).toHaveTextContent(/사용 중인 코드는 삭제할 수 없습니다\. \(Deal \d+건\)/)
    expect(screen.queryByRole('dialog')).not.toBeInTheDocument()
    expect(screen.getByRole('row', { name: /Commit/ })).toBeInTheDocument()
  })

  // Forecast 추가·순서 변경은 Status와 따로 동작한다.
  // 테스트 코드: CD-064
  it('adds and reorders forecast codes independently from statuses', async () => {
    // given: Forecast 코드 탭을 연다
    const { user } = await openForecast()

    // when: "Upside"를 추가하고 위로 이동한다
    await addCode(user, 'Upside')
    expect(await screen.findByRole('row', { name: /Upside/ })).toBeInTheDocument()
    await user.click(screen.getByRole('button', { name: 'Upside 위로 이동' }))

    // then: Upside가 Forecast 표 끝에서 두 번째다
    await waitFor(() => expect(names().indexOf('Upside')).toBe(names().length - 2))
  })
})
