import { fireEvent, screen, within } from '@testing-library/react'
import { describe, expect, it } from 'vitest'
import { addColumn, chipButton, chipItems, chipList, chipTexts, duplicateDialog, openDesigner, settingsOf, setupReportClock } from '../../../test/reportScreen'

setupReportClock()

/** 끌기 이벤트가 공유하는 최소 DataTransfer. */
function dataTransfer() {
  const data: Record<string, string> = {}
  return {
    setData: (type: string, value: string) => {
      data[type] = value
    },
    getData: (type: string) => data[type] ?? '',
    effectAllowed: 'all',
    dropEffect: 'move',
    types: [] as string[],
  }
}

describe('컬럼 칩', () => {
  // 테스트 코드: RQ-071
  it('필드를 누르면 칩이 생기고 같은 필드를 두 번 넣을 수 있으며 칩을 뺄 수 있다', async () => {
    // given: 빈 설계
    const { user } = await openDesigner()

    // when: Deal code와 금액을 넣고 금액을 한 번 더 넣는다
    await addColumn(user, 'Deal code')
    await addColumn(user, '금액')
    await addColumn(user, '금액', { again: true })

    // then: 칩이 3개이고 금액 칩이 둘이다
    expect(chipItems()).toHaveLength(3)
    expect(chipTexts()[1]).toContain('금액')
    expect(chipTexts()[2]).toContain('금액')
    expect(screen.getAllByRole('button', { name: '금액 빼기' })).toHaveLength(2)

    // when: 첫째 금액 칩을 뺀다
    await user.click(screen.getAllByRole('button', { name: '금액 빼기' })[0] as HTMLElement)

    // then: 칩이 2개로 줄고 순서가 Deal code, 금액이다
    expect(chipItems()).toHaveLength(2)
    expect(chipTexts()[0]).toContain('Deal code')
    expect(chipTexts()[1]).toContain('금액')
  })

  // 테스트 코드: RQ-074
  it('방금 넣은 칩이 선택되고 칩을 누르면 선택이 옮겨진다', async () => {
    // given: 빈 설계
    const { user } = await openDesigner()
    // when: Deal code와 Deal 이름 컬럼을 넣는다
    await addColumn(user, 'Deal code')
    await addColumn(user, 'Deal 이름')

    // then: 마지막 칩이 선택되고 그 컬럼 설정이 보인다
    expect(chipButton(1)).toHaveAttribute('aria-pressed', 'true')
    expect(chipButton(0)).toHaveAttribute('aria-pressed', 'false')
    expect(settingsOf('Deal 이름')).toBeVisible()

    // when: 첫째 칩을 누른다
    await user.click(chipButton(0))

    // then: 첫째 칩이 선택되고 Deal code 설정이 보인다
    expect(chipButton(0)).toHaveAttribute('aria-pressed', 'true')
    expect(chipButton(1)).toHaveAttribute('aria-pressed', 'false')
    expect(settingsOf('Deal code')).toBeVisible()
  })

  // 테스트 코드: RQ-071
  it('컬럼이 30개이면 더 넣을 수 없고 하나 빼면 다시 넣을 수 있다', async () => {
    // given: 빈 설계
    const { user } = await openDesigner()
    // when: 컬럼을 30개 넣는다
    for (let i = 0; i < 30; i += 1) await addColumn(user, 'Deal code', { again: i > 0 })

    // then: 칩이 30개이고 최대 안내가 보이며 추가 버튼이 꺼진다
    expect(chipItems()).toHaveLength(30)
    expect(screen.getByText('컬럼은 최대 30개입니다')).toBeVisible()
    expect(screen.getByRole('button', { name: 'Deal 이름 컬럼에 추가' })).toBeDisabled()

    // when: 컬럼 하나를 뺀다
    await user.click(screen.getAllByRole('button', { name: 'Deal code 빼기' })[0] as HTMLElement)

    // then: 안내가 사라지고 추가 버튼이 켜진다
    expect(screen.queryByText('컬럼은 최대 30개입니다')).not.toBeInTheDocument()
    expect(screen.getByRole('button', { name: 'Deal 이름 컬럼에 추가' })).toBeEnabled()
  }, 30_000)
})

describe('같은 필드 추가 확인', () => {
  const MESSAGE = "'금액'은(는) 이미 컬럼에 있습니다. 한 번 더 추가할까요?"

  // 테스트 코드: RQ-071
  it('컬럼에 없는 필드는 묻지 않고 넣는다', async () => {
    // given: 빈 설계
    const { user } = await openDesigner()

    // when: 금액을 넣는다
    await addColumn(user, '금액')

    // then: 칩 1개이고 확인 창이 없다
    expect(chipItems()).toHaveLength(1)
    expect(screen.queryByRole('dialog')).not.toBeInTheDocument()
  })

  // 테스트 코드: RQ-071
  it('이미 컬럼인 필드를 넣으면 먼저 묻고 안내 문구를 보인다', async () => {
    // given: 금액 컬럼이 이미 있는 설계
    const { user } = await openDesigner()
    await addColumn(user, '금액')

    // when: 금액을 한 번 더 넣는다
    await addColumn(user, '금액')

    // then: 확인 창에 안내 문구와 추가·취소 버튼이 보이고 칩은 그대로 1개다
    const dialog = duplicateDialog()
    expect(within(dialog).getByText(MESSAGE)).toBeVisible()
    expect(within(dialog).getByRole('button', { name: '추가' })).toBeVisible()
    expect(within(dialog).getByRole('button', { name: '취소' })).toBeVisible()
    expect(chipItems()).toHaveLength(1)
  })

  // 테스트 코드: RQ-071
  it('확인 창에서 추가를 누르면 같은 필드 칩이 하나 더 생기고 창이 닫힌다', async () => {
    // given: 금액 컬럼이 이미 있고 중복 확인 창이 떠 있다
    const { user } = await openDesigner()
    await addColumn(user, '금액')
    await addColumn(user, '금액')

    // when: 추가를 누른다
    await user.click(within(duplicateDialog()).getByRole('button', { name: '추가' }))

    // then: 칩이 2개이고 창이 닫힌다
    expect(chipItems()).toHaveLength(2)
    expect(screen.queryByRole('dialog')).not.toBeInTheDocument()
  })

  // 테스트 코드: RQ-071
  it('확인 창에서 취소하면 컬럼 수가 그대로이고 창이 닫힌다', async () => {
    // given: 금액 컬럼이 이미 있고 중복 확인 창이 떠 있다
    const { user } = await openDesigner()
    await addColumn(user, '금액')
    await addColumn(user, '금액')

    // when: 취소를 누른다
    await user.click(within(duplicateDialog()).getByRole('button', { name: '취소' }))

    // then: 칩이 1개이고 창이 닫힌다
    expect(chipItems()).toHaveLength(1)
    expect(screen.queryByRole('dialog')).not.toBeInTheDocument()
  })

  // 테스트 코드: RQ-071
  it('확인 창에서 Esc를 누르면 컬럼 수가 그대로이고 창이 닫힌다', async () => {
    // given: 금액 컬럼이 이미 있고 중복 확인 창이 떠 있다
    const { user } = await openDesigner()
    await addColumn(user, '금액')
    await addColumn(user, '금액')

    // when: Esc를 누른다
    await user.keyboard('{Escape}')

    // then: 칩이 1개이고 창이 닫힌다
    expect(chipItems()).toHaveLength(1)
    expect(screen.queryByRole('dialog')).not.toBeInTheDocument()
  })

  // 테스트 코드: RQ-071
  it('이미 컬럼인 필드의 조건을 추가할 때는 묻지 않는다', async () => {
    // given: 금액 컬럼이 있는 설계
    const { user } = await openDesigner()
    await addColumn(user, '금액')

    // when: 금액 조건을 추가한다
    await user.click(screen.getByRole('button', { name: '금액 조건 추가' }))

    // then: 확인 창이 뜨지 않는다
    expect(screen.queryByRole('dialog')).not.toBeInTheDocument()
  })
})

describe('컬럼 순서', () => {
  async function threeColumns() {
    const rendered = await openDesigner()
    await addColumn(rendered.user, 'Deal code')
    await addColumn(rendered.user, 'Deal 이름')
    await addColumn(rendered.user, 'Product')
    return rendered
  }

  const order = () => chipTexts().map((t) => (/Deal code|Deal 이름|Product/.exec(t) ?? [''])[0])

  // 테스트 코드: RQ-072
  it('칩은 끌 수 있게 표시된다', async () => {
    // when: 컬럼 3개가 있는 설계를 만든다
    await threeColumns()

    // then: 모든 칩이 draggable이다
    for (const item of chipItems()) expect(item).toHaveAttribute('draggable', 'true')
  })

  // 테스트 코드: RQ-072
  it('칩을 끌어서 놓으면 순서가 바뀐다', async () => {
    // given: Deal code, Deal 이름, Product 컬럼
    await threeColumns()
    const items = chipItems()
    const transfer = dataTransfer()

    // when: 첫째 칩을 셋째 칩 위로 끌어다 놓는다
    fireEvent.dragStart(items[0] as HTMLElement, { dataTransfer: transfer })
    fireEvent.dragOver(items[2] as HTMLElement, { dataTransfer: transfer })
    fireEvent.drop(items[2] as HTMLElement, { dataTransfer: transfer })
    fireEvent.dragEnd(items[0] as HTMLElement, { dataTransfer: transfer })

    // then: 순서가 Deal 이름, Product, Deal code다
    expect(order()).toEqual(['Deal 이름', 'Product', 'Deal code'])
  })

  // 테스트 코드: RQ-072
  it('Alt+화살표로 칩 순서를 바꾸고 포커스를 유지하며 옮김을 알린다', async () => {
    // given: 컬럼 3개가 있고 첫째 칩에 포커스가 있다
    const { user } = await threeColumns()
    chipButton(0).focus()

    // when: Alt+→를 누른다
    await user.keyboard('{Alt>}{ArrowRight}{/Alt}')

    // then: 둘째로 옮겨지고 포커스가 따라가며 안내가 나온다
    expect(order()).toEqual(['Deal 이름', 'Deal code', 'Product'])
    expect(chipButton(1)).toHaveFocus()
    expect(screen.getByText('‘Deal code’를 2번째로 옮겼습니다')).toBeInTheDocument()

    // when: Alt+→를 한 번 더 누른다
    await user.keyboard('{Alt>}{ArrowRight}{/Alt}')

    // then: 셋째로 옮겨지고 안내가 나온다
    expect(order()).toEqual(['Deal 이름', 'Product', 'Deal code'])
    expect(chipButton(2)).toHaveFocus()
    expect(screen.getByText('‘Deal code’를 3번째로 옮겼습니다')).toBeInTheDocument()

    // when: Alt+←를 누른다
    await user.keyboard('{Alt>}{ArrowLeft}{/Alt}')

    // then: 다시 둘째로 옮겨진다
    expect(order()).toEqual(['Deal 이름', 'Deal code', 'Product'])
    expect(screen.getByText('‘Deal code’를 2번째로 옮겼습니다')).toBeInTheDocument()
  })

  // 테스트 코드: RQ-072
  it('끝을 넘어가는 Alt+화살표는 순서를 바꾸지 않는다', async () => {
    // given: 컬럼 3개가 있고 마지막 칩에 포커스가 있다
    const { user } = await threeColumns()
    chipButton(2).focus()

    // when: Alt+→를 누른다
    await user.keyboard('{Alt>}{ArrowRight}{/Alt}')

    // then: 순서가 그대로다
    expect(order()).toEqual(['Deal code', 'Deal 이름', 'Product'])
  })

  // 테스트 코드: RQ-072
  it('칩을 못 옮긴 Alt+화살표 뒤에도 다른 입력칸의 포커스와 입력이 유지된다', async () => {
    // given: 컬럼 3개와 값 입력칸이 있는 조건 1개
    const { user } = await threeColumns()
    await user.click(screen.getByRole('button', { name: '+ 조건 추가' }))
    const input = screen.getByRole('textbox', { name: '조건 1 값' })

    // when: 처음·끝 칩에서 바깥쪽 Alt+화살표를 누르고 입력칸에 글자를 입력한다
    chipButton(0).focus()
    await user.keyboard('{Alt>}{ArrowLeft}{/Alt}')
    chipButton(2).focus()
    await user.keyboard('{Alt>}{ArrowRight}{/Alt}')
    input.focus()
    await user.keyboard('은행권')

    // then: 입력칸이 포커스와 입력값을 유지하고 순서는 그대로다
    expect(input).toHaveFocus()
    expect(input).toHaveValue('은행권')
    expect(order()).toEqual(['Deal code', 'Deal 이름', 'Product'])
  })

  // 테스트 코드: RQ-072
  it('Alt 없는 화살표로는 칩을 옮기지 않는다', async () => {
    // given: 컬럼 3개가 있고 첫째 칩에 포커스가 있다
    const { user } = await threeColumns()
    chipButton(0).focus()

    // when: 화살표만 누른다
    await user.keyboard('{ArrowRight}')

    // then: 순서가 그대로다
    expect(order()).toEqual(['Deal code', 'Deal 이름', 'Product'])
  })

  // 테스트 코드: RQ-072
  it('컬럼 설정에 앞으로·뒤로 버튼이 없다', async () => {
    // given: 컬럼 3개가 있는 설계
    const { user } = await threeColumns()
    // when: 둘째 칩을 선택해 설정을 연다
    await user.click(chipButton(1))
    const panel = settingsOf('Deal 이름')

    // then: 앞으로·뒤로 버튼이 없고 칩 목록은 보인다
    expect(within(panel).queryByRole('button', { name: '앞으로' })).toBeNull()
    expect(within(panel).queryByRole('button', { name: '뒤로' })).toBeNull()
    expect(chipList()).toBeVisible()
  })
})

describe('컬럼 설정 한 줄 행', () => {
  // 테스트 코드: RQ-074
  it('컬럼 설정 한 줄에 이름이 첫 칸이고 모든 조절이 안에 있다', async () => {
    // given: 빈 설계
    const { user } = await openDesigner()
    // when: Deal code 컬럼을 넣는다
    await addColumn(user, 'Deal code')
    // then: 설정 패널에 이름, 표시 이름, 앞 N자, 그룹핑, 집계가 모두 보인다
    const panel = settingsOf('Deal code')

    expect(within(panel).getByText('Deal code')).toBeVisible()
    expect(within(panel).getByLabelText('표시 이름')).toBeVisible()
    expect(within(panel).getByLabelText('앞 N자만 보기')).toBeVisible()
    expect(within(panel).getByLabelText('앞 N자의 N')).toBeVisible()
    expect(within(panel).getByLabelText('그룹핑')).toBeVisible()
    expect(within(panel).getByLabelText('집계')).toBeVisible()
  })

  // 테스트 코드: RQ-074
  it('글·숫자·선택 조절은 보이는 라벨 대신 aria-label로 이름을 가진다', async () => {
    // given: Deal code 컬럼
    const { user } = await openDesigner()
    // when: 컬럼 설정을 연다
    await addColumn(user, 'Deal code')
    const panel = settingsOf('Deal code')

    // then: 표시 이름·앞 N자의 N·집계가 aria-label을 가진다
    for (const name of ['표시 이름', '앞 N자의 N', '집계']) {
      expect(within(panel).getByLabelText(name)).toHaveAttribute('aria-label', name)
    }
  })

  // 테스트 코드: RQ-074
  it('표시 이름을 바꾸면 첫 칸에 그 이름이 보인다', async () => {
    // given: Deal code 컬럼
    const { user } = await openDesigner()
    await addColumn(user, 'Deal code')

    // when: 표시 이름을 코드값으로 입력한다
    await user.type(within(settingsOf('Deal code')).getByLabelText('표시 이름'), '코드값')

    // then: 패널 이름과 첫 칸이 코드값이고 원래 이름은 없다
    const panel = screen.getByRole('region', { name: '컬럼 설정: 코드값' })
    expect(within(panel).getByText('코드값')).toBeVisible()
    expect(within(panel).queryByText('Deal code')).toBeNull()
  })
})
