import { useForm, Controller } from 'react-hook-form'
import { zodResolver } from '@hookform/resolvers/zod'
import { AutoResizeTextarea } from '../../components/AutoResizeTextarea'
import { TagInput } from '../../components/TagInput'
import { SectionCard } from '../../components/SectionCard'
import { MarkdownContent } from '../../components/MarkdownContent'
import { EditForm, FormField } from '../../components/EditForm'
import form from '../../components/EditForm.module.css'
import { noteCreateSchema, type NoteCreateInput, type NoteFormInput } from '../../schemas/note'
import type { Note } from '../../types'
import { PanelHeader } from '../../components/PanelHeader'
import { formatDate } from '../../utils/formatDate'
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

/** Edit and create. Tags are edited here only on create (the detail sidebar owns them). */
function NoteForm({ mode, note, allTags = [], onSave, onCancel }: Omit<NotePanelProps, 'onEdit' | 'onDelete'>) {
  const { register, handleSubmit, control, formState: { errors, isSubmitting } } = useForm<NoteFormInput, unknown, NoteCreateInput>({
    resolver: zodResolver(noteCreateSchema),
    mode: 'onBlur',
    defaultValues: {
      title: note?.title ?? '',
      content: note?.content ?? '',
      tags: note?.tags ?? [],
    },
  })

  return (
    <EditForm
      heading={mode === 'create' ? 'New note' : `Editing ${note?.title}`}
      onSubmit={handleSubmit(async (data) => {
        await onSave?.(data)
      })}
      onCancel={() => onCancel?.()}
      saving={isSubmitting}
    >
      <div className={form.fields}>
        <FormField label="Title" htmlFor="note-title" required error={errors.title}>
          <input
            id="note-title"
            className={form.inputTitle}
            type="text"
            autoFocus
            placeholder="Note title"
            aria-invalid={!!errors.title}
            {...register('title')}
          />
        </FormField>
        {mode === 'create' && (
          <FormField label="Tags">
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
          </FormField>
        )}
        <FormField label="Content" htmlFor="note-content">
          <Controller
            control={control}
            name="content"
            render={({ field }) => (
              <AutoResizeTextarea
                id="note-content"
                className={form.textareaLong}
                value={field.value ?? ''}
                onChange={field.onChange}
                placeholder="Write your note here..."
              />
            )}
          />
        </FormField>
      </div>
    </EditForm>
  )
}

export function NotePanel(props: NotePanelProps) {
  const { mode, note, onEdit, onDelete } = props
  if (mode !== 'view') return <NoteForm {...props} />

  return (
    <div>
      <PanelHeader entity="note" title={note?.title} onEdit={onEdit} onDelete={onDelete} />

      <div className={styles.meta}>
        {note?.updated_at && (
          <span className={styles.updatedDate}>Updated {formatDate(note.updated_at)}</span>
        )}
      </div>

      <SectionCard>
        {note?.content ? (
          <MarkdownContent>{note.content}</MarkdownContent>
        ) : (
          <p className={styles.placeholderText}>No content yet.</p>
        )}
      </SectionCard>
    </div>
  )
}
