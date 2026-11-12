// 보기 화면은 App에서 React.lazy 청크이므로 첫 로딩이 기본 대기(1초)를 넘기지 않게 미리 읽어 둔다.
import './ReportViewPage'
import { screen, waitFor, within } from '@testing-library/react'
import { describe, expect, it } from 'vitest'
import { mockControl } from '../../../test/fake/default'
import { REPORT_TIMEOUT_MESSAGE, reportTimeout } from '../../../test/fake/errors'
import { renderAt } from '../../../test/mockApp'
import { openList, openView, saveDialog, setupReportClock, typeName } from '../../../test/reportScreen'
import { BROKEN_DEFINITION, MINE_PRIVATE, MINE_PUBLIC, OLD_PUBLIC, PARK_PRIVATE, PARK_PUBLIC, SAVED_SAMPLES, savedReport } from '../../../test/savedReports'

setupReportClock()

const NOT_FOUND_TEXT = '리포트를 찾을 수 없습니다. 삭제되었거나 볼 권한이 없습니다.'
const heading = (name: string) => screen.findByRole('heading', { level: 1, name })
/** "편집": 편집 화면으로 가는 링크(링크 모양 버튼이면 버튼). 없으면 null. */
const editControl = (): HTMLElement | null => screen.queryByRole('link', { name: '편집' }) ?? screen.queryByRole('button', { name: '편집' })
const resultReady = () => screen.findByRole('table', { name: '조회 결과' })

describe('보기 화면 앞 N자', () => {
  it('앞 N자를 저장한 컬럼은 데이터 칸을 자르고 전체 값을 title에 둔다', async () => {
    // given: Deal 이름에 앞 4자를 저장한 리포트
    const prefixed = savedReport({
      id: 16,
      name: '앞 N자 리포트',
      definition: { columns: [{ field: 'deal.name', prefixLength: 4, group: false }], conditions: [], combine: 'and', rowLimit: 100 },
    })
    // when: 보기 화면을 열고 첫 데이터 칸을 찾는다
    await openView(prefixed.id, { savedReports: [...SAVED_SAMPLES, prefixed] })
    const table = await resultReady()
    const [cell] = within(table).getAllByRole('cell')

    // then: 칸에는 앞 4자와 …만 보이고 title에 전체 값이 있다
    expect(cell).toHaveTextContent('Deal…')
    expect(cell).toHaveAttribute('title', 'Deal 이름 1')
  })
})

describe('보기 화면', () => {
  // 테스트 코드: RS-061
  it('저장 리포트를 실행해 메타·결과·생성 SQL을 보인다', async () => {
    // when: 내 공개 리포트의 보기 화면을 연다
    await openView(MINE_PUBLIC.id)

    // then: 이름·설명이 보이고 비공개 태그는 없다
    expect(await heading(MINE_PUBLIC.name)).toBeVisible()
    expect(screen.getByText(MINE_PUBLIC.description)).toBeVisible()
    expect(screen.queryByText('비공개')).not.toBeInTheDocument()
    // then: 메타에 수정 시각과 만든 사람이 있고 "수정:"은 없다
    const meta = screen.getByText(/2026-10-24 17:20/)
    expect(meta).toHaveTextContent('김영업')
    expect(meta).not.toHaveTextContent('수정:')
    // then: 결과 표 머리글과 읽기 전용 생성 SQL이 보인다
    const table = await resultReady()
    expect(within(table).getByRole('columnheader', { name: 'Vendor' })).toBeVisible()
    expect(within(table).getByRole('columnheader', { name: /^금액 합계\s?\(원\)$/ })).toBeVisible()
    expect(screen.getByText('생성 SQL 보기(읽기 전용)')).toBeVisible()
    expect(screen.getByText('SELECT … /* fake */')).toBeInTheDocument()
    expect(screen.queryByRole('textbox')).not.toBeInTheDocument()
    // then: 실행 요청이 한 번이고 설계 조회 기록은 없다
    expect(mockControl.savedReportRequests()).toEqual([{ op: 'run', id: 11 }])
    expect(mockControl.reportQueries()).toEqual([])
  })

  // 테스트 코드: RS-062
  it('최종 수정자가 만든 사람과 다르면 메타에 "수정: 이름"을 보인다', async () => {
    // when: 박영업이 만들고 김영업이 고친 공개 리포트를 연다
    await openView(PARK_PUBLIC.id)
    // then: 이름이 보인다
    expect(await heading(PARK_PUBLIC.name)).toBeVisible()
    // then: 메타에 만든 사람과 "수정: 김영업"이 있다
    const meta = screen.getByText(/2026-10-25 09:00/)
    expect(meta).toHaveTextContent('박영업')
    expect(meta).toHaveTextContent('수정: 김영업')
  })

  // 테스트 코드: RS-062
  it('비공개 리포트는 비공개 태그를 보인다', async () => {
    // when: 내 비공개 리포트를 연다
    await openView(MINE_PRIVATE.id)

    // then: 이름과 "비공개" 태그가 보인다
    expect(await heading(MINE_PRIVATE.name)).toBeVisible()
    expect(screen.getByText('비공개')).toBeVisible()
  })

  // 테스트 코드: RS-062
  it('퇴사한 만든 사람은 "(퇴사)"로 보인다', async () => {
    // when: 퇴사자가 만든 공개 리포트를 연다
    await openView(OLD_PUBLIC.id)

    // then: 메타의 만든 사람이 "강퇴사(퇴사)"다
    expect(await heading(OLD_PUBLIC.name)).toBeVisible()
    expect(screen.getByText(/2026-10-22 09:00/)).toHaveTextContent('강퇴사(퇴사)')
  })

  // 테스트 코드: RS-062
  it('admin은 남의 비공개 리포트를 열어 결과를 본다', async () => {
    // when: admin으로 남의 비공개 리포트를 연다
    await openView(PARK_PRIVATE.id, { role: 'admin' })

    // then: 이름과 "비공개" 태그가 보이고 결과 표가 나온다
    expect(await heading(PARK_PRIVATE.name)).toBeVisible()
    expect(screen.getByText('비공개')).toBeVisible()
    await resultReady()
  })

  // 테스트 코드: RS-061
  it('"다시 조회"를 누르면 저장 리포트를 다시 실행한다', async () => {
    // given: 보기 화면에 결과가 나와 있다
    const { user } = await openView(MINE_PUBLIC.id)
    await resultReady()

    // when: 다시 조회를 누른다
    await user.click(screen.getByRole('button', { name: '다시 조회' }))

    // then: 실행 요청이 두 번이 된다
    await waitFor(() => expect(mockControl.savedReportRequests().filter((r) => r.op === 'run')).toHaveLength(2))
  })

  // 테스트 코드: RS-061
  it('Action 필드를 쓰는 리포트는 Action 컬럼을 결과 표에 보인다', async () => {
    // when: Action 컬럼을 쓰는 리포트를 연다
    await openView(PARK_PUBLIC.id)

    // then: Deal 컬럼과 Action 컬럼 머리글이 보인다
    const table = await resultReady()

    expect(within(table).getByRole('columnheader', { name: 'Deal code' })).toBeVisible()
    expect(within(table).getByRole('columnheader', { name: '진행사항' })).toBeVisible()
  })
})

describe('보기 화면의 단추', () => {
  // 테스트 코드: RS-063
  it.each([
    ['sales', MINE_PUBLIC.id, true, true],
    ['sales', PARK_PUBLIC.id, true, false],
    ['user', MINE_PUBLIC.id, true, false],
    ['admin', PARK_PUBLIC.id, true, true],
    ['admin', PARK_PRIVATE.id, true, true],
  ] as const)('%s 역할의 리포트 %s: 편집 %s, 삭제 %s', async (role, id, edit, remove) => {
    // when: 역할별로 리포트의 보기 화면을 연다
    await openView(id, { role })
    await resultReady()

    // then: 다시 조회·복제는 항상 있고 편집·삭제는 권한에 따른다
    expect(screen.getByRole('button', { name: '다시 조회' })).toBeVisible()
    expect(screen.getByRole('button', { name: '복제' })).toBeVisible()
    expect(editControl() !== null).toBe(edit)
    expect(screen.queryByRole('button', { name: '삭제' }) !== null).toBe(remove)
    if (edit && editControl()?.tagName === 'A') expect(editControl()).toHaveAttribute('href', `/reports/${id}/edit`)
  })

  // 테스트 코드: RS-063
  it('삭제를 확인하면 목록으로 가고 그 리포트는 사라진다', async () => {
    // given: 내 리포트의 보기 화면
    const { user, location } = await openView(MINE_PUBLIC.id)
    await resultReady()

    // when: 삭제를 누른다
    await user.click(screen.getByRole('button', { name: '삭제' }))
    // then: 확인 문구가 보인다
    const dialog = await screen.findByRole('dialog', { name: '리포트 삭제' })
    expect(dialog).toHaveTextContent(`‘${MINE_PUBLIC.name}’ 리포트를 삭제할까요? 되돌릴 수 없습니다.`)
    // when: 확인 창에서 삭제를 누른다
    await user.click(within(dialog).getByRole('button', { name: '삭제' }))

    // then: 목록으로 가서 그 리포트가 없고 삭제 요청이 기록된다
    await waitFor(() => expect(location()).toBe('/reports'))
    expect(await screen.findByRole('table', { name: '리포트 목록' })).toBeVisible()
    expect(screen.queryByRole('link', { name: MINE_PUBLIC.name })).not.toBeInTheDocument()
    expect(mockControl.savedReportRequests().filter((r) => r.op === 'remove')).toEqual([{ op: 'remove', id: 11 }])
  })

  // 테스트 코드: RS-063
  it('삭제를 취소하면 화면에 머물고 요청이 없다', async () => {
    // given: 삭제 확인 창을 연다
    const { user, location } = await openView(MINE_PUBLIC.id)
    await resultReady()
    await user.click(screen.getByRole('button', { name: '삭제' }))

    // when: 취소를 누른다
    await user.click(within(await screen.findByRole('dialog', { name: '리포트 삭제' })).getByRole('button', { name: '취소' }))

    // then: 창이 닫히고 주소가 그대로이며 삭제 요청이 없다
    expect(screen.queryByRole('dialog')).not.toBeInTheDocument()
    expect(location()).toBe('/reports/11')
    expect(mockControl.savedReportRequests().filter((r) => r.op === 'remove')).toEqual([])
  })

  // 테스트 코드: RS-059
  it('보기 화면에서 복제하면 "복사본" 이름으로 시작해 새 리포트 편집 화면으로 간다', async () => {
    // when: 남의 공개 리포트의 보기 화면에서 복제를 누른다
    const { user, location } = await openView(PARK_PUBLIC.id)
    await resultReady()
    await user.click(screen.getByRole('button', { name: '복제' }))
    // then: 이름이 "복사본"으로 시작한다
    const dialog = await saveDialog()
    expect(within(dialog).getByRole('textbox', { name: '이름' })).toHaveValue(`${PARK_PUBLIC.name} 복사본`)
    // when: 이름을 바꿔 저장한다
    await typeName(user, dialog, '내 복제본')

    await user.click(within(dialog).getByRole('button', { name: '저장' }))

    // then: 새 리포트 편집 화면으로 가고 복제 요청이 기록된다
    await waitFor(() => expect(location()).toBe('/reports/16/edit'))
    expect(mockControl.savedReportRequests().filter((r) => r.op === 'copy')).toMatchObject([{ id: 13, body: { name: '내 복제본', visibility: 'public' } }])
  })

  // 테스트 코드: RS-060
  it('저장 정의가 지금 규칙과 맞지 않으면 복제 창 안에 서버 위반을 보인다', async () => {
    // given: 지금 규칙과 맞지 않는 저장 정의의 보기 화면에서 복제 창을 연다
    const { user, location } = await renderAt('/reports/20', { savedReports: [savedReport({ id: 20, name: '깨진 정의', definition: BROKEN_DEFINITION })] })
    await screen.findByText(/저장된 설계가 지금 규칙과 맞지 않습니다/)
    await user.click(screen.getByRole('button', { name: '복제' }))
    const dialog = await saveDialog()

    // when: 저장한다
    await user.click(within(dialog).getByRole('button', { name: '저장' }))

    // then: 창 안에 위반 문구가 보이고 주소는 그대로다
    expect(await within(dialog).findByRole('alert')).toHaveTextContent(/허용되지 않은 필드입니다: deal\.nope/)
    expect(screen.getByRole('dialog', { name: '리포트 저장' })).toBeVisible()
    expect(location()).toBe('/reports/20')
  })

  // 테스트 코드: RS-063
  it('편집 링크는 편집 화면으로 간다', async () => {
    // given: 내 리포트의 보기 화면
    const { user, location } = await openView(MINE_PUBLIC.id)
    await resultReady()

    // when: 편집을 누른다
    await user.click(editControl() as HTMLElement)

    // then: /reports/11/edit로 간다
    expect(location()).toBe('/reports/11/edit')
  })
})

describe('보기 화면의 실패', () => {
  // 테스트 코드: RS-065
  it('지금 규칙과 맞지 않는 저장 정의는 위반 안내를 보이고 편집은 남는다', async () => {
    // when: 지금 카탈로그에 없는 필드를 쓰는 리포트를 연다
    await renderAt('/reports/20', { savedReports: [savedReport({ id: 20, name: '깨진 정의', definition: BROKEN_DEFINITION })] })

    // then: 이름이 보이고 위반 안내와 위반 문구가 나오며 결과 표는 없고 편집은 있다
    expect(await heading('깨진 정의')).toBeVisible()
    expect(await screen.findByText(/저장된 설계가 지금 규칙과 맞지 않습니다\. 편집에서 고치세요/)).toBeVisible()
    expect(screen.getByText(/허용되지 않은 필드입니다: deal\.nope/)).toBeVisible()
    expect(editControl()).not.toBeNull()
    expect(screen.queryByRole('table', { name: '조회 결과' })).not.toBeInTheDocument()
  })

  // 테스트 코드: RS-064
  it('숨긴 리포트는 찾을 수 없음 안내를 보이고 목록 링크가 있다', async () => {
    // when: 남의 비공개 리포트를 연다
    const { user, location } = await openView(PARK_PRIVATE.id)

    // then: 안내가 보이고 삭제 버튼과 실행 요청이 없다
    expect(await screen.findByText(NOT_FOUND_TEXT)).toBeVisible()
    expect(screen.queryByRole('button', { name: '삭제' })).not.toBeInTheDocument()
    expect(mockControl.savedReportRequests().filter((r) => r.op === 'run')).toHaveLength(0)

    // when: 리포트 목록 링크를 누른다
    await user.click(screen.getByRole('link', { name: '리포트 목록' }))

    // then: /reports로 간다
    expect(location()).toBe('/reports')
  })

  // 테스트 코드: RS-064
  it.each(['abc', '0', '9007199254740991'])('잘못된 id %s는 찾을 수 없음 안내를 보인다', async (id) => {
    // when: 잘못된 id로 보기 화면을 연다
    await renderAt(`/reports/${id}`, { savedReports: SAVED_SAMPLES })

    // then: 찾을 수 없음 안내가 보인다
    expect(await screen.findByText(NOT_FOUND_TEXT)).toBeVisible()
  })

  // 테스트 코드: RS-065
  it('시간 초과는 서버 문구를 보이고 "다시 조회"가 켜져 있다', async () => {
    // given: 실행이 시간 초과되도록 정한 목록 화면
    const { user } = await openList()
    mockControl.setReportQueryHandler(() => {
      throw reportTimeout()
    })

    // when: 리포트 이름을 눌러 연다
    await user.click(screen.getByRole('link', { name: MINE_PUBLIC.name }))

    // then: 시간 초과 문구가 보이고 다시 조회가 켜져 있다
    expect(await screen.findByText(REPORT_TIMEOUT_MESSAGE)).toBeVisible()
    expect(screen.getByRole('button', { name: '다시 조회' })).toBeEnabled()
  })
})
