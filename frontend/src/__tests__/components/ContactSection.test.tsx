import { describe, it, expect, vi } from 'vitest';
import { render, screen, waitFor } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import ContactSection from '../../pages/resumes/ContactSection';
import type { ContactInfo } from '../../types';
import * as api from '../../services/api';

const fullContact: ContactInfo = {
  name: 'Jane Smith',
  email: 'jane@example.com',
  phone: '555-9876',
  location: 'New York, NY',
  linkedin: 'https://linkedin.com/in/janesmith',
  website: 'https://janesmith.com',
  github: 'https://github.com/janesmith',
  profiles: [],
};

const partialContact: ContactInfo = {
  name: 'John Doe',
  email: 'john@example.com',
  phone: null,
  location: null,
  linkedin: null,
  website: null,
  github: null,
  profiles: [],
};

describe('ContactSection (view mode)', () => {
  it('renders all contact fields when present', () => {
    render(<ContactSection contact={fullContact} />);

    expect(screen.getByText('Jane Smith')).toBeInTheDocument();
    expect(screen.getByText('jane@example.com')).toBeInTheDocument();
    expect(screen.getByText('555-9876')).toBeInTheDocument();
    expect(screen.getByText('New York, NY')).toBeInTheDocument();
  });

  it('renders profile links as clickable anchors', () => {
    render(<ContactSection contact={fullContact} />);

    const linkedinLink = screen.getByRole('link', { name: /linkedin/i });
    expect(linkedinLink).toHaveAttribute('href', 'https://linkedin.com/in/janesmith');

    const websiteLink = screen.getByRole('link', { name: /website/i });
    expect(websiteLink).toHaveAttribute('href', 'https://janesmith.com');

    const githubLink = screen.getByRole('link', { name: /github/i });
    expect(githubLink).toHaveAttribute('href', 'https://github.com/janesmith');
  });

  it('renders a stored javascript: URL as plain text, not a link', () => {
    render(<ContactSection contact={{ ...fullContact, website: 'javascript:alert(1)' }} />);

    expect(screen.queryByRole('link', { name: /website/i })).not.toBeInTheDocument();
    expect(screen.getByText('Website').tagName).toBe('SPAN');
    expect(screen.getByRole('link', { name: /linkedin/i })).toBeInTheDocument();
  });

  it('handles null fields gracefully', () => {
    render(<ContactSection contact={partialContact} />);

    // Present fields should render
    expect(screen.getByText('John Doe')).toBeInTheDocument();
    expect(screen.getByText('john@example.com')).toBeInTheDocument();

    // Null fields should not render or show links
    expect(screen.queryByText('555-')).not.toBeInTheDocument();
    expect(screen.queryByRole('link', { name: /linkedin/i })).not.toBeInTheDocument();
    expect(screen.queryByRole('link', { name: /website/i })).not.toBeInTheDocument();
    expect(screen.queryByRole('link', { name: /github/i })).not.toBeInTheDocument();
  });

  it('renders with empty/minimal contact info', () => {
    const emptyContact: ContactInfo = {
      name: null,
      email: null,
      phone: null,
      location: null,
      linkedin: null,
      website: null,
      github: null,
    };

    render(<ContactSection contact={emptyContact} />);

    // Section should still render with empty state or minimal content
    expect(screen.getByTestId('contact-section')).toBeInTheDocument();
  });
});

describe('ContactSection (edit mode)', () => {
  it('toggles to edit mode when edit button is clicked', async () => {
    const user = userEvent.setup();
    render(<ContactSection contact={fullContact} onUpdate={() => {}} />);

    const editButton = screen.getByRole('button', { name: /edit/i });
    await user.click(editButton);

    // Form should be visible
    expect(screen.getByLabelText(/name/i)).toBeInTheDocument();
    expect(screen.getByLabelText(/email/i)).toBeInTheDocument();
    expect(screen.getByLabelText(/phone/i)).toBeInTheDocument();
    expect(screen.getByLabelText(/location/i)).toBeInTheDocument();
  });

  it('pre-fills form fields with current values', async () => {
    const user = userEvent.setup();
    render(<ContactSection contact={fullContact} onUpdate={() => {}} />);

    await user.click(screen.getByRole('button', { name: /edit/i }));

    expect(screen.getByLabelText(/name/i)).toHaveValue('Jane Smith');
    expect(screen.getByLabelText(/email/i)).toHaveValue('jane@example.com');
    expect(screen.getByLabelText(/phone/i)).toHaveValue('555-9876');
    expect(screen.getByLabelText(/location/i)).toHaveValue('New York, NY');
    expect(screen.getByLabelText(/linkedin/i)).toHaveValue('https://linkedin.com/in/janesmith');
    expect(screen.getByLabelText(/website/i)).toHaveValue('https://janesmith.com');
    expect(screen.getByLabelText(/github/i)).toHaveValue('https://github.com/janesmith');
  });

  it('calls updateContact API on save and shows success', async () => {
    const user = userEvent.setup();
    const updateSpy = vi.spyOn(api, 'updateResumeContact').mockResolvedValue({ message: 'Success' });
    const onUpdate = vi.fn();

    render(<ContactSection contact={fullContact} onUpdate={onUpdate} />);

    await user.click(screen.getByRole('button', { name: /edit/i }));

    const nameInput = screen.getByLabelText(/name/i);
    await user.clear(nameInput);
    await user.type(nameInput, 'Jane Doe');

    await user.click(screen.getByRole('button', { name: /save/i }));

    await waitFor(() => {
      expect(updateSpy).toHaveBeenCalledWith({
        name: 'Jane Doe',
        email: 'jane@example.com',
        phone: '555-9876',
        location: 'New York, NY',
        linkedin: 'https://linkedin.com/in/janesmith',
        website: 'https://janesmith.com',
        github: 'https://github.com/janesmith',
        profiles: [],
      });
    });

    await waitFor(() => {
      expect(onUpdate).toHaveBeenCalled();
    });

    updateSpy.mockRestore();
  });

  it('reverts to view mode on cancel without saving', async () => {
    const user = userEvent.setup();
    const updateSpy = vi.spyOn(api, 'updateResumeContact');

    render(<ContactSection contact={fullContact} onUpdate={() => {}} />);

    await user.click(screen.getByRole('button', { name: /edit/i }));

    const nameInput = screen.getByLabelText(/name/i);
    await user.clear(nameInput);
    await user.type(nameInput, 'Changed Name');

    await user.click(screen.getByRole('button', { name: /cancel/i }));

    // Should be back in view mode
    expect(screen.getByText('Jane Smith')).toBeInTheDocument();
    expect(screen.queryByLabelText(/name/i)).not.toBeInTheDocument();
    expect(updateSpy).not.toHaveBeenCalled();

    updateSpy.mockRestore();
  });

  it('shows validation error for invalid email', async () => {
    const user = userEvent.setup();
    render(<ContactSection contact={fullContact} onUpdate={() => {}} />);

    await user.click(screen.getByRole('button', { name: /edit/i }));

    const emailInput = screen.getByLabelText(/email/i);
    await user.clear(emailInput);
    await user.type(emailInput, 'invalid-email');

    await user.click(screen.getByRole('button', { name: /save/i }));

    await waitFor(() => {
      expect(screen.getByText(/invalid email/i)).toBeInTheDocument();
    });
  });

  it('shows error message when API call fails', async () => {
    const user = userEvent.setup();
    const updateSpy = vi.spyOn(api, 'updateResumeContact').mockRejectedValue(
      new api.ApiClientError('Server error', 500, 'Internal server error')
    );

    render(<ContactSection contact={fullContact} onUpdate={() => {}} />);

    await user.click(screen.getByRole('button', { name: /edit/i }));
    await user.click(screen.getByRole('button', { name: /save/i }));

    await waitFor(() => {
      expect(screen.getByText(/server error/i)).toBeInTheDocument();
    });

    updateSpy.mockRestore();
  });

  it('shows extra profiles as links and saves added profiles', async () => {
    const user = userEvent.setup();
    const updateSpy = vi.spyOn(api, 'updateResumeContact').mockResolvedValue({ message: 'Success' });
    const withProfile: ContactInfo = {
      ...fullContact,
      profiles: [{ label: 'GitLab', url: 'https://gitlab.com/jane' }],
    };

    render(<ContactSection contact={withProfile} onUpdate={() => {}} />);
    expect(screen.getByRole('link', { name: 'GitLab' })).toHaveAttribute('href', 'https://gitlab.com/jane');

    await user.click(screen.getByRole('button', { name: /edit/i }));
    await user.click(screen.getByRole('button', { name: /add profile/i }));
    await user.type(screen.getByLabelText('Profile 2 label'), 'Dribbble');
    await user.type(screen.getByLabelText('Profile 2 URL'), 'https://dribbble.com/jane');
    await user.click(screen.getByRole('button', { name: /save/i }));

    await waitFor(() => {
      expect(updateSpy).toHaveBeenCalledWith(
        expect.objectContaining({
          profiles: [
            { label: 'GitLab', url: 'https://gitlab.com/jane' },
            { label: 'Dribbble', url: 'https://dribbble.com/jane' },
          ],
        }),
      );
    });
    updateSpy.mockRestore();
  });

  it('rejects a profile with a non-http url', async () => {
    const user = userEvent.setup();
    const updateSpy = vi.spyOn(api, 'updateResumeContact').mockResolvedValue({ message: 'Success' });
    render(<ContactSection contact={fullContact} onUpdate={() => {}} />);

    await user.click(screen.getByRole('button', { name: /edit/i }));
    await user.click(screen.getByRole('button', { name: /add profile/i }));
    await user.type(screen.getByLabelText('Profile 1 label'), 'Bad');
    await user.type(screen.getByLabelText('Profile 1 URL'), 'javascript:alert(1)');
    await user.click(screen.getByRole('button', { name: /save/i }));

    expect(updateSpy).not.toHaveBeenCalled();
    updateSpy.mockRestore();
  });
});
