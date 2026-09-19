export function fmtNum(value: unknown, digits = 2): string {
  if (value === null || value === undefined || value === '') {
    return '-'
  }
  const num = Number(value)
  return Number.isNaN(num) ? String(value) : num.toFixed(digits)
}

export function fmtInt(value: unknown): string {
  if (value === null || value === undefined || value === '') {
    return '-'
  }
  const num = Number(value)
  return Number.isNaN(num) ? String(value) : String(Math.trunc(num))
}

export function fmtText(value: unknown): string {
  return value === null || value === undefined || value === '' ? '-' : String(value)
}

export function fmtDate(value: unknown): string {
  if (value === null || value === undefined || value === '') {
    return '-'
  }
  return String(value).slice(0, 10)
}

export function fmtDateTime(value: unknown): string {
  if (value === null || value === undefined || value === '') {
    return '-'
  }
  return String(value).replace('T', ' ').slice(0, 19)
}
