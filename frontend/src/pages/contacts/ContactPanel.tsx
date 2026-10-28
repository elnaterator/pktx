import { useForm, Controller } from 'react-hook-form'
import { zodResolver } from '@hookform/resolvers/zod'
import { Mail, Phone, Building2, Briefcase, MapPin, Linkedin, Calendar } from 'lucide-react'
import { ICON_SIZE } from '../../theme'
import { AutoResizeTextarea } from '../../components/AutoResizeTextarea'
import { TagInput } from '../../components/TagInput'
import { DateInput } from '../../components/DateInput'
import { SectionCard } from '../../components/SectionCard'
import { MarkdownContent } from '../../components/MarkdownContent'
import { contactCreateSchema, type ContactCreateInput } from '../../schemas/contact'
import type { Contact } from '../../types'
import { ExternalLink } from '../../components/ExternalLink'
import { PanelHeader } from '../../components/PanelHeader'
import { EditForm, FormField } from '../../components/EditForm'
import form from '../../components/EditForm.module.css'
import { formatDate } from '../../utils/formatDate'
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

type DateField = 'last_contacted_date' | 'followup_date'

/** Edit and create. Tags are edited here only on create (the detail sidebar owns them). */
function ContactForm({ mode, contact, allTags = [], onSave, onCancel }: Omit<ContactPanelProps, 'onEdit' | 'onDelete'>) {
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

  const text = (
    name: 'title' | 'company' | 'relationship' | 'location' | 'email' | 'phone' | 'linkedin_url',
    label: string,
    placeholder: string,
    extra: { type?: string; list?: string } = {},
  ) => (
    <FormField label={label} htmlFor={`cp-${name}`} half={name !== 'linkedin_url'} error={errors[name]}>
      <input
        id={`cp-${name}`}
        className={form.input}
        type={extra.type ?? 'text'}
        list={extra.list}
        placeholder={placeholder}
        aria-invalid={!!errors[name]}
        {...register(name)}
      />
    </FormField>
  )

  const date = (name: DateField, label: string) => (
    <FormField label={label} htmlFor={`cp-${name}`} half error={errors[name]}>
      <Controller
        control={control}
        name={name}
        render={({ field }) => (
          <DateInput
            id={`cp-${name}`}
            className={form.input}
            placeholder="YYYY-MM-DD"
            days
            value={field.value ?? ''}
            onChange={field.onChange}
            invalid={!!errors[name]}
          />
        )}
      />
    </FormField>
  )

  return (
    <EditForm
      heading={mode === 'create' ? 'New contact' : `Editing ${contact?.name}`}
      onSubmit={handleSubmit(async (data) => {
        await onSave?.(data)
      })}
      onCancel={() => onCancel?.()}
      saving={isSubmitting}
    >
      <div className={form.fields}>
        <FormField label="Name" htmlFor="cp-name" required error={errors.name}>
          <input
            id="cp-name"
            className={form.inputTitle}
            type="text"
            autoFocus
            placeholder="Full name"
            aria-invalid={!!errors.name}
            {...register('name')}
          />
        </FormField>
        {text('title', 'Job title', 'Job title')}
        {text('company', 'Company', 'Company')}
        {text('relationship', 'Relationship', 'e.g. Recruiter', { list: 'cp-rel-suggestions' })}
        {text('location', 'Location', 'City, Country')}
        {text('email', 'Email', 'email@example.com', { type: 'email' })}
        {text('phone', 'Phone', 'Phone')}
        {text('linkedin_url', 'LinkedIn URL', 'https://linkedin.com/in/…', { type: 'url' })}
        {date('last_contacted_date', 'Last contacted')}
        {date('followup_date', 'Follow up')}
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
        <FormField label="Notes" htmlFor="cp-notes">
          <Controller
            control={control}
            name="notes"
            render={({ field }) => (
              <AutoResizeTextarea
                id="cp-notes"
                className={form.textarea}
                value={field.value ?? ''}
                onChange={field.onChange}
                placeholder="Notes, comm preferences, interests..."
              />
            )}
          />
        </FormField>
      </div>
      <datalist id="cp-rel-suggestions">
        {RELATIONSHIP_SUGGESTIONS.map((r) => <option key={r} value={r} />)}
      </datalist>
    </EditForm>
  )
}

export function ContactPanel(props: ContactPanelProps) {
  const { mode, contact, onEdit, onDelete } = props
  if (mode !== 'view') return <ContactForm {...props} />

  return (
    <div>
      <PanelHeader
        entity="contact"
        title={contact?.name}
       
        onEdit={onEdit}
        onDelete={onDelete}
      />

      <div className={styles.viewGrid}>
        <div className={styles.viewFields}>
          {contact?.relationship && (
            <div className={styles.relationshipBadge}>{contact.relationship}</div>
          )}
          <div className={styles.fieldList}>
            {contact?.email && (
              <div className={styles.fieldItem}>
                <Mail size={ICON_SIZE.md} className={styles.fieldIcon} />
                <ExternalLink href={`mailto:${contact.email}`} className={styles.fieldLink} allowMailto>
                  {contact.email}
                </ExternalLink>
              </div>
            )}
            {contact?.phone && (
              <div className={styles.fieldItem}>
                <Phone size={ICON_SIZE.md} className={styles.fieldIcon} />
                <span>{contact.phone}</span>
              </div>
            )}
            {contact?.company && (
              <div className={styles.fieldItem}>
                <Building2 size={ICON_SIZE.md} className={styles.fieldIcon} />
                <span>{contact.company}</span>
              </div>
            )}
            {contact?.title && (
              <div className={styles.fieldItem}>
                <Briefcase size={ICON_SIZE.md} className={styles.fieldIcon} />
                <span>{contact.title}</span>
              </div>
            )}
            {contact?.location && (
              <div className={styles.fieldItem}>
                <MapPin size={ICON_SIZE.md} className={styles.fieldIcon} />
                <span>{contact.location}</span>
              </div>
            )}
            {contact?.linkedin_url && (
              <div className={styles.fieldItem}>
                <Linkedin size={ICON_SIZE.md} className={styles.fieldIcon} />
                <ExternalLink href={contact.linkedin_url} className={styles.fieldLink}>
                  {contact.linkedin_url.replace(/^https?:\/\/(www\.)?linkedin\.com\/in\//, '').replace(/\/$/, '')}
                </ExternalLink>
              </div>
            )}
            {contact?.last_contacted_date && (
              <div className={styles.fieldItem}>
                <Calendar size={ICON_SIZE.md} className={styles.fieldIcon} />
                <span>Last contacted: {contact.last_contacted_date}</span>
              </div>
            )}
            {contact?.followup_date && (
              <div className={styles.fieldItem}>
                <Calendar size={ICON_SIZE.md} className={styles.fieldIcon} />
                <span className={styles.followupText}>Follow up: {contact.followup_date}</span>
              </div>
            )}
          </div>
          {contact?.updated_at && (
            <span className={styles.updatedDate}>Updated {formatDate(contact.updated_at)}</span>
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
    </div>
  )
}
