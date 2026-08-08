const URL_RE = /^https?:\/\/.+/;

export default function UrlInput({ value, onChange, error, disabled }) {
  const invalid = value.length > 0 && !URL_RE.test(value);

  return (
    <div className="flex flex-col gap-1">
      <label htmlFor="url-input" className="text-sm font-medium text-gray-700">
        Website URL
      </label>
      <input
        id="url-input"
        type="url"
        value={value}
        onChange={(e) => onChange(e.target.value)}
        disabled={disabled}
        placeholder="https://example.com"
        aria-describedby={invalid ? "url-error" : undefined}
        aria-invalid={invalid}
        className={`w-full rounded-md border px-3 py-2 text-sm shadow-sm focus:outline-none focus:ring-2 focus:ring-blue-500 disabled:bg-gray-100 ${
          invalid ? "border-red-400" : "border-gray-300"
        }`}
      />
      {invalid && (
        <p id="url-error" className="text-xs text-red-600">
          Enter a valid URL starting with http:// or https://
        </p>
      )}
      {error && !invalid && (
        <p className="text-xs text-red-600">{error}</p>
      )}
    </div>
  );
}
