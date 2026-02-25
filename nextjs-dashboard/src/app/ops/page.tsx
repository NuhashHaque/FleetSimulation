"use client";

import { useEffect, useMemo, useState } from "react";

type TelemetryItem = {
  event_time: string;
  bus_id: string;
  telemetry_id: string;
  status: string;
  speed: number;
  direction: string;
  progress: number;
  full_trips: number;
  next_stop: string | null;
};

type EventItem = {
  event_time: string;
  bus_id: string;
  event_type: string;
  telemetry_id: string;
  from_status: string | null;
  to_status: string | null;
  trip_count: number | null;
};

const BUS_OPTIONS = ["", "BUS_01", "BUS_02", "BUS_03", "BUS_04"];

export default function OpsPage() {
  const [busId, setBusId] = useState("");
  const [telemetry, setTelemetry] = useState<TelemetryItem[]>([]);
  const [events, setEvents] = useState<EventItem[]>([]);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const telemetryUrl = useMemo(() => {
    if (busId) {
      return `/api/ops/telemetry/history?bus_id=${encodeURIComponent(busId)}&limit=20`;
    }
    return "/api/ops/telemetry/latest?limit=4";
  }, [busId]);

  const eventsUrl = useMemo(() => {
    if (busId) {
      return `/api/ops/events?bus_id=${encodeURIComponent(busId)}&limit=30`;
    }
    return "/api/ops/events?limit=30";
  }, [busId]);

  const loadData = async () => {
    setLoading(true);
    setError(null);
    try {
      const [tRes, eRes] = await Promise.all([fetch(telemetryUrl), fetch(eventsUrl)]);
      if (!tRes.ok || !eRes.ok) {
        throw new Error(`API error: telemetry=${tRes.status} events=${eRes.status}`);
      }
      const tJson = await tRes.json();
      const eJson = await eRes.json();
      setTelemetry(tJson.items || []);
      setEvents(eJson.items || []);
    } catch (e) {
      setError(String(e));
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    loadData();
    const timer = setInterval(loadData, 5000);
    return () => clearInterval(timer);
  }, [telemetryUrl, eventsUrl]);

  return (
    <main className="min-h-screen p-6 text-slate-100">
      <div className="mb-5 flex items-center justify-between gap-4">
        <div>
          <h1 className="text-2xl font-bold">TimescaleDB Monitor</h1>
          <p className="text-sm text-slate-400">Telemetry + Event data (via FastAPI)</p>
        </div>
        <a href="/" className="rounded border border-slate-600 px-3 py-1.5 text-sm hover:bg-slate-800">
          Back to Control Room
        </a>
      </div>

      <div className="mb-4 flex items-center gap-3">
        <label className="text-sm">Bus:</label>
        <select
          className="rounded bg-slate-900 px-3 py-1.5 text-sm border border-slate-700"
          value={busId}
          onChange={(e) => setBusId(e.target.value)}
        >
          {BUS_OPTIONS.map((x) => (
            <option key={x || "all"} value={x}>
              {x || "All"}
            </option>
          ))}
        </select>
        <button
          onClick={loadData}
          className="rounded bg-sky-600 px-3 py-1.5 text-sm hover:bg-sky-500"
          disabled={loading}
        >
          {loading ? "Loading..." : "Refresh"}
        </button>
      </div>

      {error && (
        <div className="mb-4 rounded border border-red-500/50 bg-red-500/10 p-3 text-sm text-red-300">{error}</div>
      )}

      <section className="mb-8">
        <h2 className="mb-2 text-lg font-semibold">Telemetry</h2>
        <div className="overflow-x-auto rounded border border-slate-700">
          <table className="min-w-full text-sm">
            <thead className="bg-slate-800 text-slate-300">
              <tr>
                <th className="px-3 py-2 text-left">Time</th>
                <th className="px-3 py-2 text-left">Bus</th>
                <th className="px-3 py-2 text-left">Status</th>
                <th className="px-3 py-2 text-left">Speed</th>
                <th className="px-3 py-2 text-left">Direction</th>
                <th className="px-3 py-2 text-left">Progress</th>
                <th className="px-3 py-2 text-left">Trips</th>
                <th className="px-3 py-2 text-left">Next Stop</th>
              </tr>
            </thead>
            <tbody>
              {telemetry.map((t) => (
                <tr key={t.telemetry_id} className="border-t border-slate-800">
                  <td className="px-3 py-2">{new Date(t.event_time).toLocaleString()}</td>
                  <td className="px-3 py-2">{t.bus_id}</td>
                  <td className="px-3 py-2">{t.status}</td>
                  <td className="px-3 py-2">{Number(t.speed).toFixed(1)}</td>
                  <td className="px-3 py-2">{t.direction}</td>
                  <td className="px-3 py-2">{(Number(t.progress) * 100).toFixed(1)}%</td>
                  <td className="px-3 py-2">{t.full_trips}</td>
                  <td className="px-3 py-2">{t.next_stop || "-"}</td>
                </tr>
              ))}
              {telemetry.length === 0 && (
                <tr>
                  <td colSpan={8} className="px-3 py-6 text-center text-slate-400">No telemetry rows.</td>
                </tr>
              )}
            </tbody>
          </table>
        </div>
      </section>

      <section>
        <h2 className="mb-2 text-lg font-semibold">Event Feed</h2>
        <div className="overflow-x-auto rounded border border-slate-700">
          <table className="min-w-full text-sm">
            <thead className="bg-slate-800 text-slate-300">
              <tr>
                <th className="px-3 py-2 text-left">Time</th>
                <th className="px-3 py-2 text-left">Bus</th>
                <th className="px-3 py-2 text-left">Type</th>
                <th className="px-3 py-2 text-left">From</th>
                <th className="px-3 py-2 text-left">To</th>
                <th className="px-3 py-2 text-left">Trip Count</th>
              </tr>
            </thead>
            <tbody>
              {events.map((e) => (
                <tr key={`${e.telemetry_id}-${e.event_type}`} className="border-t border-slate-800">
                  <td className="px-3 py-2">{new Date(e.event_time).toLocaleString()}</td>
                  <td className="px-3 py-2">{e.bus_id}</td>
                  <td className="px-3 py-2">{e.event_type}</td>
                  <td className="px-3 py-2">{e.from_status || "-"}</td>
                  <td className="px-3 py-2">{e.to_status || "-"}</td>
                  <td className="px-3 py-2">{e.trip_count ?? "-"}</td>
                </tr>
              ))}
              {events.length === 0 && (
                <tr>
                  <td colSpan={6} className="px-3 py-6 text-center text-slate-400">No event rows.</td>
                </tr>
              )}
            </tbody>
          </table>
        </div>
      </section>
    </main>
  );
}
