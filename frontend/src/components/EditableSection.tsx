import { ReactNode, useState } from 'react';
import { useToast } from './toast';
import { EditActions } from './EditActions';
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
      <div className={styles.actions}>
        {editState === 'saving' ? (
          <span className={styles.saving}>Saving...</span>
        ) : (
          <EditActions
            editing={editState === 'editing'}
            onEdit={handleEdit}
            onSave={handleSave}
            onCancel={handleCancel}
            editLabel={`Edit ${title}`}
            saveLabel={`Save ${title}`}
            cancelLabel={`Cancel editing ${title}`}
          />
        )}
      </div>

      <div className={styles.content}>
        {children({ isEditing: editState === 'editing' })}
      </div>

      {editState === 'viewing' && placeholderContent}
    </div>
  );
}
