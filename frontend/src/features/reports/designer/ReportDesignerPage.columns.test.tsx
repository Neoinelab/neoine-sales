import { fireEvent, screen, within } from '@testing-library/react'
import { describe, expect, it } from 'vitest'
import { addColumn, chipButton, chipItems, chipList, chipTexts, openDesigner, settingsOf, setupReportClock } from '../../../test/reportScreen'

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

describe('컬럼 칩 (AC4)', () => {
  it('adds chips, allows the same field twice, removes a chip', async () => {
    const { user } = await openDesigner()

    await addColumn(user, 'Deal code')
    await addColumn(user, '금액(원)')
    await addColumn(user, '금액(원)')

    expect(chipItems()).toHaveLength(3)
    expect(chipTexts()[1]).toContain('금액(원)')
    expect(chipTexts()[2]).toContain('금액(원)')
    expect(screen.getAllByRole('button', { name: '금액(원) 빼기' })).toHaveLength(2)

    await user.click(screen.getAllByRole('button', { name: '금액(원) 빼기' })[0] as HTMLElement)

    expect(chipItems()).toHaveLength(2)
    expect(chipTexts()[0]).toContain('Deal code')
    expect(chipTexts()[1]).toContain('금액(원)')
  })

  it('selects the chip it just added and moves the selection with a click', async () => {
    const { user } = await openDesigner()
    await addColumn(user, 'Deal code')
    await addColumn(user, 'Deal 이름')

    expect(chipButton(1)).toHaveAttribute('aria-pressed', 'true')
    expect(chipButton(0)).toHaveAttribute('aria-pressed', 'false')
    expect(settingsOf('Deal 이름')).toBeVisible()

    await user.click(chipButton(0))

    expect(chipButton(0)).toHaveAttribute('aria-pressed', 'true')
    expect(chipButton(1)).toHaveAttribute('aria-pressed', 'false')
    expect(settingsOf('Deal code')).toBeVisible()
  })

  it('disables adding at the column limit', async () => {
    const { user } = await openDesigner()
    for (let i = 0; i < 30; i += 1) await addColumn(user, 'Deal code')

    expect(chipItems()).toHaveLength(30)
    expect(screen.getByText('컬럼은 최대 30개입니다')).toBeVisible()
    expect(screen.getByRole('button', { name: 'Deal 이름 컬럼에 추가' })).toBeDisabled()

    await user.click(screen.getAllByRole('button', { name: 'Deal code 빼기' })[0] as HTMLElement)

    expect(screen.queryByText('컬럼은 최대 30개입니다')).not.toBeInTheDocument()
    expect(screen.getByRole('button', { name: 'Deal 이름 컬럼에 추가' })).toBeEnabled()
  }, 30_000)
})

describe('컬럼 순서 (AC5)', () => {
  async function threeColumns() {
    const rendered = await openDesigner()
    await addColumn(rendered.user, 'Deal code')
    await addColumn(rendered.user, 'Deal 이름')
    await addColumn(rendered.user, 'Solution')
    return rendered
  }

  const order = () => chipTexts().map((t) => (/Deal code|Deal 이름|Solution/.exec(t) ?? [''])[0])

  it('marks the chips as draggable', async () => {
    await threeColumns()

    for (const item of chipItems()) expect(item).toHaveAttribute('draggable', 'true')
  })

  it('reorders chips by drag and drop', async () => {
    await threeColumns()
    const items = chipItems()
    const transfer = dataTransfer()

    fireEvent.dragStart(items[0] as HTMLElement, { dataTransfer: transfer })
    fireEvent.dragOver(items[2] as HTMLElement, { dataTransfer: transfer })
    fireEvent.drop(items[2] as HTMLElement, { dataTransfer: transfer })
    fireEvent.dragEnd(items[0] as HTMLElement, { dataTransfer: transfer })

    expect(order()).toEqual(['Deal 이름', 'Solution', 'Deal code'])
  })

  it('reorders chips by Alt+arrow keys, keeps the focus and announces the move', async () => {
    const { user } = await threeColumns()
    chipButton(0).focus()

    await user.keyboard('{Alt>}{ArrowRight}{/Alt}')

    expect(order()).toEqual(['Deal 이름', 'Deal code', 'Solution'])
    expect(chipButton(1)).toHaveFocus()
    expect(screen.getByText('‘Deal code’를 2번째로 옮겼습니다')).toBeInTheDocument()

    await user.keyboard('{Alt>}{ArrowRight}{/Alt}')

    expect(order()).toEqual(['Deal 이름', 'Solution', 'Deal code'])
    expect(chipButton(2)).toHaveFocus()
    expect(screen.getByText('‘Deal code’를 3번째로 옮겼습니다')).toBeInTheDocument()

    await user.keyboard('{Alt>}{ArrowLeft}{/Alt}')

    expect(order()).toEqual(['Deal 이름', 'Deal code', 'Solution'])
    expect(screen.getByText('‘Deal code’를 2번째로 옮겼습니다')).toBeInTheDocument()
  })

  it('keeps the order when Alt+arrow points past the end', async () => {
    const { user } = await threeColumns()
    chipButton(2).focus()

    await user.keyboard('{Alt>}{ArrowRight}{/Alt}')

    expect(order()).toEqual(['Deal code', 'Deal 이름', 'Solution'])
  })

  it('keeps the focus on another input after Alt+arrow that could not move a chip', async () => {
    const { user } = await threeColumns()
    await user.click(screen.getByRole('button', { name: '+ 조건 추가' }))
    const input = screen.getByRole('textbox', { name: '조건 1 값' })

    chipButton(0).focus()
    await user.keyboard('{Alt>}{ArrowLeft}{/Alt}')
    chipButton(2).focus()
    await user.keyboard('{Alt>}{ArrowRight}{/Alt}')
    input.focus()
    await user.keyboard('은행권')

    expect(input).toHaveFocus()
    expect(input).toHaveValue('은행권')
    expect(order()).toEqual(['Deal code', 'Deal 이름', 'Solution'])
  })

  it('does not move a chip with plain arrow keys', async () => {
    const { user } = await threeColumns()
    chipButton(0).focus()

    await user.keyboard('{ArrowRight}')

    expect(order()).toEqual(['Deal code', 'Deal 이름', 'Solution'])
  })

  it('has no move buttons in the setting panel', async () => {
    const { user } = await threeColumns()
    await user.click(chipButton(1))
    const panel = settingsOf('Deal 이름')

    expect(within(panel).queryByRole('button', { name: '앞으로' })).toBeNull()
    expect(within(panel).queryByRole('button', { name: '뒤로' })).toBeNull()
    expect(chipList()).toBeVisible()
  })
})

describe('컬럼 설정 한 줄 행', () => {
  it('shows the column name as the first cell and every control inside the panel', async () => {
    const { user } = await openDesigner()
    await addColumn(user, 'Deal code')
    const panel = settingsOf('Deal code')

    expect(within(panel).getByText('Deal code')).toBeVisible()
    expect(within(panel).getByLabelText('표시 이름')).toBeVisible()
    expect(within(panel).getByLabelText('앞 N자만 보기')).toBeVisible()
    expect(within(panel).getByLabelText('앞 N자의 N')).toBeVisible()
    expect(within(panel).getByLabelText('그룹핑')).toBeVisible()
    expect(within(panel).getByLabelText('집계')).toBeVisible()
  })

  it('names text, number and select controls with aria-label instead of visible labels', async () => {
    const { user } = await openDesigner()
    await addColumn(user, 'Deal code')
    const panel = settingsOf('Deal code')

    for (const name of ['표시 이름', '앞 N자의 N', '집계']) {
      expect(within(panel).getByLabelText(name)).toHaveAttribute('aria-label', name)
    }
  })

  it('shows the display name in the first cell when it is changed', async () => {
    const { user } = await openDesigner()
    await addColumn(user, 'Deal code')

    await user.type(within(settingsOf('Deal code')).getByLabelText('표시 이름'), '코드값')

    const panel = screen.getByRole('region', { name: '컬럼 설정: 코드값' })
    expect(within(panel).getByText('코드값')).toBeVisible()
    expect(within(panel).queryByText('Deal code')).toBeNull()
  })
})
