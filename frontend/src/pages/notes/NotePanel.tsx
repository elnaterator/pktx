import { useForm, Controller } from 'react-hook-form'
import { zodResolver } from '@hookform/resolvers/zod'
import { Pencil, Trash2, Check, X } from 'lucide-react'
import { ICON_SIZE } from '../../theme'
import { AutoResizeTextarea } from '../../components/AutoResizeTextarea'
import { TagInput } from '../../components/TagInput'
import { SectionCard } from '../../components/SectionCard'
import { MarkdownContent } from '../../components/MarkdownContent'
import { noteCreateSchema, type NoteCreateInput } from '../../schemas/note'
import type { Note } from '../../types'
import styles from './NotePanel.module.css'

interface NotePanelProps {
  mode: 'view' | 'edit' | 'create'
  note?: Note
  allTags?: string[]
  onSave?: (data: NoteCreateInput) => Promise<void>
  onCancel?: () => void
  onEdit?: () => void
  onDelete?: () => void
}

export function NotePanel({
  mode,
  note,
  allTags = [],
  onSave,
  onCancel,
  onEdit,
  onDelete,
}: NotePanelProps) {
  const isEditable = mode !== 'view'

  const { register, handleSubmit, control, formState: { errors, isSubmitting } } = useForm<NoteCreateInput>({
    resolver: zodResolver(noteCreateSchema),
    mode: 'onBlur',
    defaultValues: {
      title: note?.title ?? '',
      content: note?.content ?? '',
      tags: note?.tags ?? [],
    },
  })

  const handleFormSave = handleSubmit(async (data) => {
    await onSave?.(data)
  })

  return (
    <div className={mode === 'create' ? styles.panelCreate : undefined}>
      <div className={styles.topBar}>
        {isEditable ? (
          <input
            className={styles.titleInput}
            type="text"
            autoFocus
            placeholder="Note title"
            aria-label="Title"
            {...register('title')}
          />
        ) : (
          <h2 className={styles.topBarTitle}>{note?.title}</h2>
        )}
        <div className={styles.topBarActions}>
          {isEditable ? (
            <>
              <button
                type="button"
                className={styles.saveIconButton}
                onClick={handleFormSave}
                disabled={isSubmitting}
                aria-label="Save"
              >
                <Check size={ICON_SIZE.md} />
              </button>
              <button
                type="button"
                className={styles.cancelIconButton}
                onClick={onCancel}
                aria-label="Cancel"
              >
                <X size={ICON_SIZE.md} />
              </button>
            </>
          ) : (
            <>
              <button type="button" className={styles.editButton} onClick={onEdit} aria-label="Edit note">
                <Pencil size={ICON_SIZE.md} />
              </button>
              <button type="button" className={styles.deleteButton} onClick={onDelete} aria-label="Delete note">
                <Trash2 size={ICON_SIZE.md} />
              </button>
            </>
          )}
        </div>
      </div>

      {errors.title && <p className={styles.formError}>{errors.title.message}</p>}

      {isEditable ? (
        mode === 'create' && <div className={styles.metaEdit}>
          <div className={styles.metaField}>
            <label className={styles.metaLabel}>Tags</label>
            <Controller
              control={control}
              name="tags"
              render={({ field }) => (
                <TagInput
                  value={field.value ?? []}
                  onChange={field.onChange}
                  availableTags={allTags}
                  allowCreate
                />
              )}
            />
          </div>
        </div>
      ) : (
        <div className={styles.meta}>
          {note?.updated_at && (
            <span className={styles.updatedDate}>Updated {new Date(note.updated_at).toLocaleDateString()}</span>
          )}
        </div>
      )}

      <SectionCard>
        {isEditable ? (
          <Controller
            control={control}
            name="content"
            render={({ field }) => (
              <AutoResizeTextarea
                className={styles.contentTextarea}
                aria-label="Content"
                value={field.value ?? ''}
                onChange={field.onChange}
                placeholder="Write your note here..."
              />
            )}
          />
        ) : (
          note?.content ? (
            <MarkdownContent>{note.content}</MarkdownContent>
          ) : (
            <p className={styles.placeholderText}>No content yet.</p>
          )
        )}
      </SectionCard>
    </div>
  )
}
