import { useEffect, useState } from "react";
import { getHistory } from "../services/api";

export default function HistoryPanel({ onReload }) {
  const [jobs, setJobs] = useState([]);

  useEffect(() => {
    getHistory(50).then((d) => setJobs(d.jobs ?? [])).catch(() => {});
  }, [onReload]);

  if (!jobs.length) return (
    <p className="text-sm text-gray-400">No scraping history yet.</p>
  );

  return (
    <section aria-label="Scraping history">
      <h2 className="text-sm font-semibold text-gray-600 uppercase tracking-wide mb-3">Recent Jobs</h2>
      <div className="overflow-x-auto rounded-lg border border-gray-200 shadow-sm">
        <table className="min-w-full divide-y divide-gray-200 text-left text-sm">
          <thead className="bg-gray-50">
            <tr>
              {["URL", "Records", "Duration", "JS", "Date"].map((h) => (
                <th key={h} scope="col" className="px-3 py-2 text-xs font-semibold text-gray-500 uppercase tracking-wide">
                  {h}
                </th>
              ))}
            </tr>
          </thead>
          <tbody className="divide-y divide-gray-100 bg-white">
            {jobs.map((job) => (
              <tr key={job.id} className="hover:bg-gray-50">
                <td className="px-3 py-2 max-w-xs truncate text-gray-700" title={job.url}>{job.url}</td>
                <td className="px-3 py-2 text-gray-600 tabular-nums">{job.record_count}</td>
                <td className="px-3 py-2 text-gray-500 tabular-nums">{job.duration_ms} ms</td>
                <td className="px-3 py-2 text-gray-500">{job.used_js ? "✓" : "—"}</td>
                <td className="px-3 py-2 text-gray-400 whitespace-nowrap">
                  {new Date(job.created_at * 1000).toLocaleString()}
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    </section>
  );
}
