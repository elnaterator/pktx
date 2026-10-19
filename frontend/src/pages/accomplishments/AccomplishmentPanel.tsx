import { useForm, Controller } from 'react-hook-form'
import { zodResolver } from '@hookform/resolvers/zod'
import { AutoResizeTextarea } from '../../components/AutoResizeTextarea'
import { TagInput } from '../../components/TagInput'
import { SectionCard } from '../../components/SectionCard'
import { MarkdownContent } from '../../components/MarkdownContent'
import { accomplishmentCreateSchema, type AccomplishmentCreateInput } from '../../schemas/accomplishment'
import type { Accomplishment } from '../../types'
import { PanelHeader } from '../../components/PanelHeader'
import panelHeaderStyles from '../../components/PanelHeader.module.css'
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

export function AccomplishmentPanel({
  mode,
  accomplishment,
  allTags = [],
  onSave,
  onCancel,
  onEdit,
  onDelete,
}: AccomplishmentPanelProps) {
  const isEditable = mode !== 'view'

  const { register, handleSubmit, control, formState: { errors, isSubmitting } } = useForm<AccomplishmentCreateInput>({
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

  const handleFormSave = handleSubmit(async (data) => {
    await onSave?.(data)
  })

  return (
    <div className={mode === 'create' ? styles.panelCreate : undefined}>
      <PanelHeader
        editing={isEditable}
        entity="accomplishment"
        title={accomplishment?.title}
        titleEditor={
          <input
            className={panelHeaderStyles.titleInput}
            type="text"
            autoFocus
            placeholder="Brief title of the accomplishment"
            aria-label="Title"
            {...register('title')}
          />
        }
        onEdit={onEdit}
        onDelete={onDelete}
        onSave={handleFormSave}
        onCancel={onCancel}
        saving={isSubmitting}
      />

      {errors.title && <p className={styles.formError}>{errors.title.message}</p>}

      {isEditable ? (
        <div className={styles.metaEdit}>
          {mode === 'create' && <div className={styles.metaField}>
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
          </div>}
          <div className={`${styles.metaField} ${styles.metaFieldDate}`}>
            <label className={styles.metaLabel}>Date</label>
            <input
              className={styles.metaInput}
              type="date"
              {...register('accomplishment_date')}
            />
          </div>
        </div>
      ) : (
        accomplishment?.accomplishment_date && (
          <div className={styles.meta}>
            {accomplishment.accomplishment_date && (
              <span className={styles.accomplishmentDate}>Accomplished {accomplishment.accomplishment_date}</span>
            )}
          </div>
        )
      )}

      <div className={styles.starSections}>
        {STAR_FIELDS.map(({ key, label, placeholder }) => (
          <SectionCard key={key} label={label}>
            {isEditable ? (
              <Controller
                control={control}
                name={key}
                render={({ field }) => (
                  <AutoResizeTextarea
                    className={styles.sectionTextarea}
                    aria-label={label}
                    value={field.value ?? ''}
                    onChange={field.onChange}
                    placeholder={placeholder}
                  />
                )}
              />
            ) : (
              accomplishment?.[key] ? (
                <MarkdownContent>{accomplishment[key] as string}</MarkdownContent>
              ) : (
                <p className={styles.placeholderText}>{placeholder}</p>
              )
            )}
          </SectionCard>
        ))}
      </div>
    </div>
  )
}
