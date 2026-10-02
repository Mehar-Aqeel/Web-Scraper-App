import { render, screen, waitFor } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { describe, it, expect, vi, beforeEach } from 'vitest';
import Home from '../pages/Home';

// ---------------------------------------------------------------------------
// Mock the entire api module
// ---------------------------------------------------------------------------

const mockExtractData = vi.fn();
const mockExportCsv = vi.fn();
const mockGetExtractionTypes = vi.fn();

vi.mock('../services/api', () => ({
  extractData: (...args) => mockExtractData(...args),
  exportCsv: (...args) => mockExportCsv(...args),
  getExtractionTypes: (...args) => mockGetExtractionTypes(...args),
}));

const MOCK_TYPES = { types: ['title', 'headings', 'links', 'paragraphs', 'images', 'tables', 'meta', 'open_graph', 'canonical_url'] };

const MOCK_RESPONSE = {
  success: true,
  url: 'https://example.com',
  data: [
    { type: 'title',   value: 'Example Domain', source_url: 'https://example.com' },
    { type: 'heading', value: 'Welcome',         level: 'h1', source_url: 'https://example.com' },
    { type: 'link',    value: 'https://example.com/more', text: 'More info', source_url: 'https://example.com' },
  ],
  warnings: [],
  next_cursor: null,
};

beforeEach(() => {
  vi.clearAllMocks();
  mockGetExtractionTypes.mockResolvedValue(MOCK_TYPES);
});

describe('Home — extract → results → download flow', () => {
  it('shows extraction form on initial render', async () => {
    render(<Home />);
    expect(screen.getByLabelText(/website url/i)).toBeInTheDocument();
    expect(screen.getByRole('button', { name: /extract data/i })).toBeInTheDocument();
  });

  it('extract button is disabled when URL is empty', async () => {
    render(<Home />);
    expect(screen.getByRole('button', { name: /extract data/i })).toBeDisabled();
  });

  it('extract button is disabled when URL is invalid', async () => {
    render(<Home />);
    await userEvent.type(screen.getByLabelText(/website url/i), 'not-a-url');
    expect(screen.getByRole('button', { name: /extract data/i })).toBeDisabled();
  });

  it('extract button is enabled for a valid URL with fields selected', async () => {
    render(<Home />);
    await userEvent.type(screen.getByLabelText(/website url/i), 'https://example.com');
    // Wait for extraction types to load so checkboxes appear
    await waitFor(() => expect(screen.getByLabelText(/title/i)).toBeInTheDocument());
    expect(screen.getByRole('button', { name: /extract data/i })).toBeEnabled();
  });

  it('shows loading state while request is in flight', async () => {
    let resolve;
    mockExtractData.mockReturnValue(new Promise((r) => { resolve = r; }));

    render(<Home />);
    await userEvent.type(screen.getByLabelText(/website url/i), 'https://example.com');
    await waitFor(() => expect(screen.getByLabelText(/title/i)).toBeInTheDocument());
    await userEvent.click(screen.getByRole('button', { name: /extract data/i }));

    expect(screen.getByRole('status', { name: /extracting/i })).toBeInTheDocument();
    resolve(MOCK_RESPONSE);
  });

  it('renders results table after successful extraction', async () => {
    mockExtractData.mockResolvedValue(MOCK_RESPONSE);

    render(<Home />);
    await userEvent.type(screen.getByLabelText(/website url/i), 'https://example.com');
    await waitFor(() => expect(screen.getByLabelText(/title/i)).toBeInTheDocument());
    await userEvent.click(screen.getByRole('button', { name: /extract data/i }));

    await waitFor(() => expect(screen.getByRole('table')).toBeInTheDocument());
    expect(screen.getAllByText('Example Domain').length).toBeGreaterThanOrEqual(1);
    expect(screen.getAllByText('Welcome').length).toBeGreaterThanOrEqual(1);
  });

  it('shows filter panel after successful extraction', async () => {
    mockExtractData.mockResolvedValue(MOCK_RESPONSE);

    render(<Home />);
    await userEvent.type(screen.getByLabelText(/website url/i), 'https://example.com');
    await waitFor(() => expect(screen.getByLabelText(/title/i)).toBeInTheDocument());
    await userEvent.click(screen.getByRole('button', { name: /extract data/i }));

    await waitFor(() => expect(screen.getByLabelText(/search/i)).toBeInTheDocument());
  });

  it('download CSV button is enabled when results are present', async () => {
    mockExtractData.mockResolvedValue(MOCK_RESPONSE);

    render(<Home />);
    await userEvent.type(screen.getByLabelText(/website url/i), 'https://example.com');
    await waitFor(() => expect(screen.getByLabelText(/title/i)).toBeInTheDocument());
    await userEvent.click(screen.getByRole('button', { name: /extract data/i }));

    await waitFor(() => expect(screen.getByRole('button', { name: /download csv/i })).toBeEnabled());
  });

  it('triggers CSV download when Download CSV is clicked', async () => {
    mockExtractData.mockResolvedValue(MOCK_RESPONSE);
    mockExportCsv.mockResolvedValue(new Blob(['csv'], { type: 'text/csv' }));

    // Mock URL.createObjectURL / revokeObjectURL
    const createObjectURL = vi.fn(() => 'blob:mock');
    const revokeObjectURL = vi.fn();
    vi.stubGlobal('URL', { ...URL, createObjectURL, revokeObjectURL });

    render(<Home />);
    await userEvent.type(screen.getByLabelText(/website url/i), 'https://example.com');
    await waitFor(() => expect(screen.getByLabelText(/title/i)).toBeInTheDocument());
    await userEvent.click(screen.getByRole('button', { name: /extract data/i }));
    await waitFor(() => expect(screen.getByRole('button', { name: /download csv/i })).toBeEnabled());

    await userEvent.click(screen.getByRole('button', { name: /download csv/i }));

    await waitFor(() => expect(mockExportCsv).toHaveBeenCalledWith(MOCK_RESPONSE.data));
    expect(createObjectURL).toHaveBeenCalled();
    expect(revokeObjectURL).toHaveBeenCalled();
  });

  it('shows error message on API error response', async () => {
    mockExtractData.mockResolvedValue({
      success: false,
      error: { code: 'TIMEOUT', message: 'timed out' },
    });

    render(<Home />);
    await userEvent.type(screen.getByLabelText(/website url/i), 'https://example.com');
    await waitFor(() => expect(screen.getByLabelText(/title/i)).toBeInTheDocument());
    await userEvent.click(screen.getByRole('button', { name: /extract data/i }));

    await waitFor(() => expect(screen.getByRole('alert')).toBeInTheDocument());
    expect(screen.getAllByText(/timed out|slow or unreachable/i).length).toBeGreaterThanOrEqual(1);
  });

  it('shows service unavailable state on network failure', async () => {
    mockExtractData.mockRejectedValue(new TypeError('Failed to fetch'));

    render(<Home />);
    await userEvent.type(screen.getByLabelText(/website url/i), 'https://example.com');
    await waitFor(() => expect(screen.getByLabelText(/title/i)).toBeInTheDocument());
    await userEvent.click(screen.getByRole('button', { name: /extract data/i }));

    await waitFor(() => expect(screen.getByRole('alert')).toBeInTheDocument());
    expect(screen.getByText(/service is unreachable/i)).toBeInTheDocument();
  });
});
