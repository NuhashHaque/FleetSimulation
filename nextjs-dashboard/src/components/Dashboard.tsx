"use client";

import { useEffect, useRef, useState } from "react";
import mqtt, { MqttClient } from "mqtt";
import BusCard from "./BusCard";

// ── Types ─────────────────────────────────────────────────────────────────────
export type BusStatus = "IDLE" | "RUNNING" | "PAUSED";
export type Direction = "FORWARD" | "RETURN";

export interface BusTelemetry {
  bus_id: string;
  status: BusStatus;
  pos: { lat: number; lon: number };
  speed: number;
  direction: Direction;
  progress: number;      // 0–1, within the current leg
  full_trips: number;    // increments after each complete FORWARD+RETURN cycle
  at_stop: boolean;      // true while bus is dwelling at a station
  current_stop: string | null;  // station name when at_stop, else null
  next_stop: string;     // name of the next station ahead
}

const BUS_IDS = ["BUS_01", "BUS_02", "BUS_03", "BUS_04"];

const ROUTE_LABELS: Record<string, string> = {
  BUS_01: "Mirpur 10 ↔ Motijheel",
  BUS_02: "Uttara ↔ Gulshan 2",
  BUS_03: "Demra ↔ Sadarghat",
  BUS_04: "Dhanmondi 27 ↔ New Market",
};

const ROUTE_STATIONS: Record<string, string[]> = {
  BUS_01: ["Mirpur 10", "Mirpur 2", "Shyamoli", "Farmgate", "Motijheel"],
  BUS_02: ["Uttara", "Airport", "Banani", "Gulshan 1", "Gulshan 2"],
  BUS_03: ["Demra", "Jatrabari", "Postogola", "Sutrapur", "Sadarghat"],
  BUS_04: ["Dhanmondi 27", "Dhanmondi 15", "Science Lab", "Elephant Rd", "New Market"],
};

const initialState = (): Record<string, BusTelemetry> =>
  Object.fromEntries(
    BUS_IDS.map((id) => [
      id,
      {
        bus_id: id,
        status: "IDLE",
        pos: { lat: 0, lon: 0 },
        speed: 0,
        direction: "FORWARD",
        progress: 0,
        full_trips: 0,
        at_stop: false,
        current_stop: null,
        next_stop: "",
      } as BusTelemetry,
    ])
  );

// ── The broker's WebSocket URL ────────────────────────────────────────────────
// Resolved at runtime in the browser so it works regardless of hostname/port.
// Override via NEXT_PUBLIC_BROKER_WS_URL build arg if needed.
const BROKER_WS =
  (process.env.NEXT_PUBLIC_BROKER_WS_URL as string | undefined) ??
  (typeof window !== "undefined"
    ? `ws://${window.location.hostname}:9002`
    : "ws://localhost:9002");

// ── Dashboard component ───────────────────────────────────────────────────────
export default function Dashboard() {
  const [buses, setBuses] = useState<Record<string, BusTelemetry>>(initialState);
  const [connected, setConnected] = useState(false);
  const clientRef = useRef<MqttClient | null>(null);

  // ── MQTT setup (once on mount) ─────────────────────────────────────────────
  useEffect(() => {
    const client = mqtt.connect(BROKER_WS, {
      clientId: `fleet_nextjs_${Math.random().toString(16).slice(2, 8)}`,
      clean: true,
      reconnectPeriod: 3000,
    });

    clientRef.current = client;

    client.on("connect", () => {
      setConnected(true);
      client.subscribe("fleet/bus/+/telemetry", { qos: 0 });
    });

    client.on("disconnect", () => setConnected(false));
    client.on("offline", () => setConnected(false));
    client.on("error", (err: Error) => console.error("[MQTT]", err));

    client.on("message", (_topic: string, payload: Uint8Array) => {
      try {
        const data: BusTelemetry = JSON.parse(
          typeof payload === "string" ? payload : new TextDecoder().decode(payload)
        );
        if (BUS_IDS.includes(data.bus_id)) {
          setBuses((prev: Record<string, BusTelemetry>) => ({ ...prev, [data.bus_id]: data }));
        }
      } catch {/* ignore malformed packets */}
    });

    return () => {
      client.end(true);
    };
  }, []);

  // ── Command publisher ──────────────────────────────────────────────────────
  const sendCommand = (busId: string, action: "START" | "PAUSE" | "STOP" | "RESTART") => {
    clientRef.current?.publish(
      `fleet/bus/${busId}/command`,
      JSON.stringify({ action }),
      { qos: 1 }
    );
  };

  // ── Render ─────────────────────────────────────────────────────────────────
  return (
    <div className="min-h-screen p-6 font-sans">
      {/* ── Header ── */}
      <div className="mb-6 flex items-center justify-between">
        <div>
          <h1 className="text-3xl font-bold text-white">🚌 Fleet Control Room</h1>
          <p className="mt-1 text-sm text-slate-400">
            Broker: <code className="text-sky-400">{BROKER_WS}</code>
          </p>
        </div>
        <div className="flex items-center gap-3">
          <a href="/ops" className="rounded-md border border-slate-600 px-3 py-1.5 text-xs text-slate-200 hover:bg-slate-800">
            TimescaleDB Monitor
          </a>
          <div className="flex items-center gap-2 rounded-full border border-slate-700 px-4 py-1.5 text-sm">
            <span
              className={`inline-block h-2.5 w-2.5 rounded-full ${
                connected ? "bg-emerald-400 animate-pulse" : "bg-red-500"
              }`}
            />
            <span className={connected ? "text-emerald-400" : "text-red-400"}>
              {connected ? "Connected" : "Disconnected"}
            </span>
          </div>
        </div>
      </div>

      {/* ── Bus grid ── */}
      <div className="grid grid-cols-1 gap-6 md:grid-cols-2">
        {BUS_IDS.map((id) => (
          <BusCard
            key={id}
            data={buses[id]}
            routeLabel={ROUTE_LABELS[id]}
            stations={ROUTE_STATIONS[id]}
            onCommand={(action: "START" | "PAUSE" | "STOP" | "RESTART") => sendCommand(id, action)}
          />
        ))}
      </div>

      {/* ── Footer ── */}
      <p className="mt-8 text-center text-xs text-slate-600">
        Progress = fraction of current leg completed. Trips increment after the full Return leg.
      </p>
    </div>
  );
}
