import { screen, waitFor, within } from '@testing-library/react'
import { afterEach, beforeEach, describe, expect, it } from 'vitest'
import { gateway } from '../../gateway'
import { renderAt } from '../../test/mockApp'
import { PAGE, SEED_CONTENTS, meetingRows, pinClock, rowWithContent, shownContents, unpinClock, waitForRows } from '../../test/partnerMeetings'

beforeEach(pinClock)
afterEach(unpinClock)

const OWN = 'ITDR 가격 협상' // kim이 쓴 가장 최근 기록(목록의 둘째 줄)

describe('행 삭제 (AC14, AC16)', () => {
  it('asks for confirmation naming the action', async () => {
    const { user } = await renderAt(PAGE)
    await waitForRows(10)

    await user.click(within(rowWithContent(OWN)).getByRole('button', { name: '삭제' }))

    const ask = await screen.findByRole('dialog', { name: '미팅 기록 삭제' })
    expect(within(ask).getByText('이 미팅 기록을 삭제할까요?')).toBeVisible()
    expect(within(ask).getByRole('button', { name: '삭제' })).toBeVisible()
    expect(within(ask).getByRole('button', { name: '취소' })).toBeVisible()
  })

  it('keeps the record when the confirmation is cancelled', async () => {
    const { user } = await renderAt(PAGE)
    await waitForRows(10)
    await user.click(within(rowWithContent(OWN)).getByRole('button', { name: '삭제' }))

    await user.click(within(await screen.findByRole('dialog', { name: '미팅 기록 삭제' })).getByRole('button', { name: '취소' }))

    expect(screen.queryByRole('dialog')).not.toBeInTheDocument()
    expect(shownContents()).toEqual(SEED_CONTENTS.slice(0, 10))
  })

  it('removes the record from the list after the confirmation and shows the next older one', async () => {
    const { user } = await renderAt(PAGE)
    await waitForRows(10)
    await user.click(within(rowWithContent(OWN)).getByRole('button', { name: '삭제' }))

    await user.click(within(await screen.findByRole('dialog', { name: '미팅 기록 삭제' })).getByRole('button', { name: '삭제' }))

    await waitFor(() => expect(shownContents()).not.toContain(OWN))
    expect(shownContents()).toEqual(SEED_CONTENTS.filter((c) => c !== OWN).slice(0, 10))
    expect(screen.queryByRole('dialog')).not.toBeInTheDocument()
    const page = await gateway.partnerMeetings.list({ sort: 'meetingDate', order: 'desc' }, 0, 50)
    expect(page.total).toBe(11)
  })

  it('lets admin delete a record of someone else', async () => {
    const { user } = await renderAt(PAGE, { role: 'admin' })
    await waitForRows(10)
    await user.click(within(rowWithContent('수주 후 일정 점검')).getByRole('button', { name: '삭제' }))

    await user.click(within(await screen.findByRole('dialog', { name: '미팅 기록 삭제' })).getByRole('button', { name: '삭제' }))

    await waitFor(() => expect(shownContents()).not.toContain('수주 후 일정 점검'))
  })

  it('shows the server message in the dialog when the record is already gone', async () => {
    const { user } = await renderAt(PAGE)
    await waitForRows(10)
    await user.click(within(rowWithContent(OWN)).getByRole('button', { name: '삭제' }))
    const mine = (await gateway.partnerMeetings.list({ sort: 'meetingDate', order: 'desc', content: OWN }, 0, 10)).items[0]
    await gateway.partnerMeetings.remove(mine?.id ?? 0)

    await user.click(within(await screen.findByRole('dialog', { name: '미팅 기록 삭제' })).getByRole('button', { name: '삭제' }))

    expect(await screen.findByText('미팅 기록을 찾을 수 없습니다.')).toBeVisible()
  })

  it('keeps showing the other rows while one is being removed', async () => {
    const { user } = await renderAt(PAGE)
    await waitForRows(10)
    await user.click(within(rowWithContent(OWN)).getByRole('button', { name: '삭제' }))
    await user.click(within(await screen.findByRole('dialog', { name: '미팅 기록 삭제' })).getByRole('button', { name: '삭제' }))

    await waitFor(() => expect(meetingRows()).toHaveLength(10))
  })
})
