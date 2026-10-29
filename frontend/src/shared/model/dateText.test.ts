import { describe, expect, it } from 'vitest'
import { dateValueError, finalizeDateText, formatDateTyping, isDateValue, isoToDateText, parseDateText } from './dateText'

describe('formatDateTyping (AC-D1, AC-D2)', () => {
  it.each([
    ['2026', '2026'],
    ['20261', '2026.1'],
    ['202611', '2026.11'],
    ['2026112', '2026.11.2'],
    ['20261120', '2026.11.20'],
    ['202611201', '2026.11.20'],
    ['2026-11-20', '2026.11.20'],
    ['2026/11/20', '2026.11.20'],
    ['2026.11.20', '2026.11.20'],
    ['2026.', '2026.'],
    ['2026.1.', '2026.1.'],
    ['2026.1.5', '2026.1.5'],
    ['2026a11', '2026.11'],
    ['2026..11', '2026.11'],
    ['', ''],
  ])('turns %j into %j', (raw, text) => {
    expect(formatDateTyping(raw)).toBe(text)
  })

  it.each([
    [' 2026-11-20', '2026.11.20'],
    ['2026. 11. 20.', '2026.11.20'],
    ['2026-11-20 ', '2026.11.20'],
    ['  2026 / 11 / 20  ', '2026.11.20'],
  ])('cleans the pasted text %j into %j regardless of its length', (raw, text) => {
    expect(formatDateTyping(raw)).toBe(text)
  })

  it('drops digits that do not fit the day field', () => {
    expect(formatDateTyping('2026112099')).toBe('2026.11.20')
  })

  it('moves overflowing digits of a typed month into the day', () => {
    expect(formatDateTyping('2026.123')).toBe('2026.12.3')
  })
})

describe('finalizeDateText (AC-D2)', () => {
  it('pads a one-digit month and day', () => {
    expect(finalizeDateText('2026.1.5')).toBe('2026.01.05')
  })

  it('pads only the day when the month already has two digits', () => {
    expect(finalizeDateText('2026.11.5')).toBe('2026.11.05')
  })

  it.each(['2026.1', '2026', '2026.', '2026.1.', '', '26.1.5'])('leaves %j as it is', (text) => {
    expect(finalizeDateText(text)).toBe(text)
  })

  it('leaves a complete text unchanged', () => {
    expect(finalizeDateText('2026.11.20')).toBe('2026.11.20')
  })
})

describe('parseDateText (AC-D1, AC-D3)', () => {
  it('reads a complete date as an ISO value', () => {
    expect(parseDateText('2026.11.20')).toEqual({ kind: 'valid', iso: '2026-11-20' })
  })

  it('reads the boundary dates as valid', () => {
    expect(parseDateText('1900.01.01')).toEqual({ kind: 'valid', iso: '1900-01-01' })
    expect(parseDateText('2999.12.31')).toEqual({ kind: 'valid', iso: '2999-12-31' })
  })

  it('accepts February 29 of a leap year', () => {
    expect(parseDateText('2024.02.29')).toEqual({ kind: 'valid', iso: '2024-02-29' })
  })

  it('rejects February 29 of a non-leap year', () => {
    expect(parseDateText('2025.02.29')).toEqual({ kind: 'invalid' })
  })

  it('rejects day 30 of February and month 13', () => {
    expect(parseDateText('2026.02.30')).toEqual({ kind: 'invalid' })
    expect(parseDateText('2026.13.01')).toEqual({ kind: 'invalid' })
  })

  it('rejects month 00 and day 00', () => {
    expect(parseDateText('2026.00.10')).toEqual({ kind: 'invalid' })
    expect(parseDateText('2026.10.00')).toEqual({ kind: 'invalid' })
  })

  it('rejects day 31 of a 30-day month', () => {
    expect(parseDateText('2026.04.31')).toEqual({ kind: 'invalid' })
  })

  it('reports dates before 1900-01-01 and after 2999-12-31 as out of range', () => {
    expect(parseDateText('1899.12.31')).toEqual({ kind: 'out_of_range' })
    expect(parseDateText('3000.01.01')).toEqual({ kind: 'out_of_range' })
  })

  it.each(['2026.1', '2026.11.2', '2026', '2026.', '2026.11.', '202'])('reports %j as incomplete', (text) => {
    expect(parseDateText(text)).toEqual({ kind: 'incomplete' })
  })

  it('reads a blank text as empty', () => {
    expect(parseDateText('')).toEqual({ kind: 'empty' })
    expect(parseDateText('   ')).toEqual({ kind: 'empty' })
  })

  it('reads a finalized text as a date', () => {
    expect(parseDateText(finalizeDateText('2026.1.5'))).toEqual({ kind: 'valid', iso: '2026-01-05' })
  })
})

describe('isoToDateText (AC-D6)', () => {
  it('shows an ISO date with dots', () => {
    expect(isoToDateText('2026-11-20')).toBe('2026.11.20')
  })

  it('keeps an empty value empty', () => {
    expect(isoToDateText('')).toBe('')
  })

  it('keeps a non-ISO text as it is', () => {
    expect(isoToDateText('2026.13.4')).toBe('2026.13.4')
    expect(isoToDateText('abc')).toBe('abc')
  })
})

describe('isDateValue', () => {
  it('accepts a real ISO date within the range', () => {
    expect(isDateValue('2026-11-20')).toBe(true)
    expect(isDateValue('1900-01-01')).toBe(true)
    expect(isDateValue('2999-12-31')).toBe(true)
    expect(isDateValue('2024-02-29')).toBe(true)
  })

  it.each(['', '2026-13-01', '2025-02-29', '1899-12-31', '3000-01-01', '2026.11.20', '2026-1-5', '2026-11-20 ', 'abc'])('rejects %j', (value) => {
    expect(isDateValue(value)).toBe(false)
  })
})

describe('dateValueError (AC-D3)', () => {
  it('has no message for an empty or valid value', () => {
    expect(dateValueError('')).toBeNull()
    expect(dateValueError('2026-11-20')).toBeNull()
  })

  it('asks for yyyymmdd on an incomplete text', () => {
    expect(dateValueError('2026.1')).toBe('날짜를 yyyymmdd 형식으로 입력하세요.')
    expect(dateValueError('2026.11.2')).toBe('날짜를 yyyymmdd 형식으로 입력하세요.')
  })

  it('says the date does not exist on an impossible date', () => {
    expect(dateValueError('2026.13.04')).toBe('없는 날짜입니다.')
    expect(dateValueError('2026-02-30')).toBe('없는 날짜입니다.')
  })

  it('names the allowed range on an out-of-range date', () => {
    expect(dateValueError('1899.12.31')).toBe('1900.01.01부터 2999.12.31 사이로 입력하세요.')
    expect(dateValueError('3000-01-01')).toBe('1900.01.01부터 2999.12.31 사이로 입력하세요.')
  })
})
