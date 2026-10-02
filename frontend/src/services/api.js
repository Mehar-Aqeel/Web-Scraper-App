const API_BASE = import.meta.env.VITE_API_BASE ?? "http://localhost:8000/api/v1";
const WS_BASE = API_BASE.replace(/^http/, "ws");

/** Reject non-http(s) schemes before sending to the backend. */
function assertSafeUrl(url) {
  if (!/^https?:\/\//i.test(url)) {
    throw new TypeError(`Unsafe URL scheme rejected: ${url.slice(0, 80)}`);
  }
}

export async function getExtractionTypes() {
  const res = await fetch(`${API_BASE}/extract/types`);
  return res.json();
}

export async function extractData(url, fields, signal) {
  assertSafeUrl(url);
  const res = await fetch(`${API_BASE}/extract`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ url, extract: fields }),
    signal,
  });
  return res.json();
}

export async function extractJs(url, fields, signal) {
  assertSafeUrl(url);
  const res = await fetch(`${API_BASE}/extract/js`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ url, extract: fields }),
    signal,
  });
  return res.json();
}

export async function pollJob(jobId, signal) {
  const res = await fetch(`${API_BASE}/jobs/${jobId}`, { signal });
  return res.json();
}

export function connectJobWs(jobId, onEvent, onClose) {
  if (!/^[\w-]+$/.test(jobId)) throw new TypeError("Invalid job ID");
  const ws = new WebSocket(`${WS_BASE}/jobs/${jobId}/ws`);
  ws.onmessage = (e) => onEvent(JSON.parse(e.data));
  ws.onclose = () => onClose?.();
  ws.onerror = () => onClose?.();
  return ws;
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

export async function exportJson(data, signal) {
  const res = await fetch(`${API_BASE}/export/json`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ data }),
    signal,
  });
  return res.blob();
}

export async function exportExcel(data, signal) {
  const res = await fetch(`${API_BASE}/export/excel`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ data }),
    signal,
  });
  return res.blob();
}

export async function batchExtract(urls, fields, signal) {
  urls.forEach(assertSafeUrl);
  const res = await fetch(`${API_BASE}/extract/batch`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ urls, extract: fields }),
    signal,
  });
  return res.json();
}

export async function getHistory(limit = 50) {
  const res = await fetch(`${API_BASE}/history?limit=${limit}`);
  return res.json();
}

export async function getHistoryRecords(jobId) {
  const res = await fetch(`${API_BASE}/history/${jobId}/records`);
  return res.json();
}

export async function getDashboard() {
  const res = await fetch(`${API_BASE}/dashboard`);
  return res.json();
}

export async function healthCheck() {
  const res = await fetch(`${API_BASE}/health/live`);
  return res.json();
}
