
const API_BASE = import.meta.env.VITE_AGENT_URL || "http://127.0.0.1:8765";
const AGENT_TOKEN = import.meta.env.VITE_AGENT_TOKEN || "";

export type ApiDevice = {
  id: string;
  name: string;
  assigned_user: string;
  user_email: string;
  organisation: string;
  hostname: string;
  os_name: string;
  agent_version: string;
  state: "Online" | "Offline";
  last_seen: string | null;
  created_at: string;
  metrics: {
    cpu_percent?: number | null;
    cpu_model?: string;
    ram_percent?: number | null;
    ram_total_gb?: number | null;
    ram_used_mb?: number | null;
    disk_percent?: number | null;
    disk_total_gb?: number | null;
    disk_used_gb?: number | null;
    battery_percent?: number | null;
    uptime_seconds?: number | null;
    ip_address?: string;
    serial?: string;
    processes?: Array<{
      pid?: number;
      name: string;
      cpu_percent?: number;
      memory_percent?: number;
      memory_mb?: number;
    }>;
  };
};

async function api<T>(path: string): Promise<T> {
  const response = await fetch(`${API_BASE}${path}`, {
    method: "GET",
    headers: {
      "Accept": "application/json",
      ...(AGENT_TOKEN
        ? { Authorization: `Bearer ${AGENT_TOKEN}` }
        : {}),
    },
  });

  if (!response.ok) {
    throw new Error(
      `Agent request failed (${response.status}). Is CloudMonitor running?`
    );
  }

  return response.json();
}

export async function checkAgentConnection() {
  return api<{ status: string; agent: string }>("/health");
}

export async function fetchDevices(): Promise<ApiDevice[]> {
  const result = await api<{ devices: ApiDevice[] }>("/api/v1/devices");
  return result.devices;
}

export async function fetchDevice(id: string) {
  return api<ApiDevice>(
    `/api/v1/devices/${encodeURIComponent(id)}`
  );
}

// Kept for compatibility with your existing App.tsx.
export function setApiToken(_token: string) {
  // Authentication is now handled by the local agent.
}

export function getApiToken() {
  return AGENT_TOKEN;
}

export function toFrontendDevice(d: ApiDevice) {
  const m = d.metrics || {};

  const lastSeen = d.last_seen
    ? new Date(d.last_seen).toLocaleString()
    : "Not connected";

  const uptime =
    m.uptime_seconds == null
      ? "Unknown"
      : `${Math.floor(m.uptime_seconds / 86400)}d ${
          Math.floor((m.uptime_seconds % 86400) / 3600)
        }h`;

  return {
    id: d.id,
    name: d.name || d.hostname,
    user: d.assigned_user || "Unassigned",
    email: d.user_email || "—",
    organisation: d.organisation || "Local Device",
    os: d.os_name || "Unknown",
    cpuModel: m.cpu_model || "Not reported",
    cpu: m.cpu_percent ?? 0,
    ram: m.ram_percent ?? 0,
    ramTotal: m.ram_total_gb ?? 0,
    disk: m.disk_percent ?? 0,
    diskTotal: m.disk_total_gb ?? 0,
    battery: m.battery_percent ?? null,
    state: d.state,
    ticketCount: 0,
    ticketState: "None" as const,
    lastSeen,
    ip: m.ip_address || "Not reported",
    serial: m.serial || "Not reported",
    uptime,
    processes: (m.processes || []).map(p => ({
      name: p.name,
      pid: p.pid || 0,
      cpu: p.cpu_percent || 0,
      memory: p.memory_mb || 0,
      category: "Process",
    })),
  };
}
