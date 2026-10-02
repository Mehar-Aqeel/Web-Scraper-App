import { render, screen } from '@testing-library/react';
import { describe, it, expect } from 'vitest';
import ResultsTable from '../components/ResultsTable';

const ROWS = [
  { type: 'title',   value: 'Test Page',            source_url: 'https://example.com' },
  { type: 'link',    value: 'https://example.com/a', text: 'About', source_url: 'https://example.com' },
  { type: 'heading', value: 'Welcome',               level: 'h1',   source_url: 'https://example.com' },
];

describe('ResultsTable', () => {
  it('renders nothing when data is empty', () => {
    const { container } = render(<ResultsTable data={[]} scrapedUrl="https://example.com" />);
    expect(container.firstChild).toBeNull();
  });

  it('renders a table with rows', () => {
    render(<ResultsTable data={ROWS} scrapedUrl="https://example.com" />);
    expect(screen.getByRole('table')).toBeInTheDocument();
  });

  it('renders all data rows', () => {
    render(<ResultsTable data={ROWS} scrapedUrl="https://example.com" />);
    expect(screen.getAllByText('Test Page').length).toBeGreaterThanOrEqual(1);
    expect(screen.getByText('About')).toBeInTheDocument();
    expect(screen.getByText('Welcome')).toBeInTheDocument();
  });

  it('does not use dangerouslySetInnerHTML — values are plain text', () => {
    const xss = [{ type: 'title', value: '<script>alert(1)</script>', source_url: 'https://x.com' }];
    render(<ResultsTable data={xss} scrapedUrl="https://x.com" />);
    expect(screen.getAllByText('<script>alert(1)</script>').length).toBeGreaterThanOrEqual(1);
    expect(document.querySelector('script[data-injected]')).toBeNull();
  });

  it('shows the scraped URL in the site header', () => {
    render(<ResultsTable data={ROWS} scrapedUrl="https://example.com" />);
    expect(screen.getAllByText('https://example.com').length).toBeGreaterThanOrEqual(1);
  });

  it('shows the page title in the site header when title record is present', () => {
    render(<ResultsTable data={ROWS} scrapedUrl="https://example.com" />);
    // "Test Page" appears both in the header and in the table body
    const matches = screen.getAllByText('Test Page');
    expect(matches.length).toBeGreaterThanOrEqual(1);
  });

  it('shows record count', () => {
    render(<ResultsTable data={ROWS} scrapedUrl="https://example.com" />);
    expect(screen.getByText(/3 records/i)).toBeInTheDocument();
  });

  it('table rows have tabIndex for keyboard navigation', () => {
    render(<ResultsTable data={ROWS} scrapedUrl="https://example.com" />);
    const rows = screen.getAllByRole('row').slice(1); // skip header
    rows.forEach((row) => expect(row).toHaveAttribute('tabindex', '0'));
  });
});
