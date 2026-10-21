import { screen, waitFor, within } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { describe, expect, it } from 'vitest'
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

describe('첨부 파일 목록 (T-FILE-01)', () => {
  it('lists name, description, size, uploader and time with a download button', async () => {
    const { panel } = await openPanel(1, '한빛은행 ITDR 도입')
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

  it('shows a resigned uploader as 이름(퇴사)', async () => {
    const { panel } = await openPanel(1, '한빛은행 ITDR 도입')
    expect(rowOf(panel, '기술검토.xlsx')).toHaveTextContent('강퇴사(퇴사)')
  })

  it('says there are no files for a deal without attachments', async () => {
    await renderAt(await detailPath(2))
    const panel = await screen.findByRole('region', { name: '첨부 파일' })
    expect(await within(panel).findByText('첨부된 파일이 없습니다.')).toBeVisible()
  })

  it('lets a viewer download but gives no upload form and no delete buttons', async () => {
    const { panel } = await openPanel(1, '한빛은행 ITDR 도입', 'user')
    expect(within(panel).getByRole('button', { name: '견적서_한빛은행_v2.pdf' })).toBeVisible()
    expect(within(panel).queryByLabelText('파일')).not.toBeInTheDocument()
    expect(within(panel).queryByRole('button', { name: '업로드' })).not.toBeInTheDocument()
    expect(within(panel).queryByRole('button', { name: /삭제$/ })).not.toBeInTheDocument()
  })
})

describe('업로드 검증 (T-FILE-02~07)', () => {
  it('rejects a missing file', async () => {
    const { panel } = await openPanel(1, '한빛은행 ITDR 도입')
    await upload(panel, null)
    expect(await within(panel).findByRole('alert')).toHaveTextContent('업로드할 파일을 선택하세요.')
  })

  it('rejects a description longer than 100 characters and shows the counter in red', async () => {
    const { user, panel } = await openPanel(1, '한빛은행 ITDR 도입')
    await user.upload(within(panel).getByLabelText('파일'), file('메모.pdf'))
    await user.click(within(panel).getByLabelText('설명'))
    await user.paste('가'.repeat(101))
    expect(within(panel).getByText('101/100')).toHaveClass('over')
    await user.click(within(panel).getByRole('button', { name: '업로드' }))
    expect(await within(panel).findByRole('alert')).toHaveTextContent('설명은 100자 이내로 입력하세요.')
  })

  it('counts the description characters and accepts exactly 100', async () => {
    const { user, panel } = await openPanel(2, '대한제조 MFA 확대')
    await user.upload(within(panel).getByLabelText('파일'), file('메모.pdf'))
    await user.click(within(panel).getByLabelText('설명'))
    await user.paste('가'.repeat(100))
    expect(within(panel).getByText('100/100')).not.toHaveClass('over')
    await user.click(within(panel).getByRole('button', { name: '업로드' }))
    expect(await within(panel).findByRole('button', { name: '메모.pdf' })).toBeVisible()
  })

  it('rejects a file over 100MB but accepts exactly 100MB', async () => {
    const { panel } = await openPanel(2, '대한제조 MFA 확대')
    await upload(panel, file('큰파일.zip', 100 * 1024 * 1024 + 1))
    expect(await within(panel).findByRole('alert')).toHaveTextContent('파일 크기가 100MB를 초과합니다. (최대 100MB)')
    expect(within(panel).queryByRole('button', { name: '큰파일.zip' })).not.toBeInTheDocument()
  })

  it('accepts a file of exactly 100MB', async () => {
    const { panel } = await openPanel(2, '대한제조 MFA 확대')
    await upload(panel, file('딱100.zip', 100 * 1024 * 1024))
    expect(await within(panel).findByRole('button', { name: '딱100.zip' })).toBeVisible()
  })

  it.each([
    ['setup.exe', '.exe'],
    ['RUN.EXE', '.exe'],
    ['installer.msi', '.msi'],
    ['deploy.sh', '.sh'],
  ])('blocks the executable file %s', async (name, ext) => {
    const { panel } = await openPanel(2, '대한제조 MFA 확대')
    await upload(panel, file(name))
    expect(await within(panel).findByRole('alert')).toHaveTextContent(`실행·설치 파일(${ext})은 업로드할 수 없습니다.`)
  })

  it('allows a double extension such as tar.gz', async () => {
    const { panel } = await openPanel(2, '대한제조 MFA 확대')
    await upload(panel, file('backup.tar.gz', 10, 'application/gzip'))
    expect(await within(panel).findByRole('button', { name: 'backup.tar.gz' })).toBeVisible()
  })

  it('uploads a valid file, lists it first and records it in the history', async () => {
    const { user, panel } = await openPanel(2, '대한제조 MFA 확대')
    await upload(panel, file('제안서.pdf', 2048), '제안서 초안')
    expect(await within(panel).findByRole('button', { name: '제안서.pdf' })).toBeVisible()
    expect(within(panel).getByText('업로드되었습니다: 제안서.pdf')).toBeVisible()
    expect(within(panel).getByLabelText('설명')).toHaveValue('')
    await user.click(screen.getByRole('tab', { name: 'Deal History' }))
    expect(await screen.findByText(/업로드 제안서\.pdf/)).toBeVisible()
  })

  it('shows the storage failure message and keeps the list as it was', async () => {
    const { panel } = await openPanel(2, '대한제조 MFA 확대')
    mockControl.setStorageFailure(true)
    await upload(panel, file('제안서.pdf'))
    expect(await within(panel).findByRole('alert')).toHaveTextContent(
      '파일 저장 위치를 사용할 수 없어 업로드할 수 없습니다. 관리자에게 문의하세요.',
    )
    expect(within(panel).queryByRole('button', { name: '제안서.pdf' })).not.toBeInTheDocument()
  })
})

describe('같은 이름 업로드 (T-FILE-08)', () => {
  it('asks to replace or skip and replaces the file when 교체 is chosen', async () => {
    const { panel } = await openPanel(1, '한빛은행 ITDR 도입')
    await upload(panel, file('견적서_한빛은행_v2.pdf', 5000), '교체본')
    const dialog = await screen.findByRole('dialog', { name: '같은 이름의 파일' })
    expect(dialog).toHaveTextContent('같은 이름의 파일이 이미 있습니다: 견적서_한빛은행_v2.pdf')
    await userEvent.click(within(dialog).getByRole('button', { name: '교체' }))
    await waitFor(() => expect(screen.queryByRole('dialog')).not.toBeInTheDocument())
    await waitFor(() => expect(rowOf(panel, '견적서_한빛은행_v2.pdf')).toHaveTextContent('교체본'))
    expect(within(panel).getAllByRole('row')).toHaveLength(4)
    expect(within(panel).getByText('교체되었습니다: 견적서_한빛은행_v2.pdf')).toBeVisible()
  })

  it('leaves the list unchanged when 건너뛰기 is chosen', async () => {
    const { panel } = await openPanel(1, '한빛은행 ITDR 도입')
    await upload(panel, file('제안서_ITDR.pptx', 5000), '교체본')
    const dialog = await screen.findByRole('dialog', { name: '같은 이름의 파일' })
    await userEvent.click(within(dialog).getByRole('button', { name: '건너뛰기' }))
    await waitFor(() => expect(screen.queryByRole('dialog')).not.toBeInTheDocument())
    expect(rowOf(panel, '제안서_ITDR.pptx')).toHaveTextContent('ITDR 제안서(공유용)')
    expect(within(panel).getAllByRole('row')).toHaveLength(4)
  })
})

describe('삭제 권한 (T-FILE-09~10)', () => {
  it('lets a sales user delete own file and a resigned sales file but not another sales file', async () => {
    const { panel } = await openPanel(1, '한빛은행 ITDR 도입')
    expect(within(panel).getByRole('button', { name: '견적서_한빛은행_v2.pdf 삭제' })).toBeEnabled()
    expect(within(panel).getByRole('button', { name: '기술검토.xlsx 삭제' })).toBeEnabled()
    const other = within(panel).getByRole('button', { name: '제안서_ITDR.pptx 삭제' })
    expect(other).toBeDisabled()
    expect(other).toHaveAttribute('title', '본인이 올린 파일만 삭제할 수 있습니다.')
  })

  it('lets admin delete every file', async () => {
    const { panel } = await openPanel(1, '한빛은행 ITDR 도입', 'admin')
    for (const name of ['견적서_한빛은행_v2.pdf', '제안서_ITDR.pptx', '기술검토.xlsx']) {
      expect(within(panel).getByRole('button', { name: `${name} 삭제` })).toBeEnabled()
    }
  })

  it('deletes a file after confirmation and records it in the history', async () => {
    const { user, panel } = await openPanel(1, '한빛은행 ITDR 도입')
    await user.click(within(panel).getByRole('button', { name: '기술검토.xlsx 삭제' }))
    const dialog = screen.getByRole('dialog', { name: '첨부 파일 삭제' })
    expect(dialog).toHaveTextContent('기술검토.xlsx')
    await user.click(within(dialog).getByRole('button', { name: '삭제' }))
    await waitFor(() => expect(within(panel).queryByRole('button', { name: '기술검토.xlsx' })).not.toBeInTheDocument())
    await user.click(screen.getByRole('tab', { name: 'Deal History' }))
    expect(await screen.findByText(/삭제 기술검토\.xlsx/)).toBeVisible()
  })

  it('keeps the file when the delete is cancelled', async () => {
    const { user, panel } = await openPanel(1, '한빛은행 ITDR 도입')
    await user.click(within(panel).getByRole('button', { name: '기술검토.xlsx 삭제' }))
    await user.click(within(screen.getByRole('dialog')).getByRole('button', { name: '취소' }))
    expect(within(panel).getByRole('button', { name: '기술검토.xlsx' })).toBeVisible()
  })

  it('lets the other sales user delete her own file only (park on deal 1)', async () => {
    const { panel } = await openPanel(1, '한빛은행 ITDR 도입', 'sales', USER_ID.park)
    expect(within(panel).getByRole('button', { name: '제안서_ITDR.pptx 삭제' })).toBeEnabled()
    expect(within(panel).getByRole('button', { name: '견적서_한빛은행_v2.pdf 삭제' })).toBeDisabled()
  })
})

describe('같은 이름 교체 권한 (AC-11, Q2)', () => {
  it('disables 교체 with a notice when another active sales file would be replaced (N3)', async () => {
    const { panel } = await openPanel(1, '한빛은행 ITDR 도입')
    await upload(panel, file('제안서_ITDR.pptx', 5000), '덮어쓰기')
    const dialog = await screen.findByRole('dialog', { name: '같은 이름의 파일' })

    expect(within(dialog).getByRole('button', { name: '교체' })).toBeDisabled()
    expect(within(dialog).getByText('본인이 올린 파일만 교체할 수 있습니다.')).toBeVisible()
    expect(within(dialog).getByRole('button', { name: '건너뛰기' })).toBeEnabled()
    expect(rowOf(panel, '제안서_ITDR.pptx')).toHaveTextContent('ITDR 제안서(공유용)')
  })

  it('keeps 교체 enabled without the notice for the own file (N3)', async () => {
    const { panel } = await openPanel(1, '한빛은행 ITDR 도입')
    await upload(panel, file('견적서_한빛은행_v2.pdf', 5000), '내 교체')
    const dialog = await screen.findByRole('dialog', { name: '같은 이름의 파일' })

    expect(within(dialog).getByRole('button', { name: '교체' })).toBeEnabled()
    expect(within(dialog).queryByText('본인이 올린 파일만 교체할 수 있습니다.')).not.toBeInTheDocument()
  })

  it('keeps 교체 enabled without the notice for a resigned sales file (N3)', async () => {
    const { panel } = await openPanel(1, '한빛은행 ITDR 도입')
    await upload(panel, file('기술검토.xlsx', 5000), '새 검토')
    const dialog = await screen.findByRole('dialog', { name: '같은 이름의 파일' })

    expect(within(dialog).getByRole('button', { name: '교체' })).toBeEnabled()
    expect(within(dialog).queryByText('본인이 올린 파일만 교체할 수 있습니다.')).not.toBeInTheDocument()
  })

  it('lets a sales user replace the file of a resigned sales', async () => {
    const { panel } = await openPanel(1, '한빛은행 ITDR 도입')
    await upload(panel, file('기술검토.xlsx', 5000), '새 검토')
    await userEvent.click(within(await screen.findByRole('dialog', { name: '같은 이름의 파일' })).getByRole('button', { name: '교체' }))

    await waitFor(() => expect(rowOf(panel, '기술검토.xlsx')).toHaveTextContent('새 검토'))
    expect(rowOf(panel, '기술검토.xlsx')).toHaveTextContent('김영업')
  })

  it('keeps 교체 enabled for admin on another sales file (N3)', async () => {
    const { panel } = await openPanel(1, '한빛은행 ITDR 도입', 'admin')
    await upload(panel, file('제안서_ITDR.pptx', 5000), '관리자 교체')
    const dialog = await screen.findByRole('dialog', { name: '같은 이름의 파일' })

    expect(within(dialog).getByRole('button', { name: '교체' })).toBeEnabled()
    expect(within(dialog).queryByText('본인이 올린 파일만 교체할 수 있습니다.')).not.toBeInTheDocument()
  })

  it('lets admin replace another sales file', async () => {
    const { panel } = await openPanel(1, '한빛은행 ITDR 도입', 'admin')
    await upload(panel, file('제안서_ITDR.pptx', 5000), '관리자 교체')
    await userEvent.click(within(await screen.findByRole('dialog', { name: '같은 이름의 파일' })).getByRole('button', { name: '교체' }))

    await waitFor(() => expect(rowOf(panel, '제안서_ITDR.pptx')).toHaveTextContent('관리자 교체'))
  })

  it('skips without any permission message even for a file of another sales', async () => {
    const { panel } = await openPanel(1, '한빛은행 ITDR 도입')
    await upload(panel, file('제안서_ITDR.pptx', 5000), '건너뛸 설명')
    await userEvent.click(within(await screen.findByRole('dialog', { name: '같은 이름의 파일' })).getByRole('button', { name: '건너뛰기' }))

    await waitFor(() => expect(screen.queryByRole('dialog')).not.toBeInTheDocument())
    expect(within(panel).queryByRole('alert')).not.toBeInTheDocument()
  })
})

describe('업로드 검증: 서버와 같은 규칙 (AC-08, AC-20)', () => {
  it.each(['견적\u202egpj.pdf', 'a\tb.pdf', '😀'.repeat(256)])('rejects the unusable file name %j before sending', async (name) => {
    const { panel } = await openPanel(2, '대한제조 MFA 확대')
    await upload(panel, file(name))
    expect(await within(panel).findByRole('alert')).toHaveTextContent('사용할 수 없는 파일 이름입니다.')
    expect(within(panel).queryByRole('button', { name })).not.toBeInTheDocument()
  })

  it('blocks an executable whose name ends with a space', async () => {
    const { panel } = await openPanel(2, '대한제조 MFA 확대')
    await upload(panel, file('setup.exe '))
    expect(await within(panel).findByRole('alert')).toHaveTextContent('실행·설치 파일(.exe)은 업로드할 수 없습니다.')
  })

  it('blocks one of the added extensions such as .vbs', async () => {
    const { panel } = await openPanel(2, '대한제조 MFA 확대')
    await upload(panel, file('tool.vbs'))
    expect(await within(panel).findByRole('alert')).toHaveTextContent('실행·설치 파일(.vbs)은 업로드할 수 없습니다.')
  })

  it('counts the description after trimming, so 100 characters between spaces is fine', async () => {
    const { user, panel } = await openPanel(2, '대한제조 MFA 확대')
    await user.upload(within(panel).getByLabelText('파일'), file('메모.pdf'))
    await user.click(within(panel).getByLabelText('설명'))
    await user.paste(`  ${'가'.repeat(100)}  `)
    expect(within(panel).getByText('100/100')).not.toHaveClass('over')
    await user.click(within(panel).getByRole('button', { name: '업로드' }))
    expect(await within(panel).findByRole('button', { name: '메모.pdf' })).toBeVisible()
    expect(rowOf(panel, '메모.pdf')).toHaveTextContent('가'.repeat(100))
  })

  it('lists a file uploaded in NFD spelling under its NFC name', async () => {
    const { panel } = await openPanel(2, '대한제조 MFA 확대')
    await upload(panel, file('한글.pdf'.normalize('NFD')))
    expect(await within(panel).findByRole('button', { name: '한글.pdf'.normalize('NFC') })).toBeVisible()
  })
})
