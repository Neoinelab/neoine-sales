// 저장 뒤 이동하는 편집 화면은 React.lazy 청크이므로 미리 읽어 둔다.
import './ReportEditPage'
import { screen, waitFor, within } from '@testing-library/react'
import { describe, expect, it } from 'vitest'
import { addCountedColumn, openDesigner, openEditor, openEditorFromView, runQuery, saveButton, saveDialog, setupReportClock, typeName, UNSAVED_MARK } from '../../../test/reportScreen'
import { MINE_PUBLIC, SAVED_SAMPLES } from '../../../test/savedReports'

setupReportClock()

const menuLink = (name: string): HTMLElement => within(screen.getByRole('navigation', { name: '주 메뉴' })).getByRole('link', { name })
const LEAVE_TITLE = '저장하지 않은 변경이 있습니다'
const LEAVE_MESSAGE = '저장하지 않은 변경이 사라집니다. 이 화면을 떠날까요?'

function unloadIsBlocked(): boolean {
  const event = new Event('beforeunload', { cancelable: true })
  window.dispatchEvent(event)
  return event.defaultPrevented
}

/** 저장 대화상자를 열어 그대로 저장한다(이름은 바꾸지 않는다). */
async function overwrite(user: Awaited<ReturnType<typeof openEditor>>['user']): Promise<void> {
  await runQuery(user)
  await waitFor(() => expect(saveButton()).toBeEnabled())
  await user.click(saveButton())
  await user.click(within(await saveDialog()).getByRole('button', { name: '저장' }))
  await waitFor(() => expect(screen.queryByRole('dialog')).not.toBeInTheDocument())
}

describe('편집 화면에서 떠날 때 확인', () => {
  // 테스트 코드: RS-081
  it('편집 화면에서 저장 안 됨이면 떠날 때 확인하고 머물기를 누르면 남는다', async () => {
    // given: 컬럼을 넣어 저장 안 됨인 편집 화면
    const { user, location } = await openEditor(MINE_PUBLIC.id)
    await addCountedColumn(user, 'Deal code')

    // when: 상단 메뉴 링크를 누른다
    await user.click(menuLink('Deals'))

    // then: 확인 창과 안내 문구가 뜬다
    const dialog = await screen.findByRole('dialog', { name: LEAVE_TITLE })
    expect(dialog).toHaveTextContent(LEAVE_MESSAGE)
    // when: 머물기를 누른다
    await user.click(within(dialog).getByRole('button', { name: '머물기' }))

    // then: 창이 닫히고 주소와 저장 안 됨이 그대로다
    expect(screen.queryByRole('dialog')).not.toBeInTheDocument()
    expect(location()).toBe('/reports/11/edit')
    expect(screen.getByText(UNSAVED_MARK)).toBeVisible()
  })

  // 테스트 코드: RS-081
  it('떠나기를 누르면 이동한다', async () => {
    // given: 저장 안 됨이고 확인 창이 뜬 편집 화면
    const { user, location } = await openEditor(MINE_PUBLIC.id)
    await addCountedColumn(user, 'Deal code')
    // when: 링크를 누르고
    await user.click(menuLink('Deals'))

    // when: 떠나기를 누른다
    await user.click(within(await screen.findByRole('dialog', { name: LEAVE_TITLE })).getByRole('button', { name: '떠나기' }))

    // then: Deals로 이동한다
    await waitFor(() => expect(location()).toMatch(/^\/deals/))
  })

  // 테스트 코드: RS-081
  it('새 리포트 화면도 같은 문구로 확인한다', async () => {
    // given: 컬럼을 넣은 새 리포트 화면
    const { user } = await openDesigner()
    await addCountedColumn(user, 'Deal code')

    // when: 상단 메뉴 링크를 누른다
    await user.click(menuLink('Reports'))

    // then: 같은 확인 창이 뜬다
    expect(await screen.findByRole('dialog', { name: LEAVE_TITLE })).toHaveTextContent(LEAVE_MESSAGE)
  })

  // 테스트 코드: RS-081
  it('변경이 없으면 묻지 않고 이동한다', async () => {
    // given: 변경이 없는 편집 화면
    const { user, location } = await openEditor(MINE_PUBLIC.id)

    // when: 링크를 누른다
    await user.click(menuLink('Deals'))

    // then: 묻지 않고 이동한다
    await waitFor(() => expect(location()).toMatch(/^\/deals/))
    expect(screen.queryByRole('dialog')).not.toBeInTheDocument()
  })

  // 테스트 코드: RS-081
  it('변경을 원래대로 돌린 뒤에는 묻지 않고 이동한다', async () => {
    // given: 컬럼을 넣었다 뺀 편집 화면
    const { user, location } = await openEditor(MINE_PUBLIC.id)
    await addCountedColumn(user, 'Deal code')
    await user.click(screen.getByRole('button', { name: 'Deal code 빼기' }))

    // when: 링크를 누른다
    await user.click(menuLink('Deals'))

    // then: 묻지 않고 이동한다
    await waitFor(() => expect(location()).toMatch(/^\/deals/))
    expect(screen.queryByRole('dialog')).not.toBeInTheDocument()
  })

  // 테스트 코드: RS-081
  it('새로고침·탭 닫기는 저장 안 됨일 때만 막는다', async () => {
    // given: 변경 없는 편집 화면
    const { user } = await openEditor(MINE_PUBLIC.id)
    expect(unloadIsBlocked()).toBe(false)

    // when: 컬럼을 넣는다
    await addCountedColumn(user, 'Deal code')
    // then: beforeunload가 막힌다
    expect(unloadIsBlocked()).toBe(true)

    // when: 컬럼을 다시 뺀다
    await user.click(screen.getByRole('button', { name: 'Deal code 빼기' }))
    // then: beforeunload가 막지 않는다
    expect(unloadIsBlocked()).toBe(false)
  })

  // 테스트 코드: RS-081
  it('덮어쓴 직후에는 묻지 않는다', async () => {
    // given: 컬럼을 넣어 덮어쓴 편집 화면
    const { user, location } = await openEditor(MINE_PUBLIC.id)
    await addCountedColumn(user, 'Deal code')
    await overwrite(user)
    expect(unloadIsBlocked()).toBe(false)

    // when: 링크를 누른다
    await user.click(menuLink('Deals'))

    // then: 묻지 않고 이동한다
    await waitFor(() => expect(location()).toMatch(/^\/deals/))
    expect(screen.queryByRole('dialog')).not.toBeInTheDocument()
  })

  // 테스트 코드: RS-081
  it('되돌린 직후에는 묻지 않는다', async () => {
    // given: 변경을 되돌리기로 되돌린 편집 화면
    const { user, location } = await openEditor(MINE_PUBLIC.id)
    await addCountedColumn(user, 'Deal code')
    await user.click(screen.getByRole('button', { name: '되돌리기' }))
    await user.click(within(await screen.findByRole('dialog', { name: '저장된 설계로 되돌릴까요?' })).getByRole('button', { name: '되돌리기' }))
    expect(unloadIsBlocked()).toBe(false)

    // when: 링크를 누른다
    await user.click(menuLink('Deals'))

    // then: 묻지 않고 이동한다
    await waitFor(() => expect(location()).toMatch(/^\/deals/))
    expect(screen.queryByRole('dialog')).not.toBeInTheDocument()
  })

  // 테스트 코드: RS-081
  it('새 리포트를 처음 저장한 직후에는 묻지 않는다', async () => {
    // given: 새 리포트를 저장해 편집 화면으로 넘어온 상태
    const { user, location } = await openDesigner({ savedReports: SAVED_SAMPLES })
    await addCountedColumn(user, 'Deal code')
    await runQuery(user)
    await waitFor(() => expect(saveButton()).toBeEnabled())
    await user.click(saveButton())
    const dialog = await saveDialog()
    await typeName(user, dialog, '떠나기 시험')
    await user.click(within(dialog).getByRole('button', { name: '저장' }))
    await waitFor(() => expect(location()).toBe('/reports/16/edit'))
    await screen.findByRole('heading', { level: 1, name: '떠나기 시험' })
    expect(unloadIsBlocked()).toBe(false)

    // when: 링크를 누른다
    await user.click(menuLink('Deals'))

    // then: 묻지 않고 이동한다
    await waitFor(() => expect(location()).toMatch(/^\/deals/))
    expect(screen.queryByRole('dialog')).not.toBeInTheDocument()
  })
})

describe('편집 화면에서 브라우저 뒤로 가기', () => {
  // 테스트 코드: RS-107
  it('저장 안 됨이면 뒤로 가기에서 묻고 머물기면 남고 떠나기면 보기 화면으로 간다', async () => {
    // given: 보기 화면에서 편집으로 들어와 설계를 바꿔 저장 안 됨이다
    const { user, location, goTo } = await openEditorFromView(MINE_PUBLIC.id)
    await addCountedColumn(user, 'Deal code')

    // when: 뒤로 가기를 하고 머물기를 누른다
    goTo(-1)
    const dialog = await screen.findByRole('dialog', { name: LEAVE_TITLE })
    expect(dialog).toHaveTextContent(LEAVE_MESSAGE)
    await user.click(within(dialog).getByRole('button', { name: '머물기' }))

    // then: 주소와 저장 안 됨이 그대로다
    expect(location()).toBe('/reports/11/edit')
    expect(screen.getByText(UNSAVED_MARK)).toBeVisible()

    // when: 다시 뒤로 가기를 하고 떠나기를 누른다
    goTo(-1)
    await user.click(within(await screen.findByRole('dialog', { name: LEAVE_TITLE })).getByRole('button', { name: '떠나기' }))

    // then: 보기 화면으로 간다
    await waitFor(() => expect(location()).toBe('/reports/11'))
  })

  // 테스트 코드: RS-107
  it('덮어쓴 직후에는 뒤로 가기에서 묻지 않는다', async () => {
    // given: 설계를 바꿔 덮어쓴 편집 화면
    const { user, location, goTo } = await openEditorFromView(MINE_PUBLIC.id)
    await addCountedColumn(user, 'Deal code')
    await overwrite(user)

    // when: 뒤로 가기를 한다
    goTo(-1)

    // then: 묻지 않고 보기 화면으로 간다
    await waitFor(() => expect(location()).toBe('/reports/11'))
    expect(screen.queryByRole('dialog', { name: LEAVE_TITLE })).not.toBeInTheDocument()
  })

  // 테스트 코드: RS-107
  it('되돌린 직후에는 뒤로 가기에서 묻지 않는다', async () => {
    // given: 설계를 바꿨다가 되돌리기로 되돌렸다
    const { user, location, goTo } = await openEditorFromView(MINE_PUBLIC.id)
    await addCountedColumn(user, 'Deal code')
    await user.click(screen.getByRole('button', { name: '되돌리기' }))
    await user.click(within(await screen.findByRole('dialog', { name: '저장된 설계로 되돌릴까요?' })).getByRole('button', { name: '되돌리기' }))

    // when: 뒤로 가기를 한다
    goTo(-1)

    // then: 묻지 않고 보기 화면으로 간다
    await waitFor(() => expect(location()).toBe('/reports/11'))
    expect(screen.queryByRole('dialog', { name: LEAVE_TITLE })).not.toBeInTheDocument()
  })
})
