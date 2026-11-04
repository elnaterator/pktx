import { useState } from 'react'
import { FileDown } from 'lucide-react'
import { ICON_SIZE } from '../../theme'
import { fetchResumePdf, saveBlob } from '../../services/api'
import { useStoredState } from '../../hooks/useStoredState'
import { useToast } from '../../components/toast'
import { Button } from '../../components/Button'
import styles from './PdfDownload.module.css'

/** PDF styles, matching the backend's `PdfTheme`. */
export const PDF_THEMES = [
  { id: 'classic', label: 'Classic' },
  { id: 'modern', label: 'Modern' },
  { id: 'compact', label: 'Compact' },
] as const

export type PdfTheme = (typeof PDF_THEMES)[number]['id']

const isTheme = (v: unknown): v is PdfTheme => PDF_THEMES.some((t) => t.id === v)

/** Style picker + "Download PDF"; the picked style is remembered per browser. */
export default function PdfDownload({ versionId }: { versionId: number }) {
  const { error } = useToast()
  const [theme, setTheme] = useStoredState<PdfTheme>('pktx.pdfTheme', 'classic', isTheme)
  const [downloading, setDownloading] = useState(false)

  const download = async () => {
    setDownloading(true)
    try {
      const { blob, filename } = await fetchResumePdf(versionId, theme)
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
