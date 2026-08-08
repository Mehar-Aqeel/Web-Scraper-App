import { useEffect, useReducer, useRef } from "react";
import ErrorMessage from "../components/ErrorMessage";
import ExtractionOptions from "../components/ExtractionOptions";
import LoadingState from "../components/LoadingState";
import UrlInput from "../components/UrlInput";
import { extractData } from "../services/api";

// ---------------------------------------------------------------------------
// State machine
// ---------------------------------------------------------------------------

const INITIAL = {
  url: "",
  selectedFields: ["title", "headings", "links"],
  status: "idle",   // idle | loading | success | error
  data: [],
  warnings: [],
  nextCursor: null,
  error: null,
  serviceUnavailable: false,
};

function reducer(state, action) {
  switch (action.type) {
    case "SET_URL":
      return { ...state, url: action.payload };
    case "SET_FIELDS":
      return { ...state, selectedFields: action.payload };
    case "FETCH_START":
      return { ...state, status: "loading", error: null, serviceUnavailable: false };
    case "FETCH_SUCCESS":
      return {
        ...state,
        status: "success",
        data: action.payload.data,
        warnings: action.payload.warnings,
        nextCursor: action.payload.next_cursor ?? null,
      };
    case "FETCH_ERROR":
      return {
        ...state,
        status: "error",
        error: action.payload.error ?? null,
        serviceUnavailable: action.payload.serviceUnavailable ?? false,
      };
    default:
      return state;
  }
}

// ---------------------------------------------------------------------------
// Validation helper (mirrors backend rules)
// ---------------------------------------------------------------------------

function isValidUrl(url) {
  return /^https?:\/\/.+/.test(url) && url.length <= 2048;
}

// ---------------------------------------------------------------------------
// Component
// ---------------------------------------------------------------------------

export default function Home() {
  const [state, dispatch] = useReducer(reducer, INITIAL);
  const abortRef = useRef(null);

  // Cancel any in-flight request on unmount
  useEffect(() => () => abortRef.current?.abort(), []);

  const canSubmit =
    state.status !== "loading" &&
    state.selectedFields.length > 0 &&
    isValidUrl(state.url);

  async function handleExtract(e) {
    e.preventDefault();
    if (!canSubmit) return;

    // Cancel previous in-flight request if still running
    abortRef.current?.abort();
    const controller = new AbortController();
    abortRef.current = controller;

    dispatch({ type: "FETCH_START" });

    try {
      const json = await extractData(state.url, state.selectedFields, controller.signal);

      if (!json.success) {
        dispatch({ type: "FETCH_ERROR", payload: { error: json.error } });
      } else {
        dispatch({ type: "FETCH_SUCCESS", payload: json });
      }
    } catch (err) {
      if (err.name === "AbortError") return; // intentional cancel — stay in loading
      dispatch({
        type: "FETCH_ERROR",
        payload: { serviceUnavailable: true },
      });
    }
  }

  return (
    <main className="min-h-screen bg-gray-50 py-10 px-4">
      <div className="max-w-2xl mx-auto space-y-6">
        <h1 className="text-2xl font-semibold text-gray-800">Universal Web Data Extractor</h1>

        <form onSubmit={handleExtract} className="bg-white rounded-lg shadow p-6 space-y-5" noValidate>
          <UrlInput
            value={state.url}
            onChange={(v) => dispatch({ type: "SET_URL", payload: v })}
            disabled={state.status === "loading"}
          />

          <ExtractionOptions
            selected={state.selectedFields}
            onChange={(v) => dispatch({ type: "SET_FIELDS", payload: v })}
          />

          <button
            type="submit"
            disabled={!canSubmit}
            className="w-full rounded-md bg-blue-600 px-4 py-2 text-sm font-medium text-white hover:bg-blue-700 focus:outline-none focus:ring-2 focus:ring-blue-500 disabled:opacity-50 disabled:cursor-not-allowed"
          >
            {state.status === "loading" ? "Extracting…" : "Extract Data"}
          </button>
        </form>

        {state.status === "loading" && <LoadingState />}

        {state.status === "error" && (
          <ErrorMessage
            error={state.error}
            isServiceUnavailable={state.serviceUnavailable}
          />
        )}

        {state.status === "success" && state.warnings.length > 0 && (
          <div className="rounded-md bg-yellow-50 border border-yellow-200 p-3 text-xs text-yellow-800 space-y-1">
            {state.warnings.map((w, i) => <p key={i}>{w}</p>)}
          </div>
        )}

        {state.status === "success" && (
          <p className="text-sm text-gray-500">{state.data.length} records extracted.</p>
        )}
      </div>
    </main>
  );
}
