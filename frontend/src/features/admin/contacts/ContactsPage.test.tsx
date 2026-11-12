import { screen, waitFor, within } from '@testing-library/react'
import { afterEach, describe, expect, it, vi } from 'vitest'
import { gateway } from '../../../gateway'
import { renderAt } from '../../../test/mockApp'

afterEach(() => vi.restoreAllMocks())

/** 게이트웨이가 실제로 던지는 ApiError 하나(로그아웃 상태의 me() → 401). 로그인 전에 얻는다. */
async function serverError(): Promise<unknown> {
  await gateway.auth.logout()
  return gateway.auth.me().catch((e: unknown) => e)
}

type Rendered = Awaited<ReturnType<typeof renderAt>>

async function openContacts() {
  const view = await renderAt('/admin/contacts', { role: 'admin' })
  await screen.findAllByRole('row', { name: /한빛은행/ })
  return view
}

function bodyRows() {
  return screen.getAllByRole('row').slice(1)
}

function rowOf(company: string, name: string) {
  return within(screen.getByRole('row', { name: new RegExp(`${company}.*${name}`) }))
}

async function search(user: Rendered['user'], keyword: string) {
  const box = screen.getByLabelText('검색어')
  await user.clear(box)
  await user.type(box, keyword)
  await user.click(screen.getByRole('button', { name: '검색' }))
}

async function fill(user: Rendered['user'], values: Partial<Record<'회사명' | '담당자명' | '직급' | '이메일' | '전화', string>>) {
  for (const [label, value] of Object.entries(values)) {
    const input = screen.getByLabelText(label)
    await user.clear(input)
    if (value) await user.type(input, value)
  }
}

describe('contacts 목록 (T-ADMIN-07)', () => {
  // 관리 화면은 8칸 표로 첫 20건을 보이고 없는 값은 '-', 연결 Deal 수를 보인다
  // 테스트 코드: CT-072
  it('lists the first page with company, name, title, email, phone and linked deal count', async () => {
    // when: 첫 페이지를 읽는다 (전제: admin이 연락처 24건이 있는 관리 화면을 연다)
    await openContacts()

    // then: 머리글 8칸, 20행, 값이 없는 칸의 '-', 연결 Deal 수와 행마다의 수정·삭제 버튼이 보인다
    for (const header of ['구분', '회사명', '담당자명', '직급', '이메일', '전화', '연결 Deal', '작업']) {
      expect(screen.getByRole('columnheader', { name: header })).toBeInTheDocument()
    }
    expect(bodyRows()).toHaveLength(20)
    const row = rowOf('한빛은행', '정민수')
    expect(row.getByText('과장')).toBeInTheDocument()
    expect(row.getByText(/@hanbit\.test$/)).toBeInTheDocument()
    expect(row.getByText('1')).toBeInTheDocument()
    expect(row.getByRole('button', { name: '수정' })).toBeInTheDocument()
    expect(row.getByRole('button', { name: '삭제' })).toBeInTheDocument()
    expect(rowOf('미래전자', '권나연').getByText('-')).toBeInTheDocument() // 이메일 없는 연락처
  })

  // 20건을 넘으면 페이저로 다음 페이지를 본다
  // 테스트 코드: CT-073
  it('pages through all 24 contacts', async () => {
    // given: 연락처 24건의 첫 페이지
    const { user } = await openContacts()

    // when: '다음'을 누른다
    await user.click(screen.getByRole('button', { name: '다음' }))

    // then: 나머지 4건이 보이고 '다음'이 비활성이다
    await waitFor(() => expect(bodyRows()).toHaveLength(4))
    expect(screen.getByRole('button', { name: '다음' })).toBeDisabled()
  })

  // 구분을 고르면 그 종류만 보인다
  // 테스트 코드: CT-074
  it('filters by kind', async () => {
    // given: 고객과 파트너 연락처가 섞인 목록
    const { user } = await openContacts()

    await user.selectOptions(screen.getByLabelText('구분'), '파트너')

    // when: 구분을 '파트너'로 바꾼다
    await screen.findAllByRole('row', { name: /에이원시스템/ })

    // then: 파트너 7건만 보인다
    await waitFor(() => expect(bodyRows()).toHaveLength(7))
    expect(screen.queryByRole('row', { name: /한빛은행/ })).not.toBeInTheDocument()
    expect(screen.getAllByText('파트너', { selector: 'td .badge' })).toHaveLength(7)
  })

  // 검색어는 버튼·Enter로 첫 페이지부터 찾는다
  // 테스트 코드: CT-075
  it('searches by keyword from the first page, also with Enter', async () => {
    // given: 둘째 페이지를 보고 있다
    const { user } = await openContacts()

    // when: 검색어 '한빛'을 입력하고 Enter를 누른다
    await user.click(screen.getByRole('button', { name: '다음' }))

    await user.clear(screen.getByLabelText('검색어'))
    await user.type(screen.getByLabelText('검색어'), '한빛{Enter}')

    // then: 첫 페이지부터 일치하는 3건이 보인다
    await waitFor(() => expect(bodyRows()).toHaveLength(3))
    expect(screen.getByRole('row', { name: /임태호/ })).toBeInTheDocument()
  })

  // 검색어를 비우고 검색하면 전체 목록으로 돌아온다
  // 테스트 코드: CT-076
  it('shows the full list again when the keyword is emptied', async () => {
    // given: '한빛'으로 검색한 결과 3건
    const { user } = await openContacts()

    await search(user, '한빛')
    await waitFor(() => expect(bodyRows()).toHaveLength(3))

    // when: 검색어를 비우고 검색한다
    await user.clear(screen.getByLabelText('검색어'))
    await user.click(screen.getByRole('button', { name: '검색' }))

    // then: 전체 첫 페이지 20건이 보인다
    await waitFor(() => expect(bodyRows()).toHaveLength(20))
  })

  // 이메일로도 찾는다
  // 테스트 코드: CT-075
  it('searches by email too', async () => {
    // given: 연락처 목록
    const { user } = await openContacts()

    // when: 이메일 일부로 검색한다
    await search(user, 'bae1@nuri')

    // then: 그 이메일의 연락처 한 건이 보인다
    await waitFor(() => expect(bodyRows()).toHaveLength(1))
    expect(screen.getByRole('row', { name: /배성훈/ })).toBeInTheDocument()
  })

  // 조건이 있는데 결과가 없으면 조건용 빈 문구를 보인다
  // 테스트 코드: CT-077
  it('shows an empty search message when nothing matches', async () => {
    // given: 연락처 목록
    const { user } = await openContacts()

    // when: 없는 회사로 검색한다
    await search(user, '없는회사')

    // then: '조건에 맞는 연락처가 없습니다.'가 보인다
    expect(await screen.findByText('조건에 맞는 연락처가 없습니다.')).toBeInTheDocument()
  })

  // 조건 없이 연락처가 없으면 등록 안내 빈 문구를 보인다
  // 테스트 코드: CT-077
  it('shows the empty message without conditions when there are no contacts', async () => {
    // given: 연락처가 하나도 없다
    vi.spyOn(gateway.contacts, 'list').mockResolvedValue({ items: [], total: 0, offset: 0, limit: 20 })

    // when: 관리 화면을 연다
    await renderAt('/admin/contacts', { role: 'admin' })

    // then: '등록된 연락처가 없습니다.'가 보인다
    expect(await screen.findByText('등록된 연락처가 없습니다.')).toBeInTheDocument()
  })

  // 목록을 읽지 못하면 오류 배너에 서버 문구를 보인다
  // 테스트 코드: CT-078
  it('shows the message when the list cannot be loaded', async () => {
    // given: 목록 조회가 서버 오류로 실패한다
    vi.spyOn(gateway.contacts, 'list').mockRejectedValue(await serverError())

    // when: 관리 화면을 연다
    await renderAt('/admin/contacts', { role: 'admin' })

    // then: 오류 배너에 서버 문구가 보인다
    expect(await screen.findByRole('alert')).toHaveTextContent('로그인이 필요합니다.')
  })
})

describe('contacts 등록 (T-ADMIN-08)', () => {
  async function openCreate(user: Rendered['user']) {
    await user.click(screen.getByRole('button', { name: '연락처 등록' }))
    return screen.findByRole('form', { name: '연락처 등록' })
  }

  // 고객 연락처를 등록하면 폼이 닫히고 알림과 함께 목록에 Deal 0으로 나온다
  // 테스트 코드: CT-079
  it('creates a customer contact without an email', async () => {
    // given: 등록 폼을 연다
    const { user } = await openContacts()
    await openCreate(user)

    await user.selectOptions(screen.getByLabelText('연락처 구분'), '고객')
    await fill(user, { 회사명: '새솔물산', 담당자명: '홍길동', 직급: '대리' })

    // when: 고객 구분과 회사명·담당자명·직급만 채워 저장한다
    await user.click(screen.getByRole('button', { name: '저장' }))

    // then: 폼이 닫히고 등록 알림이 보이며 검색하면 연결 Deal 0인 행이 나온다
    await waitFor(() => expect(screen.queryByRole('form', { name: '연락처 등록' })).not.toBeInTheDocument())
    expect(screen.getByRole('status')).toHaveTextContent('연락처를 등록했습니다.')
    await search(user, '새솔물산')
    const row = within(await screen.findByRole('row', { name: /새솔물산/ }))
    expect(row.getByText('홍길동')).toBeInTheDocument()
    expect(row.getByText('0')).toBeInTheDocument()
  })

  // 파트너 연락처를 등록하면 파트너 목록에 나온다
  // 테스트 코드: CT-079
  it('creates a partner contact', async () => {
    // given: 등록 폼을 연다
    const { user } = await openContacts()
    await openCreate(user)

    await user.selectOptions(screen.getByLabelText('연락처 구분'), '파트너')
    await fill(user, { 회사명: '새파트너', 담당자명: '김파트', 이메일: 'p@newpartner.test', 전화: '02-1234-5678' })

    // when: 파트너 구분으로 모든 칸을 채워 저장한다
    await user.click(screen.getByRole('button', { name: '저장' }))

    await user.selectOptions(screen.getByLabelText('구분'), '파트너')

    // then: 파트너 구분 목록에 새 행이 보인다
    expect(await screen.findByRole('row', { name: /새파트너/ })).toBeInTheDocument()
  })

  // 등록 폼은 입력 중 공백을 바로 지우고 안내한다
  // 테스트 코드: CT-080
  it('removes whitespace while typing and tells the user', async () => {
    // given: 등록 폼을 연다
    const { user } = await openContacts()
    await openCreate(user)

    // when: 회사명에 공백이 든 글을 입력한다
    await user.type(screen.getByLabelText('회사명'), '새 솔 물산')

    // then: 공백이 지워지고 '공백은 입력할 수 없습니다.' 안내가 보인다
    expect(screen.getByLabelText('회사명')).toHaveValue('새솔물산')
    expect(screen.getByText('공백은 입력할 수 없습니다.')).toBeInTheDocument()
  })

  // 직급 칸은 공백을 허용한다
  // 테스트 코드: CT-080
  it('allows spaces inside the title in the form', async () => {
    // given: 등록 폼을 연다
    const { user } = await openContacts()
    await openCreate(user)

    // when: 직급에 공백이 든 글을 입력한다
    await user.type(screen.getByLabelText('직급'), '수석 과장')

    // then: 공백이 그대로 남고 공백 안내는 없다
    expect(screen.getByLabelText('직급')).toHaveValue('수석 과장')
    expect(screen.queryByText('공백은 입력할 수 없습니다.')).not.toBeInTheDocument()
  })

  // 필수 칸이 비면 요청 없이 칸 아래에 문구를 보인다
  // 테스트 코드: CT-081
  it('shows required messages and does not send a request when empty', async () => {
    // given: 비어 있는 등록 폼
    const { user } = await openContacts()
    await openCreate(user)
    const create = vi.spyOn(gateway.contacts, 'create')

    // when: 저장을 누른다
    await user.click(screen.getByRole('button', { name: '저장' }))

    // then: 회사명·담당자명 필수 문구가 보이고 생성 요청은 없다
    expect(screen.getByText('회사명을 입력하세요.')).toBeInTheDocument()
    expect(screen.getByText('담당자명을 입력하세요.')).toBeInTheDocument()
    expect(create).not.toHaveBeenCalled()
  })

  // 이메일 형식이 틀리면 요청 없이 칸 아래에 문구를 보인다
  // 테스트 코드: CT-082
  it('shows the email format message', async () => {
    // given: 회사명·담당자명을 채우고 틀린 이메일을 넣은 폼
    const { user } = await openContacts()
    await openCreate(user)

    const create = vi.spyOn(gateway.contacts, 'create')

    await fill(user, { 회사명: '새솔물산', 담당자명: '홍길동', 이메일: 'nope' })

    // when: 저장을 누른다
    await user.click(screen.getByRole('button', { name: '저장' }))

    // then: 이메일 형식 문구가 보이고 생성 요청은 없다
    expect(screen.getByText('이메일 형식이 올바르지 않습니다.')).toBeInTheDocument()
    expect(create).not.toHaveBeenCalled()
  })

  // 전화 형식이 틀리면 요청 없이 칸 아래에 문구를 보인다
  // 테스트 코드: CT-082
  it('shows the phone format message', async () => {
    // given: 회사명·담당자명을 채우고 틀린 전화를 넣은 폼
    const { user } = await openContacts()
    await openCreate(user)
    const create = vi.spyOn(gateway.contacts, 'create')

    await fill(user, { 회사명: '새솔물산', 담당자명: '홍길동', 전화: '12-34' })

    // when: 저장을 누른다
    await user.click(screen.getByRole('button', { name: '저장' }))

    // then: 전화번호 형식 문구가 보이고 생성 요청은 없다
    expect(screen.getByText('전화번호 형식이 올바르지 않습니다.')).toBeInTheDocument()
    expect(create).not.toHaveBeenCalled()
  })

  // 서버가 같은 사람으로 거절하면 폼 안에 서버 문구를 보이고 폼을 유지한다
  // 테스트 코드: CT-083
  it('shows the server message for a contact that already exists', async () => {
    // given: 이미 있는 사람의 회사명·담당자명을 채운 폼
    const { user } = await openContacts()
    await openCreate(user)

    await fill(user, { 회사명: '미래전자', 담당자명: '권나연' })

    // when: 저장을 누른다
    await user.click(screen.getByRole('button', { name: '저장' }))

    // then: 오류 배너에 '이미 등록된 연락처입니다.'가 보이고 폼과 입력이 남는다
    expect(await screen.findByRole('alert')).toHaveTextContent('이미 등록된 연락처입니다.')
    expect(screen.getByRole('form', { name: '연락처 등록' })).toBeInTheDocument()
  })

  // 취소하면 요청 없이 폼이 닫힌다
  // 테스트 코드: CT-084
  it('closes the form with cancel', async () => {
    // given: 값을 채운 등록 폼
    const { user } = await openContacts()
    await openCreate(user)
    const create = vi.spyOn(gateway.contacts, 'create')
    await fill(user, { 회사명: '취소할회사', 담당자명: '홍길동' })

    // when: 취소를 누른다
    await user.click(screen.getByRole('button', { name: '취소' }))

    // then: 폼이 닫히고 생성 요청도 없다
    expect(screen.queryByRole('form', { name: '연락처 등록' })).not.toBeInTheDocument()
    expect(create).not.toHaveBeenCalled()
  })
})

describe('contacts 수정 (T-ADMIN-09)', () => {
  // 수정 폼은 현재 값과 공유 Deal 수 안내를 보이고 저장하면 알림과 함께 표에 반영된다
  // 테스트 코드: CT-085
  it('tells how many deals will reflect the change and saves it', async () => {
    // given: Deal 1건이 쓰는 연락처의 수정 폼
    const { user } = await openContacts()


    // when: 수정 폼을 연다
    await user.click(rowOf('한빛은행', '정민수').getByRole('button', { name: '수정' }))
    const form = await screen.findByRole('form', { name: '연락처 수정' })

    // then: 현재 값과 '1개 Deal' 안내가 보인다
    expect(within(form).getByText('이 연락처를 쓰는 1개 Deal에 모두 반영됩니다.')).toBeInTheDocument()
    expect(screen.getByLabelText('회사명')).toHaveValue('한빛은행')
    expect(screen.getByLabelText('담당자명')).toHaveValue('정민수')
    // when: 직급을 바꿔 저장한다
    await fill(user, { 직급: '부장' })
    await user.click(screen.getByRole('button', { name: '저장' }))

    // then: 폼이 닫히며 수정 알림과 새 직급이 표에 보인다
    await waitFor(() => expect(screen.queryByRole('form', { name: '연락처 수정' })).not.toBeInTheDocument())
    expect(screen.getByRole('status')).toHaveTextContent('연락처를 수정했습니다.')
    expect(await within(await screen.findByRole('row', { name: /정민수/ })).findByText('부장')).toBeInTheDocument()
  })

  // 참조 Deal이 없는 연락처의 수정 폼에는 공유 안내가 없다
  // 테스트 코드: CT-086
  it('does not show the sharing notice when no deal uses the contact', async () => {
    // given: 방금 등록해 Deal이 쓰지 않는 연락처
    const { user } = await openContacts()
    await user.click(screen.getByRole('button', { name: '연락처 등록' }))
    await fill(user, { 회사명: '새솔물산', 담당자명: '홍길동' })
    await user.click(screen.getByRole('button', { name: '저장' }))
    await search(user, '새솔물산')


    // when: 수정 폼을 연다
    await user.click(within(await screen.findByRole('row', { name: /새솔물산/ })).getByRole('button', { name: '수정' }))
    await screen.findByRole('form', { name: '연락처 수정' })

    // then: 공유 안내가 없다
    expect(screen.queryByText(/Deal에 모두 반영됩니다/)).not.toBeInTheDocument()
  })

  // 수정 폼도 공백 입력을 바로 지우고 안내한다
  // 테스트 코드: CT-080
  it('blocks whitespace on edit too', async () => {
    // given: 수정 폼
    const { user } = await openContacts()
    await user.click(rowOf('한빛은행', '정민수').getByRole('button', { name: '수정' }))
    await screen.findByRole('form', { name: '연락처 수정' })

    // when: 담당자명에 공백이 든 글을 입력한다
    await fill(user, { 담당자명: '정 민 수' })

    // then: 공백이 지워지고 안내가 보인다
    expect(screen.getByLabelText('담당자명')).toHaveValue('정민수')
    expect(screen.getByText('공백은 입력할 수 없습니다.')).toBeInTheDocument()
  })
})

describe('contacts 삭제 (T-ADMIN-10)', () => {
  async function createAndFind(user: Rendered['user']) {
    await user.click(screen.getByRole('button', { name: '연락처 등록' }))
    await fill(user, { 회사명: '새솔물산', 담당자명: '홍길동' })
    await user.click(screen.getByRole('button', { name: '저장' }))
    await search(user, '새솔물산')
    return screen.findByRole('row', { name: /새솔물산/ })
  }

  // 참조 중인 연락처 삭제는 대화상자를 닫고 배너에 건수 문구를 보이며 행이 남는다
  // 테스트 코드: CT-088
  it('refuses to delete a contact that deals use and says how many', async () => {
    // given: Deal 1건이 쓰는 연락처
    const { user } = await openContacts()

    // when: 삭제를 확인한다
    await user.click(rowOf('한빛은행', '정민수').getByRole('button', { name: '삭제' }))
    await user.click(within(await screen.findByRole('dialog', { name: '연락처 삭제' })).getByRole('button', { name: '삭제' }))

    // then: 대화상자가 닫히고 배너에 '연결된 Deal이 1건' 문구가 보이며 행이 남는다
    expect(await screen.findByRole('alert')).toHaveTextContent('연결된 Deal이 1건 있어 삭제할 수 없습니다.')
    expect(screen.queryByRole('dialog')).not.toBeInTheDocument()
    expect(screen.getByRole('row', { name: /정민수/ })).toBeInTheDocument()
  })

  // 참조 없는 연락처는 확인 뒤 삭제되고 알림을 보인다
  // 테스트 코드: CT-089
  it('deletes a contact nobody uses after confirmation', async () => {
    // given: Deal이 쓰지 않는 연락처 행
    const { user } = await openContacts()
    const created = await createAndFind(user)

    // when: 삭제를 누르고 대화상자에서 확인한다
    await user.click(within(created).getByRole('button', { name: '삭제' }))
    await user.click(within(await screen.findByRole('dialog')).getByRole('button', { name: '삭제' }))

    // then: 행이 사라지고 삭제 알림이 보인다
    await waitFor(() => expect(screen.queryByRole('row', { name: /새솔물산/ })).not.toBeInTheDocument())
    expect(screen.getByRole('status')).toHaveTextContent('새솔물산 홍길동 연락처를 삭제했습니다.')
  })

  // 삭제 확인을 취소하면 요청하지 않는다
  // 테스트 코드: CT-090
  it('does nothing when the confirmation is declined', async () => {
    // given: Deal이 쓰지 않는 연락처 행
    const { user } = await openContacts()
    const created = await createAndFind(user)
    const remove = vi.spyOn(gateway.contacts, 'remove')

    // when: 삭제를 누르고 대화상자에서 취소한다
    await user.click(within(created).getByRole('button', { name: '삭제' }))
    await user.click(within(await screen.findByRole('dialog')).getByRole('button', { name: '취소' }))

    // then: 삭제 요청이 없고 행이 남는다
    expect(remove).not.toHaveBeenCalled()
    expect(screen.getByRole('row', { name: /새솔물산/ })).toBeInTheDocument()
  })
})
