import { useEffect, useState } from "react";
import { getDashboard } from "../services/api";

function StatCard({ label, value }) {
  return (
    <div className="bg-white rounded-lg border border-gray-200 shadow-sm p-4 text-center">
      <p className="text-2xl font-semibold text-gray-800">{value}</p>
      <p className="text-xs text-gray-500 mt-1">{label}</p>
    </div>
  );
}

export default function Dashboard() {
  const [stats, setStats] = useState(null);

  useEffect(() => {
    getDashboard().then(setStats).catch(() => {});
  }, []);

  if (!stats) return null;

  const typeEntries = Object.entries(stats.records_by_type ?? {}).sort((a, b) => b[1] - a[1]);

  return (
    <section aria-label="Dashboard stats" className="space-y-4">
      <h2 className="text-sm font-semibold text-gray-600 uppercase tracking-wide">Dashboard</h2>

      <div className="grid grid-cols-2 gap-3 sm:grid-cols-4">
        <StatCard label="Total jobs" value={stats.total_jobs} />
        <StatCard label="Total records" value={stats.total_records.toLocaleString()} />
        <StatCard label="Avg duration" value={`${stats.avg_duration_ms} ms`} />
        <StatCard label="Record types" value={typeEntries.length} />
      </div>

      {typeEntries.length > 0 && (
        <div className="bg-white rounded-lg border border-gray-200 shadow-sm p-4">
          <p className="text-xs font-medium text-gray-500 mb-3">Records by type</p>
          <div className="space-y-2">
            {typeEntries.map(([type, count]) => {
              const pct = stats.total_records > 0 ? Math.round((count / stats.total_records) * 100) : 0;
              return (
                <div key={type} className="flex items-center gap-3 text-sm">
                  <span className="w-28 text-gray-600 truncate">{type}</span>
                  <div className="flex-1 bg-gray-100 rounded-full h-2">
                    <div className="bg-blue-500 h-2 rounded-full" style={{ width: `${pct}%` }} />
                  </div>
                  <span className="w-10 text-right text-gray-500 tabular-nums">{count}</span>
                </div>
              );
            })}
          </div>
        </div>
      )}
    </section>
  );
}
