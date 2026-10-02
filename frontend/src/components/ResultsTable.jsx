const TYPE_LABELS = {
  title:       "Title",
  heading:     "Heading",
  paragraph:   "Paragraph",
  link:        "Link",
  image:       "Image",
  table_row:   "Table Row",
  meta:        "Meta",
  open_graph:  "Open Graph",
  canonical:   "Canonical",
};

function Cell({ value }) {
  const text = value == null ? "" : String(value);
  return (
    <td
      className="px-3 py-2 text-sm text-gray-700 max-w-xs truncate"
      title={text}
    >
      {text}
    </td>
  );
}

function SiteHeader({ scrapedUrl, data }) {
  const title = data.find((r) => r.type === "title")?.value ?? null;
  let hostname = "";
  try { hostname = new URL(scrapedUrl).hostname; } catch { /* ignore */ }
  const faviconSrc = hostname ? `https://${hostname}/favicon.ico` : null;

  return (
    <div className="flex items-center gap-3 mb-3">
      {faviconSrc && (
        <img
          src={faviconSrc}
          alt=""
          aria-hidden="true"
          width={16}
          height={16}
          className="rounded-sm"
          onError={(e) => { e.currentTarget.style.display = "none"; }}
        />
      )}
      <div className="min-w-0">
        {title && (
          <p className="text-sm font-medium text-gray-800 truncate">{title}</p>
        )}
        <p className="text-xs text-gray-500 truncate">{scrapedUrl}</p>
      </div>
    </div>
  );
}

export default function ResultsTable({ data, scrapedUrl }) {
  if (!data || data.length === 0) return null;

  return (
    <section aria-label="Extraction results">
      <SiteHeader scrapedUrl={scrapedUrl} data={data} />

      <div className="overflow-x-auto rounded-lg border border-gray-200 shadow-sm">
        <table className="min-w-full divide-y divide-gray-200 text-left">
          <thead className="bg-gray-50">
            <tr>
              {["Type", "Value", "Text / Alt", "Level", "Source URL"].map((h) => (
                <th
                  key={h}
                  scope="col"
                  className="px-3 py-2 text-xs font-semibold text-gray-500 uppercase tracking-wide"
                >
                  {h}
                </th>
              ))}
            </tr>
          </thead>
          <tbody className="divide-y divide-gray-100 bg-white">
            {data.map((row, i) => (
              <tr
                key={i}
                tabIndex={0}
                className="hover:bg-gray-50 focus:outline-none focus:ring-2 focus:ring-inset focus:ring-blue-500"
              >
                <td className="px-3 py-2 text-xs font-medium text-blue-700 whitespace-nowrap">
                  {TYPE_LABELS[row.type] ?? row.type}
                </td>
                <Cell value={row.value} />
                <Cell value={row.text ?? row.alt ?? ""} />
                <Cell value={row.level ?? ""} />
                <td className="px-3 py-2 text-xs text-gray-400 max-w-[12rem] truncate" title={row.source_url ?? ""}>
                  {row.source_url ?? ""}
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>

      <p className="mt-2 text-xs text-gray-400">{data.length} record{data.length !== 1 ? "s" : ""}</p>
    </section>
  );
}
