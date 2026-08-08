import { useEffect, useState } from "react";
import { getExtractionTypes } from "../services/api";

const LABELS = {
  title: "Title",
  meta: "Meta",
  headings: "Headings",
  paragraphs: "Paragraphs",
  links: "Links",
  images: "Images",
  tables: "Tables",
  open_graph: "Open Graph",
  canonical_url: "Canonical URL",
};

export default function ExtractionOptions({ selected, onChange }) {
  const [types, setTypes] = useState([]);

  useEffect(() => {
    getExtractionTypes()
      .then((data) => setTypes(data.types ?? []))
      .catch(() => setTypes(Object.keys(LABELS)));
  }, []);

  function toggle(type) {
    onChange(
      selected.includes(type)
        ? selected.filter((t) => t !== type)
        : [...selected, type]
    );
  }

  return (
    <fieldset>
      <legend className="text-sm font-medium text-gray-700 mb-2">
        What do you want to extract?
      </legend>
      <div className="grid grid-cols-2 gap-2 sm:grid-cols-3">
        {types.map((type) => (
          <label key={type} className="flex items-center gap-2 cursor-pointer">
            <input
              type="checkbox"
              checked={selected.includes(type)}
              onChange={() => toggle(type)}
              className="rounded"
            />
            <span className="text-sm text-gray-700">
              {LABELS[type] ?? type}
            </span>
          </label>
        ))}
      </div>
    </fieldset>
  );
}
