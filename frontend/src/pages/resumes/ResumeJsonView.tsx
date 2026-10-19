import { useMemo } from 'react'
import { Save, Undo2 } from 'lucide-react'
import type { Resume } from '../../types'
import { useToast } from '../../components/toast'
import { useResumeMutations } from '../../hooks/queries'
import styles from './ResumeJsonView.module.css'

interface ResumeJsonViewProps {
  versionId: number
  /** The saved document. */
  data: Resume
  /** Unsaved text, kept by the parent so it survives switching views. */
  draft: string | null
  onDraftChange: (draft: string | null) => void
}

const format = (data: Resume) => JSON.stringify(data, null, 2)

/** Parses the editor text; returns the document or a message for the user. */
function parse(text: string): { value: Resume } | { error: string } {
  try {
    const value: unknown = JSON.parse(text)
    if (value === null || typeof value !== 'object' || Array.isArray(value)) {
      return { error: 'A resume must be a JSON object.' }
    }
    return { value: value as Resume }
  } catch (e) {
    return { error: e instanceof Error ? e.message : 'Invalid JSON' }
  }
}

/**
 * The whole resume as editable JSON Resume. One view for reading and editing:
 * type, then Save (top right) replaces the document. The server validates, so a
 * rejected save keeps your text and shows what to fix.
 */
export default function ResumeJsonView({ versionId, data, draft, onDraftChange }: ResumeJsonViewProps) {
  const { success, error } = useToast()
  const { replaceData } = useResumeMutations()

  const saved = useMemo(() => format(data), [data])
  const text = draft ?? saved
  const dirty = draft !== null && draft !== saved
  const parsed = useMemo(() => parse(text), [text])

  const handleSave = async () => {
    if ('error' in parsed) return
    try {
      await replaceData.mutateAsync({ id: versionId, data: parsed.value })
      onDraftChange(null)
      success('Resume saved')
    } catch (e) {
      error(e instanceof Error ? e.message : 'Failed to save resume')
    }
  }

  return (
    <section className={styles.container} data-testid="resume-json-view">
      <div className={styles.header}>
        <h2 className={styles.title}>JSON Resume</h2>
        <div className={styles.actions}>
          {dirty && (
            <button
              type="button"
              className={styles.revert}
              onClick={() => onDraftChange(null)}
              disabled={replaceData.isPending}
            >
              <Undo2 size={14} aria-hidden="true" />
              Revert
            </button>
          )}
          <button
            type="button"
            className={styles.save}
            onClick={handleSave}
            disabled={!dirty || 'error' in parsed || replaceData.isPending}
          >
            <Save size={14} aria-hidden="true" />
            {replaceData.isPending ? 'Saving…' : 'Save'}
          </button>
        </div>
      </div>

      <textarea
        className={`${styles.editor} ${'error' in parsed ? styles.editorInvalid : ''}`}
        value={text}
        onChange={(e) => onDraftChange(e.target.value)}
        spellCheck={false}
        aria-label="Resume JSON"
        aria-invalid={'error' in parsed}
      />
      {'error' in parsed && (
        <p className={styles.problem} role="alert">
          {parsed.error}
        </p>
      )}
    </section>
  )
}
