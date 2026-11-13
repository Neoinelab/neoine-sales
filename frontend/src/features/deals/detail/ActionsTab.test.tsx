import { screen, waitFor, within } from '@testing-library/react'
import { describe, expect, it } from 'vitest'
import { renderAt } from '../../../test/mockApp'
import { detailPath } from '../../../test/detailTestUtils'
import { USER_ID } from '../../../test/fake/seed/ids'

/** 유형 자동완성 입력에 글자를 입력한다(목록 선택 없이 직접 입력). */
async function typeAction(user: Awaited<ReturnType<typeof renderAt>>['user'], form: HTMLElement, text: string) {
  await user.type(within(form).getByLabelText('유형'), text)
}

async function openActions(no: number, title: string, role: 'sales' | 'admin' | 'user' = 'sales') {
  const view = await renderAt(await detailPath(no, '?tab=actions'), { role })
  await screen.findByRole('heading', { level: 1, name: title })
  const table = await screen.findByRole('table', { name: 'Action 목록' })
  return { ...view, table }
}

function bodyRows(table: HTMLElement) {
  return within(table).getAllByRole('row').slice(1)
}

describe('Actions 탭 목록', () => {
  // 목록은 최신순으로 정해진 열을 보인다.
  // 테스트 코드: AC-071
  it('lists actions newest first with the columns the plan asks for', async () => {
    // given: sales가 Action이 여럿인 Deal의 Actions 탭을 연다
    const { table } = await openActions(1, '한빛은행 ITDR 도입')
    // when: 표 머리글과 첫 행들을 읽는다
    const headers = within(table).getAllByRole('columnheader').map((h) => h.textContent)
    // then: 열 순서가 수행일부터 관리까지다
    expect(headers).toEqual([
      '수행일',
      '담당자',
      '등록 시점 Status·Forecast',
      '유형',
      '진행사항',
      'Next Action',
      'Due Date',
      '상태',
      'Memo',
      '관리',
    ])
    // then: 최신 Action이 위이고 내용·상태 배지가 보인다
    const first = bodyRows(table)[0]
    expect(first).toHaveTextContent('최종 가격 협의')
    expect(first).toHaveTextContent('계약서 초안 검토')
    expect(first).toHaveTextContent('가격협상')
    expect(first).toHaveTextContent('Commit')
    expect(bodyRows(table)[1]).toHaveTextContent('임원 보고용 ROI 자료 전달')
  })

  // 현재 Next Action의 지난 Due Date에 기한초과 배지가 붙는다.
  // 테스트 코드: RK-058
  it('marks the overdue due date of the current next action', async () => {
    // when: 기한이 지난 Next Action이 있는 Deal의 Actions 탭을 연다
    const { table } = await openActions(3, '미래전자 EDR 교체')
    // then: 첫 행에 기한초과가 보인다
    expect(within(bodyRows(table)[0]!).getByText('기한초과')).toBeVisible()
  })

  // 예전 Action은 등록 당시 Status/Forecast를 보이고 현재 값과 다를 수 있다.
  // 테스트 코드: AC-071
  it('shows the registered-time status of older actions, which can differ from the current one', async () => {
    // given: Deal의 Actions 탭
    const { table } = await openActions(1, '한빛은행 ITDR 도입')
    // when: 가장 오래된 행을 읽는다
    const rows = bodyRows(table)
    const oldest = rows[rows.length - 1]!
    // then: 등록 당시 Status를 보이고 현재 Status는 아니다
    expect(oldest).toHaveTextContent('POC완료')
    expect(oldest).not.toHaveTextContent('가격협상')
  })
})

describe('Action 추가 등록', () => {
  // 추가 팝업은 읽기 전용 이전 Update 카드와 빈 유형 칸을 보인다.
  // 테스트 코드: AC-074
  it('opens the form with the previous update as a read-only reference and an empty type', async () => {
    // given: sales가 Actions 탭을 연다
    const { user } = await openActions(1, '한빛은행 ITDR 도입')
    // when: Action 추가를 누른다
    await user.click(screen.getByRole('button', { name: 'Action 추가' }))
    // then: 폼에 빈 유형 칸과 현재 Status가 있다
    const form = screen.getByRole('form', { name: 'Action 추가' })
    expect(within(form).getByLabelText('유형')).toHaveDisplayValue('')
    expect(within(form).getByLabelText('Status')).toHaveDisplayValue('가격협상')
    // then: 이전 Update 카드와 담당자 안내가 보인다
    const previous = screen.getByRole('complementary', { name: '이전 Update' })
    expect(previous).toHaveTextContent('최종 가격 협의')
    expect(previous).toHaveTextContent('계약서 초안 검토')
    expect(within(form).getByText(/담당자: 김영업/)).toBeVisible()
  })

  // 이전 Next Action을 진행사항에 채울 수 있다.
  // 테스트 코드: AC-081
  it('fills the progress with the previous next action', async () => {
    // given: sales가 Actions 탭을 열고 추가 팝업을 연다
    const { user } = await openActions(1, '한빛은행 ITDR 도입')
    await user.click(screen.getByRole('button', { name: 'Action 추가' }))
    // when: 이전 Next Action 채우기를 누른다
    await user.click(screen.getByRole('button', { name: '이전 Next Action을 진행사항에 채우기' }))
    // then: 진행사항이 이전 Next Action으로 채워진다
    expect(screen.getByLabelText('진행사항')).toHaveValue('계약서 초안 검토')
  })

  // 등록하면 목록 맨 위에 추가되고 요약 바가 갱신된다.
  // 테스트 코드: AC-077
  it('registers an action at the top of the list and refreshes the summary bar', async () => {
    // given: sales가 Actions 탭에서 추가 팝업을 연다
    const { user, table } = await openActions(1, '한빛은행 ITDR 도입')
    await user.click(screen.getByRole('button', { name: 'Action 추가' }))
    const form = screen.getByRole('form', { name: 'Action 추가' })
    // when: 유형·진행사항·Next Action·Due·Memo를 입력하고 등록한다
    await typeAction(user, form, '미팅')
    await user.type(within(form).getByLabelText('진행사항'), '법무팀 계약 검토 미팅')
    await user.type(within(form).getByLabelText('Next Action'), '날인본 수령')
    await user.type(within(form).getByLabelText('Due Date'), '2026-12-20')
    await user.type(within(form).getByLabelText('Memo'), '법무 의견 반영')
    await user.click(within(form).getByRole('button', { name: '등록' }))
    // then: 새 Action이 목록 맨 위에 보이고 팝업이 닫힌다
    await waitFor(() => expect(bodyRows(table)[0]).toHaveTextContent('법무팀 계약 검토 미팅'))
    expect(bodyRows(table)[0]).toHaveTextContent('날인본 수령')
    expect(bodyRows(table)[0]).toHaveTextContent('2026-12-20')
    expect(screen.queryByRole('dialog', { name: 'Action 추가' })).not.toBeInTheDocument()
    // when: Deal 상세 탭으로 간다
    await user.click(screen.getByRole('tab', { name: 'Deal 상세' }))
    const bar = await screen.findByRole('region', { name: 'Deal 정보' })
    // then: 요약 바 Next Action이 새 값이고 등록 알림이 보인다
    expect(within(bar).getByText(/날인본 수령/)).toBeVisible()
    expect(screen.getByText('Action이 등록되었습니다.')).toBeVisible()
  })

  // 검증 문구가 유형, 진행사항, Due Date 순으로 나오고 유형 칸에 포커스한다.
  // 테스트 코드: AC-075
  it('shows the type, "progress or Next Action" and Due Date messages and focuses the type first', async () => {
    // given: sales가 Actions 탭에서 추가 팝업을 연다
    const { user } = await openActions(1, '한빛은행 ITDR 도입')
    await user.click(screen.getByRole('button', { name: 'Action 추가' }))
    const form = screen.getByRole('form', { name: 'Action 추가' })
    // when: 모든 칸을 비우고 등록을 누른다
    await user.click(within(form).getByRole('button', { name: '등록' }))
    // then: 유형·진행사항 문구가 보이고 Due 문구는 없으며 유형 칸에 포커스가 간다
    expect(within(form).getByText('유형을 입력하세요.')).toBeVisible()
    expect(within(form).getByText('진행사항 또는 Next Action을 입력하세요.')).toBeVisible()
    expect(within(form).queryByText('Due Date를 입력하세요.')).not.toBeInTheDocument() // Next Action이 없으면 Due는 필수가 아니다
    expect(within(form).getByRole('combobox', { name: '유형' })).toHaveFocus()
    // when: Next Action만 쓰고 다시 등록을 누른다
    await user.type(within(form).getByLabelText('Next Action'), '다음 할 일')
    await user.click(within(form).getByRole('button', { name: '등록' }))
    // then: Due Date 문구가 보이고 진행사항 문구는 사라진다
    expect(within(form).getByText('Due Date를 입력하세요.')).toBeVisible()
    expect(within(form).queryByText('진행사항 또는 Next Action을 입력하세요.')).not.toBeInTheDocument()
  })

  // 지난 Due Date도 받는다.
  // 테스트 코드: AC-077
  it('accepts a past due date', async () => {
    // given: sales가 Actions 탭에서 추가 팝업을 연다
    const { user, table } = await openActions(2, '대한제조 MFA 확대')
    await user.click(screen.getByRole('button', { name: 'Action 추가' }))
    const form = screen.getByRole('form', { name: 'Action 추가' })
    await typeAction(user, form, '기타')
    // when: 지난 Due Date로 입력하고 등록한다
    await user.type(within(form).getByLabelText('진행사항'), '지난 일정 정리')
    await user.type(within(form).getByLabelText('Next Action'), '후속 확인')
    await user.type(within(form).getByLabelText('Due Date'), '2026-01-05')
    await user.click(within(form).getByRole('button', { name: '등록' }))
    // then: 새 Action이 목록 맨 위에 보인다
    await waitFor(() => expect(bodyRows(table)[0]).toHaveTextContent('지난 일정 정리'))
  })

  // 취소하면 아무것도 등록하지 않는다.
  // 테스트 코드: AC-077
  it('cancels the form without registering anything', async () => {
    // given: sales가 Actions 탭을 열고 현재 행 수를 센다
    const { user, table } = await openActions(1, '한빛은행 ITDR 도입')
    const before = bodyRows(table).length
    // when: 추가 팝업에 입력한 뒤 취소를 누른다
    await user.click(screen.getByRole('button', { name: 'Action 추가' }))
    await user.type(screen.getByLabelText('진행사항'), '버릴 내용')
    await user.click(screen.getByRole('button', { name: '취소' }))
    // then: 팝업이 닫히고 행 수가 그대로다
    expect(screen.queryByRole('dialog', { name: 'Action 추가' })).not.toBeInTheDocument()
    expect(bodyRows(table)).toHaveLength(before)
  })

  // 폼에서 Status를 바꾸면 등록 시점 값이 바뀐 Status로 저장된다.
  // 테스트 코드: AC-079
  it('stores the status at registration time when the status is changed in the form (sync popup)', async () => {
    // given: sales가 Actions 탭에서 추가 팝업을 연다
    const { user, table } = await openActions(1, '한빛은행 ITDR 도입')
    await user.click(screen.getByRole('button', { name: 'Action 추가' }))
    const form = screen.getByRole('form', { name: 'Action 추가' })
    // when: Status를 계약완료로 바꾸고 매출 확정 대화상자에서 확정한다
    await user.selectOptions(within(form).getByLabelText('Status'), '계약완료')
    const dialog = await screen.findByRole('dialog', { name: '매출 확정' })
    await user.clear(within(dialog).getByLabelText('매출금액(단위:원, 실제 값)'))
    await user.type(within(dialog).getByLabelText('매출금액(단위:원, 실제 값)'), '1850000000')
    await user.clear(within(dialog).getByLabelText('매출일(실제 값)'))
    await user.type(within(dialog).getByLabelText('매출일(실제 값)'), '2026-11-20')
    await user.click(within(dialog).getByRole('button', { name: '확정' }))
    // then: 폼에 변경 예정 안내와 새 Status가 보인다
    expect(await within(form).findByText(/저장하면 반영됩니다/)).toBeVisible()
    expect(within(form).getByLabelText('Status')).toHaveDisplayValue('계약완료')
    // when: 나머지를 입력하고 등록한다
    await typeAction(user, form, '계약')
    await user.type(within(form).getByLabelText('진행사항'), '계약 체결')
    await user.type(within(form).getByLabelText('Next Action'), '납품 일정 확인')
    await user.type(within(form).getByLabelText('Due Date'), '2026-12-01')
    await user.click(within(form).getByRole('button', { name: '등록' }))
    // then: 새 행에 계약완료·Won이 보인다
    await waitFor(() => expect(bodyRows(table)[0]).toHaveTextContent('계약 체결'))
    expect(bodyRows(table)[0]).toHaveTextContent('계약완료')
    expect(bodyRows(table)[0]).toHaveTextContent('Won')
    // when: Deal 상세 탭으로 간다
    await user.click(screen.getByRole('tab', { name: 'Deal 상세' }))
    const bar = await screen.findByRole('region', { name: 'Deal 정보' })
    // then: 요약 바 Status가 계약완료다
    expect(within(bar).getByRole('button', { name: 'Status 수정' })).toHaveTextContent('계약완료')
  })

  // 동기화 대화상자를 취소하면 Status가 그대로다.
  // 테스트 코드: AC-080
  it('keeps the status when the sync popup in the form is cancelled', async () => {
    // given: sales가 Actions 탭에서 추가 팝업을 연다
    const { user } = await openActions(1, '한빛은행 ITDR 도입')
    await user.click(screen.getByRole('button', { name: 'Action 추가' }))
    const form = screen.getByRole('form', { name: 'Action 추가' })
    // when: Status를 계약완료로 바꾸고 대화상자를 취소한다
    await user.selectOptions(within(form).getByLabelText('Status'), '계약완료')
    const dialog = await screen.findByRole('dialog', { name: '매출 확정' })
    await user.click(within(dialog).getByRole('button', { name: '취소' }))
    // then: Action 팝업은 그대로 열려 있고 Status는 원래 값이다
    await waitFor(() => expect(screen.queryByRole('dialog', { name: '매출 확정' })).not.toBeInTheDocument())
    expect(screen.getByRole('dialog', { name: 'Action 추가' })).toBeVisible()
    expect(within(form).getByLabelText('Status')).toHaveDisplayValue('가격협상')
    expect(within(form).queryByText(/저장하면 반영됩니다/)).not.toBeInTheDocument()
  })
})

describe('Action 수정·삭제', () => {
  // 예전 Action을 고치면 이력에 기록되고 등록 시점 Status는 유지된다.
  // 테스트 코드: AC-086
  it('edits an older action, explains it goes to the history, and keeps the registered status', async () => {
    // given: sales가 Actions 탭을 연다
    const { user, table } = await openActions(1, '한빛은행 ITDR 도입')
    const row = bodyRows(table)[1]!
    // when: 예전 행의 수정을 눌러 진행사항을 고친다
    await user.click(within(row).getByRole('button', { name: '수정' }))
    // then: 수정 팝업에 History 안내가 있고 Status 칸이 없다
    const form = screen.getByRole('form', { name: 'Action 수정' })
    expect(within(form).getByText(/Deal History에 기록됩니다/)).toBeVisible()
    expect(within(form).queryByLabelText('Status')).not.toBeInTheDocument()
    const progress = within(form).getByLabelText('진행사항')
    expect(progress).toHaveValue('임원 보고용 ROI 자료 전달')
    await user.clear(progress)
    await user.type(progress, 'ROI 자료 수정본 전달')
    // when: 저장한다
    await user.click(within(form).getByRole('button', { name: '저장' }))
    // then: 행이 바뀌고 수정 알림이 보인다
    await waitFor(() => expect(bodyRows(table)[1]).toHaveTextContent('ROI 자료 수정본 전달'))
    expect(screen.getByText('Action이 수정되었습니다.')).toBeVisible()
    // when: Deal History 탭으로 간다
    await user.click(screen.getByRole('tab', { name: 'Deal History' }))
    const cells = await screen.findAllByRole('cell', { name: 'Action' })
    // then: Action 이력과 "수정:" 문구가 있다
    expect(cells.length).toBeGreaterThan(0)
    expect(screen.getAllByText(/수정: /).length).toBeGreaterThan(0)
  })

  // 수정으로 진행사항과 Next Action을 모두 비우면 검증 문구가 나온다.
  // 테스트 코드: AC-086
  it('shows the validation message when an edit empties both progress and Next Action', async () => {
    // given: sales가 Actions 탭을 연다
    const { user, table } = await openActions(1, '한빛은행 ITDR 도입')
    // when: 첫 행의 수정을 눌러 두 칸을 비우고 저장한다
    await user.click(within(bodyRows(table)[0]!).getByRole('button', { name: '수정' }))
    const form = screen.getByRole('form', { name: 'Action 수정' })
    await user.clear(within(form).getByLabelText('진행사항'))
    await user.clear(within(form).getByLabelText('Next Action'))
    await user.click(within(form).getByRole('button', { name: '저장' }))
    // then: 진행사항 또는 Next Action 문구가 보인다
    expect(within(form).getByText('진행사항 또는 Next Action을 입력하세요.')).toBeVisible()
  })

  // 삭제는 확인 뒤 지우고 요약 바의 Next Action이 갱신된다.
  // 테스트 코드: AC-088
  it('deletes an action after confirmation and refreshes the next action in the summary bar', async () => {
    // given: sales가 Actions 탭을 열고 행 수를 센다
    const { user, table } = await openActions(1, '한빛은행 ITDR 도입')
    const before = bodyRows(table).length
    // when: 첫 행의 삭제를 누르고 확인 대화상자에서 삭제한다
    await user.click(within(bodyRows(table)[0]!).getByRole('button', { name: '삭제' }))
    const dialog = screen.getByRole('dialog', { name: 'Action 삭제' })
    // then: 대화상자에 History 안내가 있다
    expect(dialog).toHaveTextContent('Deal History에 기록됩니다')
    await user.click(within(dialog).getByRole('button', { name: '삭제' }))
    // then: 행이 하나 줄어든다
    await waitFor(() => expect(bodyRows(table)).toHaveLength(before - 1))
    // when: Deal 상세 탭으로 간다
    await user.click(screen.getByRole('tab', { name: 'Deal 상세' }))
    const bar = await screen.findByRole('region', { name: 'Deal 정보' })
    // then: 요약 바에서 지운 Action의 Next Action이 사라진다
    await waitFor(() => expect(within(bar).queryByText(/계약서 초안 검토/)).not.toBeInTheDocument())
  })

  // 삭제를 취소하면 Action이 그대로 남는다.
  // 테스트 코드: AC-088
  it('keeps the action when the delete is cancelled', async () => {
    // given: sales가 Actions 탭을 열고 행 수를 센다
    const { user, table } = await openActions(1, '한빛은행 ITDR 도입')
    const before = bodyRows(table).length
    // when: 삭제를 눌렀다가 취소한다
    await user.click(within(bodyRows(table)[0]!).getByRole('button', { name: '삭제' }))
    await user.click(within(screen.getByRole('dialog', { name: 'Action 삭제' })).getByRole('button', { name: '취소' }))
    // then: 행 수가 그대로다
    expect(bodyRows(table)).toHaveLength(before)
  })

  // user는 Action 추가·수정·삭제 버튼 없이 목록만 본다.
  // 테스트 코드: AC-072
  it('shows a viewer the actions without register, edit or delete controls', async () => {
    // when: user가 Actions 탭을 연다
    const { table } = await openActions(1, '한빛은행 ITDR 도입', 'user')
    // then: 추가 버튼과 수정·삭제 버튼이 없다
    expect(screen.queryByRole('button', { name: 'Action 추가' })).not.toBeInTheDocument()
    expect(within(table).queryByRole('button', { name: '수정' })).not.toBeInTheDocument()
    expect(within(table).queryByRole('button', { name: '삭제' })).not.toBeInTheDocument()
    // then: 행은 보인다
    expect(bodyRows(table).length).toBeGreaterThan(1)
  })
})

describe('Actions 검색', () => {
  async function search() {
    const view = await openActions(1, '한빛은행 ITDR 도입')
    return { ...view, form: screen.getByRole('search', { name: 'Action 검색' }) }
  }

  // 검색 바는 정해진 칸과 버튼을 갖고 정렬 입력이 없으며 수행일·기한은 전체이고 날짜 칸이 없다.
  // 테스트 코드: NA-052
  it('offers the five conditions and no sort input', async () => {
    // when: Actions 탭을 연다.
    const { form } = await search()
    // then: 정렬 칸은 없고 유형·담당자·키워드·수행일·기한 칸이 있다.
    expect(within(form).queryByLabelText('정렬')).not.toBeInTheDocument()
    for (const label of ['유형', '담당자', '키워드', '수행일', '기한']) {
      expect(within(form).getByLabelText(label)).toBeVisible()
    }
    // then: 수행일·기한은 "전체"이고 날짜 칸은 없다.
    expect(within(form).getByLabelText('수행일')).toHaveDisplayValue('전체')
    expect(within(form).getByLabelText('기한')).toHaveDisplayValue('전체')
    for (const label of ['수행일 시작', '수행일 끝', '기한 시작', '기한 끝']) {
      expect(within(form).queryByLabelText(label)).not.toBeInTheDocument()
    }
  })

  // 키워드로 검색하면 맞는 Action 한 행만 나온다.
  // 테스트 코드: NA-053
  it('searches by keyword', async () => {
    // given: 한빛은행 Deal의 Actions 탭이다.
    const { user, form, table } = await search()
    // when: 키워드 "ROI"로 검색한다.
    await user.type(within(form).getByLabelText('키워드'), 'ROI')
    await user.click(within(form).getByRole('button', { name: '검색' }))
    // then: "임원 보고용 ROI 자료 전달" 한 행만 나온다.
    await waitFor(() => expect(bodyRows(table)).toHaveLength(1))
    expect(bodyRows(table)[0]).toHaveTextContent('임원 보고용 ROI 자료 전달')
  })

  // 유형으로 검색하면 그 유형의 행만 나온다.
  // 테스트 코드: NA-053
  it('searches by type', async () => {
    // given: 한빛은행 Deal의 Actions 탭이다.
    const { user, form, table } = await search()
    await within(form).findByRole('option', { name: '이메일' })
    // when: 유형 "이메일"로 검색한다.
    await user.selectOptions(within(form).getByLabelText('유형'), '이메일')
    await user.click(within(form).getByRole('button', { name: '검색' }))
    // then: 이메일 행만 나온다.
    await waitFor(() => expect(bodyRows(table)[0]).toHaveTextContent('이메일'))
    for (const row of bodyRows(table)) expect(within(row).getAllByText('이메일').length).toBeGreaterThan(0)
  })

  // 담당자 선택지에는 퇴사자도 "(퇴사)"로 있고 그 담당자로 검색하면 빈 결과 문구가 나온다.
  // 테스트 코드: NA-053
  it('searches by actor including resigned users', async () => {
    // given: 한빛은행 Deal의 Actions 탭이다.
    const { user, form } = await search()
    const actor = within(form).getByLabelText('담당자')
    await waitFor(() => expect(within(actor).getByRole('option', { name: '강퇴사(퇴사)' })).toBeInTheDocument())
    // when: 담당자 "강퇴사(퇴사)"로 검색한다.
    await user.selectOptions(actor, '강퇴사(퇴사)')
    await user.click(within(form).getByRole('button', { name: '검색' }))
    // then: "조건에 맞는 Action이 없습니다."가 나온다.
    expect(await screen.findByText('조건에 맞는 Action이 없습니다.')).toBeVisible()
  })

  // Due Date 머리글을 누르면 Due Date 오름차순으로 보인다.
  // 테스트 코드: NA-063
  it('sorts by due date soonest first with the Due Date header', async () => {
    // given: 한빛은행 Deal의 Actions 탭이다.
    const { user, table } = await search()
    // when: Due Date 머리글을 누른다.
    await user.click(within(table).getByRole('button', { name: 'Due Date' }))
    // then: Due Date가 빠른 순서로 보인다.
    await waitFor(() => {
      const dues = bodyRows(table).map((r) => /\d{4}-\d{2}-\d{2}/.exec(within(r).getAllByRole('cell')[6]?.textContent ?? '')?.[0] ?? '')
      expect(dues.length).toBeGreaterThan(1)
      expect([...dues].sort()).toEqual(dues)
    })
  })

  // 기한·수행일을 직접 지정한 범위로 검색하면 조건에 맞는 행이 없을 때 빈 결과 문구가 나오고 초기화하면 표가 돌아온다.
  // 테스트 코드: NA-057
  it('filters by a due date range and an acted date range', async () => {
    // given: 한빛은행 Deal의 Actions 탭이다.
    const { user, form } = await search()
    // when: 기한을 "직접 지정"으로 하고 시작을 2100-01-01로 쓴 뒤 검색한다.
    await user.selectOptions(within(form).getByLabelText('기한'), '직접 지정')
    await user.type(within(form).getByLabelText('기한 시작'), '2100-01-01')
    await user.click(within(form).getByRole('button', { name: '검색' }))
    // then: 빈 결과 문구가 나온다.
    expect(await screen.findByText('조건에 맞는 Action이 없습니다.')).toBeVisible()
    // when: "초기화"를 누른다.
    await user.click(within(form).getByRole('button', { name: '초기화' }))
    // then: 표가 다시 보인다.
    expect(await screen.findByRole('table', { name: 'Action 목록' })).toBeVisible()
    // when: 수행일을 "직접 지정"으로 하고 끝을 2000-01-01로 쓴 뒤 검색한다.
    await user.selectOptions(within(form).getByLabelText('수행일'), '직접 지정')
    await user.type(within(form).getByLabelText('수행일 끝'), '2000-01-01')
    await user.click(within(form).getByRole('button', { name: '검색' }))
    // then: 빈 결과 문구가 나온다.
    expect(await screen.findByText('조건에 맞는 Action이 없습니다.')).toBeVisible()
  })

  // 초기화하면 모든 Action이 다시 보이고 키워드 칸이 빈다.
  // 테스트 코드: NA-059
  it('shows the reset result with every action again', async () => {
    // given: 키워드 "ROI"로 검색해 1행이 보인다.
    const { user, form, table } = await search()
    const total = bodyRows(table).length
    await user.type(within(form).getByLabelText('키워드'), 'ROI')
    await user.click(within(form).getByRole('button', { name: '검색' }))
    await waitFor(() => expect(bodyRows(table)).toHaveLength(1))
    // when: "초기화"를 누른다.
    await user.click(within(form).getByRole('button', { name: '초기화' }))
    // then: 모든 Action이 다시 보이고 키워드 칸이 비어 있다.
    await waitFor(() => expect(bodyRows(table)).toHaveLength(total))
    expect(within(form).getByLabelText('키워드')).toHaveValue('')
  })

  // 거꾸로 된 직접 지정 범위는 화면이 막지 않고 서버 문구를 탭 오류 배너로 보인다.
  // 테스트 코드: NA-062
  it('shows the server message in the tab banner when the custom range is reversed', async () => {
    // given: 한빛은행 Deal의 Actions 탭이다.
    const { user, form } = await search()
    // when: 수행일을 "직접 지정"으로 2026-10-21 ~ 2026-10-20으로 쓰고 검색한다.
    await user.selectOptions(within(form).getByLabelText('수행일'), '직접 지정')
    await user.type(within(form).getByLabelText('수행일 시작'), '20261021')
    await user.type(within(form).getByLabelText('수행일 끝'), '20261020')
    await user.click(within(form).getByRole('button', { name: '검색' }))
    // then: 탭 오류 배너에 서버 문구가 보인다.
    expect(await screen.findByRole('alert')).toHaveTextContent('수행일 범위의 시작은 끝보다 늦을 수 없습니다.')
  })
})

describe('Action 수정·삭제 버튼 권한', () => {
  const EDIT_TITLE = '본인 Action 또는 admin만 수정할 수 있습니다.'
  const DELETE_TITLE = '본인 Action 또는 admin만 삭제할 수 있습니다.'

  async function openAs(userId: number) {
    const view = await renderAt(await detailPath(1, '?tab=actions'), { userId })
    await screen.findByRole('heading', { level: 1, name: '한빛은행 ITDR 도입' })
    const table = await screen.findByRole('table', { name: 'Action 목록' })
    return { ...view, table }
  }

  // 담당자 본인의 모든 행에서 수정·삭제가 켜진다.
  // 테스트 코드: AC-073
  it('enables edit and delete on every row of the owner who registered them', async () => {
    // when: 담당자 본인(kim)이 Actions 탭을 연다
    const { table } = await openAs(USER_ID.kim)

    // then: 모든 행의 수정·삭제가 켜져 있고 title이 없다
    const rows = bodyRows(table)
    expect(rows.length).toBeGreaterThan(1)
    for (const row of rows) {
      expect(within(row).getByRole('button', { name: '수정' })).toBeEnabled()
      expect(within(row).getByRole('button', { name: '삭제' })).toBeEnabled()
      expect(within(row).getByRole('button', { name: '수정' })).not.toHaveAttribute('title')
    }
  })

  // 다른 sales의 행은 이유 title과 함께 꺼진다.
  // 테스트 코드: AC-073
  it('disables both buttons with the reason as title on actions of another sales', async () => {
    // when: 다른 sales(park)가 Actions 탭을 연다
    const { table } = await openAs(USER_ID.park)

    // then: 모든 행의 수정·삭제가 꺼져 있고 이유 title이 있다
    const rows = bodyRows(table)
    expect(rows.length).toBeGreaterThan(1)
    for (const row of rows) {
      const edit = within(row).getByRole('button', { name: '수정' })
      const remove = within(row).getByRole('button', { name: '삭제' })
      expect(edit).toBeDisabled()
      expect(edit).toHaveAttribute('title', EDIT_TITLE)
      expect(remove).toBeDisabled()
      expect(remove).toHaveAttribute('title', DELETE_TITLE)
    }
  })

  // 다른 sales에게도 관리 열과 추가 버튼은 보인다.
  // 테스트 코드: AC-073
  it('still shows the manage column and the register button to that other sales', async () => {
    // when: 다른 sales(park)가 Actions 탭을 연다
    const { table } = await openAs(USER_ID.park)

    // then: 관리 열 머리글과 추가 버튼이 보인다
    expect(within(table).getByRole('columnheader', { name: '관리' })).toBeVisible()
    expect(screen.getByRole('button', { name: 'Action 추가' })).toBeVisible()
  })

  // 꺼진 수정 버튼을 눌러도 수정 폼이 열리지 않는다.
  // 테스트 코드: AC-073
  it('does not open the edit form when a disabled edit button is clicked', async () => {
    // given: 다른 sales(park)가 Actions 탭을 연다
    const { user, table } = await openAs(USER_ID.park)

    // when: 꺼진 수정 버튼을 누른다
    await user.click(within(bodyRows(table)[0]!).getByRole('button', { name: '수정' }))

    // then: 수정 팝업이 없다
    expect(screen.queryByRole('dialog', { name: 'Action 수정' })).not.toBeInTheDocument()
  })

  // admin은 남의 행을 포함해 모든 행의 수정·삭제가 켜진다.
  // 테스트 코드: AC-073
  it('enables both buttons on every row for admin, including actions of other users', async () => {
    // when: admin이 Actions 탭을 연다
    const { table } = await openAs(USER_ID.root)

    // then: 모든 행의 수정·삭제가 켜져 있다
    for (const row of bodyRows(table)) {
      expect(within(row).getByRole('button', { name: '수정' })).toBeEnabled()
      expect(within(row).getByRole('button', { name: '삭제' })).toBeEnabled()
    }
  })

  // 두 사용자의 행이 섞이면 본인 행만 켜진다.
  // 테스트 코드: AC-073
  it('enables only the rows of the viewer when rows of two different users are mixed', async () => {
    // given: 다른 sales(park)가 Actions 탭을 연다
    const { user, table } = await openAs(USER_ID.park)
    // when: 새 Action을 등록한다
    await user.click(screen.getByRole('button', { name: 'Action 추가' }))
    const form = screen.getByRole('form', { name: 'Action 추가' })
    await typeAction(user, form, '통화')
    await user.type(within(form).getByLabelText('진행사항'), '박영업 후속 연락')
    await user.type(within(form).getByLabelText('Next Action'), '미팅 일정 확정')
    await user.type(within(form).getByLabelText('Due Date'), '2026-12-20')
    // when: 입력을 채우고 등록한다
    await user.click(within(form).getByRole('button', { name: '등록' }))
    await waitFor(() => expect(bodyRows(table)[0]).toHaveTextContent('박영업 후속 연락'))

    // then: 새(본인) 행은 켜지고 남의 행은 꺼진다
    const rows = bodyRows(table)
    expect(within(rows[0]!).getByRole('button', { name: '수정' })).toBeEnabled()
    expect(within(rows[0]!).getByRole('button', { name: '삭제' })).toBeEnabled()
    expect(within(rows[1]!).getByRole('button', { name: '수정' })).toBeDisabled()
    expect(within(rows[1]!).getByRole('button', { name: '삭제' })).toBeDisabled()
  })

  // user 역할에는 관리 열이 아예 없다.
  // 테스트 코드: AC-072
  it('shows a user-role viewer no manage column at all', async () => {
    // when: user가 Actions 탭을 연다
    const { table } = await openAs(USER_ID.han)

    // then: 관리 열 머리글과 수정·삭제 버튼이 없다
    expect(within(table).queryByRole('columnheader', { name: '관리' })).not.toBeInTheDocument()
    expect(within(table).queryByRole('button', { name: '수정' })).not.toBeInTheDocument()
    expect(within(table).queryByRole('button', { name: '삭제' })).not.toBeInTheDocument()
  })
})
