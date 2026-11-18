import { screen, waitFor, within } from '@testing-library/react'
import { describe, expect, it } from 'vitest'
import { addColumn, addCondition, chipItems, openDesigner, openDesignerFromList, setupReportClock, UNSAVED_MARK } from '../../../test/reportScreen'

setupReportClock()

const menuLink = (name: string): HTMLElement => within(screen.getByRole('navigation', { name: '주 메뉴' })).getByRole('link', { name })
const LEAVE_TITLE = '저장하지 않은 변경이 있습니다'

/** beforeunload를 보내고 막았는지(기본 동작 취소) 돌려준다. */
function unloadIsBlocked(): boolean {
  const event = new Event('beforeunload', { cancelable: true })
  window.dispatchEvent(event)
  return event.defaultPrevented
}

describe('떠날 때 확인', () => {
  // 테스트 코드: RQ-101
  it('바뀐 설계가 있으면 떠나기 전에 묻고 머물기를 누르면 남는다', async () => {
    // given: 컬럼을 하나 넣어 설계를 바꿨다
    const { user, location } = await openDesigner()
    await addColumn(user, 'Deal code')

    // when: 메뉴의 Deals 링크를 누른다
    await user.click(menuLink('Deals'))

    // then: 저장하지 않은 변경 확인 창이 뜬다
    const dialog = await screen.findByRole('dialog', { name: LEAVE_TITLE })
    expect(dialog).toHaveTextContent('저장하지 않은 변경이 사라집니다. 이 화면을 떠날까요?')

    // when: 머물기를 누른다
    await user.click(within(dialog).getByRole('button', { name: '머물기' }))

    // then: 창이 닫히고 화면과 설계가 그대로다
    expect(screen.queryByRole('dialog')).not.toBeInTheDocument()
    expect(location()).toBe('/reports/new')
    expect(chipItems()).toHaveLength(1)
  })

  // 테스트 코드: RQ-101
  it('떠나기를 누르면 화면을 떠난다', async () => {
    // given: 바뀐 설계에서 Deals 링크를 눌러 확인 창이 떠 있다
    const { user, location } = await openDesigner()
    await addColumn(user, 'Deal code')
    await user.click(menuLink('Deals'))

    // when: 떠나기를 누른다
    await user.click(within(await screen.findByRole('dialog', { name: LEAVE_TITLE })).getByRole('button', { name: '떠나기' }))

    // then: Deals로 이동하고 창이 닫힌다
    await waitFor(() => expect(location()).toMatch(/^\/deals/))
    expect(screen.queryByRole('dialog', { name: LEAVE_TITLE })).not.toBeInTheDocument()
  })

  // 테스트 코드: RQ-101
  it('조건만 추가했어도 떠날 때 묻는다', async () => {
    // given: 조건만 추가한 설계
    const { user } = await openDesigner()
    await addCondition(user, 'Vendor')

    // when: 메뉴의 Reports 링크를 누른다
    await user.click(menuLink('Reports'))

    // then: 확인 창이 뜬다
    expect(await screen.findByRole('dialog', { name: LEAVE_TITLE })).toBeVisible()
  })

  // 테스트 코드: RQ-101
  it('바뀐 것이 없으면 묻지 않고 떠난다', async () => {
    // given: 바뀌지 않은 설계
    const { user, location } = await openDesigner()

    // when: 메뉴의 Deals 링크를 누른다
    await user.click(menuLink('Deals'))

    // then: 바로 이동하고 확인 창이 없다
    await waitFor(() => expect(location()).toMatch(/^\/deals/))
    expect(screen.queryByRole('dialog')).not.toBeInTheDocument()
  })

  // 테스트 코드: RQ-101
  it('바뀐 것을 되돌렸으면 묻지 않고 떠난다', async () => {
    // given: 컬럼을 넣었다가 뺐다
    const { user, location } = await openDesigner()
    await addColumn(user, 'Deal code')
    await user.click(screen.getByRole('button', { name: 'Deal code 빼기' }))

    // when: 메뉴의 Deals 링크를 누른다
    await user.click(menuLink('Deals'))

    // then: 바로 이동하고 확인 창이 없다
    await waitFor(() => expect(location()).toMatch(/^\/deals/))
    expect(screen.queryByRole('dialog')).not.toBeInTheDocument()
  })

  // 테스트 코드: RQ-101
  it('beforeunload는 설계가 바뀌어 있는 동안만 막는다', async () => {
    // when: 바뀌지 않은 설계를 연다
    const { user } = await openDesigner()
    // then: 새로고침을 막지 않는다
    expect(unloadIsBlocked()).toBe(false)

    // when: 컬럼을 넣는다
    await addColumn(user, 'Deal code')
    // then: 새로고침을 막는다
    expect(unloadIsBlocked()).toBe(true)

    // when: 컬럼을 뺀다
    await user.click(screen.getByRole('button', { name: 'Deal code 빼기' }))
    // then: 다시 막지 않는다
    expect(unloadIsBlocked()).toBe(false)
  })

  // 테스트 코드: RQ-101
  it('디자이너를 떠난 뒤에는 새로고침을 막지 않는다', async () => {
    // given: 바뀐 설계에서 떠나기를 눌러 Deals로 이동했다
    const { user, location } = await openDesigner()
    await addColumn(user, 'Deal code')
    await user.click(menuLink('Deals'))
    await user.click(within(await screen.findByRole('dialog', { name: LEAVE_TITLE })).getByRole('button', { name: '떠나기' }))
    // when: 이동이 끝난다
    await waitFor(() => expect(location()).toMatch(/^\/deals/))

    // then: 새로고침을 막지 않는다
    expect(unloadIsBlocked()).toBe(false)
  })
})

describe('좁은 화면 메뉴', () => {
  const toggle = (): HTMLElement => screen.getByRole('button', { name: '메뉴 열기' })

  // 테스트 코드: RQ-101
  it('떠나기를 누르면 열려 있던 좁은 화면 메뉴가 닫힌다', async () => {
    // given: 바뀐 설계에서 좁은 화면 메뉴를 열었다
    const { user, location } = await openDesigner()
    await addColumn(user, 'Deal code')
    await user.click(toggle())
    expect(toggle()).toHaveAttribute('aria-expanded', 'true')

    // when: Deals 링크를 누르고 떠나기를 누른다
    await user.click(menuLink('Deals'))
    await user.click(within(await screen.findByRole('dialog', { name: LEAVE_TITLE })).getByRole('button', { name: '떠나기' }))

    // then: 이동하고 메뉴가 닫힌다
    await waitFor(() => expect(location()).toMatch(/^\/deals/))
    expect(toggle()).toHaveAttribute('aria-expanded', 'false')
  })

  it('바뀐 것이 없으면 링크를 눌렀을 때 열려 있던 메뉴가 닫힌다', async () => {
    // given: 바뀌지 않은 설계에서 좁은 화면 메뉴를 열었다
    const { user, location } = await openDesigner()
    await user.click(toggle())

    // when: Deals 링크를 누른다
    await user.click(menuLink('Deals'))

    // then: 이동하고 메뉴가 닫힌다
    await waitFor(() => expect(location()).toMatch(/^\/deals/))
    expect(toggle()).toHaveAttribute('aria-expanded', 'false')
  })
})

describe('초기화', () => {
  // 테스트 코드: RQ-102
  it('바뀐 설계를 초기화하려 하면 묻고 취소하면 설계가 남는다', async () => {
    // given: 컬럼을 하나 넣어 설계를 바꿨다
    const { user } = await openDesigner()
    await addColumn(user, 'Deal code')

    // when: 초기화를 눌러 확인 창에서 취소한다
    await user.click(screen.getByRole('button', { name: '초기화' }))

    const dialog = await screen.findByRole('dialog', { name: '설계를 모두 지울까요?' })
    await user.click(within(dialog).getByRole('button', { name: '취소' }))

    // then: 창이 닫히고 설계가 남는다
    expect(screen.queryByRole('dialog')).not.toBeInTheDocument()
    expect(chipItems()).toHaveLength(1)
  })

  // 테스트 코드: RQ-102
  it('확인하면 설계를 모두 지우고 결합도 AND로 돌아간다', async () => {
    // given: 컬럼, 조건, OR 결합이 있는 설계
    const { user } = await openDesigner()
    await addColumn(user, 'Deal code')
    await addCondition(user, 'Vendor')
    await user.click(screen.getByRole('radio', { name: /OR/ }))

    // when: 초기화를 누르고 확인 창에서 초기화한다
    await user.click(screen.getByRole('button', { name: '초기화' }))
    await user.click(within(await screen.findByRole('dialog', { name: '설계를 모두 지울까요?' })).getByRole('button', { name: '초기화' }))

    // then: 컬럼과 조건이 없고 결합은 AND이며 새로고침을 막지 않는다
    expect(chipItems()).toHaveLength(0)
    expect(screen.queryByRole('combobox', { name: '조건 1 필드' })).not.toBeInTheDocument()
    expect(screen.getByRole('radio', { name: /AND/ })).toBeChecked()
    expect(unloadIsBlocked()).toBe(false)
  })

  // 테스트 코드: RQ-102
  it('바뀐 것이 없으면 묻지 않고 초기화한다', async () => {
    // given: 바뀌지 않은 설계
    const { user } = await openDesigner()

    // when: 초기화를 누른다
    await user.click(screen.getByRole('button', { name: '초기화' }))

    // then: 확인 창이 뜨지 않는다
    expect(screen.queryByRole('dialog')).not.toBeInTheDocument()
  })
})

describe('브라우저 뒤로·앞으로 가기', () => {
  // 테스트 코드: RQ-125
  it('바뀐 설계에서 뒤로 가기를 하면 묻고 머물기면 주소와 설계가 그대로이며 다시 뒤로 가면 또 묻는다', async () => {
    // given: 목록에서 새 리포트로 들어와 컬럼과 조건을 넣어 저장 안 됨이다
    const { user, location, goTo } = await openDesignerFromList()
    await addColumn(user, 'Deal code')
    await addCondition(user, 'Vendor')
    expect(screen.getByText(UNSAVED_MARK)).toBeVisible()

    // when: 뒤로 가기를 한다
    goTo(-1)

    // then: 확인 창과 안내 문구가 뜬다
    const dialog = await screen.findByRole('dialog', { name: LEAVE_TITLE })
    expect(dialog).toHaveTextContent('저장하지 않은 변경이 사라집니다. 이 화면을 떠날까요?')

    // when: 머물기를 누른다
    await user.click(within(dialog).getByRole('button', { name: '머물기' }))

    // then: 창이 닫히고 주소와 설계가 그대로다
    expect(screen.queryByRole('dialog')).not.toBeInTheDocument()
    expect(location()).toBe('/reports/new')
    expect(chipItems()).toHaveLength(1)
    expect(screen.getByRole('combobox', { name: '조건 1 필드' })).toBeVisible()
    expect(screen.getByText(UNSAVED_MARK)).toBeVisible()

    // when: 한 번 더 뒤로 가기를 한다
    goTo(-1)

    // then: 같은 창이 다시 뜬다
    expect(await screen.findByRole('dialog', { name: LEAVE_TITLE })).toBeVisible()
  })

  // 테스트 코드: RQ-126
  it('뒤로 가기에서 떠나기를 고르면 창이 한 번만 뜨고 목록으로 가며 새로고침을 막지 않는다', async () => {
    // given: 목록에서 들어와 컬럼을 넣었다
    const { user, location, goTo } = await openDesignerFromList()
    await addColumn(user, 'Deal code')

    // when: 뒤로 가기를 하고 떠나기를 누른다
    goTo(-1)
    await user.click(within(await screen.findByRole('dialog', { name: LEAVE_TITLE })).getByRole('button', { name: '떠나기' }))

    // then: 주소가 /reports이고 목록이 보이며 두 번째 창이 없고 새로고침을 막지 않는다
    await waitFor(() => expect(location()).toBe('/reports'))
    expect(await screen.findByRole('link', { name: '+ 새 리포트' })).toBeVisible()
    expect(screen.queryByRole('dialog')).not.toBeInTheDocument()
    expect(unloadIsBlocked()).toBe(false)
  })

  // 테스트 코드: RQ-126
  it('앞으로 가기에서 떠나기를 고르면 다음 화면으로 간다', async () => {
    // given: 목록 → 새 리포트 → Deals(바뀐 것 없어 묻지 않음) → 뒤로 가기로 돌아와 컬럼을 넣었다
    const { user, location, goTo } = await openDesignerFromList()
    await user.click(menuLink('Deals'))
    await waitFor(() => expect(location()).toMatch(/^\/deals/))
    goTo(-1)
    await screen.findByRole('button', { name: 'Deal code 컬럼에 추가' })
    await addColumn(user, 'Deal code')

    // when: 앞으로 가기를 하고 떠나기를 누른다
    goTo(1)
    await user.click(within(await screen.findByRole('dialog', { name: LEAVE_TITLE })).getByRole('button', { name: '떠나기' }))

    // then: 주소가 /deals다
    await waitFor(() => expect(location()).toMatch(/^\/deals/))
  })

  // 테스트 코드: RQ-127
  it('바뀐 것이 없으면 뒤로 가기에서 묻지 않는다', async () => {
    // given: 목록에서 들어온 바뀌지 않은 설계
    const { location, goTo } = await openDesignerFromList()

    // when: 뒤로 가기를 한다
    goTo(-1)

    // then: 창 없이 /reports가 된다
    await waitFor(() => expect(location()).toBe('/reports'))
    expect(screen.queryByRole('dialog')).not.toBeInTheDocument()
  })

  // 테스트 코드: RQ-127
  it('컬럼을 넣었다 뺀 설계는 뒤로 가기에서 묻지 않는다', async () => {
    // given: 컬럼을 넣었다가 칩을 지웠다
    const { user, location, goTo } = await openDesignerFromList()
    await addColumn(user, 'Deal code')
    await user.click(screen.getByRole('button', { name: 'Deal code 빼기' }))

    // when: 뒤로 가기를 한다
    goTo(-1)

    // then: 창 없이 /reports가 된다
    await waitFor(() => expect(location()).toBe('/reports'))
    expect(screen.queryByRole('dialog')).not.toBeInTheDocument()
  })

  // 테스트 코드: RQ-127
  it('링크로 떠난 이동은 떠나기 뒤 두 번째 창 없이 끝난다', async () => {
    // given: 목록에서 들어와 컬럼을 넣었다
    const { user, location } = await openDesignerFromList()
    await addColumn(user, 'Deal code')

    // when: Deals 링크를 눌러 창이 한 번 뜨고 떠나기를 누른다
    await user.click(menuLink('Deals'))
    await user.click(within(await screen.findByRole('dialog', { name: LEAVE_TITLE })).getByRole('button', { name: '떠나기' }))

    // then: 두 번째 창 없이 /deals다
    await waitFor(() => expect(location()).toMatch(/^\/deals/))
    expect(screen.queryByRole('dialog')).not.toBeInTheDocument()
  })
})
