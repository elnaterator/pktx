import { useForm, Controller } from 'react-hook-form'
import { zodResolver } from '@hookform/resolvers/zod'
import { Pencil, Trash2, Check, X, Mail, Phone, Building2, Briefcase, MapPin, Linkedin, Calendar } from 'lucide-react'
import { AutoResizeTextarea } from '../../components/AutoResizeTextarea'
import { TagInput } from '../../components/TagInput'
import { FieldError } from '../../components/FieldError'
import { SectionCard } from '../../components/SectionCard'
import { MarkdownContent } from '../../components/MarkdownContent'
import { contactCreateSchema, type ContactCreateInput } from '../../schemas/contact'
import type { Contact } from '../../types'
import { ExternalLink } from '../../components/ExternalLink'
import styles from './ContactPanel.module.css'

const RELATIONSHIP_SUGGESTIONS = [
  'Colleague', 'Recruiter', 'Manager', 'Mentor', 'Peer', 'Friend', 'Other',
]

interface ContactPanelProps {
  mode: 'view' | 'edit' | 'create'
  contact?: Contact
  allTags?: string[]
  onSave?: (data: ContactCreateInput) => Promise<void>
  onCancel?: () => void
  onEdit?: () => void
  onDelete?: () => void
}

export function ContactPanel({
  mode,
  contact,
  allTags = [],
  onSave,
  onCancel,
  onEdit,
  onDelete,
}: ContactPanelProps) {
  const isEditable = mode !== 'view'

  const { register, handleSubmit, control, formState: { errors, isSubmitting } } = useForm<ContactCreateInput>({
    resolver: zodResolver(contactCreateSchema),
    mode: 'onBlur',
    defaultValues: {
      name: contact?.name ?? '',
      email: contact?.email ?? '',
      phone: contact?.phone ?? '',
      company: contact?.company ?? '',
      title: contact?.title ?? '',
      relationship: contact?.relationship ?? '',
      linkedin_url: contact?.linkedin_url ?? '',
      location: contact?.location ?? '',
      last_contacted_date: contact?.last_contacted_date ?? '',
      followup_date: contact?.followup_date ?? '',
      notes: contact?.notes ?? '',
      tags: contact?.tags ?? [],
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
            placeholder="Full name"
            aria-label="Name"
            {...register('name')}
          />
        ) : (
          <h2 className={styles.topBarTitle}>{contact?.name}</h2>
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
              <button type="button" className={styles.editButton} onClick={onEdit} aria-label="Edit contact">
                <Pencil size={14} />
              </button>
              <button type="button" className={styles.deleteButton} onClick={onDelete} aria-label="Delete contact">
                <Trash2 size={14} />
              </button>
            </>
          )}
        </div>
      </div>

      {errors.name && <p className={styles.formError}>{errors.name.message}</p>}

      {isEditable ? (
        <div className={styles.editGrid}>
          <div className={styles.editFields}>
            <div className={styles.fieldGroup}>
              <label className={styles.fieldLabel}>Relationship</label>
              <input
                className={styles.fieldInput}
                type="text"
                list="cp-rel-suggestions"
                placeholder="e.g. Recruiter"
                {...register('relationship')}
              />
              <datalist id="cp-rel-suggestions">
                {RELATIONSHIP_SUGGESTIONS.map((r) => <option key={r} value={r} />)}
              </datalist>
            </div>
            <div className={styles.fieldGroup}>
              <label className={styles.fieldLabel}>Email</label>
              <input
                className={styles.fieldInput}
                type="email"
                placeholder="email@example.com"
                aria-invalid={!!errors.email}
                {...register('email')}
              />
              <FieldError error={errors.email} />
            </div>
            <div className={styles.fieldGroup}>
              <label className={styles.fieldLabel}>Phone</label>
              <input
                className={styles.fieldInput}
                type="text"
                placeholder="+1 555 000 0000"
                {...register('phone')}
              />
            </div>
            <div className={styles.fieldGroup}>
              <label className={styles.fieldLabel}>Company</label>
              <input
                className={styles.fieldInput}
                type="text"
                placeholder="Company"
                {...register('company')}
              />
            </div>
            <div className={styles.fieldGroup}>
              <label className={styles.fieldLabel}>Title</label>
              <input
                className={styles.fieldInput}
                type="text"
                placeholder="Job title"
                {...register('title')}
              />
            </div>
            <div className={styles.fieldGroup}>
              <label className={styles.fieldLabel}>Location</label>
              <input
                className={styles.fieldInput}
                type="text"
                placeholder="City, Country"
                {...register('location')}
              />
            </div>
            <div className={styles.fieldGroup}>
              <label className={styles.fieldLabel}>LinkedIn URL</label>
              <input
                className={styles.fieldInput}
                type="url"
                placeholder="https://linkedin.com/in/..."
                aria-invalid={!!errors.linkedin_url}
                {...register('linkedin_url')}
              />
              <FieldError error={errors.linkedin_url} />
            </div>
            <div className={styles.fieldGroup}>
              <label className={styles.fieldLabel}>Last Contacted</label>
              <input
                className={styles.fieldInput}
                type="date"
                {...register('last_contacted_date')}
              />
            </div>
            <div className={styles.fieldGroup}>
              <label className={styles.fieldLabel}>Follow Up Date</label>
              <input
                className={styles.fieldInput}
                type="date"
                {...register('followup_date')}
              />
            </div>
            <div className={styles.fieldGroup}>
              <label className={styles.fieldLabel}>Tags</label>
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
          <div className={styles.editNotes}>
            <label className={styles.fieldLabel}>Notes</label>
            <Controller
              control={control}
              name="notes"
              render={({ field }) => (
                <AutoResizeTextarea
                  className={styles.notesTextarea}
                  value={field.value ?? ''}
                  onChange={field.onChange}
                  placeholder="Notes, comm preferences, interests..."
                />
              )}
            />
          </div>
        </div>
      ) : (
        <div className={styles.viewGrid}>
          <div className={styles.viewFields}>
            {contact?.relationship && (
              <div className={styles.relationshipBadge}>{contact.relationship}</div>
            )}
            <div className={styles.fieldList}>
              {contact?.email && (
                <div className={styles.fieldItem}>
                  <Mail size={14} className={styles.fieldIcon} />
                  <ExternalLink href={`mailto:${contact.email}`} className={styles.fieldLink} allowMailto>
                    {contact.email}
                  </ExternalLink>
                </div>
              )}
              {contact?.phone && (
                <div className={styles.fieldItem}>
                  <Phone size={14} className={styles.fieldIcon} />
                  <span>{contact.phone}</span>
                </div>
              )}
              {contact?.company && (
                <div className={styles.fieldItem}>
                  <Building2 size={14} className={styles.fieldIcon} />
                  <span>{contact.company}</span>
                </div>
              )}
              {contact?.title && (
                <div className={styles.fieldItem}>
                  <Briefcase size={14} className={styles.fieldIcon} />
                  <span>{contact.title}</span>
                </div>
              )}
              {contact?.location && (
                <div className={styles.fieldItem}>
                  <MapPin size={14} className={styles.fieldIcon} />
                  <span>{contact.location}</span>
                </div>
              )}
              {contact?.linkedin_url && (
                <div className={styles.fieldItem}>
                  <Linkedin size={14} className={styles.fieldIcon} />
                  <ExternalLink href={contact.linkedin_url} className={styles.fieldLink}>
                    {contact.linkedin_url.replace(/^https?:\/\/(www\.)?linkedin\.com\/in\//, '').replace(/\/$/, '')}
                  </ExternalLink>
                </div>
              )}
              {contact?.last_contacted_date && (
                <div className={styles.fieldItem}>
                  <Calendar size={14} className={styles.fieldIcon} />
                  <span>Last contacted: {contact.last_contacted_date}</span>
                </div>
              )}
              {contact?.followup_date && (
                <div className={styles.fieldItem}>
                  <Calendar size={14} className={styles.fieldIcon} />
                  <span className={styles.followupText}>Follow up: {contact.followup_date}</span>
                </div>
              )}
            </div>
            {contact?.tags && contact.tags.length > 0 && (
              <div className={styles.tagList}>
                {contact.tags.map((tag) => (
                  <span key={tag} className={styles.tagBadge}>{tag}</span>
                ))}
              </div>
            )}
            {contact?.updated_at && (
              <span className={styles.updatedDate}>Updated {new Date(contact.updated_at).toLocaleDateString()}</span>
            )}
          </div>
          <SectionCard>
            {contact?.notes ? (
              <MarkdownContent>{contact.notes}</MarkdownContent>
            ) : (
              <p className={styles.placeholderText}>No notes yet.</p>
            )}
          </SectionCard>
        </div>
      )}
    </div>
  )
}
