import { screen, waitFor, within } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { afterEach, describe, expect, it, vi } from 'vitest'
import { gateway } from '../../../gateway'
import { ApiError } from '../../../shared/api/problem'
import { mockControl } from '../../../test/fake/default'
import { renderAt } from '../../../test/mockApp'
import { detailPath } from '../../../test/detailTestUtils'
import { USER_ID } from '../../../test/fake/seed/ids'

type Role = 'sales' | 'admin' | 'user'

async function openPanel(no: number, title: string, role: Role = 'sales', userId?: number) {
  const view = await renderAt(await detailPath(no), userId ? { userId } : { role })
  await screen.findByRole('heading', { level: 1, name: title })
  const panel = await screen.findByRole('region', { name: '첨부 파일' })
  await waitFor(() => expect(within(panel).queryByText('불러오는 중…')).not.toBeInTheDocument())
  return { ...view, panel }
}

/** 실제로 큰 버퍼를 만들지 않고 크기만 지정한 File. */
function file(name: string, size = 10, type = 'application/pdf'): File {
  const f = new File(['x'], name, { type })
  Object.defineProperty(f, 'size', { value: size })
  return f
}

function rowOf(panel: HTMLElement, name: string) {
  return within(panel).getByRole('row', { name: new RegExp(name) })
}

async function upload(panel: HTMLElement, f: File | null, description = '') {
  const user = userEvent.setup()
  if (f) await user.upload(within(panel).getByLabelText('파일'), f)
  if (description) await user.type(within(panel).getByLabelText('설명'), description)
  await user.click(within(panel).getByRole('button', { name: '업로드' }))
}

describe('첨부 파일 목록', () => {
  // 테스트 코드: AT-041
  it('첨부 목록은 파일명·설명·크기·업로더·시각을 보이고 파일명은 내려받기 버튼이다', async () => {
    // when: 첨부 패널을 연다 (전제: sales로 연 Deal 상세의 첨부 패널(첨부 3개, 하나는 퇴사자가 올림))
    const { panel } = await openPanel(1, '한빛은행 ITDR 도입')
    // then: 머리글 6칸과 한 행의 파일명 버튼·설명·업로더·크기가 보이고 행은 머리글 포함 4개다
    expect(within(panel).getAllByRole('columnheader').map((h) => h.textContent)).toEqual([
      '파일명',
      '설명',
      '크기',
      '업로드한 사용자',
      '업로드 시각',
      '관리',
    ])
    const row = rowOf(panel, '견적서_한빛은행_v2.pdf')
    expect(within(row).getByRole('button', { name: '견적서_한빛은행_v2.pdf' })).toBeVisible()
    expect(row).toHaveTextContent('2차 견적서')
    expect(row).toHaveTextContent('김영업')
    expect(row).toHaveTextContent(/2\.3 MB|2\.4 MB/)
    expect(within(panel).getAllByRole('row')).toHaveLength(4)
  })

  // 테스트 코드: AT-041
  it('퇴사한 업로더는 "이름(퇴사)"로 보인다', async () => {
    // when: sales가 첨부 패널을 연다 (전제: 퇴사자가 올린 파일이 있는 Deal)
    const { panel } = await openPanel(1, '한빛은행 ITDR 도입')

    // then: 퇴사자가 올린 파일의 업로더가 "강퇴사(퇴사)"다
    expect(rowOf(panel, '기술검토.xlsx')).toHaveTextContent('강퇴사(퇴사)')
  })

  // 테스트 코드: AT-042
  it('첨부가 없는 Deal은 "첨부된 파일이 없습니다."를 보인다', async () => {
    // when: Deal 상세를 연다 (전제: 첨부가 없는 Deal)
    await renderAt(await detailPath(2))
    // then: 첨부 패널에 "첨부된 파일이 없습니다."가 보인다
    const panel = await screen.findByRole('region', { name: '첨부 파일' })
    expect(await within(panel).findByText('첨부된 파일이 없습니다.')).toBeVisible()
  })

  // 테스트 코드: AT-043
  it('user는 내려받기만 하고 업로드 폼과 삭제 버튼이 없다', async () => {
    // when: 첨부 패널을 본다 (전제: user로 연 첨부가 있는 Deal)
    const { panel } = await openPanel(1, '한빛은행 ITDR 도입', 'user')
    // then: 파일명 버튼은 보이고 "파일" 칸·"업로드" 버튼·삭제 버튼은 없다
    expect(within(panel).getByRole('button', { name: '견적서_한빛은행_v2.pdf' })).toBeVisible()
    expect(within(panel).queryByLabelText('파일')).not.toBeInTheDocument()
    expect(within(panel).queryByRole('button', { name: '업로드' })).not.toBeInTheDocument()
    expect(within(panel).queryByRole('button', { name: /삭제$/ })).not.toBeInTheDocument()
  })
})

describe('업로드 검증', () => {
  // 테스트 코드: AT-044
  it('파일 없이 업로드하면 요청 없이 문구를 보인다', async () => {
    // given: sales로 연 Deal의 업로드 폼
    const { panel } = await openPanel(1, '한빛은행 ITDR 도입')
    // when: 파일을 고르지 않고 업로드를 누른다
    await upload(panel, null)
    // then: "업로드할 파일을 선택하세요."가 alert로 보인다
    expect(await within(panel).findByRole('alert')).toHaveTextContent('업로드할 파일을 선택하세요.')
  })

  // 테스트 코드: AT-045
  it('설명이 100자를 넘으면 글자 수를 강조하고 업로드 때 문구를 보인다', async () => {
    // given: sales로 연 Deal의 업로드 폼에 파일을 고른다
    const { user, panel } = await openPanel(1, '한빛은행 ITDR 도입')
    await user.upload(within(panel).getByLabelText('파일'), file('메모.pdf'))
    // when: 설명에 101자를 붙여 넣고
    await user.click(within(panel).getByLabelText('설명'))
    await user.paste('가'.repeat(101))
    // then: 글자 수 "101/100"이 강조되고
    expect(within(panel).getByText('101/100')).toHaveClass('over')
    // when: 업로드를 누른다
    await user.click(within(panel).getByRole('button', { name: '업로드' }))
    // then: "설명은 100자 이내로 입력하세요."가 보인다
    expect(await within(panel).findByRole('alert')).toHaveTextContent('설명은 100자 이내로 입력하세요.')
  })

  // 테스트 코드: AT-045
  it('설명 정확히 100자는 강조 없이 올라간다', async () => {
    // given: sales로 연 Deal의 업로드 폼에 파일을 고른다
    const { user, panel } = await openPanel(2, '대한제조 MFA 확대')
    await user.upload(within(panel).getByLabelText('파일'), file('메모.pdf'))
    // when: 설명에 100자를 붙여 넣는다
    await user.click(within(panel).getByLabelText('설명'))
    await user.paste('가'.repeat(100))
    // then: 글자 수 "100/100"에 강조가 없다
    expect(within(panel).getByText('100/100')).not.toHaveClass('over')
    // when: 업로드를 누른다
    await user.click(within(panel).getByRole('button', { name: '업로드' }))
    // then: 파일이 목록에 보인다
    expect(await within(panel).findByRole('button', { name: '메모.pdf' })).toBeVisible()
  })

  // 테스트 코드: AT-044
  it('100MB를 넘는 파일은 요청 없이 문구를 보이고 목록에 없다', async () => {
    // given: sales로 연 Deal의 업로드 폼
    const { panel } = await openPanel(2, '대한제조 MFA 확대')
    // when: 100MB보다 1바이트 큰 파일을 올린다
    await upload(panel, file('큰파일.zip', 100 * 1024 * 1024 + 1))
    // then: 크기 초과 문구가 보이고 목록에 새 파일이 없다
    expect(await within(panel).findByRole('alert')).toHaveTextContent('파일 크기가 100MB를 초과합니다. (최대 100MB)')
    expect(within(panel).queryByRole('button', { name: '큰파일.zip' })).not.toBeInTheDocument()
  })

  // 테스트 코드: AT-044
  it('정확히 100MB 파일은 올라간다', async () => {
    // given: sales로 연 Deal의 업로드 폼
    const { panel } = await openPanel(2, '대한제조 MFA 확대')
    // when: 정확히 100MB 파일을 올린다
    await upload(panel, file('딱100.zip', 100 * 1024 * 1024))
    // then: 목록에 파일이 보인다
    expect(await within(panel).findByRole('button', { name: '딱100.zip' })).toBeVisible()
  })

  // 테스트 코드: AT-044
  it.each([
    ['setup.exe', '.exe'],
    ['RUN.EXE', '.exe'],
    ['installer.msi', '.msi'],
    ['deploy.sh', '.sh'],
  ])('차단 확장자 파일 %s는 요청 없이 문구를 보인다', async (name, ext) => {
    // given: sales로 연 Deal의 업로드 폼
    const { panel } = await openPanel(2, '대한제조 MFA 확대')
    // when: 실행 파일을 올린다
    await upload(panel, file(name))
    // then: 소문자 확장자가 든 차단 문구가 alert로 보인다
    expect(await within(panel).findByRole('alert')).toHaveTextContent(`실행·설치 파일(${ext})은 업로드할 수 없습니다.`)
  })

  // 테스트 코드: AT-044
  it('tar.gz 같은 이중 확장자는 올라간다', async () => {
    // given: sales로 연 Deal의 업로드 폼
    const { panel } = await openPanel(2, '대한제조 MFA 확대')
    // when: "backup.tar.gz"를 올린다
    await upload(panel, file('backup.tar.gz', 10, 'application/gzip'))
    // then: 목록에 파일이 보인다
    expect(await within(panel).findByRole('button', { name: 'backup.tar.gz' })).toBeVisible()
  })

  // 테스트 코드: AT-046
  it('올리면 목록에 보이고 알림이 뜨며 폼이 비워지고 History에 남는다', async () => {
    // given: sales로 연 Deal의 업로드 폼(첨부 없음)
    const { user, panel } = await openPanel(2, '대한제조 MFA 확대')
    // when: "제안서.pdf"를 설명과 함께 올린다
    await upload(panel, file('제안서.pdf', 2048), '제안서 초안')
    // then: 목록에 파일, 성공 알림이 보이고 설명 칸이 비워진다
    expect(await within(panel).findByRole('button', { name: '제안서.pdf' })).toBeVisible()
    expect(within(panel).getByText('업로드되었습니다: 제안서.pdf')).toBeVisible()
    expect(within(panel).getByLabelText('설명')).toHaveValue('')
    // when: Deal History 탭을 연다
    await user.click(screen.getByRole('tab', { name: 'Deal History' }))
    // then: "업로드 제안서.pdf"가 보인다
    expect(await screen.findByText(/업로드 제안서\.pdf/)).toBeVisible()
  })

  // 테스트 코드: AT-047
  it('저장 위치 장애면 서버 문구를 보이고 목록은 그대로다', async () => {
    // given: 저장소 장애를 켠 Deal의 업로드 폼
    const { panel } = await openPanel(2, '대한제조 MFA 확대')
    mockControl.setStorageFailure(true)
    // when: 파일을 올린다
    await upload(panel, file('제안서.pdf'))
    // then: 저장 위치 문구가 alert로 보이고 목록에 새 파일이 없다
    expect(await within(panel).findByRole('alert')).toHaveTextContent(
      '파일 저장 위치를 사용할 수 없어 업로드할 수 없습니다. 관리자에게 문의하세요.',
    )
    expect(within(panel).queryByRole('button', { name: '제안서.pdf' })).not.toBeInTheDocument()
  })
})

describe('같은 이름 업로드', () => {
  // 테스트 코드: AT-048
  it('같은 이름이면 묻고 "덮어쓰기"를 누르면 설명이 바뀐다', async () => {
    // given: 본인이 올린 파일이 있는 Deal의 업로드 폼
    const { panel } = await openPanel(1, '한빛은행 ITDR 도입')
    // when: 같은 이름을 새 설명으로 올린다
    await upload(panel, file('견적서_한빛은행_v2.pdf', 5000), '교체본')
    // then: "같은 이름의 파일" 대화상자와 문구가 보인다
    const dialog = await screen.findByRole('dialog', { name: '같은 이름의 파일' })
    expect(dialog).toHaveTextContent('같은 이름의 파일이 이미 있습니다: 견적서_한빛은행_v2.pdf')
    await userEvent.click(within(dialog).getByRole('button', { name: '덮어쓰기' }))
    // then: 대화상자가 닫히고 설명이 바뀌며 행 수는 그대로이고 "교체되었습니다" 알림이 보인다
    await waitFor(() => expect(screen.queryByRole('dialog')).not.toBeInTheDocument())
    await waitFor(() => expect(rowOf(panel, '견적서_한빛은행_v2.pdf')).toHaveTextContent('교체본'))
    expect(within(panel).getAllByRole('row')).toHaveLength(4)
    expect(within(panel).getByText('교체되었습니다: 견적서_한빛은행_v2.pdf')).toBeVisible()
  })

  // 테스트 코드: AT-048
  it('"취소"를 누르면 목록이 그대로다', async () => {
    // given: 다른 sales의 파일이 있는 Deal의 업로드 폼
    const { panel } = await openPanel(1, '한빛은행 ITDR 도입')
    const send = vi.spyOn(gateway.attachments, 'upload')
    // when: 같은 이름을 올려 대화상자를 연다
    await upload(panel, file('제안서_ITDR.pptx', 5000), '교체본')
    const dialog = await screen.findByRole('dialog', { name: '같은 이름의 파일' })
    await userEvent.click(within(dialog).getByRole('button', { name: '취소' }))
    // then: 대화상자가 닫히고 설명과 행 수가 그대로다
    await waitFor(() => expect(screen.queryByRole('dialog')).not.toBeInTheDocument())
    expect(rowOf(panel, '제안서_ITDR.pptx')).toHaveTextContent('ITDR 제안서(공유용)')
    expect(within(panel).getAllByRole('row')).toHaveLength(4)
    expect(send.mock.calls.map((call) => call[1].onExists)).toEqual(['ask'])
  })
})

describe('삭제 권한', () => {
  // 테스트 코드: AT-050
  it('sales는 본인·퇴사 sales 파일은 지울 수 있고 다른 sales 파일은 지울 수 없다', async () => {
    // when: 첨부 패널을 연다 (전제: sales로 연 Deal(본인·퇴사 sales·다른 sales의 파일))
    const { panel } = await openPanel(1, '한빛은행 ITDR 도입')
    // then: 본인·퇴사 sales 파일의 삭제는 활성, 다른 sales 파일은 비활성이고 안내 title이 있다
    expect(within(panel).getByRole('button', { name: '견적서_한빛은행_v2.pdf 삭제' })).toBeEnabled()
    expect(within(panel).getByRole('button', { name: '기술검토.xlsx 삭제' })).toBeEnabled()
    const other = within(panel).getByRole('button', { name: '제안서_ITDR.pptx 삭제' })
    expect(other).toBeDisabled()
    expect(other).toHaveAttribute('title', '본인이 올린 파일만 삭제할 수 있습니다.')
  })

  // 테스트 코드: AT-050
  it('admin은 모든 파일을 지울 수 있다', async () => {
    // when: 첨부 패널을 연다 (전제: admin으로 연 Deal)
    const { panel } = await openPanel(1, '한빛은행 ITDR 도입', 'admin')
    // then: 모든 파일의 삭제 버튼이 활성이다
    for (const name of ['견적서_한빛은행_v2.pdf', '제안서_ITDR.pptx', '기술검토.xlsx']) {
      expect(within(panel).getByRole('button', { name: `${name} 삭제` })).toBeEnabled()
    }
  })

  // 테스트 코드: AT-051
  it('확인하면 삭제되고 History에 남는다', async () => {
    // given: 삭제할 수 있는 "기술검토.xlsx"가 있는 Deal
    const { user, panel } = await openPanel(1, '한빛은행 ITDR 도입')
    // when: 삭제 버튼을 누른다
    await user.click(within(panel).getByRole('button', { name: '기술검토.xlsx 삭제' }))
    // then: 확인 대화상자에 파일 이름이 보인다
    const dialog = screen.getByRole('dialog', { name: '첨부 파일 삭제' })
    expect(dialog).toHaveTextContent('기술검토.xlsx')
    // when: "삭제"를 누른다
    await user.click(within(dialog).getByRole('button', { name: '삭제' }))
    // then: 목록에서 사라진다
    await waitFor(() => expect(within(panel).queryByRole('button', { name: '기술검토.xlsx' })).not.toBeInTheDocument())
    // when: Deal History 탭을 연다
    await user.click(screen.getByRole('tab', { name: 'Deal History' }))
    // then: "삭제 기술검토.xlsx"가 보인다
    expect(await screen.findByText(/삭제 기술검토\.xlsx/)).toBeVisible()
  })

  // 테스트 코드: AT-051
  it('삭제를 취소하면 파일이 그대로다', async () => {
    // given: 삭제할 수 있는 "기술검토.xlsx"가 있는 Deal
    const { user, panel } = await openPanel(1, '한빛은행 ITDR 도입')
    // when: 삭제 버튼을 누르고
    await user.click(within(panel).getByRole('button', { name: '기술검토.xlsx 삭제' }))
    // when: 대화상자에서 "취소"를 누른다
    await user.click(within(screen.getByRole('dialog')).getByRole('button', { name: '취소' }))
    // then: 파일이 목록에 그대로 있다
    expect(within(panel).getByRole('button', { name: '기술검토.xlsx' })).toBeVisible()
  })

  // 테스트 코드: AT-050
  it('다른 sales는 자기 파일만 지울 수 있다', async () => {
    // when: 첨부 패널을 연다 (전제: sales 박영업으로 연 Deal)
    const { panel } = await openPanel(1, '한빛은행 ITDR 도입', 'sales', USER_ID.park)
    // then: 자기 파일의 삭제는 활성, 남의 파일은 비활성이다
    expect(within(panel).getByRole('button', { name: '제안서_ITDR.pptx 삭제' })).toBeEnabled()
    expect(within(panel).getByRole('button', { name: '견적서_한빛은행_v2.pdf 삭제' })).toBeDisabled()
  })
})

describe('같은 이름 교체 권한', () => {
  // 테스트 코드: AT-049
  it('재직 중인 다른 sales의 파일이면 "덮어쓰기"는 비활성이고 안내가 보인다', async () => {
    // given: sales로 연 Deal의 업로드 폼
    const { panel } = await openPanel(1, '한빛은행 ITDR 도입')
    // when: 다른 재직 sales의 파일과 같은 이름을 올린다
    await upload(panel, file('제안서_ITDR.pptx', 5000), '덮어쓰기')
    // then: 같은 이름 대화상자가 뜬다
    const dialog = await screen.findByRole('dialog', { name: '같은 이름의 파일' })

    expect(within(dialog).getByRole('button', { name: '덮어쓰기' })).toBeDisabled()
    expect(within(dialog).getByText('본인이 올린 파일만 교체할 수 있습니다.')).toBeVisible()
    expect(within(dialog).getByRole('button', { name: '취소' })).toBeEnabled()
    expect(rowOf(panel, '제안서_ITDR.pptx')).toHaveTextContent('ITDR 제안서(공유용)')
  })

  // 테스트 코드: AT-049
  it('본인 파일이면 "덮어쓰기"가 활성이고 안내가 없다', async () => {
    // given: sales로 연 Deal의 업로드 폼
    const { panel } = await openPanel(1, '한빛은행 ITDR 도입')
    // when: 본인 파일과 같은 이름을 올린다
    await upload(panel, file('견적서_한빛은행_v2.pdf', 5000), '내 교체')
    // then: 같은 이름 대화상자가 뜬다
    const dialog = await screen.findByRole('dialog', { name: '같은 이름의 파일' })

    expect(within(dialog).getByRole('button', { name: '덮어쓰기' })).toBeEnabled()
    expect(within(dialog).queryByText('본인이 올린 파일만 교체할 수 있습니다.')).not.toBeInTheDocument()
  })

  // 테스트 코드: AT-049
  it('퇴사한 sales의 파일이면 "덮어쓰기"가 활성이고 안내가 없다', async () => {
    // given: sales로 연 Deal의 업로드 폼
    const { panel } = await openPanel(1, '한빛은행 ITDR 도입')
    // when: 퇴사 sales의 파일과 같은 이름을 올린다
    await upload(panel, file('기술검토.xlsx', 5000), '새 검토')
    // then: 같은 이름 대화상자가 뜬다
    const dialog = await screen.findByRole('dialog', { name: '같은 이름의 파일' })

    expect(within(dialog).getByRole('button', { name: '덮어쓰기' })).toBeEnabled()
    expect(within(dialog).queryByText('본인이 올린 파일만 교체할 수 있습니다.')).not.toBeInTheDocument()
  })

  // 테스트 코드: AT-049
  it('sales가 퇴사한 sales의 파일을 교체하면 설명이 바뀌고 업로더가 요청자가 된다', async () => {
    // given: sales로 연 Deal의 업로드 폼
    const { panel } = await openPanel(1, '한빛은행 ITDR 도입')
    // when: 퇴사 sales의 파일과 같은 이름을 올리고
    await upload(panel, file('기술검토.xlsx', 5000), '새 검토')
    await userEvent.click(within(await screen.findByRole('dialog', { name: '같은 이름의 파일' })).getByRole('button', { name: '덮어쓰기' }))

    // then: 설명이 바뀌고 업로더가 요청자(김영업)다
    await waitFor(() => expect(rowOf(panel, '기술검토.xlsx')).toHaveTextContent('새 검토'))
    expect(rowOf(panel, '기술검토.xlsx')).toHaveTextContent('김영업')
  })

  // 테스트 코드: AT-049
  it('admin은 다른 sales의 파일도 "덮어쓰기"가 활성이고 안내가 없다', async () => {
    // given: admin으로 연 Deal의 업로드 폼
    const { panel } = await openPanel(1, '한빛은행 ITDR 도입', 'admin')
    // when: 다른 sales의 파일과 같은 이름을 올린다
    await upload(panel, file('제안서_ITDR.pptx', 5000), '관리자 교체')
    // then: 같은 이름 대화상자가 뜬다
    const dialog = await screen.findByRole('dialog', { name: '같은 이름의 파일' })

    expect(within(dialog).getByRole('button', { name: '덮어쓰기' })).toBeEnabled()
    expect(within(dialog).queryByText('본인이 올린 파일만 교체할 수 있습니다.')).not.toBeInTheDocument()
  })

  // 테스트 코드: AT-049
  it('admin은 다른 sales의 파일을 교체할 수 있다', async () => {
    // given: admin으로 연 Deal의 업로드 폼
    const { panel } = await openPanel(1, '한빛은행 ITDR 도입', 'admin')
    // when: 다른 sales의 파일과 같은 이름을 올리고
    await upload(panel, file('제안서_ITDR.pptx', 5000), '관리자 교체')
    await userEvent.click(within(await screen.findByRole('dialog', { name: '같은 이름의 파일' })).getByRole('button', { name: '덮어쓰기' }))

    // then: 설명이 바뀐다
    await waitFor(() => expect(rowOf(panel, '제안서_ITDR.pptx')).toHaveTextContent('관리자 교체'))
  })

  // 테스트 코드: AT-048
  it('다른 sales의 파일이어도 "취소"는 권한 안내 없이 닫힌다', async () => {
    // given: sales로 연 Deal의 업로드 폼
    const { panel } = await openPanel(1, '한빛은행 ITDR 도입')
    // when: 다른 sales의 파일과 같은 이름을 올리고
    await upload(panel, file('제안서_ITDR.pptx', 5000), '건너뛸 설명')
    await userEvent.click(within(await screen.findByRole('dialog', { name: '같은 이름의 파일' })).getByRole('button', { name: '취소' }))

    // then: 대화상자가 닫히고 오류 알림이 없다
    await waitFor(() => expect(screen.queryByRole('dialog')).not.toBeInTheDocument())
    expect(within(panel).queryByRole('alert')).not.toBeInTheDocument()
  })
})

describe('업로드 검증: 서버와 같은 규칙', () => {
  // 테스트 코드: AT-044
  it.each(['견적\u202egpj.pdf', 'a\tb.pdf', '😀'.repeat(256)])('쓸 수 없는 파일 이름 %j는 요청 없이 문구를 보인다', async (name) => {
    // given: sales로 연 Deal의 업로드 폼
    const { panel } = await openPanel(2, '대한제조 MFA 확대')
    // when: 방향 제어 문자·탭·256자 이름의 파일을 올린다
    await upload(panel, file(name))
    // then: "사용할 수 없는 파일 이름입니다."가 보이고 목록에 없다
    expect(await within(panel).findByRole('alert')).toHaveTextContent('사용할 수 없는 파일 이름입니다.')
    expect(within(panel).queryByRole('button', { name })).not.toBeInTheDocument()
  })

  // 테스트 코드: AT-044
  it('이름 끝에 공백이 있어도 실행 파일은 차단한다', async () => {
    // given: sales로 연 Deal의 업로드 폼
    const { panel } = await openPanel(2, '대한제조 MFA 확대')
    // when: "setup.exe "를 올린다
    await upload(panel, file('setup.exe '))
    // then: 차단 확장자 문구가 보인다
    expect(await within(panel).findByRole('alert')).toHaveTextContent('실행·설치 파일(.exe)은 업로드할 수 없습니다.')
  })

  // 테스트 코드: AT-044
  it('추가된 차단 확장자(.vbs)도 막는다', async () => {
    // given: sales로 연 Deal의 업로드 폼
    const { panel } = await openPanel(2, '대한제조 MFA 확대')
    // when: "tool.vbs"를 올린다
    await upload(panel, file('tool.vbs'))
    // then: ".vbs" 차단 문구가 보인다
    expect(await within(panel).findByRole('alert')).toHaveTextContent('실행·설치 파일(.vbs)은 업로드할 수 없습니다.')
  })

  // 테스트 코드: AT-045
  it('설명은 앞뒤 공백을 뺀 글자 수로 세어 공백 사이 100자는 올라간다', async () => {
    // given: sales로 연 Deal의 업로드 폼에 파일을 고른다
    const { user, panel } = await openPanel(2, '대한제조 MFA 확대')
    await user.upload(within(panel).getByLabelText('파일'), file('메모.pdf'))
    // when: 앞뒤 공백이 붙은 100자 설명을 붙여 넣고
    await user.click(within(panel).getByLabelText('설명'))
    await user.paste(`  ${'가'.repeat(100)}  `)
    // then: 글자 수가 "100/100"이고 강조가 없다
    expect(within(panel).getByText('100/100')).not.toHaveClass('over')
    // when: 업로드를 누른다
    await user.click(within(panel).getByRole('button', { name: '업로드' }))
    // then: 목록에 보이고 설명은 100자다
    expect(await within(panel).findByRole('button', { name: '메모.pdf' })).toBeVisible()
    expect(rowOf(panel, '메모.pdf')).toHaveTextContent('가'.repeat(100))
  })

  // 테스트 코드: AT-046
  it('NFD로 고른 파일은 NFC 이름으로 목록에 보인다', async () => {
    // given: sales로 연 Deal의 업로드 폼
    const { panel } = await openPanel(2, '대한제조 MFA 확대')
    // when: NFD 표기 이름의 파일을 올린다
    await upload(panel, file('한글.pdf'.normalize('NFD')))
    // then: 목록에 NFC 이름 버튼이 보인다
    expect(await within(panel).findByRole('button', { name: '한글.pdf'.normalize('NFC') })).toBeVisible()
  })
})

describe('내려받기 (AT-052)', () => {
  const saved: { name: string; blob: unknown }[] = []

  /** jsdom에는 파일 저장이 없어, 객체 URL 생성과 링크 클릭을 가로채 "저장 시작"을 기록한다. */
  function interceptSaving() {
    saved.length = 0
    let lastBlob: unknown = null
    Object.assign(URL, {
      createObjectURL: (blob: Blob) => {
        lastBlob = blob
        return 'blob:fake'
      },
      revokeObjectURL: () => undefined,
    })
    vi.spyOn(HTMLAnchorElement.prototype, 'click').mockImplementation(function (this: HTMLAnchorElement) {
      saved.push({ name: this.download, blob: lastBlob })
    })
  }

  afterEach(() => {
    vi.restoreAllMocks()
    Reflect.deleteProperty(URL, 'createObjectURL')
    Reflect.deleteProperty(URL, 'revokeObjectURL')
  })

  // 테스트 코드: AT-052
  it('파일명을 누르면 첨부 이름으로 파일 저장을 시작한다', async () => {
    // given: 파일 저장을 가로챈 브라우저와 첨부가 있는 Deal을 user로 연다
    interceptSaving()
    const { user, panel } = await openPanel(1, '한빛은행 ITDR 도입', 'user')

    // when: 파일명 "견적서_한빛은행_v2.pdf"를 누른다
    await user.click(within(panel).getByRole('button', { name: '견적서_한빛은행_v2.pdf' }))

    // then: 그 이름으로 내용(Blob) 저장이 시작되고 오류 배너는 없다
    await waitFor(() => expect(saved).toHaveLength(1))
    expect(saved[0]?.name).toBe('견적서_한빛은행_v2.pdf')
    expect(saved[0]?.blob).toBeInstanceOf(Blob)
    expect(within(panel).queryByRole('alert')).not.toBeInTheDocument()
  })

  // 테스트 코드: AT-052
  it('다운로드가 503으로 실패하면 서버 문구를 보이고 저장하지 않는다', async () => {
    // given: 다운로드가 저장 위치 장애(503)로 실패하는 게이트웨이와 첨부가 있는 Deal
    interceptSaving()
    const detail = '파일 저장 위치를 사용할 수 없습니다. 관리자에게 문의하세요.'
    const problem = { type: 'https://neoine-sales/problems/storage-unavailable', title: 'Storage Unavailable', status: 503, detail }
    vi.spyOn(gateway.attachments, 'download').mockRejectedValue(new ApiError(503, problem))
    const { user, panel } = await openPanel(1, '한빛은행 ITDR 도입')

    // when: 파일명 "견적서_한빛은행_v2.pdf"를 누른다
    await user.click(within(panel).getByRole('button', { name: '견적서_한빛은행_v2.pdf' }))

    // then: 패널에 서버 문구의 오류 배너가 보이고 파일 저장은 시작되지 않는다
    expect(await within(panel).findByRole('alert')).toHaveTextContent(detail)
    expect(saved).toHaveLength(0)
  })
})
