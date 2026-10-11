import { useForm, Controller } from 'react-hook-form';
import { zodResolver } from '@hookform/resolvers/zod';
import { EditableSection } from '../../components/EditableSection';
import { updateSummary, updateVersionSummary } from '../../services/api';
import { MarkdownContent } from '../../components/MarkdownContent';
import { AutoResizeTextarea } from '../../components/AutoResizeTextarea';
import { FieldError } from '../../components/FieldError';
import { summarySchema, type SummaryInput } from '../../schemas/resumeEntry';
import styles from './SummarySection.module.css';

interface SummarySectionProps {
  summary: string;
  onUpdate?: () => void;
  versionId?: number;
}

export default function SummarySection({ summary, onUpdate, versionId }: SummarySectionProps) {
  const { control, trigger, getValues, formState: { errors } } = useForm<SummaryInput>({
    resolver: zodResolver(summarySchema),
    mode: 'onChange',
    defaultValues: { summary },
  });

  const handleSave = async () => {
    const isValid = await trigger();
    if (!isValid) throw new Error('Summary cannot be empty');
    const { summary: value } = summarySchema.parse(getValues());
    if (versionId !== undefined) {
      await updateVersionSummary(versionId, value);
    } else {
      await updateSummary(value);
    }
    if (onUpdate) onUpdate();
  };

  if (!onUpdate) {
    return (
      <section className={styles.container} data-testid="summary-section">
        <h2 className={styles.sectionLabel}>Summary</h2>
        {summary ? (
          <MarkdownContent>{summary}</MarkdownContent>
        ) : (
          <p className={styles.empty}>No summary available.</p>
        )}
      </section>
    );
  }

  const placeholder = !summary ? (
    <p className={styles.placeholder}>Click the pencil icon to add a summary</p>
  ) : undefined;

  return (
    <EditableSection title="Summary" onSave={handleSave} placeholderContent={placeholder}>
      {({ isEditing }) => (
        <div data-testid="summary-section">
          <h2 className={styles.sectionLabel}>Summary</h2>
          {isEditing ? (
            <div className={styles.formField}>
              <Controller
                control={control}
                name="summary"
                render={({ field }) => (
                  <AutoResizeTextarea
                    value={field.value}
                    onChange={field.onChange}
                    className={`${styles.textarea} ${errors.summary ? styles.textareaError : ''}`}
                    placeholder="Enter your professional summary..."
                  />
                )}
              />
              <FieldError error={errors.summary} />
            </div>
          ) : (
            <>
              {summary && (
                <MarkdownContent>{summary}</MarkdownContent>
              )}
            </>
          )}
        </div>
      )}
    </EditableSection>
  );
}
