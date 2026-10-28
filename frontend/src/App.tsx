
import { useCallback, useEffect, useState } from "react";
import {
  Area, AreaChart, CartesianGrid, ResponsiveContainer,
  Tooltip, XAxis, YAxis,
} from "recharts";
import "./App.css";

const API = import.meta.env.VITE_API_URL || "http://127.0.0.1:8000";

type Metric = {
  timestamp: string;
  cpu_percent: number;
  ram_percent: number;
  disk_percent: number;
  cpu_temp_c: number | null;
  battery_percent: number | null;
  top_processes: {
    pid: number;
    name: string;
    cpu_percent: number;
    memory_percent: number;
  }[];
};

type Device = {
  id: string;
  hostname: string;
  os_version: string;
  cpu_model: string;
  cpu_count: number;
  total_ram_mb: number;
  online: boolean;
  last_seen: string | null;
  latest: Metric | null;
};

type Alert = {
  id: number;
  hostname: string;
  kind: string;
  message: string;
  created_at: string;
};

export default function App() {
  const [token, setToken] = useState(
    () => sessionStorage.getItem("admin_token") || ""
  );
  const [username, setUsername] = useState("admin");
  const [password, setPassword] = useState("");
  const [devices, setDevices] = useState<Device[]>([]);
  const [alerts, setAlerts] = useState<Alert[]>([]);
  const [selected, setSelected] = useState("");
  const [history, setHistory] = useState<Metric[]>([]);
  const [code, setCode] = useState("");
  const [error, setError] = useState("");
  const [busy, setBusy] = useState(false);

  const api = useCallback(async <T,>(
    path: string,
    init: RequestInit = {},
  ): Promise<T> => {
    const response = await fetch(`${API}${path}`, {
      ...init,
      headers: {
        ...(init.body ? { "Content-Type": "application/json" } : {}),
        ...(token ? { Authorization: `Bearer ${token}` } : {}),
        ...init.headers,
      },
    });

    if (response.status === 401) {
      sessionStorage.removeItem("admin_token");
      setToken("");
      throw new Error("Session expired. Please sign in again.");
    }

    if (!response.ok) {
      const data = await response.json().catch(() => ({}));
      throw new Error(data.detail || `Request failed: ${response.status}`);
    }

    return response.json() as Promise<T>;
  }, [token]);

  async function login(event: React.FormEvent) {
    event.preventDefault();
    setBusy(true);
    setError("");

    try {
      const response = await fetch(`${API}/auth/login`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ username, password }),
      });
      const data = await response.json();

      if (!response.ok) {
        throw new Error(data.detail || "Login failed");
      }

      sessionStorage.setItem("admin_token", data.access_token);
      setToken(data.access_token);
      setPassword("");
    } catch (e) {
      setError(e instanceof Error ? e.message : "Login failed");
    } finally {
      setBusy(false);
    }
  }

  const refresh = useCallback(async () => {
    try {
      const [nextDevices, nextAlerts] = await Promise.all([
        api<Device[]>("/devices"),
        api<Alert[]>("/alerts"),
      ]);
      setDevices(nextDevices);
      setAlerts(nextAlerts);
      setSelected((current) =>
        current && nextDevices.some((d) => d.id === current)
          ? current
          : nextDevices[0]?.id || ""
      );
      setError("");
    } catch (e) {
      setError(e instanceof Error ? e.message : "Unable to load dashboard");
    }
  }, [api]);

  useEffect(() => {
    if (!token) return;
    void refresh();
    const timer = window.setInterval(() => void refresh(), 15000);
    return () => window.clearInterval(timer);
  }, [token, refresh]);

  useEffect(() => {
    if (!token || !selected) {
      setHistory([]);
      return;
    }

    let cancelled = false;

    const load = async () => {
      try {
        const result = await api<Metric[]>(
          `/devices/${selected}/metrics?limit=60`
        );
        if (!cancelled) setHistory(result);
      } catch (e) {
        if (!cancelled) {
          setError(e instanceof Error ? e.message : "Unable to load metrics");
        }
      }
    };

    void load();
    const timer = window.setInterval(() => void load(), 15000);

    return () => {
      cancelled = true;
      window.clearInterval(timer);
    };
  }, [api, token, selected]);

  async function generateCode() {
    setError("");
    try {
      const result = await api<{ code: string; expires_in_minutes: number }>(
        "/admin/enrollment-codes",
        { method: "POST" }
      );
      setCode(result.code);
    } catch (e) {
      setError(e instanceof Error ? e.message : "Could not create code");
    }
  }

  if (!token) {
    return (
      <main className="login">
        <form className="login-card" onSubmit={login}>
          <span className="brand">HD</span>
          <p className="eyebrow">ENDPOINT MANAGEMENT</p>
          <h1>HelpdeskOps</h1>
          <p className="muted">Sign in to your monitoring dashboard.</p>

          <label>Username
            <input
              value={username}
              onChange={(e) => setUsername(e.target.value)}
              required
            />
          </label>
          <label>Password
            <input
              type="password"
              value={password}
              onChange={(e) => setPassword(e.target.value)}
              required
            />
          </label>

          {error && <p className="error">{error}</p>}
          <button disabled={busy}>
            {busy ? "Signing in…" : "Sign in"}
          </button>
        </form>
      </main>
    );
  }

  const device = devices.find((d) => d.id === selected);
  const latest = device?.latest;
  const chartData = history.map((m) => ({
    ...m,
    time: new Date(m.timestamp).toLocaleTimeString(),
  }));

  return (
    <main className="dashboard">
      <header className="header">
        <div>
          <p className="eyebrow">IT OPERATIONS / OVERVIEW</p>
          <h1>Endpoint monitoring</h1>
          <p className="muted">Windows device health and diagnostics</p>
        </div>
        <div className="header-actions">
          <button className="secondary" onClick={() => void refresh()}>
            Refresh
          </button>
          <button onClick={() => {
            sessionStorage.removeItem("admin_token");
            setToken("");
          }}>Sign out</button>
        </div>
      </header>

      {error && <p className="error banner">{error}</p>}

      <section className="stats">
        <Stat label="Registered devices" value={devices.length} />
        <Stat label="Online" value={devices.filter((d) => d.online).length} />
        <Stat label="Offline" value={devices.filter((d) => !d.online).length} />
        <Stat label="Active alerts" value={alerts.length} />
      </section>

      <section className="panel">
        <div className="panel-header">
          <div>
            <h2>Managed computers</h2>
            <p className="muted">Authorized, enrolled devices</p>
          </div>
          <button onClick={() => void generateCode()}>+ Enroll device</button>
        </div>

        {code && (
          <div className="enrollment">
            <strong>One-time enrollment code</strong>
            <code>{code}</code>
            <p className="muted">Valid for 15 minutes. Use only on the intended computer.</p>
            <button className="secondary" onClick={() => {
              void navigator.clipboard.writeText(code);
            }}>Copy code</button>
            <button className="secondary" onClick={() => setCode("")}>Hide</button>
          </div>
        )}

        <div className="table-wrap">
          <table>
            <thead>
              <tr><th>Computer</th><th>Status</th><th>CPU</th><th>RAM</th><th>Disk</th></tr>
            </thead>
            <tbody>
              {devices.map((d) => (
                <tr
                  key={d.id}
                  className={selected === d.id ? "selected" : ""}
                  onClick={() => setSelected(d.id)}
                >
                  <td><strong>{d.hostname}</strong><small>{d.os_version}</small></td>
                  <td><span className={`status ${d.online ? "online" : "offline"}`}>
                    {d.online ? "● Online" : "● Offline"}
                  </span></td>
                  <td>{d.latest ? `${d.latest.cpu_percent.toFixed(1)}%` : "—"}</td>
                  <td>{d.latest ? `${d.latest.ram_percent.toFixed(1)}%` : "—"}</td>
                  <td>{d.latest ? `${d.latest.disk_percent.toFixed(1)}%` : "—"}</td>
                </tr>
              ))}
              {!devices.length && (
                <tr><td colSpan={5} className="empty">
                  No devices yet. Create an enrollment code to get started.
                </td></tr>
              )}
            </tbody>
          </table>
        </div>
      </section>

      <section className="stats">
        <Stat label="CPU usage" value={latest ? `${latest.cpu_percent.toFixed(1)}%` : "—"} />
        <Stat label="RAM usage" value={latest ? `${latest.ram_percent.toFixed(1)}%` : "—"} />
        <Stat label="Temperature" value={latest?.cpu_temp_c != null ? `${latest.cpu_temp_c.toFixed(1)}°C` : "N/A"} />
        <Stat label="Battery" value={latest?.battery_percent != null ? `${latest.battery_percent.toFixed(0)}%` : "N/A"} />
      </section>

      <section className="panel">
        <h2>{device ? `${device.hostname} performance` : "Performance history"}</h2>
        <p className="muted">Latest 60 measurements</p>
        <div className="chart">
          {chartData.length ? (
            <ResponsiveContainer width="100%" height="100%">
              <AreaChart data={chartData}>
                <CartesianGrid strokeDasharray="3 3" />
                <XAxis dataKey="time" minTickGap={35} />
                <YAxis domain={[0, 100]} unit="%" />
                <Tooltip />
                <Area dataKey="cpu_percent" name="CPU" stroke="#635bdb" fill="#dcd9ff" />
                <Area dataKey="ram_percent" name="RAM" stroke="#0e9f6e" fill="#d1fae5" />
              </AreaChart>
            </ResponsiveContainer>
          ) : <p className="empty">Select a device and wait for metrics.</p>}
        </div>
      </section>

      <section className="panel">
        <h2>Top processes</h2>
        <p className="muted">Latest reported CPU usage</p>
        <div className="table-wrap">
          <table>
            <thead><tr><th>Process</th><th>PID</th><th>CPU</th><th>Memory</th></tr></thead>
            <tbody>
              {(latest?.top_processes || []).map((p) => (
                <tr key={`${p.pid}-${p.name}`}>
                  <td>{p.name}</td><td>{p.pid}</td>
                  <td>{p.cpu_percent.toFixed(1)}%</td>
                  <td>{p.memory_percent.toFixed(1)}%</td>
                </tr>
              ))}
              {!latest?.top_processes?.length && (
                <tr><td colSpan={4} className="empty">No process data received yet.</td></tr>
              )}
            </tbody>
          </table>
        </div>
      </section>

      <section className="panel">
        <h2>Active alerts</h2>
        {alerts.length ? alerts.map((a) => (
          <div className="alert" key={a.id}>
            <strong>{a.hostname} · {a.kind.toUpperCase()}</strong>
            <p>{a.message}</p>
            <small>{new Date(a.created_at).toLocaleString()}</small>
          </div>
        )) : <p className="empty">No active alerts.</p>}
      </section>
    </main>
  );
}

function Stat({ label, value }: { label: string; value: string | number }) {
  return <div className="stat">
    <span>{label}</span>
    <strong>{value}</strong>
  </div>;
}
