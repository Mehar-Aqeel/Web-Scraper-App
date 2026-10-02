import { useEffect, useMemo, useReducer, useRef, useState } from "react";
import Dashboard from "../components/Dashboard";
import ErrorMessage from "../components/ErrorMessage";
import ExtractionOptions from "../components/ExtractionOptions";
import FilterPanel from "../components/FilterPanel";
import Footer from "../components/Footer";
import HistoryPanel from "../components/HistoryPanel";
import HowItWorks from "../components/HowItWorks";
import LoadingState from "../components/LoadingState";
import Navbar from "../components/Navbar";
import ResultsTable from "../components/ResultsTable";
import UrlInput from "../components/UrlInput";
import {
  batchExtract,
  connectJobWs,
  exportCsv,
  exportExcel,
  exportJson,
  extractData,
  extractJs,
  pollJob,
} from "../services/api";

// ---------------------------------------------------------------------------
// State machine
// ---------------------------------------------------------------------------

const INITIAL = {
  url: "",
  batchUrls: "",
  selectedFields: ["title", "headings", "links"],
  useJs: false,
  batchMode: false,
  status: "idle",
  stage: null,
  progress: null,
  data: [],
  warnings: [],
  nextCursor: null,
  scrapedUrl: "",
  error: null,
  serviceUnavailable: false,
};

function reducer(state, action) {
  switch (action.type) {
    case "SET_URL":        return { ...state, url: action.payload };
    case "SET_BATCH_URLS": return { ...state, batchUrls: action.payload };
    case "SET_FIELDS":     return { ...state, selectedFields: action.payload };
    case "SET_USE_JS":     return { ...state, useJs: action.payload };
    case "SET_BATCH_MODE": return { ...state, batchMode: action.payload };
    case "FETCH_START":
      return { ...state, status: "loading", stage: null, progress: null, error: null, serviceUnavailable: false };
    case "SET_PROGRESS":
      return { ...state, stage: action.payload.stage, progress: action.payload.progress };
    case "FETCH_SUCCESS":
      return {
        ...state,
        status: "success",
        stage: null,
        progress: null,
        data: action.payload.data,
        warnings: action.payload.warnings ?? [],
        nextCursor: action.payload.next_cursor ?? null,
        scrapedUrl: action.payload.url ?? state.url,
      };
    case "FETCH_ERROR":
      return {
        ...state,
        status: "error",
        stage: null,
        progress: null,
        error: action.payload.error ?? null,
        serviceUnavailable: action.payload.serviceUnavailable ?? false,
      };
    default:
      return state;
  }
}

function isValidUrl(url) {
  return /^https?:\/\/.+/.test(url) && url.length <= 2048;
}

const FILTER_INITIAL = { keyword: "", type: "all", hideEmpty: false, dedupe: false };

function applyFilters(data, filters) {
  let rows = data;
  if (filters.type !== "all") rows = rows.filter((r) => r.type === filters.type);
  if (filters.hideEmpty) rows = rows.filter((r) => r.value != null && String(r.value).trim() !== "");
  if (filters.keyword.trim()) {
    const kw = filters.keyword.trim().toLowerCase();
    rows = rows.filter((r) => Object.values(r).some((v) => v != null && String(v).toLowerCase().includes(kw)));
  }
  if (filters.dedupe) {
    const seen = new Set();
    rows = rows.filter((r) => { const k = JSON.stringify(r); if (seen.has(k)) return false; seen.add(k); return true; });
  }
  return rows;
}

// ---------------------------------------------------------------------------
// Component
// ---------------------------------------------------------------------------

const TABS = ["Home", "Extract", "History", "Dashboard"];

export default function Home() {
  const [state, dispatch] = useReducer(reducer, INITIAL);
  const [filters, setFilters] = useState(FILTER_INITIAL);
  const [exportLoading, setExportLoading] = useState(null);
  const [activeTab, setActiveTab] = useState("Home");
  const [historyKey, setHistoryKey] = useState(0);
  const abortRef = useRef(null);
  const wsRef = useRef(null);
  const extractSectionRef = useRef(null);

  useEffect(() => {
    if (state.status === "success") {
      setFilters(FILTER_INITIAL);
      setHistoryKey((k) => k + 1);
    }
  }, [state.status, state.data]);

  useEffect(() => () => {
    abortRef.current?.abort();
    wsRef.current?.close();
  }, []);

  const filteredData = useMemo(() => applyFilters(state.data, filters), [state.data, filters]);

  const parsedBatchUrls = state.batchUrls
    .split("\n")
    .map((u) => u.trim())
    .filter(Boolean);

  const canSubmit =
    state.status !== "loading" &&
    state.selectedFields.length > 0 &&
    (state.batchMode
      ? parsedBatchUrls.length > 0 && parsedBatchUrls.length <= 20
      : isValidUrl(state.url));

  function handleGetStarted() {
    setActiveTab("Extract");
    setTimeout(() => extractSectionRef.current?.scrollIntoView({ behavior: "smooth" }), 50);
  }

  async function triggerDownload(blob, filename) {
    const url = URL.createObjectURL(blob);
    const a = document.createElement("a");
    a.href = url;
    a.download = filename;
    a.click();
    URL.revokeObjectURL(url);
  }

  async function handleExport(format) {
    if (!filteredData.length || exportLoading) return;
    setExportLoading(format);
    try {
      if (format === "csv") {
        const blob = await exportCsv(filteredData);
        await triggerDownload(blob, "extraction.csv");
      } else if (format === "json") {
        const blob = await exportJson(filteredData);
        await triggerDownload(blob, "extraction.json");
      } else if (format === "excel") {
        const blob = await exportExcel(filteredData);
        await triggerDownload(blob, "extraction.xlsx");
      }
    } finally {
      setExportLoading(null);
    }
  }

  async function handleExtract(e) {
    e.preventDefault();
    if (!canSubmit) return;

    abortRef.current?.abort();
    wsRef.current?.close();
    const controller = new AbortController();
    abortRef.current = controller;

    dispatch({ type: "FETCH_START" });

    try {
      if (state.batchMode) {
        const json = await batchExtract(parsedBatchUrls, state.selectedFields, controller.signal);
        if (!json.results) {
          dispatch({ type: "FETCH_ERROR", payload: { error: json.error ?? { code: "INTERNAL_ERROR", message: "Batch failed." } } });
          return;
        }
        const allData = json.results.flatMap((r) => r.data);
        const allWarnings = json.results.flatMap((r) =>
          r.success ? r.warnings : [`${r.url}: ${r.error}`]
        );
        dispatch({ type: "FETCH_SUCCESS", payload: { data: allData, warnings: allWarnings, url: parsedBatchUrls[0] } });

      } else if (state.useJs) {
        const job = await extractJs(state.url, state.selectedFields, controller.signal);
        if (!job.job_id) {
          dispatch({ type: "FETCH_ERROR", payload: { error: job.error ?? { code: "INTERNAL_ERROR", message: "Failed to start job." } } });
          return;
        }
        const ws = connectJobWs(
          job.job_id,
          (event) => {
            if (event.stage !== undefined) {
              dispatch({ type: "SET_PROGRESS", payload: { stage: event.stage, progress: event.progress } });
            }
            if (event.status === "done" || event.status === "error") ws.close();
          },
          async () => {
            const result = await pollJob(job.job_id, controller.signal).catch(() => null);
            if (!result || result.status === "error") {
              dispatch({ type: "FETCH_ERROR", payload: { error: { code: "INTERNAL_ERROR", message: result?.error ?? "JS extraction failed." } } });
            } else if (result.status === "done") {
              dispatch({ type: "FETCH_SUCCESS", payload: { ...result, url: state.url } });
            }
          }
        );
        wsRef.current = ws;

      } else {
        const json = await extractData(state.url, state.selectedFields, controller.signal);
        if (!json.success) {
          dispatch({ type: "FETCH_ERROR", payload: { error: json.error } });
        } else {
          dispatch({ type: "FETCH_SUCCESS", payload: json });
        }
      }
    } catch (err) {
      if (err.name === "AbortError") return;
      dispatch({ type: "FETCH_ERROR", payload: { serviceUnavailable: true } });
    }
  }

  return (
    <div className="min-h-screen flex flex-col bg-gray-50">
      <Navbar activeTab={activeTab} onTabChange={setActiveTab} />

      <main className="flex-1">
        <div className="max-w-6xl mx-auto px-4 sm:px-6 lg:px-8 py-10">

          {/* ── Home / Guide tab ── */}
          {activeTab === "Home" && (
            <HowItWorks onGetStarted={handleGetStarted} />
          )}

          {/* ── Extract tab ── */}
          {activeTab === "Extract" && (
            <div ref={extractSectionRef} className="space-y-6">

              {/* Page header */}
              <div className="space-y-1">
                <h2 className="text-2xl font-bold text-gray-900">Web Data Extractor</h2>
                <p className="text-sm text-gray-500">
                  Enter a URL, choose what to extract, and download the results.
                </p>
              </div>

              {/* Extract form card */}
              <form
                onSubmit={handleExtract}
                className="bg-white rounded-2xl shadow-sm border border-gray-200 p-6 sm:p-8 space-y-6"
                noValidate
              >
                {/* Batch toggle */}
                <label className="flex items-center gap-2.5 text-sm text-gray-600 cursor-pointer select-none w-fit">
                  <input
                    type="checkbox"
                    checked={state.batchMode}
                    onChange={(e) => dispatch({ type: "SET_BATCH_MODE", payload: e.target.checked })}
                    className="rounded focus:ring-2 focus:ring-blue-500"
                  />
                  <span className="font-medium">Batch mode</span>
                  <span className="text-xs text-gray-400 bg-gray-100 px-2 py-0.5 rounded-full">up to 20 URLs</span>
                </label>

                {state.batchMode ? (
                  <div className="flex flex-col gap-1.5">
                    <label htmlFor="batch-urls" className="text-sm font-medium text-gray-700">
                      URLs <span className="text-gray-400 font-normal">(one per line)</span>
                    </label>
                    <textarea
                      id="batch-urls"
                      rows={5}
                      value={state.batchUrls}
                      onChange={(e) => dispatch({ type: "SET_BATCH_URLS", payload: e.target.value })}
                      disabled={state.status === "loading"}
                      placeholder={"https://example.com\nhttps://other.com"}
                      className="w-full rounded-lg border border-gray-300 px-3 py-2 text-sm shadow-sm focus:outline-none focus:ring-2 focus:ring-blue-500 disabled:bg-gray-100 font-mono"
                    />
                    <p className="text-xs text-gray-400">{parsedBatchUrls.length} / 20 URLs</p>
                  </div>
                ) : (
                  <UrlInput
                    value={state.url}
                    onChange={(v) => dispatch({ type: "SET_URL", payload: v })}
                    disabled={state.status === "loading"}
                  />
                )}

                <ExtractionOptions
                  selected={state.selectedFields}
                  onChange={(v) => dispatch({ type: "SET_FIELDS", payload: v })}
                />

                {!state.batchMode && (
                  <label className="flex items-center gap-2.5 text-sm text-gray-600 cursor-pointer select-none w-fit">
                    <input
                      type="checkbox"
                      checked={state.useJs}
                      onChange={(e) => dispatch({ type: "SET_USE_JS", payload: e.target.checked })}
                      className="rounded focus:ring-2 focus:ring-blue-500"
                    />
                    <span className="font-medium">Enable JS rendering</span>
                    <span className="text-xs text-gray-400 bg-gray-100 px-2 py-0.5 rounded-full">slower — headless browser</span>
                  </label>
                )}

                <button
                  type="submit"
                  disabled={!canSubmit}
                  className="w-full rounded-lg bg-blue-600 px-4 py-3 text-sm font-semibold text-white hover:bg-blue-700 focus:outline-none focus:ring-2 focus:ring-blue-500 disabled:opacity-50 disabled:cursor-not-allowed transition-colors shadow-sm"
                >
                  {state.status === "loading"
                    ? "Extracting…"
                    : state.batchMode
                    ? "Extract All URLs"
                    : "Extract Data"}
                </button>
              </form>

              {state.status === "loading" && (
                <div className="bg-white rounded-2xl border border-gray-200 shadow-sm p-6">
                  <LoadingState stage={state.stage} progress={state.progress} />
                </div>
              )}

              {state.status === "error" && (
                <ErrorMessage error={state.error} isServiceUnavailable={state.serviceUnavailable} />
              )}

              {state.status === "success" && state.warnings.length > 0 && (
                <div className="rounded-xl bg-yellow-50 border border-yellow-200 p-4 text-xs text-yellow-800 space-y-1">
                  {state.warnings.map((w, i) => <p key={i}>⚠ {w}</p>)}
                </div>
              )}

              {state.status === "success" && state.data.length > 0 && (
                <>
                  {/* Results header */}
                  <div className="flex flex-wrap items-center justify-between gap-3 bg-white rounded-2xl border border-gray-200 shadow-sm p-4 sm:p-5">
                    <div className="flex items-center gap-3">
                      <div className="w-9 h-9 rounded-lg bg-green-50 flex items-center justify-center">
                        <svg className="w-5 h-5 text-green-600" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={2}>
                          <path strokeLinecap="round" strokeLinejoin="round" d="M9 12.75L11.25 15 15 9.75M21 12a9 9 0 11-18 0 9 9 0 0118 0z" />
                        </svg>
                      </div>
                      <div>
                        <p className="text-sm font-semibold text-gray-900">
                          {filteredData.length} result{filteredData.length !== 1 ? "s" : ""}
                          {filteredData.length !== state.data.length && (
                            <span className="text-gray-400 font-normal"> of {state.data.length}</span>
                          )}
                        </p>
                        {state.scrapedUrl && (
                          <p className="text-xs text-gray-400 truncate max-w-xs">{state.scrapedUrl}</p>
                        )}
                      </div>
                    </div>

                    <div className="flex gap-2 shrink-0">
                      {[
                        { fmt: "csv",   label: "CSV",   color: "bg-emerald-600 hover:bg-emerald-700" },
                        { fmt: "json",  label: "JSON",  color: "bg-violet-600 hover:bg-violet-700" },
                        { fmt: "excel", label: "Excel", color: "bg-blue-600 hover:bg-blue-700" },
                      ].map(({ fmt, label, color }) => (
                        <button
                          key={fmt}
                          onClick={() => handleExport(fmt)}
                          disabled={!filteredData.length || exportLoading !== null}
                          className={`rounded-lg ${color} px-3 py-2 text-xs font-semibold text-white focus:outline-none focus:ring-2 focus:ring-offset-1 disabled:opacity-50 disabled:cursor-not-allowed transition-colors`}
                        >
                          {exportLoading === fmt ? "…" : `↓ ${label}`}
                        </button>
                      ))}
                    </div>
                  </div>

                  <FilterPanel
                    data={state.data}
                    filters={filters}
                    onFiltersChange={setFilters}
                    filteredCount={filteredData.length}
                  />

                  <ResultsTable data={filteredData} scrapedUrl={state.scrapedUrl} />
                </>
              )}
            </div>
          )}

          {/* ── History tab ── */}
          {activeTab === "History" && (
            <div className="space-y-4">
              <div className="space-y-1">
                <h2 className="text-2xl font-bold text-gray-900">Scraping History</h2>
                <p className="text-sm text-gray-500">All past extraction jobs and their results.</p>
              </div>
              <HistoryPanel onReload={historyKey} />
            </div>
          )}

          {/* ── Dashboard tab ── */}
          {activeTab === "Dashboard" && (
            <div className="space-y-4">
              <div className="space-y-1">
                <h2 className="text-2xl font-bold text-gray-900">Dashboard</h2>
                <p className="text-sm text-gray-500">Aggregate stats across all extraction jobs.</p>
              </div>
              <Dashboard />
            </div>
          )}

        </div>
      </main>

      <Footer />
    </div>
  );
}
