import { screen, waitFor, within } from '@testing-library/react'
import { describe, expect, it } from 'vitest'
import { gateway } from '../../../gateway'
import { renderAt } from '../../../test/mockApp'

async function openLabels(role: 'admin' | 'sales' = 'admin') {
  const view = await renderAt('/admin/deal', { role })
  await view.user.click(await screen.findByRole('tab', { name: 'BANT Label' }))
  await screen.findByRole('region', { name: 'Budget' })
  await screen.findByText('단독 예산 확보')
  return view
}

function section(name: string) {
  return within(screen.getByRole('region', { name }))
}

function labelRow(category: string, name: string) {
  return within(section(category).getByRole('row', { name: new RegExp(name) }))
}

async function addLabel(user: Awaited<ReturnType<typeof renderAt>>['user'], category: string, name: string) {
  await user.type(section(category).getByLabelText('새 Label 이름'), name)
  await user.click(section(category).getByRole('button', { name: '추가' }))
}

describe('BANT Label 관리 목록 (T-LABEL-01, T-ADMIN-06)', () => {
  it('shows one section per BANT category with its default labels', async () => {
    await openLabels()

    for (const category of ['Budget', 'Authority', 'Need', 'Timeline']) {
      expect(screen.getByRole('region', { name: category })).toBeInTheDocument()
    }
    expect(labelRow('Budget', '단독 예산 확보')).toBeTruthy()
    expect(section('Authority').getByText('CEO 보고 완료')).toBeInTheDocument()
    expect(section('Need').getByText('컴플라이언스')).toBeInTheDocument()
    expect(section('Timeline').getByText('금년 구매')).toBeInTheDocument()
    expect(section('Budget').queryByText('CEO 보고 완료')).not.toBeInTheDocument()
  })

  it('marks default labels and shows the usage count and who created them', async () => {
    await openLabels()

    const row = labelRow('Budget', '단독 예산 확보')
    expect(row.getByText('기본')).toBeInTheDocument()
    expect(row.getByText(/Deal \d+건/)).toBeInTheDocument()
    expect(row.getByText('시스템')).toBeInTheDocument()
  })

  it('shows the creator and time of a label made by a user', async () => {
    const { user } = await openLabels()

    await addLabel(user, 'Budget', '분기 예산')

    const row = labelRow('Budget', '분기 예산')
    expect(await screen.findByText('분기 예산')).toBeInTheDocument()
    expect(row.queryByText('기본')).not.toBeInTheDocument()
    expect(row.getByText(/최관리/)).toBeInTheDocument()
    expect(row.getByText('Deal 0건')).toBeInTheDocument()
  })
})

describe('BANT Label 추가·수정 (T-LABEL-02~03)', () => {
  it('adds a label and clears the input', async () => {
    const { user } = await openLabels()

    await addLabel(user, 'Need', '규제 대응')

    expect(await section('Need').findByText('규제 대응')).toBeInTheDocument()
    expect(section('Need').getByLabelText('새 Label 이름')).toHaveValue('')
  })

  it('rejects a duplicate name in the same category regardless of case', async () => {
    const { user } = await openLabels()
    await addLabel(user, 'Need', 'Audit Ready')
    await section('Need').findByText('Audit Ready')

    await addLabel(user, 'Need', 'audit ready')

    expect(await screen.findByRole('alert')).toHaveTextContent('같은 구분에 이미 있는 Label 이름입니다.')
  })

  it('lets the same name exist in a different category', async () => {
    const { user } = await openLabels()

    await addLabel(user, 'Need', '미확인')

    expect(await section('Need').findByText('미확인')).toBeInTheDocument()
    expect(section('Budget').getAllByText('미확인')).toHaveLength(1)
  })

  it('shows the server messages for an empty and a too long name', async () => {
    const { user } = await openLabels()

    await user.click(section('Timeline').getByRole('button', { name: '추가' }))
    expect(await screen.findByRole('alert')).toHaveTextContent('Label 이름을 입력하세요.')

    await addLabel(user, 'Timeline', 'x'.repeat(51))
    await waitFor(() => expect(screen.getByRole('alert')).toHaveTextContent('Label 이름은 50자 이내로 입력하세요.'))
  })

  it('renames a label, including one in use', async () => {
    const { user } = await openLabels()

    await user.click(labelRow('Budget', '단독 예산 확보').getByRole('button', { name: '이름 수정' }))
    const input = screen.getByLabelText('Label 이름')
    await user.clear(input)
    await user.type(input, '전액 예산 확보')
    await user.click(screen.getByRole('button', { name: '저장' }))

    expect(await section('Budget').findByText('전액 예산 확보')).toBeInTheDocument()
    expect(section('Budget').queryByText('단독 예산 확보')).not.toBeInTheDocument()
  })

  it('rejects renaming to a name that already exists in the category', async () => {
    const { user } = await openLabels()

    await user.click(labelRow('Budget', '단독 예산 확보').getByRole('button', { name: '이름 수정' }))
    const input = screen.getByLabelText('Label 이름')
    await user.clear(input)
    await user.type(input, '풀 예산 확보')
    await user.click(screen.getByRole('button', { name: '저장' }))

    expect(await screen.findByRole('alert')).toHaveTextContent('같은 구분에 이미 있는 Label 이름입니다.')
  })
})

describe('BANT Label 삭제 (T-LABEL-05)', () => {
  it('deletes an unused label after confirmation', async () => {
    const { user } = await openLabels()
    await addLabel(user, 'Budget', '임시 Label')
    await section('Budget').findByText('임시 Label')

    await user.click(labelRow('Budget', '임시 Label').getByRole('button', { name: '삭제' }))
    await user.click(within(await screen.findByRole('dialog', { name: 'Label 삭제' })).getByRole('button', { name: '삭제' }))

    await waitFor(() => expect(section('Budget').queryByText('임시 Label')).not.toBeInTheDocument())
  })

  it('keeps the label when the confirmation is declined', async () => {
    const { user } = await openLabels()
    await addLabel(user, 'Budget', '임시 Label')
    await section('Budget').findByText('임시 Label')

    await user.click(labelRow('Budget', '임시 Label').getByRole('button', { name: '삭제' }))
    await user.click(within(await screen.findByRole('dialog')).getByRole('button', { name: '취소' }))

    expect(section('Budget').getByText('임시 Label')).toBeInTheDocument()
  })

  it('refuses to delete a label that deals use and says how many', async () => {
    const { user } = await openLabels()

    await user.click(labelRow('Budget', '단독 예산 확보').getByRole('button', { name: '삭제' }))
    await user.click(within(await screen.findByRole('dialog')).getByRole('button', { name: '삭제' }))

    expect(await screen.findByRole('alert')).toHaveTextContent(/사용 중인 Label은 삭제할 수 없습니다\. \(Deal \d+건\)/)
    expect(section('Budget').getByText('단독 예산 확보')).toBeInTheDocument()
  })
})

describe('BANT Label 권한 (T-LABEL-04)', () => {
  it('lets sales create a label through the gateway but not rename or remove it', async () => {
    await renderAt('/deals', { role: 'sales' })
    const created = await gateway.labels.create('budget', '영업이 만든 Label')

    await expect(gateway.labels.rename(created.id, '바꾼 이름')).rejects.toMatchObject({ status: 403 })
    await expect(gateway.labels.remove(created.id)).rejects.toMatchObject({ status: 403 })
  })
})
