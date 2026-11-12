import { screen, waitFor, within } from '@testing-library/react'
import { afterEach, beforeEach, describe, expect, it } from 'vitest'
import { gateway } from '../../gateway'
import { renderAt } from '../../test/mockApp'
import { PAGE, SEED_CONTENTS, meetingRows, pinClock, rowWithContent, shownContents, unpinClock, waitForRows } from '../../test/partnerMeetings'

beforeEach(pinClock)
afterEach(unpinClock)

const OWN = 'ITDR 가격 협상' // kim이 쓴 가장 최근 기록(목록의 둘째 줄)

describe('행 삭제', () => {
  // 삭제를 누르면 확인 창이 뜬다.
  // 테스트 코드: PA-087
  it('asks for confirmation naming the action', async () => {
    // given: 내 기록이 있는 목록
    const { user } = await renderAt(PAGE)
    await waitForRows(10)

    // when: 내 기록의 삭제를 누른다
    await user.click(within(rowWithContent(OWN)).getByRole('button', { name: '삭제' }))

    // then: 삭제 확인 창에 문구와 삭제·취소 버튼이 보인다
    const ask = await screen.findByRole('dialog', { name: '미팅 기록 삭제' })
    expect(within(ask).getByText('이 미팅 기록을 삭제할까요?')).toBeVisible()
    expect(within(ask).getByRole('button', { name: '삭제' })).toBeVisible()
    expect(within(ask).getByRole('button', { name: '취소' })).toBeVisible()
  })

  // 확인 창에서 취소하면 기록이 남는다.
  // 테스트 코드: PA-087
  it('keeps the record when the confirmation is cancelled', async () => {
    // given: 삭제 확인 창이 열려 있다
    const { user } = await renderAt(PAGE)
    await waitForRows(10)
    await user.click(within(rowWithContent(OWN)).getByRole('button', { name: '삭제' }))

    // when: 취소를 누른다
    await user.click(within(await screen.findByRole('dialog', { name: '미팅 기록 삭제' })).getByRole('button', { name: '취소' }))

    // then: 창이 닫히고 목록이 그대로다
    expect(screen.queryByRole('dialog')).not.toBeInTheDocument()
    expect(shownContents()).toEqual(SEED_CONTENTS.slice(0, 10))
  })

  // 확인하면 기록이 지워지고 다음 기록이 보인다.
  // 테스트 코드: PA-087
  it('removes the record from the list after the confirmation and shows the next older one', async () => {
    // given: 삭제 확인 창이 열려 있다
    const { user } = await renderAt(PAGE)
    await waitForRows(10)
    await user.click(within(rowWithContent(OWN)).getByRole('button', { name: '삭제' }))

    // when: 삭제를 확인한다
    await user.click(within(await screen.findByRole('dialog', { name: '미팅 기록 삭제' })).getByRole('button', { name: '삭제' }))

    // then: 기록이 사라지고 다음으로 오래된 기록이 채워지며 서버에도 11건이다
    await waitFor(() => expect(shownContents()).not.toContain(OWN))
    expect(shownContents()).toEqual(SEED_CONTENTS.filter((c) => c !== OWN).slice(0, 10))
    expect(screen.queryByRole('dialog')).not.toBeInTheDocument()
    const page = await gateway.partnerMeetings.list({ sort: 'meetingDate', order: 'desc' }, 0, 50)
    expect(page.total).toBe(11)
  })

  // admin은 남의 기록을 삭제한다.
  // 테스트 코드: PA-087
  it('lets admin delete a record of someone else', async () => {
    // given: admin으로 연 목록과 남의 기록의 삭제 확인 창
    const { user } = await renderAt(PAGE, { role: 'admin' })
    await waitForRows(10)
    await user.click(within(rowWithContent('수주 후 일정 점검')).getByRole('button', { name: '삭제' }))

    // when: 삭제를 확인한다
    await user.click(within(await screen.findByRole('dialog', { name: '미팅 기록 삭제' })).getByRole('button', { name: '삭제' }))

    // then: 남의 기록이 사라진다
    await waitFor(() => expect(shownContents()).not.toContain('수주 후 일정 점검'))
  })

  // 이미 지워졌으면 대화상자에 서버 문구를 보인다.
  // 테스트 코드: PA-087
  it('shows the server message in the dialog when the record is already gone', async () => {
    // given: 삭제 확인 창이 열린 사이에 같은 기록이 이미 지워졌다
    const { user } = await renderAt(PAGE)
    await waitForRows(10)
    await user.click(within(rowWithContent(OWN)).getByRole('button', { name: '삭제' }))
    const mine = (await gateway.partnerMeetings.list({ sort: 'meetingDate', order: 'desc', content: OWN }, 0, 10)).items[0]
    await gateway.partnerMeetings.remove(mine?.id ?? 0)

    // when: 삭제를 확인한다
    await user.click(within(await screen.findByRole('dialog', { name: '미팅 기록 삭제' })).getByRole('button', { name: '삭제' }))

    // then: 서버 문구가 보인다
    expect(await screen.findByText('미팅 기록을 찾을 수 없습니다.')).toBeVisible()
  })

  // 하나를 지우는 동안에도 나머지 행이 보인다.
  // 테스트 코드: PA-087
  it('keeps showing the other rows while one is being removed', async () => {
    // given: 목록과 삭제 확인 창
    const { user } = await renderAt(PAGE)
    await waitForRows(10)
    await user.click(within(rowWithContent(OWN)).getByRole('button', { name: '삭제' }))
    // when: 삭제를 확인한다
    await user.click(within(await screen.findByRole('dialog', { name: '미팅 기록 삭제' })).getByRole('button', { name: '삭제' }))

    // then: 행이 10개로 채워진다
    await waitFor(() => expect(meetingRows()).toHaveLength(10))
  })
})
