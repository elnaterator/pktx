import { ReactNode, useState } from 'react';
import { useToast } from './toast';
import { EditActions } from './EditActions';
import { EditForm } from './EditForm';
import styles from './EditableSection.module.css';

type EditState = 'viewing' | 'editing' | 'saving';

interface EditableSectionProps {
  children: (props: { isEditing: boolean }) => ReactNode;
  onSave: () => Promise<void>;
  title: string;
  placeholderContent?: ReactNode;
  /** Called when editing is abandoned, e.g. to reset the form. */
  onCancel?: () => void;
}

export function EditableSection({ children, onSave, title, placeholderContent, onCancel }: EditableSectionProps) {
  const [editState, setEditState] = useState<EditState>('viewing');
  const { success: toastSuccess, error: toastError } = useToast();

  const handleEdit = () => {
    setEditState('editing');
  };

  const handleCancel = () => {
    onCancel?.();
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

  if (editState !== 'viewing') {
    return (
      <div className={styles.container}>
        <EditForm
          heading={`Editing ${title.toLowerCase()}`}
          onSubmit={handleSave}
          onCancel={handleCancel}
          saving={editState === 'saving'}
          saveLabel={`Save ${title}`}
          cancelLabel={`Cancel editing ${title}`}
        >
          {children({ isEditing: true })}
        </EditForm>
      </div>
    );
  }

  return (
    <div className={styles.container}>
      <div className={styles.actions}>
        <EditActions editing={false} onEdit={handleEdit} editLabel={`Edit ${title}`} />
      </div>

      <div className={styles.content}>
        {children({ isEditing: false })}
      </div>

      {placeholderContent}
    </div>
  );
}
