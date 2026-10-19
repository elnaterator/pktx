import { ReactNode, useState } from 'react';
import { Pencil, Check, X } from 'lucide-react';
import { ICON_SIZE } from '../theme';
import { useToast } from './toast';
import styles from './EditableSection.module.css';

type EditState = 'viewing' | 'editing' | 'saving';

interface EditableSectionProps {
  children: (props: { isEditing: boolean }) => ReactNode;
  onSave: () => Promise<void>;
  title: string;
  placeholderContent?: ReactNode;
}

export function EditableSection({ children, onSave, title, placeholderContent }: EditableSectionProps) {
  const [editState, setEditState] = useState<EditState>('viewing');
  const { success: toastSuccess, error: toastError } = useToast();

  const handleEdit = () => {
    setEditState('editing');
  };

  const handleCancel = () => {
    setEditState('viewing');
  };

  const handleSave = async () => {
    setEditState('saving');

    try {
      await onSave();
      toastSuccess('Changes saved successfully');
      setEditState('viewing');
    } catch (err) {
      toastError(err instanceof Error ? err.message : 'Failed to save changes');
      setEditState('editing');
    }
  };

  return (
    <div className={styles.container}>
      {editState === 'viewing' && (
        <button
          onClick={handleEdit}
          className={styles.editIcon}
          aria-label={`Edit ${title}`}
        >
          <Pencil size={ICON_SIZE.md} />
        </button>
      )}

      {(editState === 'editing' || editState === 'saving') && (
        <div className={styles.editActions}>
          {editState === 'editing' && (
            <>
              <button
                onClick={handleSave}
                className={`${styles.actionButton} ${styles.saveIcon}`}
                aria-label={`Save ${title}`}
              >
                <Check size={ICON_SIZE.md} />
              </button>
              <button
                onClick={handleCancel}
                className={`${styles.actionButton} ${styles.cancelIcon}`}
                aria-label={`Cancel editing ${title}`}
              >
                <X size={ICON_SIZE.md} />
              </button>
            </>
          )}
          {editState === 'saving' && (
            <span className={styles.saving}>Saving...</span>
          )}
        </div>
      )}

      <div className={styles.content}>
        {children({ isEditing: editState === 'editing' })}
      </div>

      {editState === 'viewing' && placeholderContent}
    </div>
  );
}
