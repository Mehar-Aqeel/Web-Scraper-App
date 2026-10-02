import { render, screen } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { describe, it, expect, vi } from 'vitest';
import UrlInput from '../components/UrlInput';

function setup(value = '', onChange = vi.fn(), props = {}) {
  render(<UrlInput value={value} onChange={onChange} {...props} />);
  return { input: screen.getByRole('textbox', { name: /website url/i }), onChange };
}

describe('UrlInput', () => {
  it('renders with a visible label', () => {
    setup();
    expect(screen.getByLabelText(/website url/i)).toBeInTheDocument();
  });

  it('shows no error for an empty value', () => {
    setup('');
    expect(screen.queryByRole('alert')).not.toBeInTheDocument();
    expect(screen.queryByText(/valid url/i)).not.toBeInTheDocument();
  });

  it('shows inline error for an invalid URL', () => {
    setup('not-a-url');
    expect(screen.getByText(/valid url starting with http/i)).toBeInTheDocument();
  });

  it('does not show error for a valid http URL', () => {
    setup('http://example.com');
    expect(screen.queryByText(/valid url/i)).not.toBeInTheDocument();
  });

  it('does not show error for a valid https URL', () => {
    setup('https://example.com/path?q=1');
    expect(screen.queryByText(/valid url/i)).not.toBeInTheDocument();
  });

  it('calls onChange when user types', async () => {
    const onChange = vi.fn();
    setup('', onChange);
    await userEvent.type(screen.getByRole('textbox', { name: /website url/i }), 'h');
    expect(onChange).toHaveBeenCalled();
  });

  it('is disabled when disabled prop is true', () => {
    setup('', vi.fn(), { disabled: true });
    expect(screen.getByRole('textbox', { name: /website url/i })).toBeDisabled();
  });

  it('sets aria-invalid when value is invalid', () => {
    setup('bad-url');
    expect(screen.getByRole('textbox', { name: /website url/i })).toHaveAttribute('aria-invalid', 'true');
  });
});
