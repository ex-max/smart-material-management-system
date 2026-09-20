/** 无依赖 CSV 导出：浏览器 Blob 下载，带 UTF-8 BOM 便于 Excel 识别中文。 */
export type CsvCell = string | number | null | undefined

function escapeCell(cell: CsvCell): string {
  const text = cell === null || cell === undefined ? '' : String(cell)
  return /[",\n\r]/.test(text) ? '"' + text.replace(/"/g, '""') + '"' : text
}

export function downloadCsv(filename: string, rows: CsvCell[][]): void {
  const csv = rows.map((row) => row.map(escapeCell).join(',')).join('\r\n')
  const blob = new Blob(['\ufeff' + csv], { type: 'text/csv;charset=utf-8;' })
  const url = URL.createObjectURL(blob)
  const link = document.createElement('a')
  link.href = url
  link.download = filename
  document.body.appendChild(link)
  link.click()
  document.body.removeChild(link)
  URL.revokeObjectURL(url)
}
