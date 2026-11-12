import { Check, Copy } from 'lucide-react'
import { ICON_SIZE } from '../../theme'
import { fetchNotePdf } from '../../services/api'
import { useCopyToClipboard } from '../../hooks/useCopyToClipboard'
import { markdownToText } from '../../utils/markdownToText'
import { Button } from '../../components/Button'
import PdfDownload from '../../components/PdfDownload'
import type { Note } from '../../types'
import styles from './NoteActions.module.css'

/**
 * Take a note elsewhere: copy it as plain text (markdown stripped) or
 * download it as a letter PDF headed by the default resume's contact details.
 */
export function NoteActions({ note }: { note: Note }) {
  const { copied, copy } = useCopyToClipboard()
  const Icon = copied ? Check : Copy

  return (
    <div className={styles.actions}>
      <Button
        size="sm"
        disabled={!note.content.trim()}
        title="Copy as plain text"
        onClick={() => copy(markdownToText(note.content))}
      >
        <Icon size={ICON_SIZE.sm} aria-hidden="true" />
        <span aria-live="polite">{copied ? 'Copied' : 'Copy text'}</span>
      </Button>
      <PdfDownload fetchPdf={(theme) => fetchNotePdf(note.id, theme)} />
    </div>
  )
}
