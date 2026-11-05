/**
 * 通用 XLSX 导出：浏览器端生成 .xlsx 并触发下载（无额外运行时依赖）。
 *
 * 为什么不是一句 XLSX.write？
 * - SheetJS 社区版（xlsx 0.18.x）**不写单元格样式、也不写冻结窗格**（样式属 Pro 版能力），
 *   社区版只会输出列宽/自动筛选/行高等工作表结构。本工具需要「表头加粗 + 浅蓝底 + 冻结首行」，
 *   因此用无新增依赖的方式做最小 OOXML 补丁：
 *   1) 以 STORED（不压缩）方式写出 xlsx，便于安全解析并重建 ZIP；
 *   2) 改写 xl/styles.xml（追加加粗字体、solid 填充与表头 cellXfs）与 sheet1.xml（表头 s="1" + pane 冻结）；
 *   3) 重算 CRC32 后重建 ZIP，其余条目原样保留。
 * 只动 styles.xml 与首张工作表，Excel / WPS / LibreOffice 均可正常打开。
 *
 * 调用方式与 utils/csv.ts 对齐：rows 为二维单元格数组（null/undefined 视作空单元格）。
 */

import type { CsvCell } from './csv'

export type XlsxCell = CsvCell

export interface XlsxColumn {
  label: string
  /** 列宽（字符数，中文按 2 个字符估算）；不传则按表头与内容自动估算 */
  width?: number
}

export interface XlsxTable {
  columns: XlsxColumn[]
  rows: XlsxCell[][]
}

export interface XlsxOptions {
  /** 工作表名（默认 Sheet1；非法字符替换为空格，超长截断到 31 字符） */
  sheetName?: string
}

const XLSX_MIME = 'application/vnd.openxmlformats-officedocument.spreadsheetml.sheet'

// ---------------------------------------------------------------- CRC32 / ZIP

const CRC_TABLE = (() => {
  const table = new Uint32Array(256)
  for (let i = 0; i < 256; i += 1) {
    let value = i
    for (let bit = 0; bit < 8; bit += 1) {
      value = value & 1 ? 0xedb88320 ^ (value >>> 1) : value >>> 1
    }
    table[i] = value >>> 0
  }
  return table
})()

function crc32(bytes: Uint8Array): number {
  let crc = 0xffffffff
  for (let i = 0; i < bytes.length; i += 1) {
    crc = CRC_TABLE[(crc ^ bytes[i]) & 0xff] ^ (crc >>> 8)
  }
  return (crc ^ 0xffffffff) >>> 0
}

interface ZipEntry {
  name: string
  data: Uint8Array
  flags: number
  time: number
  date: number
}

/** 解析 SheetJS 以 compression:false 写出的 STORED ZIP（不处理 data descriptor / ZIP64）。 */
function parseStoredZip(buffer: ArrayBuffer): ZipEntry[] {
  const view = new DataView(buffer)
  const bytes = new Uint8Array(buffer)
  const decoder = new TextDecoder()
  const entries: ZipEntry[] = []
  let offset = 0

  while (offset + 30 <= bytes.length && view.getUint32(offset, true) === 0x04034b50) {
    const flags = view.getUint16(offset + 6, true)
    const method = view.getUint16(offset + 8, true)
    const time = view.getUint16(offset + 10, true)
    const date = view.getUint16(offset + 12, true)
    const size = view.getUint32(offset + 22, true)
    const nameLength = view.getUint16(offset + 26, true)
    const extraLength = view.getUint16(offset + 28, true)
    if (method !== 0) {
      throw new Error('xlsx 导出失败：仅支持 STORED ZIP')
    }
    if (flags & 0x0008) {
      throw new Error('xlsx 导出失败：不支持 data descriptor')
    }
    const name = decoder.decode(bytes.subarray(offset + 30, offset + 30 + nameLength))
    const start = offset + 30 + nameLength + extraLength
    entries.push({ name, data: bytes.subarray(start, start + size), flags, time, date })
    offset = start + size
  }

  if (entries.length === 0) {
    throw new Error('xlsx 导出失败：无法解析工作簿')
  }
  return entries
}

/** 按 STORED 方式重建 ZIP（重算 CRC 与偏移）。 */
function buildZip(entries: ZipEntry[]): Uint8Array {
  const encoder = new TextEncoder()
  const localParts: Uint8Array[] = []
  const centralParts: Uint8Array[] = []
  let localOffset = 0
  let centralSize = 0

  for (const entry of entries) {
    const nameBytes = encoder.encode(entry.name)
    const crc = crc32(entry.data)

    const local = new Uint8Array(30 + nameBytes.length)
    const localView = new DataView(local.buffer)
    localView.setUint32(0, 0x04034b50, true)
    localView.setUint16(4, 20, true)
    localView.setUint16(6, entry.flags & ~0x0008, true)
    localView.setUint16(8, 0, true)
    localView.setUint16(10, entry.time, true)
    localView.setUint16(12, entry.date, true)
    localView.setUint32(14, crc, true)
    localView.setUint32(18, entry.data.length, true)
    localView.setUint32(22, entry.data.length, true)
    localView.setUint16(26, nameBytes.length, true)
    localView.setUint16(28, 0, true)
    local.set(nameBytes, 30)
    localParts.push(local, entry.data)

    const central = new Uint8Array(46 + nameBytes.length)
    const centralView = new DataView(central.buffer)
    centralView.setUint32(0, 0x02014b50, true)
    centralView.setUint16(4, 20, true)
    centralView.setUint16(6, 20, true)
    centralView.setUint16(8, entry.flags & ~0x0008, true)
    centralView.setUint16(10, 0, true)
    centralView.setUint16(12, entry.time, true)
    centralView.setUint16(14, entry.date, true)
    centralView.setUint32(16, crc, true)
    centralView.setUint32(20, entry.data.length, true)
    centralView.setUint32(24, entry.data.length, true)
    centralView.setUint16(28, nameBytes.length, true)
    centralView.setUint16(30, 0, true)
    centralView.setUint16(32, 0, true)
    centralView.setUint16(34, 0, true)
    centralView.setUint16(36, 0, true)
    centralView.setUint32(38, 0, true)
    centralView.setUint32(42, localOffset, true)
    central.set(nameBytes, 46)
    centralParts.push(central)

    localOffset += local.length + entry.data.length
    centralSize += central.length
  }

  const eocd = new Uint8Array(22)
  const eocdView = new DataView(eocd.buffer)
  eocdView.setUint32(0, 0x06054b50, true)
  eocdView.setUint16(4, 0, true)
  eocdView.setUint16(6, 0, true)
  eocdView.setUint16(8, entries.length, true)
  eocdView.setUint16(10, entries.length, true)
  eocdView.setUint32(12, centralSize, true)
  eocdView.setUint32(16, localOffset, true)
  eocdView.setUint16(20, 0, true)

  const output = new Uint8Array(localOffset + centralSize + eocd.length)
  let cursor = 0
  for (const part of localParts) {
    output.set(part, cursor)
    cursor += part.length
  }
  for (const part of centralParts) {
    output.set(part, cursor)
    cursor += part.length
  }
  output.set(eocd, cursor)
  return output
}

// ------------------------------------------------------------- OOXML 样式补丁

/**
 * 在 SheetJS 生成的 styles.xml 中追加：
 * - 第 2 个字体（加粗）→ fontId=1
 * - 第 3 个填充（浅蓝底）→ fillId=2
 * - 第 2 个 cellXfs（引用 fontId=1 / fillId=2）→ 样式索引 s=1
 */
function patchStyleSheet(xml: string): string {
  let patched = xml.replace(/<fonts count="(\d+)">/, (_match, count: string) => {
    return '<fonts count="' + (Number(count) + 1) + '">'
  })
  patched = patched.replace(
    '</fonts>',
    '<font><b/><sz val="11"/><color theme="1"/><name val="Calibri"/><family val="2"/><scheme val="minor"/></font></fonts>',
  )
  patched = patched.replace(/<fills count="(\d+)">/, (_match, count: string) => {
    return '<fills count="' + (Number(count) + 1) + '">'
  })
  patched = patched.replace(
    '</fills>',
    '<fill><patternFill patternType="solid"><fgColor rgb="FFDDEBF7"/><bgColor indexed="64"/></patternFill></fill></fills>',
  )
  patched = patched.replace(/<cellXfs count="(\d+)">/, (_match, count: string) => {
    return '<cellXfs count="' + (Number(count) + 1) + '">'
  })
  patched = patched.replace(
    '</cellXfs>',
    '<xf numFmtId="0" fontId="1" fillId="2" borderId="0" xfId="0" applyFont="1" applyFill="1"/></cellXfs>',
  )
  return patched
}

/** 首行表头补 s="1"，并在 sheetView 上冻结第 1 行。 */
function patchWorksheet(xml: string): string {
  let patched = xml
  if (!patched.includes('<pane ')) {
    patched = patched.replace(
      /<sheetView\b([^>]*)\/>/,
      '<sheetView$1><pane ySplit="1" topLeftCell="A2" activePane="bottomLeft" state="frozen"/>' +
        '<selection pane="bottomLeft" activeCell="A2" sqref="A2"/></sheetView>',
    )
  }
  return patched.replace(
    /<c r="([A-Z]+)1"((?:\s+[A-Za-z]+="[^"]*")*)>/g,
    (match, ref: string, attrs: string) => {
      if (/\ss="/.test(attrs)) {
        return match
      }
      return '<c r="' + ref + '1" s="1"' + attrs + '>'
    },
  )
}

function patchHeaderStyle(entries: ZipEntry[]): void {
  const encoder = new TextEncoder()
  const decoder = new TextDecoder()
  for (const entry of entries) {
    if (entry.name === 'xl/styles.xml') {
      entry.data = encoder.encode(patchStyleSheet(decoder.decode(entry.data)))
    } else if (entry.name === 'xl/worksheets/sheet1.xml') {
      entry.data = encoder.encode(patchWorksheet(decoder.decode(entry.data)))
    }
  }
}

// --------------------------------------------------------------- 表格构建/下载

async function loadXlsx(): Promise<typeof import('xlsx')> {
  const mod = (await import('xlsx')) as typeof import('xlsx') & { default?: typeof import('xlsx') }
  return mod.default ?? mod
}

function sanitizeSheetName(name: string | undefined): string {
  const cleaned = (name || 'Sheet1').replace(/[\\/?*[\]:]/g, ' ').trim()
  return (cleaned || 'Sheet1').slice(0, 31)
}

/** 估算显示宽度：CJK 字符按 2 个字符计。 */
function displayWidth(value: XlsxCell): number {
  const text = value === null || value === undefined ? '' : String(value)
  let width = 0
  for (const char of text) {
    width += /[\u1100-\u115f\u2e80-\ua4cf\uac00-\ud7a3\uf900-\ufaff\ufe30-\ufe4f\uff00-\uff60\uffe0-\uffe6]/.test(char)
      ? 2
      : 1
  }
  return width
}

function resolveWidths(columns: XlsxColumn[], rows: XlsxCell[][]): number[] {
  return columns.map((column, index) => {
    let measured = displayWidth(column.label)
    for (const row of rows) {
      measured = Math.max(measured, displayWidth(row[index]))
    }
    const width = column.width ?? measured
    return Math.min(60, Math.max(8, Math.round(width + 2)))
  })
}

/** 构建 .xlsx 字节（供下载与测试复用）。 */
export async function buildXlsxBuffer(table: XlsxTable, options: XlsxOptions = {}): Promise<Uint8Array> {
  const { columns, rows } = table
  if (columns.length === 0) {
    throw new Error('至少需要一列表头')
  }
  const XLSX = await loadXlsx()
  const aoa: XlsxCell[][] = [
    columns.map((column) => column.label),
    ...rows.map((row) => columns.map((_column, index) => row[index] ?? null)),
  ]
  const sheet = XLSX.utils.aoa_to_sheet(aoa, { cellDates: false })
  sheet['!cols'] = resolveWidths(columns, rows).map((width) => ({ wch: width }))
  sheet['!rows'] = [{ hpt: 24 }]
  sheet['!autofilter'] = {
    ref: XLSX.utils.encode_range({
      s: { c: 0, r: 0 },
      e: { c: columns.length - 1, r: Math.max(aoa.length - 1, 0) },
    }),
  }

  const workbook = XLSX.utils.book_new()
  XLSX.utils.book_append_sheet(workbook, sheet, sanitizeSheetName(options.sheetName))
  const written = XLSX.write(workbook, { bookType: 'xlsx', type: 'array', compression: false }) as ArrayBuffer
  const buffer = (written instanceof ArrayBuffer ? written : (written as Uint8Array).buffer) as ArrayBuffer
  const entries = parseStoredZip(buffer)
  patchHeaderStyle(entries)
  return buildZip(entries)
}

function saveBlob(filename: string, bytes: Uint8Array): void {
  const name = /\.xlsx$/i.test(filename) ? filename : filename + '.xlsx'
  const buffer = bytes.buffer.slice(bytes.byteOffset, bytes.byteOffset + bytes.byteLength) as ArrayBuffer
  const blob = new Blob([buffer], { type: XLSX_MIME })
  const url = URL.createObjectURL(blob)
  const link = document.createElement('a')
  link.href = url
  link.download = name
  document.body.appendChild(link)
  link.click()
  document.body.removeChild(link)
  URL.revokeObjectURL(url)
}

/** 导出 { columns, rows } 为 .xlsx（浏览器触发下载）。 */
export async function downloadXlsx(
  filename: string,
  table: XlsxTable,
  options: XlsxOptions = {},
): Promise<void> {
  const bytes = await buildXlsxBuffer(table, options)
  saveBlob(filename, bytes)
}

/**
 * 与 downloadCsv 对齐的调用方式：rows 第一行为表头，其余为数据。
 * 例：downloadXlsxRows('erp-dashboard.xlsx', csvRows())
 */
export async function downloadXlsxRows(
  filename: string,
  rows: CsvCell[][],
  options: XlsxOptions = {},
): Promise<void> {
  if (rows.length === 0) {
    throw new Error('没有可导出的数据')
  }
  const [header, ...body] = rows
  const columns: XlsxColumn[] = header.map((cell) => ({
    label: cell === null || cell === undefined ? '' : String(cell),
  }))
  await downloadXlsx(filename, { columns, rows: body }, options)
}
