import { render, screen } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { describe, it, expect, vi } from 'vitest';
import FilterPanel from '../components/FilterPanel';

const DATA = [
  { type: 'title',  value: 'Hello World',           source_url: 'https://example.com' },
  { type: 'link',   value: 'https://example.com/a', source_url: 'https://example.com' },
  { type: 'link',   value: 'https://example.com/b', source_url: 'https://example.com' },
];

const BASE_FILTERS = { keyword: '', type: 'all', hideEmpty: false, dedupe: false };

function setup(overrides = {}, filteredCount = DATA.length, onChange = vi.fn()) {
  const filters = { ...BASE_FILTERS, ...overrides };
  render(
    <FilterPanel
      data={DATA}
      filters={filters}
      onFiltersChange={onChange}
      filteredCount={filteredCount}
    />
  );
  return { onChange };
}

describe('FilterPanel', () => {
  it('renders search input with label', () => {
    setup();
    expect(screen.getByLabelText(/search/i)).toBeInTheDocument();
  });

  it('renders type dropdown with label', () => {
    setup();
    expect(screen.getByLabelText(/type/i)).toBeInTheDocument();
  });

  it('renders hide empty and deduplicate checkboxes', () => {
    setup();
    expect(screen.getByLabelText(/hide empty/i)).toBeInTheDocument();
    expect(screen.getByLabelText(/deduplicate/i)).toBeInTheDocument();
  });

  it('shows live filtered count', () => {
    setup({}, 2);
    expect(screen.getByText(/2 of 3 records/i)).toBeInTheDocument();
  });

  it('calls onFiltersChange with updated keyword when typing', async () => {
    const { onChange } = setup();
    await userEvent.type(screen.getByLabelText(/search/i), 'hello');
    expect(onChange).toHaveBeenCalledWith(expect.objectContaining({ keyword: expect.stringContaining('h') }));
  });

  it('calls onFiltersChange with updated type when dropdown changes', async () => {
    const { onChange } = setup();
    await userEvent.selectOptions(screen.getByLabelText(/type/i), 'link');
    expect(onChange).toHaveBeenCalledWith(expect.objectContaining({ type: 'link' }));
  });

  it('calls onFiltersChange with hideEmpty true when toggled', async () => {
    const { onChange } = setup();
    await userEvent.click(screen.getByLabelText(/hide empty/i));
    expect(onChange).toHaveBeenCalledWith(expect.objectContaining({ hideEmpty: true }));
  });

  it('calls onFiltersChange with dedupe true when toggled', async () => {
    const { onChange } = setup();
    await userEvent.click(screen.getByLabelText(/deduplicate/i));
    expect(onChange).toHaveBeenCalledWith(expect.objectContaining({ dedupe: true }));
  });

  it('type dropdown includes all unique types from data', () => {
    setup();
    expect(screen.getByRole('option', { name: 'title' })).toBeInTheDocument();
    expect(screen.getByRole('option', { name: 'link' })).toBeInTheDocument();
  });
});
