const ALL_TYPES = "all";

export default function FilterPanel({ data, filters, onFiltersChange, filteredCount }) {
  const types = [...new Set(data.map((r) => r.type))].sort();

  function set(key, value) {
    onFiltersChange({ ...filters, [key]: value });
  }

  return (
    <div className="bg-white rounded-lg border border-gray-200 shadow-sm p-4 space-y-3">
      <div className="flex flex-wrap gap-3 items-end">

        {/* Keyword search */}
        <div className="flex flex-col gap-1 flex-1 min-w-[180px]">
          <label htmlFor="filter-search" className="text-xs font-medium text-gray-600">
            Search
          </label>
          <input
            id="filter-search"
            type="search"
            value={filters.keyword}
            onChange={(e) => set("keyword", e.target.value)}
            placeholder="Filter by keyword…"
            className="rounded-md border border-gray-300 px-3 py-1.5 text-sm focus:outline-none focus:ring-2 focus:ring-blue-500"
          />
        </div>

        {/* Type dropdown */}
        <div className="flex flex-col gap-1">
          <label htmlFor="filter-type" className="text-xs font-medium text-gray-600">
            Type
          </label>
          <select
            id="filter-type"
            value={filters.type}
            onChange={(e) => set("type", e.target.value)}
            className="rounded-md border border-gray-300 px-3 py-1.5 text-sm focus:outline-none focus:ring-2 focus:ring-blue-500"
          >
            <option value={ALL_TYPES}>All types</option>
            {types.map((t) => (
              <option key={t} value={t}>{t}</option>
            ))}
          </select>
        </div>

        {/* Toggles */}
        <div className="flex gap-4 items-center pb-0.5">
          <label className="flex items-center gap-2 text-sm text-gray-600 cursor-pointer select-none">
            <input
              type="checkbox"
              checked={filters.hideEmpty}
              onChange={(e) => set("hideEmpty", e.target.checked)}
              className="rounded focus:ring-2 focus:ring-blue-500"
            />
            Hide empty
          </label>
          <label className="flex items-center gap-2 text-sm text-gray-600 cursor-pointer select-none">
            <input
              type="checkbox"
              checked={filters.dedupe}
              onChange={(e) => set("dedupe", e.target.checked)}
              className="rounded focus:ring-2 focus:ring-blue-500"
            />
            Deduplicate
          </label>
        </div>
      </div>

      <p className="text-xs text-gray-400">
        {filteredCount} of {data.length} record{data.length !== 1 ? "s" : ""}
      </p>
    </div>
  );
}
