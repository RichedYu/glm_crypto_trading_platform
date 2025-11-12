import dayjs from 'dayjs'
import Decimal from 'decimal.js'

export const formatCurrency = (value: number, digits = 2): string =>
  new Decimal(value).toNumber().toLocaleString(undefined, {
    minimumFractionDigits: digits,
    maximumFractionDigits: digits,
  })

export const formatPercent = (value: number, digits = 2): string =>
  `${value >= 0 ? '+' : ''}${value.toFixed(digits)}%`

export const formatDateTime = (value: string): string =>
  dayjs(value).format('YYYY-MM-DD HH:mm')

export const formatDuration = (start: string): string => {
  const durMinutes = dayjs().diff(dayjs(start), 'minute')
  if (durMinutes < 60) return `${durMinutes}m`
  if (durMinutes < 60 * 24) return `${Math.round(durMinutes / 60)}h`
  return `${Math.round(durMinutes / 60 / 24)}d`
}
