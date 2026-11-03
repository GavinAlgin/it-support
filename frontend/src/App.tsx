import { useEffect, useMemo, useState } from "react";
import { AnimatePresence, motion } from "framer-motion";
import {
  Activity, AlertCircle, BatteryCharging, Bell, Check, ChevronDown,
  ChevronLeft, ChevronRight, CircleHelp, Clock3, Cpu, Database,
  Ellipsis, HardDrive, LayoutDashboard, Menu, Monitor,
  RefreshCw, Search, Settings, ShieldCheck, Ticket, Users,
  Wifi, WifiOff, X, Zap, MemoryStick, Laptop,
} from "lucide-react";
import "./index.css";

type DeviceState = "Online" | "Offline" | "Maintenance";
type TicketState = "Open" | "In progress" | "None";

type Device = {
  id: string;
  name: string;
  user: string;
  email: string;
  organisation: string;
  os: string;
  cpuModel: string;
  cpu: number;
  ram: number;
  ramTotal: number;
  disk: number;
  diskTotal: number;
  battery: number | null;
  state: DeviceState;
  ticketCount: number;
  ticketState: TicketState;
  lastSeen: string;
  ip: string;
  serial: string;
  uptime: string;
  processes?: ProcessInfo[];
};

type ProcessInfo = {
  name: string;
  pid: number;
  cpu: number;
  memory: number;
  category: string;
};

const fmt = (n: number) => `${n}%`;

function Metric({
  label, value, icon: Icon, detail, color = "text-zinc-900",
}: {
  label: string; value: string | number; icon: typeof Monitor;
  detail: string; color?: string;
}) {
  return (
    <div className="rounded-xl border border-zinc-200 bg-white p-5 shadow-sm transition hover:-translate-y-0.5 hover:shadow-md">
      <div className="flex items-center justify-between">
        <p className="text-sm font-medium text-zinc-500">{label}</p>
        <span className="rounded-lg bg-zinc-100 p-2">
          <Icon size={18} className="text-zinc-600" />
        </span>
      </div>
      <p className={`mt-4 text-3xl font-semibold tracking-tight ${color}`}>{value}</p>
      <p className="mt-2 text-xs text-zinc-500">{detail}</p>
    </div>
  );
}

function StateBadge({ state }: { state: DeviceState }) {
  const styles: Record<DeviceState, string> = {
    Online: "bg-emerald-50 text-emerald-700 ring-emerald-600/20",
    Offline: "bg-red-50 text-red-700 ring-red-600/20",
    Maintenance: "bg-amber-50 text-amber-700 ring-amber-600/20",
  };
  return (
    <span className={`inline-flex items-center gap-1.5 whitespace-nowrap rounded-full px-2.5 py-1 text-xs font-medium ring-1 ring-inset ${styles[state]}`}>
      <span className={`h-1.5 w-1.5 rounded-full ${
        state === "Online" ? "bg-emerald-500" :
        state === "Offline" ? "bg-red-500" : "bg-amber-500"
      }`} />
      {state}
    </span>
  );
}

function UsageBar({ value }: { value: number }) {
  const color = value >= 80 ? "bg-red-500" : value >= 65 ? "bg-amber-500" : "bg-blue-600";
  return (
    <div className="flex min-w-24 items-center gap-2">
      <div className="h-1.5 w-16 overflow-hidden rounded-full bg-zinc-100">
        <motion.div
          initial={{ width: 0 }}
          animate={{ width: `${Math.min(value, 100)}%` }}
          transition={{ duration: 0.55 }}
          className={`h-full rounded-full ${color}`}
        />
      </div>
      <span className={`text-xs tabular-nums ${value >= 80 ? "font-semibold text-red-600" : "text-zinc-600"}`}>
        {value}%
      </span>
    </div>
  );
}

function ComputerDetails({ device, onBack }: { device: Device; onBack: () => void }) {
  const processes = device.state === "Online" ? (device.processes ?? []) : [];

  return (
    <motion.div initial={{ opacity: 0, x: 12 }} animate={{ opacity: 1, x: 0 }} className="space-y-6">
      <button onClick={onBack} className="inline-flex items-center gap-2 text-sm font-medium text-zinc-600 hover:text-zinc-950">
        <ChevronLeft size={17} /> Back to computers
      </button>
      <div className="flex flex-col justify-between gap-4 sm:flex-row sm:items-start">
        <div>
          <p className="text-sm text-zinc-500">Computer inventory / {device.id}</p>
          <h1 className="mt-2 text-2xl font-semibold tracking-tight">{device.name}</h1>
          <p className="mt-1 text-sm text-zinc-500">{device.organisation} · {device.user}</p>
        </div>
        <StateBadge state={device.state} />
      </div>

      {device.state !== "Online" && (
        <div className="flex gap-3 rounded-xl border border-amber-200 bg-amber-50 p-4 text-sm text-amber-900">
          <AlertCircle size={20} className="shrink-0" />
          <div><strong>Device telemetry unavailable.</strong> The computer is {device.state.toLowerCase()}. Resource figures and process lists may be stale or unavailable.</div>
        </div>
      )}

      <div className="grid gap-4 sm:grid-cols-2 xl:grid-cols-4">
        <Metric label="CPU usage" value={device.state === "Online" ? fmt(device.cpu) : "—"} icon={Cpu} detail={device.cpuModel} />
        <Metric label="Memory" value={device.state === "Online" && device.ramTotal ? `${device.ram}%` : "—"} icon={MemoryStick} detail={device.ramTotal ? `${Math.round(device.ramTotal * device.ram / 100)} / ${device.ramTotal} GB used` : "No telemetry"} />
        <Metric label="Disk usage" value={device.state === "Online" && device.diskTotal ? `${device.disk}%` : "—"} icon={HardDrive} detail={device.diskTotal ? `${Math.round(device.diskTotal * device.disk / 100)} / ${device.diskTotal} GB used` : "No telemetry"} />
        <Metric label="Battery" value={device.battery === null ? "N/A" : `${device.battery}%`} icon={BatteryCharging} detail={device.battery === null ? "Desktop or unavailable" : "Reported battery level"} />
      </div>

      <section className="overflow-hidden rounded-xl border border-zinc-200 bg-white shadow-sm">
        <div className="flex flex-col gap-2 border-b border-zinc-200 p-5 sm:flex-row sm:items-center sm:justify-between">
          <div>
            <h2 className="font-semibold">Task Manager</h2>
            <p className="mt-1 text-sm text-zinc-500">Applications and processes using computer resources</p>
          </div>
          <span className="text-xs text-zinc-500">{processes.length} live processes</span>
        </div>
        <div className="overflow-x-auto">
          <table className="w-full min-w-[620px] text-left text-sm">
            <thead className="bg-zinc-50 text-xs text-zinc-500">
              <tr>
                <th className="px-5 py-3 font-medium">Application / process</th>
                <th className="px-5 py-3 font-medium">PID</th>
                <th className="px-5 py-3 font-medium">CPU</th>
                <th className="px-5 py-3 font-medium">Memory</th>
                <th className="px-5 py-3 font-medium">Category</th>
              </tr>
            </thead>
            <tbody className="divide-y divide-zinc-100">
              {processes.map((p) => (
                <tr key={p.pid} className="hover:bg-zinc-50">
                  <td className="px-5 py-4 font-medium">{p.name}</td>
                  <td className="px-5 py-4 text-zinc-500">{p.pid}</td>
                  <td className="px-5 py-4"><UsageBar value={p.cpu} /></td>
                  <td className="px-5 py-4">{p.memory} MB</td>
                  <td className="px-5 py-4 text-zinc-500">{p.category}</td>
                </tr>
              ))}
              {processes.length === 0 && (
                <tr><td colSpan={5} className="px-5 py-12 text-center text-zinc-500">
                  No process telemetry available while this device is offline.
                </td></tr>
              )}
            </tbody>
          </table>
        </div>
        <div className="border-t border-zinc-100 bg-zinc-50 px-5 py-3 text-xs text-zinc-500">
          Live process information reported by the connected desktop agent.
        </div>
      </section>

      <section className="rounded-xl border border-zinc-200 bg-white p-5 shadow-sm">
        <h2 className="font-semibold">Device information</h2>
        <div className="mt-4 grid gap-5 sm:grid-cols-2 lg:grid-cols-3">
          {[
            ["Device ID", device.id],
            ["Assigned user", device.user],
            ["Email", device.email],
            ["Operating system", device.os],
            ["Serial number", device.serial],
            ["IP address", device.ip],
            ["Last seen", device.lastSeen],
            ["Uptime", device.uptime],
            ["Organisation", device.organisation],
          ].map(([label, value]) => (
            <div key={label}>
              <p className="text-xs text-zinc-500">{label}</p>
              <p className="mt-1 break-words text-sm font-medium">{value}</p>
            </div>
          ))}
        </div>
      </section>

      <section className="rounded-xl border border-zinc-200 bg-white p-5 shadow-sm">
        <div className="flex items-center gap-2">
          <Activity size={19} />
          <h2 className="font-semibold">Activity log</h2>
        </div>
        <div className="mt-4 space-y-4">
          {[
            ["Device record created", "Inventory entry available for administration."],
            [device.state === "Online" ? "Last heartbeat received" : "Device connection lost", `Last reported: ${device.lastSeen}.`],
            [`${device.ticketCount} active ticket${device.ticketCount === 1 ? "" : "s"}`, device.ticketCount ? `Current ticket status: ${device.ticketState}.` : "No active support tickets."],
          ].map(([title, description], i) => (
            <div key={title} className="flex gap-3">
              <span className="mt-1 flex h-7 w-7 shrink-0 items-center justify-center rounded-full bg-zinc-100 text-zinc-600">
                {i === 0 ? <Check size={14} /> : i === 1 ? <Activity size={14} /> : <Ticket size={14} />}
              </span>
              <div>
                <p className="text-sm font-medium">{title}</p>
                <p className="mt-1 text-xs text-zinc-500">{description}</p>
              </div>
            </div>
          ))}
        </div>
      </section>
    </motion.div>
  );
}

export default function App() {
  const [devices, setDevices] = useState<Device[]>([]);
  const [agentUrl, setAgentUrl] = useState(() => localStorage.getItem("cloudmonitor.agentUrl") || "http://127.0.0.1:8765");
  const [agentToken, setAgentToken] = useState(() => localStorage.getItem("cloudmonitor.agentToken") || "");
  const [agentStatus, setAgentStatus] = useState<"Disconnected" | "Connecting" | "Connected" | "Error">("Disconnected");
  const [agentError, setAgentError] = useState("");
  const [lastSync, setLastSync] = useState("");
  const [agentDisplayName, setAgentDisplayName] = useState("");
  const [agentAssignedUser, setAgentAssignedUser] = useState("");
  const [agentUserEmail, setAgentUserEmail] = useState("");
  const [agentOrganisation, setAgentOrganisation] = useState("");
  const [query, setQuery] = useState("");
  const [stateFilter, setStateFilter] = useState("All states");
  const [ticketFilter, setTicketFilter] = useState("All tickets");
  const [activeMenu, setActiveMenu] = useState<string | null>(null);
  const [selected, setSelected] = useState<Device | null>(null);
  const [notice, setNotice] = useState("");
  const [section, setSection] = useState("Computers");
  const [mobileNav, setMobileNav] = useState(false);

  async function fetchAgentDevice() {
    if (!agentToken.trim()) {
      setAgentStatus("Disconnected");
      return;
    }
    setAgentStatus("Connecting");
    try {
      const response = await fetch(`${agentUrl.replace(/\/$/, "")}/api/v1/device`, {
        headers: { Authorization: `Bearer ${agentToken.trim()}` },
        cache: "no-store",
      });
      if (!response.ok) throw new Error(response.status === 401 ? "Invalid agent token." : `Agent returned ${response.status}.`);
      const raw = await response.json();
      const ramTotal = Number(raw.ram_total_gb || 0);
      const diskTotal = Number(raw.disk_total_gb || 0);
      const device: Device = {
        id: String(raw.id),
        name: raw.display_name || raw.hostname || "Connected computer",
        user: raw.assigned_user || "Unassigned",
        email: raw.user_email || "—",
        organisation: raw.organisation || "Unassigned organisation",
        os: raw.os_name || "Unknown OS",
        cpuModel: raw.cpu_model || "Unknown processor",
        cpu: Number(raw.cpu_percent || 0),
        ram: Number(raw.ram_percent || 0),
        ramTotal,
        disk: Number(raw.disk_percent || 0),
        diskTotal,
        battery: raw.battery_percent == null ? null : Number(raw.battery_percent),
        state: raw.monitoring_enabled ? "Online" : "Maintenance",
        ticketCount: 0,
        ticketState: "None",
        lastSeen: raw.last_seen ? new Date(raw.last_seen).toLocaleTimeString() : "Just now",
        ip: raw.ip_address || "Unknown",
        serial: raw.serial || "Not provided",
        uptime: `${Math.floor(Number(raw.uptime_seconds || 0) / 86400)}d ${Math.floor((Number(raw.uptime_seconds || 0) % 86400) / 3600)}h`,
        processes: Array.isArray(raw.processes) ? raw.processes.map((p: any) => ({
          name: p.name || "Unknown",
          pid: Number(p.pid || 0),
          cpu: Number(p.cpu_percent || 0),
          memory: Number(p.memory_mb || 0),
          category: p.category || "Process",
        })) : [],
      };
      setDevices(currentDevices => {
        const previous = currentDevices.find(d => d.id === device.id);
        const updated = {
          ...device,
          ticketCount: previous?.ticketCount ?? 0,
          ticketState: previous?.ticketState ?? "None" as TicketState,
        };
        setSelected(current => current?.id === updated.id ? updated : current);
        return [updated];
      });
      setAgentStatus("Connected");
      setAgentError("");
      setLastSync(new Date().toLocaleTimeString());
    } catch (error) {
      setAgentStatus("Error");
      setAgentError(error instanceof Error ? error.message : "Could not connect to desktop agent.");
      setDevices(current => current.map(d => ({ ...d, state: "Offline" })));
    }
  }

  async function sendAgentCommand(command: "pause" | "resume" | "refresh") {
    if (!agentToken.trim()) {
      notify("Connect to the desktop agent first.");
      return;
    }
    try {
      const response = await fetch(`${agentUrl.replace(/\/$/, "")}/api/v1/commands`, {
        method: "POST",
        headers: {
          Authorization: `Bearer ${agentToken.trim()}`,
          "Content-Type": "application/json",
        },
        body: JSON.stringify({ command }),
      });
      const result = await response.json();
      if (!response.ok) throw new Error(result.detail || "Command failed.");
      await fetchAgentDevice();
      notify(`Agent command "${command}" sent successfully.`);
    } catch (error) {
      notify(error instanceof Error ? error.message : "Could not send command.");
    }
  }

  async function sendAgentMetadata() {
    if (!agentToken.trim()) {
      notify("Connect to the desktop agent first.");
      return;
    }
    try {
      const response = await fetch(`${agentUrl.replace(/\/$/, "")}/api/v1/commands`, {
        method: "POST",
        headers: { Authorization: `Bearer ${agentToken.trim()}`, "Content-Type": "application/json" },
        body: JSON.stringify({
          command: "metadata",
          display_name: agentDisplayName,
          assigned_user: agentAssignedUser,
          user_email: agentUserEmail,
          organisation: agentOrganisation,
        }),
      });
      const result = await response.json();
      if (!response.ok) throw new Error(result.detail || "Metadata update failed.");
      await fetchAgentDevice();
      notify("Computer details sent to the desktop agent.");
    } catch (error) {
      notify(error instanceof Error ? error.message : "Could not update agent metadata.");
    }
  }

  useEffect(() => {
    if (!agentToken.trim()) return;
    localStorage.setItem("cloudmonitor.agentUrl", agentUrl);
    localStorage.setItem("cloudmonitor.agentToken", agentToken);
    let active = true;
    const poll = async () => {
      if (!active) return;
      await fetchAgentDevice();
    };
    poll();
    const timer = window.setInterval(poll, 3000);
    return () => {
      active = false;
      window.clearInterval(timer);
    };
  }, [agentUrl, agentToken]);

  const online = devices.filter(d => d.state === "Online").length;
  const offline = devices.filter(d => d.state === "Offline").length;
  const openTickets = devices.reduce((sum, d) => sum + d.ticketCount, 0);
  const alerts = devices.filter(d => d.state === "Online" && (d.cpu >= 80 || d.ram >= 80 || d.disk >= 90)).length;

  const filtered = useMemo(() => devices.filter(d => {
    const text = `${d.id} ${d.name} ${d.user} ${d.organisation} ${d.serial}`.toLowerCase();
    const matchText = text.includes(query.toLowerCase());
    const matchState = stateFilter === "All states" || d.state === stateFilter;
    const matchTicket = ticketFilter === "All tickets" ||
      (ticketFilter === "Has tickets" && d.ticketCount > 0) ||
      (ticketFilter === "No tickets" && d.ticketCount === 0);
    return matchText && matchState && matchTicket;
  }), [devices, query, stateFilter, ticketFilter]);

  function notify(message: string) {
    setNotice(message);
    window.setTimeout(() => setNotice(""), 3000);
  }

  function changeTicket(device: Device) {
    const count = device.ticketCount ? 0 : 1;
    const updated = { ...device, ticketCount: count, ticketState: count ? "Open" as const : "None" as const };
    setDevices(prev => prev.map(d => d.id === device.id ? updated : d));
    if (selected?.id === device.id) setSelected(updated);
    setActiveMenu(null);
    notify(count ? "Ticket created locally" : "Tickets cleared locally");
  }

  const navItems = [
    { name: "Overview", icon: LayoutDashboard },
    { name: "Computers", icon: Monitor },
    { name: "Tickets", icon: Ticket },
    { name: "Users", icon: Users },
    { name: "Settings", icon: Settings },
  ];

  return (
    <div className="min-h-screen bg-[#fafafa] text-zinc-900">
      <aside className={`fixed inset-y-0 left-0 z-40 flex w-64 flex-col border-r border-zinc-200 bg-white transition-transform duration-200 lg:translate-x-0 ${mobileNav ? "translate-x-0" : "-translate-x-full"}`}>
        <div className="flex h-[72px] items-center gap-3 border-b border-zinc-100 px-5">
          <div className="flex h-10 w-10 items-center justify-center rounded-xl bg-blue-600 text-white">
            <Monitor size={22} />
          </div>
          <div>
            <p className="text-base font-bold tracking-tight">techloom<span className="text-blue-600">/&gt;</span></p>
            <p className="text-[10px] font-semibold tracking-[.16em] text-zinc-500">SERVICE DESK</p>
          </div>
          <button onClick={() => setMobileNav(false)} className="ml-auto rounded-md p-1 text-zinc-500 lg:hidden" aria-label="Close navigation"><X size={18} /></button>
        </div>
        <div className="px-3 py-5">
          <p className="mb-3 px-3 text-[11px] font-semibold uppercase tracking-wider text-zinc-400">Workspace</p>
          <nav className="space-y-1">
            {navItems.map(({ name, icon: Icon }) => (
              <button key={name} onClick={() => {
                setSection(name); setSelected(null); setMobileNav(false);
              }} className={`flex w-full items-center gap-3 rounded-lg px-3 py-2.5 text-sm font-medium transition ${section === name && !selected ? "bg-blue-50 text-blue-700" : "text-zinc-600 hover:bg-zinc-50 hover:text-zinc-950"}`}>
                <Icon size={18} />{name}
                {name === "Tickets" && openTickets > 0 && <span className="ml-auto rounded-full bg-zinc-100 px-2 py-0.5 text-xs text-zinc-600">{openTickets}</span>}
              </button>
            ))}
          </nav>
        </div>
        <div className="mt-auto border-t border-zinc-100 p-4">
          <div className="flex items-center gap-3 rounded-xl bg-zinc-50 p-3">
            <div className="flex h-9 w-9 items-center justify-center rounded-full bg-blue-100 text-sm font-semibold text-blue-700">TA</div>
            <div className="min-w-0 flex-1">
              <p className="truncate text-sm font-semibold">Techloom Admin</p>
              <p className="truncate text-xs text-zinc-500">Administrator</p>
            </div>
            <Ellipsis size={18} className="text-zinc-400" />
          </div>
        </div>
      </aside>

      {mobileNav && <button aria-label="Close navigation overlay" onClick={() => setMobileNav(false)} className="fixed inset-0 z-30 bg-black/30 lg:hidden" />}

      <div className="min-h-screen lg:pl-64">
        <header className="sticky top-0 z-20 flex h-[72px] items-center justify-between border-b border-zinc-200 bg-white/90 px-4 backdrop-blur-md sm:px-8">
          <div className="flex items-center gap-3">
            <button onClick={() => setMobileNav(true)} className="rounded-lg p-2 hover:bg-zinc-100 lg:hidden" aria-label="Open navigation"><Menu size={20} /></button>
            <div className="hidden items-center gap-2 text-sm text-zinc-400 sm:flex">
              <span>Workspace</span><ChevronRight size={15} />
              <span className="font-medium text-zinc-800">{selected ? selected.name : section}</span>
            </div>
            <span className="font-semibold sm:hidden">{selected ? selected.name : section}</span>
          </div>
          <div className="flex items-center gap-2 sm:gap-4">
            <span className="hidden items-center gap-1.5 text-xs text-zinc-500 md:flex"><span className="h-2 w-2 rounded-full bg-emerald-500" /> {agentStatus === "Connected" ? "Agent connected" : "Agent disconnected"}</span>
            <button className="relative rounded-lg p-2 text-zinc-500 hover:bg-zinc-100" aria-label="Notifications" onClick={() => notify(`${offline} offline devices · ${openTickets} active tickets`)}>
              <Bell size={19} />
              {(offline > 0 || openTickets > 0) && <span className="absolute right-1.5 top-1.5 h-2 w-2 rounded-full bg-red-500 ring-2 ring-white" />}
            </button>
            <div className="flex h-9 w-9 items-center justify-center rounded-full bg-blue-100 text-xs font-bold text-blue-700">TA</div>
          </div>
        </header>

        <main className="mx-auto max-w-[1600px] space-y-6 p-4 sm:p-8">
          {selected ? (
            <ComputerDetails device={selected} onBack={() => setSelected(null)} />
          ) : section === "Computers" || section === "Overview" ? (
            <>
              <div className="flex flex-col justify-between gap-4 sm:flex-row sm:items-end">
                <div>
                  <p className="text-sm text-zinc-500">Monitor and manage your organisation's endpoints</p>
                  <h1 className="mt-2 text-2xl font-semibold tracking-tight sm:text-3xl">{section === "Overview" ? "Service desk overview" : "Computer inventory"}</h1>
                  <p className="mt-2 text-sm text-zinc-500">Manage devices, monitor system health and track support issues.</p>
                </div>
                <div className="flex flex-wrap gap-2">
                  <button onClick={() => sendAgentCommand("refresh")} className="btn-secondary"><RefreshCw size={15} /> Refresh agent</button>
                  <button onClick={() => setSection("Settings")} className="btn-primary"><Wifi size={16} /> Connect agent</button>
                </div>
              </div>

              <div className="grid gap-4 sm:grid-cols-2 xl:grid-cols-4">
                <Metric label="Total computers" value={devices.length} icon={Monitor} detail="Registered inventory" />
                <Metric label="Online devices" value={online} icon={Wifi} detail={`${devices.length ? Math.round(online / devices.length * 100) : 0}% of inventory`} color="text-emerald-700" />
                <Metric label="Offline devices" value={offline} icon={WifiOff} detail="Check connection and heartbeat" color={offline ? "text-red-600" : "text-zinc-900"} />
                <Metric label="Active tickets" value={openTickets} icon={Ticket} detail="Across registered computers" color={openTickets ? "text-amber-700" : "text-zinc-900"} />
              </div>

              <div className="grid gap-4 lg:grid-cols-[1.6fr_1fr]">
                <div className="rounded-xl border border-zinc-200 bg-white p-5 shadow-sm">
                  <div className="flex items-center justify-between">
                    <div>
                      <h2 className="font-semibold">Device health</h2>
                      <p className="mt-1 text-xs text-zinc-500">Current status reported by the desktop agent</p>
                    </div>
                    <ShieldCheck className="text-zinc-400" size={20} />
                  </div>
                  <div className="mt-6 flex h-3 overflow-hidden rounded-full bg-zinc-100">
                    <motion.div initial={{ width: 0 }} animate={{ width: `${devices.length ? online / devices.length * 100 : 0}%` }} className="bg-emerald-500" />
                    <motion.div initial={{ width: 0 }} animate={{ width: `${devices.length ? offline / devices.length * 100 : 0}%` }} className="bg-red-500" />
                    <motion.div initial={{ width: 0 }} animate={{ width: `${devices.length ? devices.filter(d => d.state === "Maintenance").length / devices.length * 100 : 0}%` }} className="bg-amber-400" />
                  </div>
                  <div className="mt-4 flex flex-wrap gap-x-5 gap-y-2 text-xs text-zinc-600">
                    <span className="flex items-center gap-2"><span className="h-2 w-2 rounded-full bg-emerald-500" /> Online ({online})</span>
                    <span className="flex items-center gap-2"><span className="h-2 w-2 rounded-full bg-red-500" /> Offline ({offline})</span>
                    <span className="flex items-center gap-2"><span className="h-2 w-2 rounded-full bg-amber-400" /> Maintenance ({devices.filter(d => d.state === "Maintenance").length})</span>
                  </div>
                </div>
                <div className="rounded-xl border border-zinc-200 bg-white p-5 shadow-sm">
                  <div className="flex items-center justify-between">
                    <h2 className="font-semibold">Needs attention</h2>
                    <AlertCircle size={19} className="text-amber-600" />
                  </div>
                  <div className="mt-4 space-y-3">
                    <div className="flex items-center justify-between text-sm"><span className="text-zinc-600">Offline devices</span><span className="font-semibold text-red-600">{offline}</span></div>
                    <div className="flex items-center justify-between text-sm"><span className="text-zinc-600">High resource usage</span><span className="font-semibold text-amber-600">{alerts}</span></div>
                    <div className="flex items-center justify-between text-sm"><span className="text-zinc-600">Devices with tickets</span><span className="font-semibold">{devices.filter(d => d.ticketCount > 0).length}</span></div>
                  </div>
                </div>
              </div>

              <section className="overflow-visible rounded-xl border border-zinc-200 bg-white shadow-sm">
                <div className="flex flex-col justify-between gap-4 border-b border-zinc-200 p-5 xl:flex-row xl:items-center">
                  <div>
                    <h2 className="font-semibold">{section === "Overview" ? "Recent computers" : "All computers"}</h2>
                    <p className="mt-1 text-sm text-zinc-500">View endpoint health, assigned users and open tickets.</p>
                  </div>
                  <div className="flex flex-col gap-2 sm:flex-row sm:flex-wrap">
                    <div className="relative min-w-0 sm:w-64">
                      <Search size={17} className="absolute left-3 top-1/2 -translate-y-1/2 text-zinc-400" />
                      <input value={query} onChange={e => setQuery(e.target.value)} placeholder="Search computers..." className="field pl-9" />
                    </div>
                    <select value={stateFilter} onChange={e => setStateFilter(e.target.value)} className="field sm:w-40">
                      <option>All states</option><option>Online</option><option>Offline</option><option>Maintenance</option>
                    </select>
                    <select value={ticketFilter} onChange={e => setTicketFilter(e.target.value)} className="field sm:w-40">
                      <option>All tickets</option><option>Has tickets</option><option>No tickets</option>
                    </select>
                  </div>
                </div>
                <div className="overflow-x-auto">
                  <table className="w-full min-w-[1160px] text-left text-sm">
                    <thead className="border-b border-zinc-200 bg-zinc-50 text-xs text-zinc-500">
                      <tr>
                        <th className="px-5 py-3 font-medium">Device ID</th>
                        <th className="px-4 py-3 font-medium">Assigned user</th>
                        <th className="px-4 py-3 font-medium">Computer</th>
                        <th className="px-4 py-3 font-medium">Computer state</th>
                        <th className="px-4 py-3 font-medium">CPU</th>
                        <th className="px-4 py-3 font-medium">RAM</th>
                        <th className="px-4 py-3 font-medium">Disk</th>
                        <th className="px-4 py-3 font-medium">Battery</th>
                        <th className="px-4 py-3 font-medium">Tickets</th>
                        <th className="px-4 py-3 font-medium">Last seen</th>
                        <th className="px-4 py-3 text-right font-medium">Actions</th>
                      </tr>
                    </thead>
                    <tbody className="divide-y divide-zinc-100">
                      {filtered.map((d, index) => (
                        <motion.tr key={d.id} initial={{ opacity: 0 }} animate={{ opacity: 1 }} transition={{ delay: index * .025 }} className="transition-colors hover:bg-zinc-50/80">
                          <td className="px-5 py-4 font-medium text-zinc-700">{d.id}</td>
                          <td className="px-4 py-4">
                            <div className="flex items-center gap-2.5">
                              <div className="flex h-8 w-8 shrink-0 items-center justify-center rounded-full bg-zinc-100 text-xs font-semibold text-zinc-600">
                                {d.user === "Unassigned" ? "—" : d.user.split(" ").filter(Boolean).slice(0, 2).map(s => s[0]).join("")}
                              </div>
                              <div><p className="whitespace-nowrap text-sm font-medium">{d.user}</p><p className="mt-0.5 max-w-36 truncate text-xs text-zinc-500">{d.email}</p></div>
                            </div>
                          </td>
                          <td className="px-4 py-4">
                            <button onClick={() => setSelected(d)} className="text-left font-medium text-blue-700 hover:underline">{d.name}</button>
                            <p className="mt-1 max-w-40 truncate text-xs text-zinc-500">{d.organisation}</p>
                          </td>
                          <td className="px-4 py-4"><StateBadge state={d.state} /></td>
                          <td className="px-4 py-4">{d.state === "Online" ? <UsageBar value={d.cpu} /> : <span className="text-xs text-zinc-400">—</span>}</td>
                          <td className="px-4 py-4">{d.state === "Online" ? <UsageBar value={d.ram} /> : <span className="text-xs text-zinc-400">—</span>}</td>
                          <td className="px-4 py-4">{d.state === "Online" ? <UsageBar value={d.disk} /> : <span className="text-xs text-zinc-400">—</span>}</td>
                          <td className="px-4 py-4">{d.battery === null ? <span className="text-xs text-zinc-400">N/A</span> : <span className="inline-flex items-center gap-1 text-xs"><BatteryCharging size={15} />{d.battery}%</span>}</td>
                          <td className="px-4 py-4">
                            {d.ticketCount ? (
                              <button onClick={() => { setSection("Tickets"); setSelected(null); }} className="inline-flex items-center gap-1.5 whitespace-nowrap rounded-full bg-amber-50 px-2.5 py-1 text-xs font-medium text-amber-700 hover:bg-amber-100">
                                <Ticket size={13} />{d.ticketCount} open
                              </button>
                            ) : <span className="text-xs text-zinc-400">None</span>}
                          </td>
                          <td className="whitespace-nowrap px-4 py-4 text-xs text-zinc-500">{d.lastSeen}</td>
                          <td className="relative px-4 py-4 text-right">
                            <button aria-label={`Actions for ${d.name}`} onClick={() => setActiveMenu(activeMenu === d.id ? null : d.id)} className="rounded-lg p-2 text-zinc-500 hover:bg-zinc-100 hover:text-zinc-900">
                              <Ellipsis size={18} />
                            </button>
                            <AnimatePresence>
                              {activeMenu === d.id && (
                                <motion.div initial={{ opacity: 0, y: -4 }} animate={{ opacity: 1, y: 0 }} exit={{ opacity: 0, y: -4 }} className="absolute right-8 top-12 z-30 w-52 rounded-xl border border-zinc-200 bg-white p-1.5 text-left shadow-xl">
                                  <button onClick={() => { setSelected(d); setActiveMenu(null); }} className="menu-item"><Activity size={15} /> View details</button>
                                  <button onClick={() => { changeTicket(d); }} className="menu-item"><Ticket size={15} /> {d.ticketCount ? "Clear tickets" : "Create ticket"}</button>

                                </motion.div>
                              )}
                            </AnimatePresence>
                          </td>
                        </motion.tr>
                      ))}
                      {filtered.length === 0 && (
                        <tr><td colSpan={11} className="px-5 py-16 text-center">
                          <Search size={24} className="mx-auto text-zinc-300" />
                          <p className="mt-3 font-medium">No computers found</p>
                          <p className="mt-1 text-sm text-zinc-500">Try another search or change the filters.</p>
                        </td></tr>
                      )}
                    </tbody>
                  </table>
                </div>
                <div className="flex flex-col justify-between gap-3 border-t border-zinc-200 px-5 py-3 text-xs text-zinc-500 sm:flex-row sm:items-center">
                  <span>Showing {filtered.length} of {devices.length} computers</span>
                  <span className="flex items-center gap-2"><span className="h-2 w-2 rounded-full bg-emerald-500" />Online · <span className="h-2 w-2 rounded-full bg-red-500" />Offline · <span className="h-2 w-2 rounded-full bg-amber-400" />Maintenance</span>
                </div>
              </section>
              <p className="text-center text-xs text-zinc-400">Techloom Service Desk · Direct desktop-agent connection</p>
            </>
          ) : section === "Tickets" ? (
            <section className="space-y-5">
              <div><h1 className="text-2xl font-semibold">Support tickets</h1><p className="mt-2 text-sm text-zinc-500">Tickets linked to registered computers.</p></div>
              <div className="overflow-x-auto rounded-xl border border-zinc-200 bg-white">
                <table className="w-full min-w-[650px] text-left text-sm">
                  <thead className="bg-zinc-50 text-xs text-zinc-500"><tr><th className="px-5 py-3">Computer</th><th className="px-5 py-3">Assigned user</th><th className="px-5 py-3">Ticket status</th><th className="px-5 py-3">Count</th><th className="px-5 py-3">Action</th></tr></thead>
                  <tbody className="divide-y divide-zinc-100">{devices.filter(d => d.ticketCount > 0).map(d => <tr key={d.id}><td className="px-5 py-4"><button className="font-medium text-blue-700 hover:underline" onClick={() => setSelected(d)}>{d.name}</button><p className="text-xs text-zinc-500">{d.id}</p></td><td className="px-5 py-4">{d.user}</td><td className="px-5 py-4"><span className="rounded-full bg-amber-50 px-2.5 py-1 text-xs text-amber-700">{d.ticketState}</span></td><td className="px-5 py-4">{d.ticketCount}</td><td className="px-5 py-4"><button className="text-sm font-medium text-blue-700" onClick={() => setSelected(d)}>View device</button></td></tr>)}</tbody>
                </table>
                {openTickets === 0 && <p className="p-8 text-center text-sm text-zinc-500">No demo tickets are currently open.</p>}
              </div>
              <p className="text-xs text-zinc-500">Ticket IDs, descriptions, priorities, assignment, and resolution workflow should be added through a ticketing backend.</p>
            </section>
          ) : section === "Users" ? (
            <section className="space-y-5">
              <div><h1 className="text-2xl font-semibold">Assigned users</h1><p className="mt-2 text-sm text-zinc-500">People associated with the device inventory.</p></div>
              <div className="overflow-x-auto rounded-xl border border-zinc-200 bg-white"><table className="w-full min-w-[600px] text-left text-sm"><thead className="bg-zinc-50 text-xs text-zinc-500"><tr><th className="px-5 py-3">User</th><th className="px-5 py-3">Email</th><th className="px-5 py-3">Organisation</th><th className="px-5 py-3">Computers</th></tr></thead><tbody className="divide-y divide-zinc-100">{[...new Map<string, Device>(devices.filter(d => d.user !== "Unassigned").map(d => [d.user, d] as [string, Device])).values()].map(d => <tr key={d.user}><td className="px-5 py-4 font-medium">{d.user}</td><td className="px-5 py-4 text-zinc-500">{d.email}</td><td className="px-5 py-4">{d.organisation}</td><td className="px-5 py-4">{devices.filter(x => x.user === d.user).length}</td></tr>)}</tbody></table></div>
            </section>
          ) : (
            <section className="max-w-2xl space-y-5">
              <div><h1 className="text-2xl font-semibold">Agent connection</h1><p className="mt-2 text-sm text-zinc-500">Connect directly to the CloudMonitor desktop application. No backend is used.</p></div>
              <div className="rounded-xl border border-zinc-200 bg-white p-5 shadow-sm space-y-4">
                <div className="flex items-center justify-between gap-3">
                  <h2 className="font-semibold">Local desktop agent</h2>
                  <span className={`rounded-full px-2.5 py-1 text-xs font-medium ${agentStatus === "Connected" ? "bg-emerald-50 text-emerald-700" : agentStatus === "Error" ? "bg-red-50 text-red-700" : "bg-amber-50 text-amber-700"}`}>{agentStatus}</span>
                </div>
                <div><label className="mb-1.5 block text-sm font-medium">Agent address</label><input value={agentUrl} onChange={e => setAgentUrl(e.target.value)} placeholder="http://127.0.0.1:8765" className="field" /></div>
                <div><label className="mb-1.5 block text-sm font-medium">Agent API token</label><input value={agentToken} onChange={e => setAgentToken(e.target.value)} type="password" placeholder="Copy the token from CloudMonitor Desktop Agent" className="field" /></div>
                {agentError && <p className="text-sm text-red-600">{agentError}</p>}
                <p className="text-xs text-zinc-500">Copy the API token displayed in the desktop agent. The connection is checked automatically every 3 seconds.</p>
                <div className="flex flex-wrap gap-2">
                  <button onClick={() => { localStorage.setItem("cloudmonitor.agentUrl", agentUrl); localStorage.setItem("cloudmonitor.agentToken", agentToken); fetchAgentDevice(); }} className="btn-primary"><Wifi size={15} /> Connect / test</button>
                  <button onClick={() => sendAgentCommand("refresh")} className="btn-secondary"><RefreshCw size={15} /> Request refresh</button>
                </div>
                <div className="border-t border-zinc-100 pt-4">
                  <h3 className="text-sm font-semibold">Agent controls</h3>
                  <p className="mt-1 text-xs text-zinc-500">Commands are sent directly to the running desktop agent.</p>
                  <div className="mt-3 flex flex-wrap gap-2">
                    <button onClick={() => sendAgentCommand("pause")} className="btn-secondary">Pause monitoring</button>
                    <button onClick={() => sendAgentCommand("resume")} className="btn-secondary">Resume monitoring</button>
                  </div>
                </div>
                <p className="text-xs text-zinc-500">Last successful sync: {lastSync || "Not connected"}</p>
                <div className="border-t border-zinc-100 pt-4 space-y-3">
                  <h3 className="text-sm font-semibold">Send computer details to agent</h3>
                  <div><label className="mb-1 block text-xs font-medium">Computer display name</label><input value={agentDisplayName} onChange={e => setAgentDisplayName(e.target.value)} className="field" placeholder="e.g. Reception-PC" /></div>
                  <div><label className="mb-1 block text-xs font-medium">Assigned user</label><input value={agentAssignedUser} onChange={e => setAgentAssignedUser(e.target.value)} className="field" placeholder="Full name" /></div>
                  <div><label className="mb-1 block text-xs font-medium">User email</label><input value={agentUserEmail} onChange={e => setAgentUserEmail(e.target.value)} className="field" placeholder="name@company.co.za" /></div>
                  <div><label className="mb-1 block text-xs font-medium">Institute / business</label><input value={agentOrganisation} onChange={e => setAgentOrganisation(e.target.value)} className="field" placeholder="Organisation name" /></div>
                  <button onClick={sendAgentMetadata} className="btn-secondary">Send details to agent</button>
                </div>
              </div>
            </section>
          )}
        </main>
      </div>

      <AnimatePresence>
        {notice && (
          <motion.div initial={{ opacity: 0, y: 20 }} animate={{ opacity: 1, y: 0 }} exit={{ opacity: 0, y: 10 }} role="status" className="fixed bottom-5 right-5 z-[70] flex max-w-[calc(100vw-40px)] items-center gap-3 rounded-xl bg-zinc-950 px-4 py-3 text-sm text-white shadow-xl">
            <span className="flex h-6 w-6 items-center justify-center rounded-full bg-emerald-500"><Check size={14} /></span>{notice}
            <button onClick={() => setNotice("")} className="ml-2 text-zinc-400 hover:text-white" aria-label="Dismiss notification"><X size={15} /></button>
          </motion.div>
        )}
      </AnimatePresence>
    </div>
  );
}
