import { useState } from 'react'
import { FileDown } from 'lucide-react'
import { ICON_SIZE } from '../theme'
import { saveBlob, type DataExport } from '../services/api'
import { useStoredState } from '../hooks/useStoredState'
import { useToast } from './toast'
import { Button } from './Button'
import styles from './PdfDownload.module.css'

/** PDF styles in picker order, matching the backend's `PdfTheme`; the first is the default. */
export const PDF_THEMES = [
  { id: 'modern', label: 'Modern' },
  { id: 'compact', label: 'Compact' },
  { id: 'classic', label: 'Classic' },
  { id: 'jakes', label: "Jake's" },
  { id: 'executive', label: 'Executive' },
  { id: 'minimal', label: 'Minimal' },
] as const

export type PdfTheme = (typeof PDF_THEMES)[number]['id']

const isTheme = (v: unknown): v is PdfTheme => PDF_THEMES.some((t) => t.id === v)

interface PdfDownloadProps {
  /** Fetches the document rendered in the picked style. */
  fetchPdf: (theme: PdfTheme) => Promise<DataExport>
}

/**
 * Style picker + "Download PDF" for any document the backend renders. The
 * picked style is remembered per browser and shared by every such control.
 */
export default function PdfDownload({ fetchPdf }: PdfDownloadProps) {
  const { error } = useToast()
  const [theme, setTheme] = useStoredState<PdfTheme>('pktx.pdfTheme', PDF_THEMES[0].id, isTheme)
  const [downloading, setDownloading] = useState(false)

  const download = async () => {
    setDownloading(true)
    try {
      const { blob, filename } = await fetchPdf(theme)
      saveBlob(blob, filename)
    } catch {
      error('Failed to export PDF')
    } finally {
      setDownloading(false)
    }
  }

  return (
    <div className={styles.group}>
      <select
        className={styles.select}
        aria-label="PDF style"
        value={theme}
        disabled={downloading}
        onChange={(e) => isTheme(e.target.value) && setTheme(e.target.value)}
      >
        {PDF_THEMES.map((t) => (
          <option key={t.id} value={t.id}>
            {t.label}
          </option>
        ))}
      </select>
      <Button
        size="sm"
        onClick={download}
        disabled={downloading}
        aria-busy={downloading}
      >
        <FileDown size={ICON_SIZE.sm} aria-hidden="true" />
        {downloading ? 'Preparing PDF…' : 'Download PDF'}
      </Button>
    </div>
  )
}
