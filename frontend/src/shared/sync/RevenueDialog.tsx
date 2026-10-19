import { useState } from 'react'
import { amountInputError, formatThousandWon, parseAmountInput, REVENUE_AMOUNT_LABEL } from '../model/money'
import { AmountInput } from '../ui/AmountInput'
import { Modal } from '../ui/Modal'

export const DATE_MESSAGE = '매출일을 입력하세요.'

interface RevenueDialogProps {
  /** SyncPlan.notice("Status가 '계약완료'로, Forecast가 'Won'으로 함께 변경됩니다.") */
  notice: string
  /** 기존 예상 매출금액·Expected Close로 미리 채운다. */
  defaultAmount?: number
  defaultDate?: string
  /** finalizePlan 거부 문구 등 대화상자 안에 보일 오류. */
  error?: string | null
  onConfirm: (resolution: { revenueAmount: number; revenueDate: string }) => void
  onCancel: () => void
}

/** "매출 확정" 팝업: 실제 매출금액·매출일이 모두 유효할 때만 `확정`이 활성. 취소는 변경 없음. */
export function RevenueDialog({ notice, defaultAmount, defaultDate, error, onConfirm, onCancel }: RevenueDialogProps) {
  const initialAmount = defaultAmount === undefined ? '' : formatThousandWon(defaultAmount)
  const [amount, setAmount] = useState(initialAmount)
  const [date, setDate] = useState(defaultDate ?? '')
  const [touched, setTouched] = useState({ amount: false, date: false })
  // 보이는 값을 건드리지 않았으면 원래 원 값을 그대로 쓴다.
  const parsed = defaultAmount !== undefined && amount === initialAmount ? defaultAmount : parseAmountInput(amount)
  const valid = parsed !== null && date !== ''

  return (
    <Modal
      title="매출 확정"
      onClose={onCancel}
      footer={
        <>
          <button type="button" onClick={onCancel}>
            취소
          </button>
          <button
            type="button"
            className="primary"
            disabled={!valid}
            onClick={() => parsed !== null && onConfirm({ revenueAmount: parsed, revenueDate: date })}
          >
            확정
          </button>
        </>
      }
    >
      <p>{notice}</p>
      <div className="field">
        <label>
          <span>{REVENUE_AMOUNT_LABEL}</span>
          <AmountInput
            name="revenueAmount"
            value={amount}
            onChange={(text) => {
              setAmount(text)
              setTouched((t) => ({ ...t, amount: true }))
            }}
            onBlur={() => setTouched((t) => ({ ...t, amount: true }))}
          />
        </label>
        {touched.amount && parsed === null && <p className="field-error">{amountInputError(amount)}</p>}
      </div>
      <div className="field">
        <label>
          <span>매출일(실제 값)</span>
          <input
            name="revenueDate"
            type="date"
            value={date}
            onChange={(e) => {
              setDate(e.target.value)
              setTouched((t) => ({ ...t, date: true }))
            }}
            onBlur={() => setTouched((t) => ({ ...t, date: true }))}
          />
        </label>
        {touched.date && date === '' && <p className="field-error">{DATE_MESSAGE}</p>}
      </div>
      {error && (
        <p role="alert" className="field-error">
          {error}
        </p>
      )}
    </Modal>
  )
}
