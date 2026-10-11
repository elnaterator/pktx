import { describe, it, expect, vi, beforeEach, afterEach } from 'vitest';
import { screen, waitFor, within } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import ContactSection from '../../pages/resumes/ContactSection';
import type { ContactInfo, ContactKeyPreset } from '../../types';
import * as api from '../../services/api';
import { renderWithQuery } from '../test-utils';

const presets: ContactKeyPreset[] = [
  { key: 'Email', kind: 'email' },
  { key: 'Website', kind: 'url' },
  { key: 'LinkedIn', kind: 'url' },
  { key: 'GitHub', kind: 'url' },
  { key: 'GitLab', kind: 'url' },
];

const fullContact: ContactInfo = {
  name: 'Jane Smith',
  phone: '555-9876',
  location: 'New York, NY',
  fields: [
    { key: 'Email', value: 'jane@example.com' },
    { key: 'LinkedIn', value: 'https://linkedin.com/in/janesmith' },
    { key: 'Website', value: 'https://janesmith.com' },
    { key: 'Pronouns', value: 'she/her' },
  ],
};

const emptyContact: ContactInfo = { name: null, phone: null, location: null, fields: [] };

beforeEach(() => {
  vi.spyOn(api, 'listResumeContactKeys').mockResolvedValue(presets);
});

afterEach(() => {
  vi.restoreAllMocks();
});

const renderEditable = (contact: ContactInfo, onUpdate = vi.fn()) =>
  renderWithQuery(<ContactSection contact={contact} onUpdate={onUpdate} />);

const startEditing = async (user: ReturnType<typeof userEvent.setup>) => {
  await user.click(screen.getByRole('button', { name: /edit/i }));
  // Wait for the preset keys so preset rows render as labels, not custom inputs.
  await screen.findByRole('option', { name: 'GitHub' });
};

describe('ContactSection (view mode)', () => {
  it('renders name, phone, location and details', async () => {
    renderWithQuery(<ContactSection contact={fullContact} />);

    expect(screen.getByText('Jane Smith')).toBeInTheDocument();
    expect(screen.getByText('555-9876')).toBeInTheDocument();
    expect(screen.getByText('New York, NY')).toBeInTheDocument();
    expect(screen.getByText('Pronouns: she/her')).toBeInTheDocument();
  });

  it('renders emails as mailto links and URLs as links labelled by key', async () => {
    renderWithQuery(<ContactSection contact={fullContact} />);

    expect(await screen.findByRole('link', { name: 'jane@example.com' })).toHaveAttribute(
      'href',
      'mailto:jane@example.com',
    );
    expect(screen.getByRole('link', { name: 'LinkedIn' })).toHaveAttribute(
      'href',
      'https://linkedin.com/in/janesmith',
    );
    expect(screen.getByRole('link', { name: 'Website' })).toHaveAttribute(
      'href',
      'https://janesmith.com',
    );
  });

  it('links a custom key when its value is an http(s) URL', () => {
    renderWithQuery(
      <ContactSection
        contact={{ ...emptyContact, fields: [{ key: 'Blog', value: 'https://blog.example.com' }] }}
      />,
    );
    expect(screen.getByRole('link', { name: 'Blog' })).toHaveAttribute('href', 'https://blog.example.com');
  });

  it('renders a stored javascript: URL as plain text, not a link', async () => {
    renderWithQuery(
      <ContactSection
        contact={{ ...fullContact, fields: [{ key: 'Website', value: 'javascript:alert(1)' }] }}
      />,
    );

    await waitFor(() => expect(screen.getByText('Website').tagName).toBe('SPAN'));
    expect(screen.queryByRole('link', { name: /website/i })).not.toBeInTheDocument();
  });

  it('renders with empty contact info', () => {
    renderWithQuery(<ContactSection contact={emptyContact} />);
    expect(screen.getByTestId('contact-section')).toBeInTheDocument();
  });
});

describe('ContactSection (edit mode)', () => {
  it('always shows name, phone and location', async () => {
    const user = userEvent.setup();
    renderEditable(emptyContact);
    await startEditing(user);

    expect(screen.getByLabelText('Name')).toHaveValue('');
    expect(screen.getByLabelText('Phone')).toHaveValue('');
    expect(screen.getByLabelText('Location')).toHaveValue('');
  });

  it('pre-fills values and shows preset keys as labels, custom keys as inputs', async () => {
    const user = userEvent.setup();
    renderEditable(fullContact);
    await startEditing(user);

    expect(screen.getByLabelText('Name')).toHaveValue('Jane Smith');
    expect(screen.getByLabelText('Phone')).toHaveValue('555-9876');
    expect(screen.getByLabelText('Email')).toHaveValue('jane@example.com');
    expect(screen.getByLabelText('LinkedIn')).toHaveValue('https://linkedin.com/in/janesmith');
    expect(screen.getByLabelText('Detail 4 key')).toHaveValue('Pronouns');
    expect(screen.getByLabelText('Detail 4 value')).toHaveValue('she/her');
  });

  it('lists common keys first, minus the ones already used, then Custom', async () => {
    const user = userEvent.setup();
    renderEditable(fullContact);
    await startEditing(user);

    const options = within(screen.getByLabelText('Add detail')).getAllByRole('option');
    expect(options.map((o) => o.textContent)).toEqual([
      'Choose a detail…',
      'GitHub',
      'GitLab',
      'Custom…',
    ]);
  });

  it('adds a preset detail and saves it', async () => {
    const user = userEvent.setup();
    const updateSpy = vi.spyOn(api, 'updateResumeContact').mockResolvedValue({ message: 'ok' });
    const onUpdate = vi.fn();
    renderEditable(emptyContact, onUpdate);
    await startEditing(user);

    await user.type(screen.getByLabelText('Name'), 'Jo');
    await user.selectOptions(screen.getByLabelText('Add detail'), 'GitHub');
    await user.type(screen.getByLabelText('GitHub'), 'github.com/jo');
    await user.click(screen.getByRole('button', { name: /save/i }));

    await waitFor(() => {
      expect(updateSpy).toHaveBeenCalledWith({
        name: 'Jo',
        phone: null,
        location: null,
        fields: [{ key: 'GitHub', value: 'https://github.com/jo' }],
      });
    });
    await waitFor(() => expect(onUpdate).toHaveBeenCalled());
    // The chosen preset is no longer offered.
    expect(
      within(screen.queryByLabelText('Add detail') ?? document.body).queryByRole('option', {
        name: 'GitHub',
      }),
    ).not.toBeInTheDocument();
  });

  it('adds a custom key and saves it', async () => {
    const user = userEvent.setup();
    const updateSpy = vi.spyOn(api, 'updateResumeContact').mockResolvedValue({ message: 'ok' });
    renderEditable(emptyContact);
    await startEditing(user);

    await user.selectOptions(screen.getByLabelText('Add detail'), 'Custom…');
    await user.type(screen.getByLabelText('Detail 1 key'), 'Pronouns');
    await user.type(screen.getByLabelText('Detail 1 value'), 'they/them');
    await user.click(screen.getByRole('button', { name: /save/i }));

    await waitFor(() => {
      expect(updateSpy).toHaveBeenCalledWith(
        expect.objectContaining({ fields: [{ key: 'Pronouns', value: 'they/them' }] }),
      );
    });
  });

  it('removes a detail', async () => {
    const user = userEvent.setup();
    const updateSpy = vi.spyOn(api, 'updateResumeContact').mockResolvedValue({ message: 'ok' });
    renderEditable(fullContact);
    await startEditing(user);

    await user.click(screen.getByRole('button', { name: 'Remove Email' }));
    await user.click(screen.getByRole('button', { name: /save/i }));

    await waitFor(() => {
      const sent = updateSpy.mock.calls[0][0] as ContactInfo;
      expect(sent.fields.map((f) => f.key)).toEqual(['LinkedIn', 'Website', 'Pronouns']);
    });
  });

  it('rejects an invalid email, a non-http URL, a blank value and duplicate keys', async () => {
    const user = userEvent.setup();
    const updateSpy = vi.spyOn(api, 'updateResumeContact').mockResolvedValue({ message: 'ok' });
    renderEditable(fullContact);
    await startEditing(user);

    // The form remounts after a failed save, so look inputs up again each time.
    const email = () => screen.getByLabelText('Email');
    const site = () => screen.getByLabelText('Website');
    await user.clear(email());
    await user.type(email(), 'invalid-email');
    await user.click(screen.getByRole('button', { name: /save/i }));
    expect(await screen.findByText(/invalid email/i)).toBeInTheDocument();

    await user.clear(email());
    await user.type(email(), 'ok@example.com');
    await user.clear(site());
    await user.type(site(), 'javascript:alert(1)');
    await user.click(screen.getByRole('button', { name: /save/i }));
    expect(await screen.findByText(/valid http\(s\) url/i)).toBeInTheDocument();

    await user.clear(site());
    await user.click(screen.getByRole('button', { name: /save/i }));
    expect(await screen.findByText(/value is required/i)).toBeInTheDocument();

    await user.type(site(), 'https://janesmith.com');
    await user.selectOptions(screen.getByLabelText('Add detail'), 'Custom…');
    await user.type(screen.getByLabelText('Detail 5 key'), 'pronouns');
    await user.type(screen.getByLabelText('Detail 5 value'), 'x');
    await user.click(screen.getByRole('button', { name: /save/i }));
    expect(await screen.findByText(/duplicate key/i)).toBeInTheDocument();

    expect(updateSpy).not.toHaveBeenCalled();
  });

  it('reverts to view mode on cancel without saving', async () => {
    const user = userEvent.setup();
    const updateSpy = vi.spyOn(api, 'updateResumeContact');
    renderEditable(fullContact);
    await startEditing(user);

    const nameInput = screen.getByLabelText('Name');
    await user.clear(nameInput);
    await user.type(nameInput, 'Changed Name');
    await user.click(screen.getByRole('button', { name: /cancel/i }));

    expect(screen.getByText('Jane Smith')).toBeInTheDocument();
    expect(screen.queryByLabelText('Name')).not.toBeInTheDocument();
    expect(updateSpy).not.toHaveBeenCalled();
  });

  it('shows an error message when the API call fails', async () => {
    const user = userEvent.setup();
    vi.spyOn(api, 'updateResumeContact').mockRejectedValue(
      new api.ApiClientError('Server error', 500, 'Internal server error'),
    );
    renderEditable(fullContact);
    await startEditing(user);
    await user.click(screen.getByRole('button', { name: /save/i }));

    await waitFor(() => {
      expect(screen.getByText(/server error/i)).toBeInTheDocument();
    });
  });

  it('saves through the versioned endpoint when given a version id', async () => {
    const user = userEvent.setup();
    const versionSpy = vi.spyOn(api, 'updateVersionContact').mockResolvedValue({ message: 'ok' });
    renderWithQuery(<ContactSection contact={emptyContact} onUpdate={() => {}} versionId={9} />);
    await startEditing(user);
    await user.type(screen.getByLabelText('Name'), 'Jo');
    await user.click(screen.getByRole('button', { name: /save/i }));
    await waitFor(() => expect(versionSpy).toHaveBeenCalledWith(9, expect.objectContaining({ name: 'Jo' })));
  });
});
