import { useEffect, useMemo } from 'react';
import { useFieldArray, useForm } from 'react-hook-form';
import { zodResolver } from '@hookform/resolvers/zod';
import { Trash2 } from 'lucide-react';
import type { ContactInfo, ContactKind } from '../../types';
import { EditableSection } from '../../components/EditableSection';
import { updateResumeContact, updateVersionContact } from '../../services/api';
import { useResumeContactKeys } from '../../hooks/queries';
import { FieldError } from '../../components/FieldError';
import { buildContactSchema, type ContactFormInput } from '../../schemas/resumeEntry';
import { ExternalLink } from '../../components/ExternalLink';
import { safeHref } from '../../utils/safeUrl';
import styles from './ContactSection.module.css';

interface ContactSectionProps {
  contact: ContactInfo;
  onUpdate?: () => void;
  versionId?: number;
}

const CUSTOM = '__custom__';

function ContactReadView({
  contact,
  kindOf,
}: {
  contact: ContactInfo;
  kindOf: (key: string) => ContactKind;
}) {
  const items: React.ReactNode[] = [];
  if (contact.phone) items.push(<span className={styles.contactItem}>{contact.phone}</span>);
  if (contact.location) items.push(<span className={styles.contactItem}>{contact.location}</span>);
  for (const f of contact.fields ?? []) {
    const kind = kindOf(f.key);
    if (kind === 'email') {
      items.push(
        <ExternalLink
          href={`mailto:${f.value}`}
          allowMailto
          className={`${styles.contactItem} ${styles.contactLink}`}
        >
          {f.value}
        </ExternalLink>,
      );
    } else if (kind === 'url' || safeHref(f.value)) {
      // Links read as their key (LinkedIn, GitHub, ...). An unsafe stored URL
      // renders as plain, non-clickable text.
      items.push(
        <ExternalLink href={f.value} className={`${styles.contactItem} ${styles.contactLink}`}>
          {f.key}
        </ExternalLink>,
      );
    } else {
      items.push(
        <span className={styles.contactItem}>
          {f.key}: {f.value}
        </span>,
      );
    }
  }

  return (
    <div className={styles.readView}>
      {contact.name && <h1 className={styles.nameHeading}>{contact.name}</h1>}
      {items.length > 0 && (
        <div className={styles.contactRow}>
          {items.map((item, i) => (
            <span key={i} className={styles.contactCell}>
              {item}
            </span>
          ))}
        </div>
      )}
    </div>
  );
}

export default function ContactSection({ contact, onUpdate, versionId }: ContactSectionProps) {
  const presetsQuery = useResumeContactKeys();
  const presets = useMemo(() => presetsQuery.data ?? [], [presetsQuery.data]);
  const kindOf = useMemo(() => {
    const byKey = new Map(presets.map((p) => [p.key.toLowerCase().replace(/\s+/g, ''), p.kind]));
    return (key: string): ContactKind => byKey.get(key.toLowerCase().replace(/\s+/g, '')) ?? 'text';
  }, [presets]);
  const schema = useMemo(() => buildContactSchema(kindOf), [kindOf]);
  const isPreset = (key: string) => presets.some((p) => p.key.toLowerCase() === key.toLowerCase());

  const toDefaults = (c: ContactInfo): ContactFormInput => ({
    name: c.name ?? '',
    phone: c.phone ?? '',
    location: c.location ?? '',
    fields: (c.fields ?? []).map((f) => ({ ...f, custom: !isPreset(f.key) })),
  });

  const {
    register,
    control,
    trigger,
    getValues,
    reset,
    watch,
    formState: { errors },
  } = useForm<ContactFormInput>({
    resolver: zodResolver(schema),
    mode: 'onChange',
    defaultValues: toDefaults(contact),
  });
  const fields = useFieldArray({ control, name: 'fields' });

  useEffect(() => {
    reset(toDefaults(contact));
    // eslint-disable-next-line react-hooks/exhaustive-deps -- presets only affect which rows are custom
  }, [contact, presets, reset]);

  const handleSave = async () => {
    const isValid = await trigger();
    if (!isValid) throw new Error('Please fix validation errors');
    const parsed = schema.parse(getValues());
    const contactData: ContactInfo = {
      name: parsed.name ?? null,
      phone: parsed.phone ?? null,
      location: parsed.location ?? null,
      fields: parsed.fields.map(({ key, value }) => ({ key, value })),
    };
    if (versionId !== undefined) {
      await updateVersionContact(versionId, contactData);
    } else {
      await updateResumeContact(contactData);
    }
    if (onUpdate) onUpdate();
  };

  if (!onUpdate) {
    return (
      <section data-testid="contact-section">
        <ContactReadView contact={contact} kindOf={kindOf} />
      </section>
    );
  }

  const used = new Set(watch('fields')?.map((f) => (f.key ?? '').toLowerCase()));
  const available = presets.filter((p) => !used.has(p.key.toLowerCase()));

  return (
    <EditableSection title="Contact Information" onSave={handleSave}>
      {({ isEditing }) => (
        <div data-testid="contact-section">
          {isEditing ? (
            <form className={styles.form} onSubmit={(e) => e.preventDefault()}>
              <div className={styles.formField}>
                <label htmlFor="name" className={styles.formLabel}>Name</label>
                <input
                  type="text"
                  id="name"
                  className={`${styles.input} ${styles.inputName}`}
                  {...register('name')}
                />
              </div>

              <div className={styles.formRow}>
                <div className={styles.formField}>
                  <label htmlFor="phone" className={styles.formLabel}>Phone</label>
                  <input type="tel" id="phone" className={styles.input} {...register('phone')} />
                </div>
                <div className={styles.formField}>
                  <label htmlFor="location" className={styles.formLabel}>Location</label>
                  <input
                    type="text"
                    id="location"
                    className={styles.input}
                    {...register('location')}
                  />
                </div>
              </div>

              {fields.fields.map((row, index) => {
                const rowErrors = errors.fields?.[index];
                const key = watch(`fields.${index}.key`) ?? '';
                const custom = watch(`fields.${index}.custom`);
                return (
                  <div key={row.id} className={styles.detailRow}>
                    <div className={styles.formField}>
                      {custom ? (
                        <input
                          type="text"
                          className={styles.input}
                          placeholder="Custom key (e.g. Pronouns)"
                          aria-label={`Detail ${index + 1} key`}
                          {...register(`fields.${index}.key` as const)}
                        />
                      ) : (
                        <label htmlFor={`detail-${index}`} className={styles.formLabel}>
                          {key}
                        </label>
                      )}
                      <FieldError error={rowErrors?.key} />
                    </div>
                    <div className={`${styles.formField} ${styles.detailValue}`}>
                      <input
                        type={kindOf(key) === 'email' ? 'email' : 'text'}
                        id={`detail-${index}`}
                        className={`${styles.input} ${rowErrors?.value ? styles.inputError : ''}`}
                        placeholder={kindOf(key) === 'url' ? 'https://...' : undefined}
                        aria-label={custom ? `Detail ${index + 1} value` : undefined}
                        {...register(`fields.${index}.value` as const)}
                      />
                      <FieldError error={rowErrors?.value} />
                    </div>
                    <button
                      type="button"
                      className={styles.removeDetail}
                      onClick={() => fields.remove(index)}
                      aria-label={`Remove ${key || `detail ${index + 1}`}`}
                    >
                      <Trash2 size={14} />
                    </button>
                  </div>
                );
              })}

              <div className={styles.formField}>
                <label htmlFor="add-detail" className={styles.formLabel}>Add detail</label>
                <select
                  id="add-detail"
                  className={styles.input}
                  value=""
                  onChange={(e) => {
                    const choice = e.target.value;
                    if (choice === CUSTOM) fields.append({ key: '', value: '', custom: true });
                    else if (choice) fields.append({ key: choice, value: '', custom: false });
                  }}
                >
                  <option value="">Choose a detail…</option>
                  {available.map((p) => (
                    <option key={p.key} value={p.key}>{p.key}</option>
                  ))}
                  <option value={CUSTOM}>Custom…</option>
                </select>
              </div>
            </form>
          ) : (
            <ContactReadView contact={contact} kindOf={kindOf} />
          )}
        </div>
      )}
    </EditableSection>
  );
}
