const API_BASE = import.meta.env.VITE_API_BASE ?? "http://localhost:8000/api/v1";

export async function getExtractionTypes() {
  const res = await fetch(`${API_BASE}/extract/types`);
  return res.json();
}

export async function extractData(url, fields, signal) {
  const res = await fetch(`${API_BASE}/extract`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ url, extract: fields }),
    signal,
  });
  return res.json();
}

export async function exportCsv(data, signal) {
  const res = await fetch(`${API_BASE}/export/csv`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ data }),
    signal,
  });
  return res.blob();
}

export async function healthCheck() {
  const res = await fetch(`${API_BASE}/health/live`);
  return res.json();
}
