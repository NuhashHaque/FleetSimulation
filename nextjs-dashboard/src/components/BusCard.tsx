"use client";

import type { BusTelemetry, Direction } from "./Dashboard";

// ── Status appearance map ─────────────────────────────────────────────────────
const STATUS_STYLES: Record<string, { dot: string; badge: string; label: string }> = {
  IDLE:    { dot: "bg-amber-400",   badge: "bg-amber-400/10 text-amber-400 border-amber-400/30",  label: "IDLE"    },
  RUNNING: { dot: "bg-emerald-400 animate-pulse", badge: "bg-emerald-400/10 text-emerald-400 border-emerald-400/30", label: "RUNNING" },
  PAUSED:  { dot: "bg-red-400",     badge: "bg-red-400/10 text-red-400 border-red-400/30",       label: "PAUSED"  },
};

interface Props {
  data: BusTelemetry;
  routeLabel: string;
  stations: string[];
  onCommand: (action: "START" | "PAUSE" | "STOP" | "RESTART") => void;
}

// ── Progress bar ──────────────────────────────────────────────────────────────
function ProgressBar({ value, from, to, color }: { value: number; from: string; to: string; color: string }) {
  const pct = Math.round(value * 100);
  return (
    <div className="space-y-1">
      <div className="flex items-center justify-between gap-1">
        <span className="text-[10px] text-slate-400 truncate max-w-[38%]">{from}</span>
        <span className="text-[10px] text-slate-500 shrink-0">{pct}%</span>
        <span className="text-[10px] text-slate-400 truncate max-w-[38%] text-right">{to}</span>
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

// ── Route Strip ─────────────────────────────────────────────────────────────
interface RouteStripProps {
  stations: string[];
  progress: number;
  direction: Direction;
  atStop: boolean;
  currentStop: string | null;
}

function RouteStrip({ stations, progress, direction, atStop, currentStop }: RouteStripProps) {
  const nSegs = stations.length - 1;
  const busIdx = direction === "FORWARD" ? progress * nSegs : nSegs * (1 - progress);
  const filledPct = (busIdx / nSegs) * 100;

  return (
    <div className="w-full space-y-1">

      {/* ── Track row: bus + line + dots ── */}
      <div className="relative w-full h-6">
        {/* Base track */}
        <div className="absolute inset-x-0 h-px bg-slate-600" style={{ top: "50%" }} />
        {/* Filled segment */}
        <div
          className="absolute h-px bg-sky-400 transition-all duration-700"
          style={{ top: "50%", left: 0, width: `${filledPct}%` }}
        />
        {/* Bus emoji */}
        <div
          className="absolute -translate-x-1/2 transition-all duration-700 select-none"
          style={{ top: 0, left: `${filledPct}%`, fontSize: 14, lineHeight: "14px" }}
        >
          🚌
        </div>
        {/* Dots */}
        {stations.map((name, i) => {
          const pct = (i / nSegs) * 100;
          const reached = direction === "FORWARD" ? i <= busIdx + 0.05 : i >= busIdx - 0.05;
          const isCurrent = atStop && currentStop === name;
          return (
            <div
              key={name}
              className={`absolute w-3 h-3 rounded-full border-2 -translate-x-1/2 -translate-y-1/2 transition-all ${
                isCurrent
                  ? "bg-amber-400 border-amber-300 ring-2 ring-amber-400/40"
                  : reached
                  ? "bg-sky-400 border-sky-400"
                  : "bg-slate-800 border-slate-500"
              }`}
              style={{ left: `${pct}%`, top: "50%" }}
            />
          );
        })}
      </div>

      {/* ── Labels flex row — each label is flex-1 so names fit without overflow ── */}
      <div className="flex w-full">
        {stations.map((name, i) => {
          const isCurrent = atStop && currentStop === name;
          return (
            <div
              key={name}
              className={`flex-1 leading-tight break-words ${
                i === 0 ? "text-left pr-0.5" : i === nSegs ? "text-right pl-0.5" : "text-center px-0.5"
              } ${
                isCurrent ? "text-amber-400 font-bold" : "text-slate-500"
              }`}
              style={{ fontSize: 8.5 }}
            >
              {name}
            </div>
          );
        })}
      </div>

    </div>
  );
}

// ── Bus card ─────────────────────────────────────────────────────────────
export default function BusCard({ data, routeLabel, stations, onCommand }: Props) {
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

      {/* ── AT STOP banner ── */}
      {data.at_stop && data.current_stop && (
        <div className="flex items-center gap-2 rounded-lg bg-amber-400/10 border border-amber-400/30 px-3 py-2">
          <span className="text-amber-400 text-lg">🛍️</span>
          <div>
            <p className="text-xs font-semibold text-amber-400">AT STOP</p>
            <p className="text-sm text-white font-bold">{data.current_stop}</p>
          </div>
        </div>
      )}

      {/* ── Metrics ── */}
      <div className="grid grid-cols-3 gap-3 text-center">
        <Metric label="Speed" value={data.at_stop ? "STOPPED" : `${data.speed.toFixed(1)} km/h`} />
        <Metric label="Direction" value={data.direction === "FORWARD" ? "➡️ FWD" : "⬅️ RET"} />
        <Metric label="Full Trips" value={String(data.full_trips)} />
      </div>

      {/* ── Route strip ── */}
      <RouteStrip
        stations={stations}
        progress={data.progress}
        direction={data.direction}
        atStop={data.at_stop}
        currentStop={data.current_stop}
      />

      {/* ── GPS ── */}
      <p className="text-xs text-slate-500">
        📍 lat <span className="text-slate-300">{data.pos.lat.toFixed(5)}</span>
        &nbsp; lon <span className="text-slate-300">{data.pos.lon.toFixed(5)}</span>
      </p>

      {/* ── Progress bars ── */}
      <div className="space-y-2">
        <ProgressBar
          from={stations[0]}
          to={stations[stations.length - 1]}
          value={data.direction === "FORWARD" ? data.progress : 0}
          color="bg-sky-400"
        />
        <ProgressBar
          from={stations[stations.length - 1]}
          to={stations[0]}
          value={data.direction === "RETURN" ? data.progress : 0}
          color="bg-violet-400"
        />
      </div>

      {/* ── Control buttons ── */}
      <div className="grid grid-cols-4 gap-2 pt-1">
        <button
          onClick={() => onCommand("START")}
          disabled={isRunning}
          className={`rounded-lg py-2 text-xs font-semibold transition-all
            ${isIdle || isPaused
              ? "bg-emerald-500 hover:bg-emerald-400 text-white"
              : "cursor-not-allowed bg-slate-700 text-slate-500"}`}
        >
          ▶ Start
        </button>
        <button
          onClick={() => onCommand("PAUSE")}
          disabled={!isRunning}
          className={`rounded-lg py-2 text-xs font-semibold transition-all
            ${isRunning
              ? "bg-amber-500 hover:bg-amber-400 text-white"
              : "cursor-not-allowed bg-slate-700 text-slate-500"}`}
        >
          ⏸ Pause
        </button>
        <button
          onClick={() => onCommand("STOP")}
          disabled={isIdle}
          className={`rounded-lg py-2 text-xs font-semibold transition-all
            ${!isIdle
              ? "bg-red-500 hover:bg-red-400 text-white"
              : "cursor-not-allowed bg-slate-700 text-slate-500"}`}
        >
          ⏹ Stop
        </button>
        <button
          onClick={() => onCommand("RESTART")}
          className="rounded-lg py-2 text-xs font-semibold transition-all bg-indigo-500 hover:bg-indigo-400 text-white"
        >
          🔄 Restart
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
