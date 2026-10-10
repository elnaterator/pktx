import { useEffect } from 'react';
import { useFieldArray, useForm } from 'react-hook-form';
import { zodResolver } from '@hookform/resolvers/zod';
import type { ContactInfo } from '../../types';
import { EditableSection } from '../../components/EditableSection';
import { updateResumeContact, updateVersionContact } from '../../services/api';
import { FieldError } from '../../components/FieldError';
import { contactInfoSchema, type ContactInfoInput } from '../../schemas/resumeEntry';
import { ExternalLink } from '../../components/ExternalLink';
import styles from './ContactSection.module.css';

interface ContactSectionProps {
  contact: ContactInfo;
  onUpdate?: () => void;
  versionId?: number;
}

function ContactReadView({ contact }: { contact: ContactInfo }) {
  const details: string[] = [];
  if (contact.email) details.push(contact.email);
  if (contact.phone) details.push(contact.phone);
  if (contact.location) details.push(contact.location);

  const links: { label: string; href: string }[] = [];
  if (contact.linkedin) links.push({ label: 'LinkedIn', href: contact.linkedin });
  if (contact.website) links.push({ label: 'Website', href: contact.website });
  if (contact.github) links.push({ label: 'GitHub', href: contact.github });
  for (const p of contact.profiles ?? []) links.push({ label: p.label, href: p.url });

  return (
    <div className={styles.readView}>
      {contact.name && <h1 className={styles.nameHeading}>{contact.name}</h1>}
      {(details.length > 0 || links.length > 0) && (
        <div className={styles.contactRow}>
          {details.map((d, i) => (
            <span key={i} className={styles.contactItem}>{d}</span>
          ))}
          {links.map((l, i) => (
            <ExternalLink
              key={i}
              href={l.href}
              className={`${styles.contactItem} ${styles.contactLink}`}
            >
              {l.label}
            </ExternalLink>
          ))}
        </div>
      )}
    </div>
  );
}

const toDefaults = (c: ContactInfo): ContactInfoInput => ({
  name: c.name ?? '',
  email: c.email ?? '',
  phone: c.phone ?? '',
  location: c.location ?? '',
  linkedin: c.linkedin ?? '',
  website: c.website ?? '',
  github: c.github ?? '',
  profiles: c.profiles ?? [],
})

export default function ContactSection({ contact, onUpdate, versionId }: ContactSectionProps) {
  const { register, control, trigger, getValues, reset, formState: { errors } } = useForm<ContactInfoInput>({
    resolver: zodResolver(contactInfoSchema),
    mode: 'onChange',
    defaultValues: toDefaults(contact),
  });

  const profiles = useFieldArray({ control, name: 'profiles' });

  useEffect(() => {
    reset(toDefaults(contact));
  }, [contact, reset]);

  const handleSave = async () => {
    const isValid = await trigger();
    if (!isValid) throw new Error('Please fix validation errors');
    const parsed = contactInfoSchema.parse(getValues());
    const contactData: ContactInfo = {
      name: parsed.name ?? null,
      email: parsed.email ?? null,
      phone: parsed.phone ?? null,
      location: parsed.location ?? null,
      linkedin: parsed.linkedin ?? null,
      website: parsed.website ?? null,
      github: parsed.github ?? null,
      profiles: parsed.profiles,
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
        <ContactReadView contact={contact} />
      </section>
    );
  }

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
                  <label htmlFor="email" className={styles.formLabel}>Email</label>
                  <input
                    type="email"
                    id="email"
                    className={`${styles.input} ${errors.email ? styles.inputError : ''}`}
                    {...register('email')}
                  />
                  <FieldError error={errors.email} />
                </div>
                <div className={styles.formField}>
                  <label htmlFor="phone" className={styles.formLabel}>Phone</label>
                  <input
                    type="tel"
                    id="phone"
                    className={styles.input}
                    {...register('phone')}
                  />
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

              <div className={styles.formRow}>
                <div className={styles.formField}>
                  <label htmlFor="linkedin" className={styles.formLabel}>LinkedIn</label>
                  <input
                    type="url"
                    id="linkedin"
                    className={styles.input}
                    placeholder="https://linkedin.com/in/username"
                    {...register('linkedin')}
                  />
                  <FieldError error={errors.linkedin} />
                </div>
                <div className={styles.formField}>
                  <label htmlFor="website" className={styles.formLabel}>Website</label>
                  <input
                    type="url"
                    id="website"
                    className={styles.input}
                    placeholder="https://example.com"
                    {...register('website')}
                  />
                  <FieldError error={errors.website} />
                </div>
                <div className={styles.formField}>
                  <label htmlFor="github" className={styles.formLabel}>GitHub</label>
                  <input
                    type="url"
                    id="github"
                    className={styles.input}
                    placeholder="https://github.com/username"
                    {...register('github')}
                  />
                  <FieldError error={errors.github} />
                </div>
              </div>

              <div className={styles.formField}>
                <span className={styles.formLabel}>Other profiles</span>
                {profiles.fields.map((field, index) => (
                  <div key={field.id} className={styles.formRow}>
                    <div className={styles.formField}>
                      <input
                        type="text"
                        className={styles.input}
                        placeholder="Label (e.g. GitLab)"
                        aria-label={`Profile ${index + 1} label`}
                        {...register(`profiles.${index}.label` as const)}
                      />
                      <FieldError error={errors.profiles?.[index]?.label} />
                    </div>
                    <div className={styles.formField}>
                      <input
                        type="url"
                        className={styles.input}
                        placeholder="https://..."
                        aria-label={`Profile ${index + 1} URL`}
                        {...register(`profiles.${index}.url` as const)}
                      />
                      <FieldError error={errors.profiles?.[index]?.url} />
                    </div>
                    <button
                      type="button"
                      onClick={() => profiles.remove(index)}
                      aria-label={`Remove profile ${index + 1}`}
                    >
                      Remove
                    </button>
                  </div>
                ))}
                <button
                  type="button"
                  onClick={() => profiles.append({ label: '', url: '' })}
                >
                  Add profile
                </button>
              </div>
            </form>
          ) : (
            <ContactReadView contact={contact} />
          )}
        </div>
      )}
    </EditableSection>
  );
}
