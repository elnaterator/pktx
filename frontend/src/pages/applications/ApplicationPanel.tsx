import { useForm, Controller } from 'react-hook-form'
import { zodResolver } from '@hookform/resolvers/zod'
import { Pencil, Trash2, Check, X } from 'lucide-react'
import { FieldError } from '../../components/FieldError'
import { TagInput } from '../../components/TagInput'
import { AutoResizeTextarea } from '../../components/AutoResizeTextarea'
import { SectionCard } from '../../components/SectionCard'
import { MarkdownContent } from '../../components/MarkdownContent'
import { applicationCreateSchema, APPLICATION_STATUSES } from '../../schemas/application'
import type { ApplicationCreateInput } from '../../schemas/application'
import type { Application } from '../../types'
import { ExternalLink } from '../../components/ExternalLink'
import styles from './ApplicationPanel.module.css'

export type ApplicationPanelInput = ApplicationCreateInput

const STATUS_COLORS: Record<string, { bg: string; color: string }> = {
  Interested:     { bg: 'rgba(136,136,220,0.12)', color: '#9898d8' },
  Applied:        { bg: 'rgba(86,156,214,0.12)',  color: '#76c0f0' },
  'Phone Screen': { bg: 'rgba(220,180,80,0.12)',  color: '#d4b060' },
  Interview:      { bg: 'rgba(180,120,220,0.12)', color: '#c080e0' },
  Offer:          { bg: 'rgba(82,183,136,0.12)',  color: '#52b788' },
  Rejected:       { bg: 'rgba(255,68,68,0.10)',   color: '#ff6868' },
  Withdrawn:      { bg: 'rgba(120,120,120,0.10)', color: '#888888' },
  Accepted:       { bg: 'rgba(82,183,136,0.22)',  color: '#52b788' },
}

interface ApplicationPanelProps {
  mode: 'view' | 'edit' | 'create'
  application?: Application
  allTags?: string[]
  onSave?: (data: ApplicationPanelInput) => Promise<void>
  onCancel?: () => void
  onEdit?: () => void
  onDelete?: () => void
}

export function ApplicationPanel({
  mode,
  application,
  allTags = [],
  onSave,
  onCancel,
  onEdit,
  onDelete,
}: ApplicationPanelProps) {
  const isEditable = mode !== 'view'

  const {
    register,
    handleSubmit,
    control,
    formState: { errors, isSubmitting },
  } = useForm<ApplicationPanelInput>({
    resolver: zodResolver(applicationCreateSchema),
    mode: 'onBlur',
    defaultValues: {
      company: application?.company ?? '',
      position: application?.position ?? '',
      status: (application?.status as ApplicationPanelInput['status']) ?? 'Interested',
      url: application?.url ?? '',
      tags: application?.tags ?? [],
      description: application?.description ?? '',
      notes: application?.notes ?? '',
    },
  })

  const handleFormSave = handleSubmit(async (data) => {
    await onSave?.(data)
  })

  const statusStyle = application
    ? (STATUS_COLORS[application.status] ?? { bg: 'rgba(120,120,120,0.10)', color: '#888888' })
    : null

  return (
    <div className={mode === 'create' ? styles.panelCreate : undefined}>
      {/* Top bar: labels row above values/inputs row */}
      <div className={styles.topBar}>
        <div className={styles.topBarLabels}>
          <span className={styles.topBarLabel}>Company</span>
          <span className={styles.topBarLabel}>Position</span>
        </div>

        <div className={styles.topBarMain}>
          {isEditable ? (
            <>
              <div className={styles.topBarField}>
                <input
                  className={styles.titleInput}
                  type="text"
                  placeholder="Company"
                  aria-label="Company *"
                  aria-invalid={!!errors.company}
                  autoFocus={mode === 'create'}
                  {...register('company')}
                />
                <FieldError error={errors.company} />
              </div>
              <div className={styles.topBarField}>
                <input
                  className={styles.titleInput}
                  type="text"
                  placeholder="Position"
                  aria-label="Position *"
                  aria-invalid={!!errors.position}
                  {...register('position')}
                />
                <FieldError error={errors.position} />
              </div>
            </>
          ) : (
            <>
              <span className={styles.topBarValue}>{application?.company}</span>
              <span className={styles.topBarValue}>{application?.position}</span>
            </>
          )}
        </div>

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
                <Check size={14} />
              </button>
              <button
                type="button"
                className={styles.cancelIconButton}
                onClick={onCancel}
                aria-label="Cancel"
              >
                <X size={14} />
              </button>
            </>
          ) : (
            <>
              <button type="button" className={styles.editButton} onClick={onEdit} aria-label="Edit application">
                <Pencil size={14} />
              </button>
              <button type="button" className={styles.deleteButton} onClick={onDelete} aria-label="Delete application">
                <Trash2 size={14} />
              </button>
            </>
          )}
        </div>
      </div>

      {/* Meta: tags + date */}
      {isEditable ? (
        <div className={styles.metaEdit}>
          <div className={styles.metaField}>
            <span className={styles.metaLabel}>Tags</span>
            <Controller
              name="tags"
              control={control}
              render={({ field }) => (
                <TagInput
                  value={field.value ?? []}
                  onChange={field.onChange}
                  availableTags={allTags}
                  allowCreate
                  placeholder="Add tag..."
                />
              )}
            />
          </div>
        </div>
      ) : (
        <div className={styles.meta}>
          {application?.tags && application.tags.length > 0 && (
            <div className={styles.tagList}>
              {application.tags.map((tag) => (
                <span key={tag} className={styles.tagBadge}>{tag}</span>
              ))}
            </div>
          )}
          {application?.updated_at && (
            <span className={styles.updatedDate}>
              Updated {new Date(application.updated_at).toLocaleDateString()}
            </span>
          )}
        </div>
      )}

      {/* Section cards */}
      <div className={styles.sections}>
        <SectionCard label="Details">
          <div className={styles.detailsRow}>
            <div className={styles.detailsField}>
              {isEditable ? (
                <>
                  <label className={styles.detailsLabel} htmlFor="ap-status">Status</label>
                  <select id="ap-status" className={styles.select} {...register('status')}>
                    {APPLICATION_STATUSES.map((s) => (
                      <option key={s} value={s}>{s}</option>
                    ))}
                  </select>
                </>
              ) : (
                <>
                  <span className={styles.detailsLabel}>Status</span>
                  <span
                    className={styles.statusBadgeInline}
                    style={statusStyle ? { background: statusStyle.bg, color: statusStyle.color } : undefined}
                  >
                    {application?.status}
                  </span>
                </>
              )}
            </div>
            <div className={styles.detailsField}>
              {isEditable ? (
                <>
                  <label className={styles.detailsLabel} htmlFor="ap-url">URL</label>
                  <input
                    id="ap-url"
                    type="url"
                    className={styles.input}
                    placeholder="https://..."
                    aria-invalid={!!errors.url}
                    {...register('url')}
                  />
                  <FieldError error={errors.url} />
                </>
              ) : (
                <>
                  <span className={styles.detailsLabel}>URL</span>
                  {application?.url ? (
                    <ExternalLink href={application.url} className={styles.urlLink}>
                      {application.url}
                    </ExternalLink>
                  ) : (
                    <span className={styles.emptyText}>—</span>
                  )}
                </>
              )}
            </div>
          </div>
        </SectionCard>

        <SectionCard label="Description">
          {isEditable ? (
            <Controller
              name="description"
              control={control}
              render={({ field }) => (
                <AutoResizeTextarea
                  id="ap-description"
                  className={styles.sectionTextarea}
                  value={field.value ?? ''}
                  onChange={field.onChange}
                  placeholder="Job description, requirements…"
                />
              )}
            />
          ) : application?.description ? (
            <MarkdownContent>{application.description}</MarkdownContent>
          ) : (
            <p className={styles.placeholderText}>Job description, requirements…</p>
          )}
        </SectionCard>

        <SectionCard label="Notes">
          {isEditable ? (
            <Controller
              name="notes"
              control={control}
              render={({ field }) => (
                <AutoResizeTextarea
                  id="ap-notes"
                  className={styles.sectionTextarea}
                  value={field.value ?? ''}
                  onChange={field.onChange}
                  placeholder="Personal notes…"
                />
              )}
            />
          ) : application?.notes ? (
            <MarkdownContent>{application.notes}</MarkdownContent>
          ) : (
            <p className={styles.placeholderText}>Personal notes…</p>
          )}
        </SectionCard>

      </div>
    </div>
  )
}
