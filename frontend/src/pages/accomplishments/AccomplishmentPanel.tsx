import { useForm, Controller } from 'react-hook-form'
import { zodResolver } from '@hookform/resolvers/zod'
import { AutoResizeTextarea } from '../../components/AutoResizeTextarea'
import { DateInput } from '../../components/DateInput'
import { TagInput } from '../../components/TagInput'
import { SectionCard } from '../../components/SectionCard'
import { MarkdownContent } from '../../components/MarkdownContent'
import { EditForm, FormField } from '../../components/EditForm'
import form from '../../components/EditForm.module.css'
import { accomplishmentCreateSchema, type AccomplishmentCreateInput, type AccomplishmentFormInput } from '../../schemas/accomplishment'
import type { Accomplishment } from '../../types'
import { PanelHeader } from '../../components/PanelHeader'
import styles from './AccomplishmentPanel.module.css'

const STAR_FIELDS: { key: 'situation' | 'task' | 'action' | 'result'; label: string; placeholder: string }[] = [
  { key: 'situation', label: 'Situation', placeholder: 'Describe the context or background…' },
  { key: 'task', label: 'Task', placeholder: 'What was your specific responsibility or goal?' },
  { key: 'action', label: 'Action', placeholder: 'What steps did you take to address the situation?' },
  { key: 'result', label: 'Result', placeholder: 'What was the outcome or impact? Include metrics where possible.' },
]

interface AccomplishmentPanelProps {
  mode: 'view' | 'edit' | 'create'
  accomplishment?: Accomplishment
  allTags?: string[]
  onSave?: (data: AccomplishmentCreateInput) => Promise<void>
  onCancel?: () => void
  onEdit?: () => void
  onDelete?: () => void
}

/** Edit and create. Tags are edited here only on create (the detail sidebar owns them). */
function AccomplishmentForm({
  mode,
  accomplishment,
  allTags = [],
  onSave,
  onCancel,
}: Omit<AccomplishmentPanelProps, 'onEdit' | 'onDelete'>) {
  const { register, handleSubmit, control, formState: { errors, isSubmitting } } = useForm<AccomplishmentFormInput, unknown, AccomplishmentCreateInput>({
    resolver: zodResolver(accomplishmentCreateSchema),
    mode: 'onBlur',
    defaultValues: {
      title: accomplishment?.title ?? '',
      situation: accomplishment?.situation ?? '',
      task: accomplishment?.task ?? '',
      action: accomplishment?.action ?? '',
      result: accomplishment?.result ?? '',
      accomplishment_date: accomplishment?.accomplishment_date ?? '',
      tags: accomplishment?.tags ?? [],
    },
  })

  return (
    <EditForm
      heading={mode === 'create' ? 'New accomplishment' : `Editing ${accomplishment?.title}`}
      onSubmit={handleSubmit(async (data) => {
        await onSave?.(data)
      })}
      onCancel={() => onCancel?.()}
      saving={isSubmitting}
    >
      <div className={form.fields}>
        <FormField label="Title" htmlFor="acc-title" required error={errors.title}>
          <input
            id="acc-title"
            className={form.inputTitle}
            type="text"
            autoFocus
            placeholder="Brief title of the accomplishment"
            aria-invalid={!!errors.title}
            {...register('title')}
          />
        </FormField>
        <FormField label="Date" htmlFor="acc-date" half error={errors.accomplishment_date}>
          <Controller
            control={control}
            name="accomplishment_date"
            render={({ field }) => (
              <DateInput
                id="acc-date"
                className={form.input}
                placeholder="YYYY-MM-DD"
                days
                value={field.value ?? ''}
                onChange={field.onChange}
                invalid={!!errors.accomplishment_date}
              />
            )}
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
        {STAR_FIELDS.map(({ key, label, placeholder }) => (
          <FormField key={key} label={label} htmlFor={`acc-${key}`}>
            <Controller
              control={control}
              name={key}
              render={({ field }) => (
                <AutoResizeTextarea
                  id={`acc-${key}`}
                  className={form.textarea}
                  value={field.value ?? ''}
                  onChange={field.onChange}
                  placeholder={placeholder}
                />
              )}
            />
          </FormField>
        ))}
      </div>
    </EditForm>
  )
}

export function AccomplishmentPanel(props: AccomplishmentPanelProps) {
  const { mode, accomplishment, onEdit, onDelete } = props
  if (mode !== 'view') return <AccomplishmentForm {...props} />

  return (
    <div>
      <PanelHeader
        entity="accomplishment"
        title={accomplishment?.title}
       
        onEdit={onEdit}
        onDelete={onDelete}
      />

      {accomplishment?.accomplishment_date && (
        <div className={styles.meta}>
          <span className={styles.accomplishmentDate}>Accomplished {accomplishment.accomplishment_date}</span>
        </div>
      )}

      <div className={styles.starSections}>
        {STAR_FIELDS.map(({ key, label, placeholder }) => (
          <SectionCard key={key} label={label}>
            {accomplishment?.[key] ? (
              <MarkdownContent>{accomplishment[key] as string}</MarkdownContent>
            ) : (
              <p className={styles.placeholderText}>{placeholder}</p>
            )}
          </SectionCard>
        ))}
      </div>
    </div>
  )
}
