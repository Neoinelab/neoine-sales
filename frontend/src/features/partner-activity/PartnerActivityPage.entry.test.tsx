import { screen, waitFor, within } from '@testing-library/react'
import { afterEach, beforeEach, describe, expect, it } from 'vitest'
import { renderAt } from '../../test/mockApp'
import {
  PAGE,
  TODAY_TEXT,
  chooseDeal,
  choosePartner,
  fieldsOf,
  openEntryDialog,
  pinClock,
  unpinClock,
  waitForRows,
} from '../../test/partnerMeetings'

beforeEach(pinClock)
afterEach(unpinClock)

describe('미팅 내용 입력 팝업 열기 (AC6, AC7)', () => {
  it('opens a dialog with one empty row, focus on the partner, and today as the default date', async () => {
    const { user } = await renderAt(PAGE)
    await waitForRows(10)

    const dialog = await openEntryDialog(user)

    expect(within(dialog).getAllByRole('group')).toHaveLength(1)
    const { partner, deal, date, content, remove } = fieldsOf(dialog, 1)
    await waitFor(() => expect(partner).toHaveFocus())
    expect(partner).toHaveValue('')
    expect(deal).toHaveValue('')
    expect(date).toHaveValue(TODAY_TEXT)
    expect(content).toHaveValue('')
    expect(remove).toBeDisabled()
    expect(within(dialog).getByRole('button', { name: '저장' })).toBeEnabled()
    expect(within(dialog).getByRole('button', { name: '취소' })).toBeVisible()
    expect(within(dialog).getByRole('button', { name: '행 추가' })).toBeVisible()
  })

  it('gives the dialog to admin as well', async () => {
    const { user } = await renderAt(PAGE, { role: 'admin' })
    await waitForRows(10)

    expect(await openEntryDialog(user)).toBeVisible()
  })

  it('does not open for a read-only user because the button is not there', async () => {
    await renderAt(PAGE, { role: 'user' })
    await waitForRows(10)

    expect(screen.queryByRole('button', { name: '미팅 내용 입력' })).not.toBeInTheDocument()
  })
})

describe('행 추가·삭제 (AC10)', () => {
  it('adds a row with today as its date and renumbers the rows when one is removed', async () => {
    const { user } = await renderAt(PAGE)
    await waitForRows(10)
    const dialog = await openEntryDialog(user)

    await user.click(within(dialog).getByRole('button', { name: '행 추가' }))

    expect(within(dialog).getAllByRole('group')).toHaveLength(2)
    expect(fieldsOf(dialog, 2).date).toHaveValue(TODAY_TEXT)
    expect(fieldsOf(dialog, 1).remove).toBeEnabled()
    await user.type(fieldsOf(dialog, 2).content, '둘째 행')
    await user.click(fieldsOf(dialog, 1).remove)
    expect(within(dialog).getAllByRole('group')).toHaveLength(1)
    expect(fieldsOf(dialog, 1).content).toHaveValue('둘째 행')
    expect(fieldsOf(dialog, 1).remove).toBeDisabled()
  })

  it('allows at most 50 rows and explains it', async () => {
    const { user } = await renderAt(PAGE)
    await waitForRows(10)
    const dialog = await openEntryDialog(user)

    for (let i = 1; i < 50; i += 1) await user.click(within(dialog).getByRole('button', { name: '행 추가' }))
    expect(within(dialog).getAllByRole('group')).toHaveLength(50)
    await user.click(within(dialog).getByRole('button', { name: '행 추가' }))

    expect(within(dialog).getAllByRole('group')).toHaveLength(50)
    expect(await within(dialog).findByText('한 번에 50건까지 입력할 수 있습니다.')).toBeVisible()
  }, 60_000)
})

describe('파트너와 Deal 선택 (AC8)', () => {
  it('lists the registered partner companies', async () => {
    const { user } = await renderAt(PAGE)
    await waitForRows(10)
    const dialog = await openEntryDialog(user)

    await user.click(fieldsOf(dialog, 1).partner)

    const names = within(await within(dialog).findByRole('listbox', { name: '파트너' }))
      .getAllByRole('option')
      .map((o) => o.textContent)
    expect([...names].sort()).toEqual(['넷브릿지', '디지털웨이', '시큐어원', '에이원시스템', '코어테크'])
  })

  it('narrows the partner list by what is typed', async () => {
    const { user } = await renderAt(PAGE)
    await waitForRows(10)
    const dialog = await openEntryDialog(user)

    await user.type(fieldsOf(dialog, 1).partner, '코어')

    expect(within(await within(dialog).findByRole('listbox', { name: '파트너' })).getAllByRole('option')).toHaveLength(1)
  })

  it('keeps the Deal field disabled until a partner is chosen', async () => {
    const { user } = await renderAt(PAGE)
    await waitForRows(10)
    const dialog = await openEntryDialog(user)

    expect(fieldsOf(dialog, 1).deal).toBeDisabled()
    await choosePartner(user, dialog, 1, '코어테크')

    expect(fieldsOf(dialog, 1).deal).toBeEnabled()
  })

  it('offers only the deals the chosen company is an active partner of, with the customer company', async () => {
    const { user } = await renderAt(PAGE)
    await waitForRows(10)
    const dialog = await openEntryDialog(user)

    await choosePartner(user, dialog, 1, '코어테크')

    const list = await within(dialog).findByRole('listbox', { name: 'Deal' })
    const options = within(list).getAllByRole('option')
    expect(options).toHaveLength(4)
    for (const name of ['대한제조 MFA 확대', '세종에너지 취약점 진단', '미래전자 ITDR', '바른제약 ITDR']) {
      expect(within(list).getByRole('option', { name: new RegExp(name) })).toBeVisible()
    }
    expect(within(list).getByRole('option', { name: /대한제조 MFA 확대.*\[\d{8}-D002\]/ })).toHaveTextContent('대한제조')
    expect(within(list).queryByRole('option', { name: /누리통신 MFA/ })).not.toBeInTheDocument() // 이전 파트너였던 Deal
  })

  it('includes a won deal among the choices', async () => {
    const { user } = await renderAt(PAGE)
    await waitForRows(10)
    const dialog = await openEntryDialog(user)

    await choosePartner(user, dialog, 1, '디지털웨이')

    expect(await within(dialog).findByRole('option', { name: /청명대학교 SSO\/MFA/ })).toBeVisible()
  })

  it('puts the chosen deal text in the field', async () => {
    const { user } = await renderAt(PAGE)
    await waitForRows(10)
    const dialog = await openEntryDialog(user)

    await choosePartner(user, dialog, 1, '코어테크')
    await chooseDeal(user, dialog, /미래전자 ITDR/)

    expect(fieldsOf(dialog, 1).deal.value).toMatch(/^미래전자 ITDR \[\d{8}-D015\]$/)
  })

  it('clears the chosen deal when the partner changes to a company that has no such deal', async () => {
    const { user } = await renderAt(PAGE)
    await waitForRows(10)
    const dialog = await openEntryDialog(user)
    await choosePartner(user, dialog, 1, '코어테크')
    await chooseDeal(user, dialog, /미래전자 ITDR/)

    await user.clear(fieldsOf(dialog, 1).partner)
    await choosePartner(user, dialog, 1, '넷브릿지')

    expect(fieldsOf(dialog, 1).deal).toHaveValue('')
  })

  it('works per row: choosing a partner in the second row leaves the first row untouched', async () => {
    const { user } = await renderAt(PAGE)
    await waitForRows(10)
    const dialog = await openEntryDialog(user)
    await user.click(within(dialog).getByRole('button', { name: '행 추가' }))

    await choosePartner(user, dialog, 2, '시큐어원')

    expect(fieldsOf(dialog, 2).partner).toHaveValue('시큐어원')
    expect(fieldsOf(dialog, 1).partner).toHaveValue('')
    expect(fieldsOf(dialog, 1).deal).toBeDisabled()
    expect(fieldsOf(dialog, 2).deal).toBeEnabled()
  })
})
