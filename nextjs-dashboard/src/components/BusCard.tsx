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
  // busIdx: float 0…nSegs — 0 = Station 1 end, nSegs = Station N end
  const busIdx =
    direction === "FORWARD" ? progress * nSegs : nSegs * (1 - progress);
  const filledPct = (busIdx / nSegs) * 100;

  return (
    <div className="relative w-full" style={{ height: 58 }}>
      {/* Base line */}
      <div
        className="absolute left-0 right-0 h-px bg-slate-600"
        style={{ top: 6 }}
      />
      {/* Filled (travelled) line */}
      <div
        className="absolute h-px bg-sky-400 transition-all duration-700"
        style={{ top: 6, left: 0, width: `${filledPct}%` }}
      />
      {/* Bus emoji indicator */}
      <div
        className="absolute text-sm leading-none transition-all duration-700"
        style={{ top: -10, left: `${filledPct}%`, transform: "translateX(-50%)" }}
      >
        🚌
      </div>

      {/* Station dots + labels */}
      {stations.map((name, i) => {
        const pct = (i / nSegs) * 100;
        // Station is "reached" if bus has passed or is at it
        const reached =
          direction === "FORWARD" ? i <= busIdx + 0.05 : i >= busIdx - 0.05;
        const isCurrent = atStop && currentStop === name;

        return (
          <div
            key={name}
            className="absolute flex flex-col items-center"
            style={{ left: `${pct}%`, top: 0, transform: "translateX(-50%)" }}
          >
            {/* Dot */}
            <div
              className={`w-3 h-3 rounded-full border-2 transition-all ${
                isCurrent
                  ? "bg-amber-400 border-amber-300 ring-2 ring-amber-400/40"
                  : reached
                  ? "bg-sky-400 border-sky-400"
                  : "bg-slate-800 border-slate-500"
              }`}
            />
            {/* Label */}
            <span
              className={`text-center leading-tight mt-2 ${
                isCurrent ? "text-amber-400 font-semibold" : "text-slate-500"
              }`}
              style={{ fontSize: 9, maxWidth: 46, wordBreak: "break-word" }}
            >
              {name}
            </span>
          </div>
        );
      })}
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
