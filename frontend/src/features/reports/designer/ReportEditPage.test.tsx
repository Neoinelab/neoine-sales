// 편집 화면은 App에서 React.lazy 청크이므로 첫 로딩이 기본 대기(1초)를 넘기지 않게 미리 읽어 둔다.
import './ReportEditPage'
import { screen, waitFor, within } from '@testing-library/react'
import { describe, expect, it } from 'vitest'
import { gateway } from '../../../gateway'
import { mockControl } from '../../../test/fake/default'
import { renderAt } from '../../../test/mockApp'
import { showTab } from '../../../test/reportLayout'
import { addCountedColumn, chipButton, chipItems, chipTexts, lastQuery, openEditor, runQuery, saveButton, saveDialog, settingsOf, setupReportClock, typeName, UNSAVED_MARK, waitForHiddenResult } from '../../../test/reportScreen'
import {
  BROKEN_DEFINITION,
  MINE_PUBLIC,
  NO_REPORT_ID,
  PARK_PUBLIC,
  SAVED_SAMPLES,
  VENDOR_DEFINITION,
  reportInput,
  savedReport,
} from '../../../test/savedReports'

setupReportClock()

const NOT_FOUND_TEXT = '리포트를 찾을 수 없습니다. 삭제되었거나 볼 권한이 없습니다.'
const COPY_NAME = `${MINE_PUBLIC.name} 복사본`
const dialogOf = async () => within(await saveDialog())
const unsavedMark = () => screen.queryByText(UNSAVED_MARK)

describe('저장된 설계 불러오기', () => {
  // 테스트 코드: RS-073
  it('저장된 설계를 싣고 한 번 조회하며 저장 안 됨 표시는 없다', async () => {
    // when: 내 공개 리포트의 편집 화면을 연다
    await openEditor(MINE_PUBLIC.id)

    // then: 제목과 저장된 컬럼·조건·행 수가 실려 있다
    expect(screen.getByRole('heading', { level: 1, name: MINE_PUBLIC.name })).toBeVisible()
    expect(chipItems()).toHaveLength(2)
    expect(chipTexts()[1]).toContain('금액 합계')
    expect(chipTexts()[1]).toContain('▼ 내림')
    expect(screen.queryByRole('combobox', { name: '정렬 방향' })).not.toBeInTheDocument()
    expect(screen.getByRole('combobox', { name: '최대 행' })).toHaveDisplayValue('1,000')
    expect(screen.getByRole('combobox', { name: '조건 1 필드' })).toBeVisible()
    // then: 조회가 한 번 갔고 저장 요청은 없으며 저장 안 됨 표시가 없다
    expect(mockControl.reportQueries()).toEqual([VENDOR_DEFINITION])
    expect(mockControl.savedReportRequests()).toEqual([])
    expect(unsavedMark()).not.toBeInTheDocument()
    // then: 저장·다른 이름으로 저장·되돌리기 버튼이 있고 초기화는 없다
    for (const name of ['저장', '다른 이름으로 저장', '되돌리기']) expect(screen.getByRole('button', { name })).toBeVisible()
    expect(screen.queryByRole('button', { name: '초기화' })).not.toBeInTheDocument()
  })

  it('저장된 컬럼 정렬을 그 컬럼 설정에서 보인다', async () => {
    // given: 편집 화면을 연다
    const { user } = await openEditor(MINE_PUBLIC.id)

    // when: 금액 합계 컬럼의 설정을 연다
    await user.click(chipButton(1))

    // then: 정렬이 내림차순이다
    expect(within(settingsOf('금액 합계')).getByRole('combobox', { name: '정렬' })).toHaveDisplayValue('내림차순')
  })

  // 테스트 코드: RS-073
  it('첫 결과 뒤에는 스스로 다시 조회하지 않는다', async () => {
    // given: 첫 조회가 끝난 편집 화면
    const { user } = await openEditor(MINE_PUBLIC.id)

    // when: 컬럼을 하나 더 넣는다
    await addCountedColumn(user, 'Deal code')

    // then: 조회는 여전히 한 번이다
    expect(mockControl.reportQueries()).toHaveLength(1)
  })

  // 테스트 코드: RS-073
  it('user 역할도 남의 공개 리포트를 편집 화면으로 연다', async () => {
    // when: user 역할로 남의 공개 리포트의 편집 화면을 연다
    await openEditor(PARK_PUBLIC.id, { role: 'user' })

    // then: 제목과 저장된 컬럼이 실린다
    expect(screen.getByRole('heading', { level: 1, name: PARK_PUBLIC.name })).toBeVisible()
    expect(chipItems()).toHaveLength(2)
  })

  // 테스트 코드: RS-064
  it('숨긴 리포트의 편집 화면은 찾을 수 없음 안내와 목록 링크를 보인다', async () => {
    // when: 남의 비공개 리포트의 편집 화면을 연다
    await renderAt('/reports/14/edit', { savedReports: SAVED_SAMPLES })

    // then: 안내와 목록 링크가 보이고 조회 요청이 없다
    expect(await screen.findByText(NOT_FOUND_TEXT)).toBeVisible()
    expect(screen.getByRole('link', { name: '리포트 목록' })).toHaveAttribute('href', '/reports')
    expect(mockControl.reportQueries()).toEqual([])
  })

  // 테스트 코드: RS-064
  it.each([String(NO_REPORT_ID), 'abc', '0', '1.5'])('잘못된 id %s의 편집 화면은 찾을 수 없음 안내를 보인다', async (id) => {
    // when: 잘못된 id로 편집 화면을 연다
    await renderAt(`/reports/${id}/edit`, { savedReports: SAVED_SAMPLES })

    // then: 찾을 수 없음 안내가 보인다
    expect(await screen.findByText(NOT_FOUND_TEXT)).toBeVisible()
  })

  it('카탈로그에 없어진 필드를 그대로 싣고 첫 조회 뒤 서버 위반을 보인다', async () => {
    // given: 지금 카탈로그에 없는 필드를 쓰는 리포트
    const broken = savedReport({ id: 20, name: '깨진 정의', definition: BROKEN_DEFINITION })
    // when: 편집 화면을 연다
    await renderAt('/reports/20/edit', { savedReports: [broken] })

    // then: 그 필드가 칩으로 실리고 서버 위반이 보이며 저장이 꺼져 있다
    expect(await screen.findByRole('heading', { level: 1, name: '깨진 정의' })).toBeVisible()
    expect((await screen.findAllByText(/허용되지 않은 필드입니다: deal\.nope/)).length).toBeGreaterThan(0)
    expect(chipItems()).toHaveLength(1)
    expect(chipTexts()[0]).toContain('deal.nope')
    expect(saveButton()).toBeDisabled()
  })
})

describe('저장 안 됨 표시와 덮어쓰기', () => {
  // 테스트 코드: RS-074
  it('변경하면 저장 안 됨이 붙고 덮어쓰면 사라진다', async () => {
    // given: 편집 화면(저장 안 됨 없음)
    const { user, location } = await openEditor(MINE_PUBLIC.id)
    expect(unsavedMark()).not.toBeInTheDocument()

    // when: 컬럼을 넣는다
    await addCountedColumn(user, 'Deal code')

    // then: 저장 안 됨(status)이 붙는다
    expect(screen.getByText(UNSAVED_MARK)).toBeVisible()
    expect(screen.getByText(UNSAVED_MARK)).toHaveAttribute('role', 'status')

    // when: 조회하고 저장 창을 연다
    await runQuery(user)
    await waitFor(() => expect(saveButton()).toBeEnabled())
    await user.click(saveButton())
    // then: 창 기본값이 저장된 이름·설명·공개 범위다
    const dialog = await dialogOf()
    expect(dialog.getByRole('textbox', { name: '이름' })).toHaveValue(MINE_PUBLIC.name)
    expect(dialog.getByRole('textbox', { name: '설명' })).toHaveValue(MINE_PUBLIC.description)
    expect(dialog.getByRole('combobox', { name: '공개 범위' })).toHaveDisplayValue('모든 사용자에게 보임')

    // when: 저장한다
    await user.click(dialog.getByRole('button', { name: '저장' }))

    // then: 창이 닫히고 저장 안 됨이 사라지며 주소와 제목이 그대로다
    await waitFor(() => expect(screen.queryByRole('dialog')).not.toBeInTheDocument())
    expect(unsavedMark()).not.toBeInTheDocument()
    expect(location()).toBe('/reports/11/edit')
    expect(screen.getByRole('heading', { level: 1, name: MINE_PUBLIC.name })).toBeVisible()
    // then: 덮어쓰기 요청이 revision 1로 가고 서버가 revision 2가 된다
    const [update] = mockControl.savedReportRequests()
    expect(update).toMatchObject({ op: 'update', id: 11, body: { revision: 1, name: MINE_PUBLIC.name, visibility: 'public' } })
    expect((update?.body as { definition: typeof VENDOR_DEFINITION }).definition.columns).toHaveLength(3)
    expect(await gateway.reports.get(11)).toMatchObject({ revision: 2 })
  })

  // 테스트 코드: RS-080
  it('변경을 원래대로 돌리면 저장 안 됨이 사라진다', async () => {
    // given: 편집 화면
    const { user } = await openEditor(MINE_PUBLIC.id)

    // when: 컬럼을 넣는다
    await addCountedColumn(user, 'Deal code')
    // then: 저장 안 됨이 붙는다
    expect(screen.getByText(UNSAVED_MARK)).toBeVisible()
    // when: 그 컬럼을 뺀다
    await user.click(screen.getByRole('button', { name: 'Deal code 빼기' }))

    // then: 저장 안 됨이 사라진다
    expect(unsavedMark()).not.toBeInTheDocument()
  })

  // 테스트 코드: RS-074
  it('첫 덮어쓰기 뒤 다음 덮어쓰기는 응답의 새 revision을 쓴다', async () => {
    // given: 편집 화면
    const { user } = await openEditor(MINE_PUBLIC.id)
    // when: 컬럼을 바꿔 조회하고 덮어쓰기를 두 번 한다
    for (const label of ['Deal code', 'Deal 이름']) {
      await showTab(user, 'design')
      await addCountedColumn(user, label)
      await runQuery(user)
      await waitFor(() => expect(saveButton()).toBeEnabled())
      await user.click(saveButton())
      await user.click((await dialogOf()).getByRole('button', { name: '저장' }))
      await waitFor(() => expect(screen.queryByRole('dialog')).not.toBeInTheDocument())
    }

    // then: 요청 revision이 1, 2이고 저장 안 됨이 없다
    expect(mockControl.savedReportRequests().map((r) => (r.body as { revision: number }).revision)).toEqual([1, 2])
    expect(unsavedMark()).not.toBeInTheDocument()
  })

  // 테스트 코드: RS-074
  it('덮어쓴 뒤 다시 바꾸면 저장 안 됨이 다시 붙는다', async () => {
    // given: 덮어쓰기를 마친 편집 화면
    const { user } = await openEditor(MINE_PUBLIC.id)
    await addCountedColumn(user, 'Deal code')
    await runQuery(user)
    await waitFor(() => expect(saveButton()).toBeEnabled())
    await user.click(saveButton())
    await user.click((await dialogOf()).getByRole('button', { name: '저장' }))
    await waitFor(() => expect(unsavedMark()).not.toBeInTheDocument())

    // when: 컬럼을 뺀다
    await showTab(user, 'design')
    await user.click(screen.getByRole('button', { name: 'Deal code 빼기' }))

    // then: 저장 안 됨이 다시 붙는다
    expect(screen.getByText(UNSAVED_MARK)).toBeVisible()
  })

  // 테스트 코드: RS-074
  it('이름을 바꿔 덮어쓰면 제목이 새 이름을 따른다', async () => {
    // given: 조회가 끝난 편집 화면과 저장 창
    const { user } = await openEditor(MINE_PUBLIC.id)
    await addCountedColumn(user, 'Deal code')
    await runQuery(user)
    await waitFor(() => expect(saveButton()).toBeEnabled())
    await user.click(saveButton())
    const dialog = await dialogOf()
    // when: 이름을 바꿔 저장한다
    await typeName(user, await saveDialog(), '이름을 바꿈')

    await user.click(dialog.getByRole('button', { name: '저장' }))

    // then: 제목이 새 이름이다
    expect(await screen.findByRole('heading', { level: 1, name: '이름을 바꿈' })).toBeVisible()
  })
})

describe('충돌', () => {
  /** 다른 사용자가 먼저 저장한 상황을 같은 계정의 순차 호출로 만든다(revision 1 → 2). */
  async function saveElsewhere(): Promise<void> {
    await gateway.reports.update(MINE_PUBLIC.id, { ...reportInput({ name: MINE_PUBLIC.name, description: MINE_PUBLIC.description }), revision: 1 })
  }

  // 테스트 코드: RS-075
  it('다른 사람이 먼저 저장했으면 충돌 경고와 "다른 이름으로 저장"이 나온다', async () => {
    // given: 설계를 바꿔 조회한 뒤 다른 사용자가 먼저 저장했다
    const { user } = await openEditor(MINE_PUBLIC.id)
    await addCountedColumn(user, 'Deal code')
    await runQuery(user)
    await waitFor(() => expect(saveButton()).toBeEnabled())
    await saveElsewhere()
    await user.click(saveButton())
    const dialog = await dialogOf()

    // when: 저장 창에서 저장한다
    await user.click(dialog.getByRole('button', { name: '저장' }))

    // then: 충돌 안내와 "다른 이름으로 저장", 아래 "닫기"가 보인다
    const alert = await dialog.findByRole('alert')
    expect(alert).toHaveTextContent('다른 사용자가 먼저 이 리포트를 저장했습니다')
    expect(within(alert).getByRole('button', { name: '다른 이름으로 저장' })).toBeVisible()
    expect(dialog.getByRole('button', { name: '닫기' })).toBeVisible()

    // when: 작성 탭으로 옮긴다
    await showTab(user, 'design')
    // then: 바꾼 설계와 저장 안 됨이 남아 있고 서버는 다른 사용자의 값이다
    expect(chipItems()).toHaveLength(3)
    expect(screen.getByText(UNSAVED_MARK)).toBeVisible()
    expect(await gateway.reports.get(MINE_PUBLIC.id)).toMatchObject({ revision: 2 })
  })

  // 테스트 코드: RS-075
  it('충돌 창을 닫아도 설계가 남는다', async () => {
    // given: 충돌 경고가 뜬 저장 창
    const { user } = await openEditor(MINE_PUBLIC.id)
    await addCountedColumn(user, 'Deal code')
    await runQuery(user)
    await waitFor(() => expect(saveButton()).toBeEnabled())
    await saveElsewhere()
    await user.click(saveButton())
    const dialog = await dialogOf()
    await user.click(dialog.getByRole('button', { name: '저장' }))
    await dialog.findByRole('alert')

    // when: 닫기를 누른다
    await user.click(dialog.getByRole('button', { name: '닫기' }))

    // then: 창이 닫힌다
    expect(screen.queryByRole('dialog')).not.toBeInTheDocument()

    // when: 작성 탭으로 옮긴다
    await showTab(user, 'design')
    // then: 바꾼 설계와 저장 안 됨이 남는다
    expect(chipItems()).toHaveLength(3)
    expect(screen.getByText(UNSAVED_MARK)).toBeVisible()
  })

  // 테스트 코드: RS-075
  it('충돌 경고에서 다른 이름으로 저장하면 새 리포트가 생긴다', async () => {
    // given: 충돌 경고가 뜬 저장 창
    const { user, location } = await openEditor(MINE_PUBLIC.id)
    await addCountedColumn(user, 'Deal code')
    await runQuery(user)
    await waitFor(() => expect(saveButton()).toBeEnabled())
    await saveElsewhere()
    await user.click(saveButton())
    const dialog = await dialogOf()
    await user.click(dialog.getByRole('button', { name: '저장' }))
    const alert = await dialog.findByRole('alert')

    // when: 경고의 "다른 이름으로 저장"을 누른다
    await user.click(within(alert).getByRole('button', { name: '다른 이름으로 저장' }))

    // then: 이름이 "복사본"으로 바뀐다
    expect(dialog.getByRole('textbox', { name: '이름' })).toHaveValue(COPY_NAME)
    // when: 저장한다
    await user.click(dialog.getByRole('button', { name: '저장' }))
    // then: 새 리포트 편집 화면으로 가고 요청은 update 둘과 create다
    await waitFor(() => expect(location()).toBe('/reports/16/edit'))
    expect(mockControl.savedReportRequests().map((r) => r.op)).toEqual(['update', 'update', 'create'])
  })
})

describe('다른 이름으로 저장', () => {
  // 테스트 코드: RS-077
  it('다른 이름으로 저장하면 "복사본" 이름의 새 리포트가 만들어지고 원본은 그대로다', async () => {
    // given: 설계를 바꿔 조회한 편집 화면
    const { user, location } = await openEditor(MINE_PUBLIC.id)
    await addCountedColumn(user, 'Deal code')
    await runQuery(user)
    await waitFor(() => expect(saveButton()).toBeEnabled())
    // when: 다른 이름으로 저장 창을 연다
    await user.click(screen.getByRole('button', { name: '다른 이름으로 저장' }))
    // then: 이름이 "복사본", 공개 범위가 공개로 시작한다
    const dialog = await dialogOf()
    expect(dialog.getByRole('textbox', { name: '이름' })).toHaveValue(COPY_NAME)
    expect(dialog.getByRole('combobox', { name: '공개 범위' })).toHaveDisplayValue('모든 사용자에게 보임')

    // when: 저장한다
    await user.click(dialog.getByRole('button', { name: '저장' }))

    // then: 새 리포트 편집 화면으로 가고 만들기 요청이 지금 설계를 싣는다
    await waitFor(() => expect(location()).toBe('/reports/16/edit'))
    expect(await screen.findByRole('heading', { level: 1, name: COPY_NAME })).toBeVisible()
    expect(unsavedMark()).not.toBeInTheDocument()
    const [create] = mockControl.savedReportRequests()
    expect(create).toMatchObject({ op: 'create', id: null, body: { name: COPY_NAME, visibility: 'public', definition: lastQuery() } })
    // then: 원본은 revision 1 그대로다
    expect(await gateway.reports.get(MINE_PUBLIC.id)).toMatchObject({ revision: 1, definition: VENDOR_DEFINITION })
  })

  // 테스트 코드: RS-077
  it('복사본 이름은 100자로 자른다', async () => {
    // given: 이름이 98자인 리포트
    const longName = 'x'.repeat(98)
    const { user } = await renderAt('/reports/30/edit', { savedReports: [savedReport({ id: 30, name: longName })] })
    await waitForHiddenResult()

    // when: 다른 이름으로 저장 창을 연다
    await user.click(screen.getByRole('button', { name: '다른 이름으로 저장' }))

    // then: 이름이 "<이름> 복사본"을 100자로 자른 값이다
    const name = (await dialogOf()).getByRole('textbox', { name: '이름' })
    expect(name).toHaveValue(`${longName} 복사본`.slice(0, 100))
    expect((name as HTMLInputElement).value).toHaveLength(100)
  })

  // 테스트 코드: RS-077
  it('남의 리포트의 복사본은 공개 범위를 자유롭게 고른다', async () => {
    // given: 남의 공개 리포트의 편집 화면
    const { user } = await openEditor(PARK_PUBLIC.id)

    // when: 다른 이름으로 저장 창을 연다
    await user.click(screen.getByRole('button', { name: '다른 이름으로 저장' }))

    // then: 공개 범위 선택이 켜져 있다
    expect((await dialogOf()).getByRole('combobox', { name: '공개 범위' })).toBeEnabled()
  })

  // 테스트 코드: RS-070
  it('이미 있는 이름이면 이름 칸 아래 문구를 보인다', async () => {
    // given: 다른 이름으로 저장 창에 이미 있는 이름을 넣는다
    const { user } = await openEditor(MINE_PUBLIC.id)
    await user.click(screen.getByRole('button', { name: '다른 이름으로 저장' }))
    const dialog = await dialogOf()
    await typeName(user, await saveDialog(), MINE_PUBLIC.name)

    // when: 저장한다
    await user.click(dialog.getByRole('button', { name: '저장' }))

    // then: 이름 중복 문구가 창 안에 보인다
    expect(await dialog.findByText('같은 이름의 리포트가 이미 있습니다.')).toBeVisible()
  })
})

describe('공개 범위', () => {
  // 테스트 코드: RS-078
  it.each([
    ['sales', MINE_PUBLIC.id, true],
    ['admin', PARK_PUBLIC.id, true],
    ['sales', PARK_PUBLIC.id, false],
    ['user', MINE_PUBLIC.id, false],
  ] as const)('%s 역할의 리포트 %s 편집: 공개 범위 선택이 켜져 있는가 %s', async (role, id, enabled) => {
    // given: 역할별로 편집 화면을 연다
    const { user } = await openEditor(id, { role })
    // when: 저장 창을 연다
    await user.click(saveButton())
    const dialog = await dialogOf()

    // then: 만든 사람·admin이면 공개 범위가 켜지고 아니면 꺼지며 잠금 안내가 보인다
    const select = dialog.getByRole('combobox', { name: '공개 범위' })
    if (enabled) {
      expect(select).toBeEnabled()
      expect(dialog.queryByText('공개 범위는 만든 사람 또는 admin만 바꿀 수 있습니다')).not.toBeInTheDocument()
    } else {
      expect(select).toBeDisabled()
      expect(dialog.getByText('공개 범위는 만든 사람 또는 admin만 바꿀 수 있습니다')).toBeVisible()
    }
  })

  // 테스트 코드: RS-078
  it('만든 사람이 아닌 편집자는 공개 범위가 잠기고 지금 값으로 덮어쓴다', async () => {
    // given: 남의 공개 리포트를 고쳐 조회한 편집 화면
    const { user, location } = await openEditor(PARK_PUBLIC.id)
    await addCountedColumn(user, 'Deal 이름')
    await runQuery(user)
    await waitFor(() => expect(saveButton()).toBeEnabled())
    // when: 저장 창을 연다
    await user.click(saveButton())
    const dialog = await dialogOf()
    // then: 공개 범위가 잠겨 있다
    expect(dialog.getByRole('combobox', { name: '공개 범위' })).toBeDisabled()

    // when: 저장한다
    await user.click(dialog.getByRole('button', { name: '저장' }))

    // then: 요청이 공개(public)로 가서 만든 사람은 그대로, 수정자는 나로 저장된다
    await waitFor(() => expect(screen.queryByRole('dialog')).not.toBeInTheDocument())
    expect(location()).toBe('/reports/13/edit')
    expect(mockControl.savedReportRequests()[0]).toMatchObject({ op: 'update', id: 13, body: { visibility: 'public', revision: 1 } })
    expect(await gateway.reports.get(PARK_PUBLIC.id)).toMatchObject({ owner: { id: PARK_PUBLIC.owner.id }, updatedBy: { id: MINE_PUBLIC.owner.id } })
  })
})

describe('되돌리기', () => {
  // 테스트 코드: RS-079
  it('되돌리기는 확인 뒤 저장된 설계로 돌아간다', async () => {
    // given: 컬럼을 둘 더 넣은 편집 화면
    const { user } = await openEditor(MINE_PUBLIC.id)
    await addCountedColumn(user, 'Deal code')
    await addCountedColumn(user, 'Deal 이름')
    expect(chipItems()).toHaveLength(4)

    // when: 되돌리기를 누른다
    await user.click(screen.getByRole('button', { name: '되돌리기' }))

    // then: 확인 창과 안내 문구가 보인다
    const dialog = await screen.findByRole('dialog', { name: '저장된 설계로 되돌릴까요?' })
    expect(dialog).toHaveTextContent('저장하지 않은 변경이 사라집니다.')
    // when: 확인 창에서 되돌리기를 누른다
    await user.click(within(dialog).getByRole('button', { name: '되돌리기' }))

    // then: 저장된 설계(컬럼 2개)로 돌아가고 저장 안 됨이 사라지며 요청이 없다
    expect(screen.queryByRole('dialog')).not.toBeInTheDocument()
    expect(chipItems()).toHaveLength(2)
    expect(chipTexts()[1]).toContain('금액 합계')
    expect(unsavedMark()).not.toBeInTheDocument()
    expect(mockControl.savedReportRequests()).toEqual([])
  })

  // 테스트 코드: RS-079
  it('되돌리기를 취소하면 변경이 남는다', async () => {
    // given: 컬럼을 하나 더 넣은 편집 화면
    const { user } = await openEditor(MINE_PUBLIC.id)
    await addCountedColumn(user, 'Deal code')

    // when: 되돌리기를 누르고 확인 창에서 취소한다
    await user.click(screen.getByRole('button', { name: '되돌리기' }))
    await user.click(within(await screen.findByRole('dialog', { name: '저장된 설계로 되돌릴까요?' })).getByRole('button', { name: '취소' }))

    // then: 창이 닫히고 변경과 저장 안 됨이 남는다
    expect(screen.queryByRole('dialog')).not.toBeInTheDocument()
    expect(chipItems()).toHaveLength(3)
    expect(screen.getByText(UNSAVED_MARK)).toBeVisible()
  })

  // 테스트 코드: RS-079
  it('되돌리기는 처음 불러온 설계가 아니라 마지막 덮어쓰기의 설계로 돌아간다', async () => {
    // given: 컬럼을 넣어 덮어쓴 뒤 컬럼을 하나 더 넣은 편집 화면
    const { user } = await openEditor(MINE_PUBLIC.id)
    await addCountedColumn(user, 'Deal code')
    await runQuery(user)
    await waitFor(() => expect(saveButton()).toBeEnabled())
    await user.click(saveButton())
    await user.click((await dialogOf()).getByRole('button', { name: '저장' }))
    await waitFor(() => expect(unsavedMark()).not.toBeInTheDocument())
    await showTab(user, 'design')
    await addCountedColumn(user, 'Deal 이름')

    // when: 되돌리기를 확인한다
    await user.click(screen.getByRole('button', { name: '되돌리기' }))
    await user.click(within(await screen.findByRole('dialog', { name: '저장된 설계로 되돌릴까요?' })).getByRole('button', { name: '되돌리기' }))

    // then: 마지막 덮어쓰기의 설계(컬럼 3개)로 돌아가고 저장 안 됨이 없다
    expect(chipItems()).toHaveLength(3)
    expect(unsavedMark()).not.toBeInTheDocument()
  })
})
