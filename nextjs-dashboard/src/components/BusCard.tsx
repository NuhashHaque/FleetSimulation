"use client";

import type { BusTelemetry } from "./Dashboard";

// ── Status appearance map ─────────────────────────────────────────────────────
const STATUS_STYLES: Record<string, { dot: string; badge: string; label: string }> = {
  IDLE:    { dot: "bg-amber-400",   badge: "bg-amber-400/10 text-amber-400 border-amber-400/30",  label: "IDLE"    },
  RUNNING: { dot: "bg-emerald-400 animate-pulse", badge: "bg-emerald-400/10 text-emerald-400 border-emerald-400/30", label: "RUNNING" },
  PAUSED:  { dot: "bg-red-400",     badge: "bg-red-400/10 text-red-400 border-red-400/30",       label: "PAUSED"  },
};

interface Props {
  data: BusTelemetry;
  routeLabel: string;
  onCommand: (action: "START" | "PAUSE" | "STOP") => void;
}

// ── Progress bar ──────────────────────────────────────────────────────────────
function ProgressBar({ value, label, color }: { value: number; label: string; color: string }) {
  const pct = Math.round(value * 100);
  return (
    <div className="space-y-1">
      <div className="flex justify-between text-xs text-slate-400">
        <span>{label}</span>
        <span>{pct}%</span>
      </div>
      <div className="h-2 w-full overflow-hidden rounded-full bg-slate-700">
        <div
          className={`h-full rounded-full transition-all duration-700 ${color}`}
          style={{ width: `${pct}%` }}
        />
      </div>
    </div>
  );
}

// ── Bus card ──────────────────────────────────────────────────────────────────
export default function BusCard({ data, routeLabel, onCommand }: Props) {
  const st = STATUS_STYLES[data.status] ?? STATUS_STYLES.IDLE;
  const isRunning = data.status === "RUNNING";
  const isPaused  = data.status === "PAUSED";
  const isIdle    = data.status === "IDLE";

  return (
    <div className="rounded-2xl border border-slate-700 bg-slate-800/60 p-5 backdrop-blur-sm shadow-xl space-y-4">

      {/* ── Header row ── */}
      <div className="flex items-start justify-between">
        <div>
          <h2 className="text-xl font-bold text-white">{data.bus_id}</h2>
          <p className="text-xs text-slate-400 mt-0.5">{routeLabel}</p>
        </div>
        <span className={`flex items-center gap-1.5 rounded-full border px-3 py-0.5 text-xs font-semibold ${st.badge}`}>
          <span className={`h-1.5 w-1.5 rounded-full ${st.dot}`} />
          {st.label}
        </span>
      </div>

      {/* ── Metrics ── */}
      <div className="grid grid-cols-3 gap-3 text-center">
        <Metric label="Speed" value={`${data.speed.toFixed(1)} km/h`} />
        <Metric label="Direction" value={data.direction === "FORWARD" ? "➡️ FWD" : "⬅️ RET"} />
        <Metric label="Trips ✓" value={String(data.trip_count)} />
      </div>

      {/* ── GPS ── */}
      <p className="text-xs text-slate-500">
        📍 lat <span className="text-slate-300">{data.pos.lat.toFixed(5)}</span>
        &nbsp; lon <span className="text-slate-300">{data.pos.lon.toFixed(5)}</span>
      </p>

      {/* ── Progress bars ── */}
      <div className="space-y-2">
        <ProgressBar
          label="➡️  FORWARD  (St.1 → St.5)"
          value={data.direction === "FORWARD" ? data.progress : 0}
          color="bg-sky-400"
        />
        <ProgressBar
          label="⬅️  RETURN   (St.5 → St.1)"
          value={data.direction === "RETURN" ? data.progress : 0}
          color="bg-violet-400"
        />
      </div>

      {/* ── Control buttons ── */}
      <div className="grid grid-cols-3 gap-2 pt-1">
        <button
          onClick={() => onCommand("START")}
          disabled={isRunning}
          className={`rounded-lg py-2 text-sm font-semibold transition-all
            ${isIdle || isPaused
              ? "bg-emerald-500 hover:bg-emerald-400 text-white"
              : "cursor-not-allowed bg-slate-700 text-slate-500"}`}
        >
          ▶ Start
        </button>
        <button
          onClick={() => onCommand("PAUSE")}
          disabled={!isRunning}
          className={`rounded-lg py-2 text-sm font-semibold transition-all
            ${isRunning
              ? "bg-amber-500 hover:bg-amber-400 text-white"
              : "cursor-not-allowed bg-slate-700 text-slate-500"}`}
        >
          ⏸ Pause
        </button>
        <button
          onClick={() => onCommand("STOP")}
          disabled={isIdle}
          className={`rounded-lg py-2 text-sm font-semibold transition-all
            ${!isIdle
              ? "bg-red-500 hover:bg-red-400 text-white"
              : "cursor-not-allowed bg-slate-700 text-slate-500"}`}
        >
          ⏹ Stop
        </button>
      </div>
    </div>
  );
}

// ── Small metric block ────────────────────────────────────────────────────────
function Metric({ label, value }: { label: string; value: string }) {
  return (
    <div className="rounded-xl bg-slate-900/60 px-2 py-2">
      <p className="text-[10px] uppercase tracking-wider text-slate-500">{label}</p>
      <p className="mt-0.5 text-sm font-semibold text-white">{value}</p>
    </div>
  );
}
