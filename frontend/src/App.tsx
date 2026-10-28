
import { useMemo, useState } from "react";
import { AnimatePresence, motion } from "framer-motion";
import {
  Activity, AlertCircle, BatteryCharging, Bell, Check, ChevronDown,
  ChevronLeft, ChevronRight, CircleHelp, Clock3, Cpu, Database,
  Ellipsis, HardDrive, LayoutDashboard, LoaderCircle, Menu, Monitor,
  Plus, RefreshCw, Search, Settings, ShieldCheck, Ticket, Users,
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
};

type ProcessInfo = {
  name: string;
  pid: number;
  cpu: number;
  memory: number;
  category: string;
};

const initialDevices: Device[] = [
  {
    id: "PC-001", name: "Reception-PC", user: "Sarah Mokoena",
    email: "sarah@example.com", organisation: "Techloom HQ",
    os: "Windows 11 Pro", cpuModel: "Intel Core i5-12400",
    cpu: 24, ram: 62, ramTotal: 16, disk: 48, diskTotal: 512,
    battery: null, state: "Online", ticketCount: 1,
    ticketState: "Open", lastSeen: "Just now", ip: "192.168.1.101",
    serial: "TL-2025-001", uptime: "3d 5h 24m",
  },
  {
    id: "PC-002", name: "Lab-PC-014", user: "David Khumalo",
    email: "david@example.com", organisation: "Training Institute",
    os: "Windows 10 Pro", cpuModel: "Intel Core i3-10100",
    cpu: 0, ram: 0, ramTotal: 8, disk: 0, diskTotal: 256,
    battery: null, state: "Offline", ticketCount: 2,
    ticketState: "Open", lastSeen: "2 hours ago", ip: "192.168.1.114",
    serial: "TL-2024-014", uptime: "Unknown",
  },
  {
    id: "PC-003", name: "Finance-PC", user: "Mary Nkosi",
    email: "mary@example.com", organisation: "Techloom HQ",
    os: "Windows 11 Pro", cpuModel: "Intel Core i7-12700",
    cpu: 78, ram: 84, ramTotal: 32, disk: 73, diskTotal: 1024,
    battery: null, state: "Online", ticketCount: 0,
    ticketState: "None", lastSeen: "Just now", ip: "192.168.1.103",
    serial: "TL-2025-003", uptime: "6d 12h 08m",
  },
  {
    id: "LT-004", name: "Director-Laptop", user: "Admin User",
    email: "admin@example.com", organisation: "Techloom HQ",
    os: "Windows 11 Pro", cpuModel: "Intel Core Ultra 5",
    cpu: 12, ram: 38, ramTotal: 16, disk: 36, diskTotal: 512,
    battery: 87, state: "Online", ticketCount: 1,
    ticketState: "In progress", lastSeen: "Just now", ip: "192.168.1.104",
    serial: "TL-2025-004", uptime: "1d 7h 14m",
  },
  {
    id: "PC-005", name: "Workshop-PC", user: "Unassigned",
    email: "—", organisation: "Mathosim Workshop",
    os: "Windows 10 Pro", cpuModel: "Intel Core i5-8500",
    cpu: 0, ram: 0, ramTotal: 8, disk: 0, diskTotal: 256,
    battery: null, state: "Maintenance", ticketCount: 1,
    ticketState: "In progress", lastSeen: "Yesterday", ip: "192.168.1.105",
    serial: "TL-2023-005", uptime: "Unknown",
  },
];

const demoProcesses: ProcessInfo[] = [
  { name: "Google Chrome", pid: 4210, cpu: 18.4, memory: 1240, category: "Browser" },
  { name: "Microsoft Teams", pid: 2784, cpu: 12.1, memory: 860, category: "Communication" },
  { name: "Antimalware Service", pid: 1108, cpu: 8.2, memory: 420, category: "Security" },
  { name: "Visual Studio Code", pid: 5160, cpu: 6.8, memory: 680, category: "Development" },
  { name: "Windows Explorer", pid: 940, cpu: 2.1, memory: 180, category: "System" },
];

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

function DeviceModal({
  onClose, onAdd,
}: {
  onClose: () => void;
  onAdd: (device: Device) => void;
}) {
  const [name, setName] = useState("");
  const [user, setUser] = useState("");
  const [email, setEmail] = useState("");
  const [organisation, setOrganisation] = useState("");
  const [os, setOs] = useState("Windows 11 Pro");
  const [serial, setSerial] = useState("");
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState("");

  function submit(e: React.FormEvent<HTMLFormElement>) {
    e.preventDefault();
    if (loading) return;
    setError("");

    setLoading(true);
    // Demo only: replace this timeout with your registration API.
    window.setTimeout(() => {
      const device: Device = {
        id: `PC-${String(Date.now()).slice(-5)}`,
        name: name.trim(),
        user: user.trim() || "Unassigned",
        email: email.trim() || "—",
        organisation: organisation.trim(),
        os,
        cpuModel: "Awaiting agent data",
        cpu: 0, ram: 0, ramTotal: 0, disk: 0, diskTotal: 0,
        battery: null, state: "Offline", ticketCount: 0,
        ticketState: "None", lastSeen: "Not connected",
        ip: "Pending agent", serial: serial.trim() || "Not provided",
        uptime: "Unknown",
      };
      onAdd(device);
    }, 1400);
  }

  return (
    <motion.div
      className="fixed inset-0 z-50 flex items-center justify-center overflow-y-auto bg-zinc-950/40 p-4 backdrop-blur-sm"
      initial={{ opacity: 0 }} animate={{ opacity: 1 }} exit={{ opacity: 0 }}
      onMouseDown={(e) => { if (e.target === e.currentTarget && !loading) onClose(); }}
    >
      <motion.div
        initial={{ opacity: 0, y: 18, scale: 0.98 }}
        animate={{ opacity: 1, y: 0, scale: 1 }}
        exit={{ opacity: 0, y: 12, scale: 0.98 }}
        transition={{ duration: 0.2 }}
        className="my-auto w-full max-w-lg rounded-2xl border border-zinc-200 bg-white shadow-2xl"
      >
        <div className="flex items-start justify-between border-b border-zinc-100 p-6">
          <div>
            <div className="mb-3 flex h-10 w-10 items-center justify-center rounded-xl bg-blue-50 text-blue-700">
              <Monitor size={21} />
            </div>
            <h2 className="text-lg font-semibold">Add a computer</h2>
            <p className="mt-1 text-sm text-zinc-500">
              Register a workstation or laptop in your inventory.
            </p>
          </div>
          <button onClick={onClose} disabled={loading} aria-label="Close modal" className="rounded-lg p-2 text-zinc-500 hover:bg-zinc-100">
            <X size={19} />
          </button>
        </div>

        <form onSubmit={submit} className="space-y-4 p-6">
          <div>
            <label className="mb-1.5 block text-sm font-medium">Computer name *</label>
            <input required maxLength={80} value={name} onChange={(e) => setName(e.target.value)}
              placeholder="e.g. Reception-PC" className="field" />
          </div>
          <div className="grid gap-4 sm:grid-cols-2">
            <div>
              <label className="mb-1.5 block text-sm font-medium">Assigned user</label>
              <input value={user} onChange={(e) => setUser(e.target.value)}
                placeholder="Full name" className="field" />
            </div>
            <div>
              <label className="mb-1.5 block text-sm font-medium">User email</label>
              <input type="email" value={email} onChange={(e) => setEmail(e.target.value)}
                placeholder="user@company.co.za" className="field" />
            </div>
          </div>
          <div>
            <label className="mb-1.5 block text-sm font-medium">Institute / business *</label>
            <input required value={organisation} onChange={(e) => setOrganisation(e.target.value)}
              placeholder="Organisation or department" className="field" />
          </div>
          <div className="grid gap-4 sm:grid-cols-2">
            <div>
              <label className="mb-1.5 block text-sm font-medium">Operating system</label>
              <select value={os} onChange={(e) => setOs(e.target.value)} className="field">
                <option>Windows 11 Pro</option>
                <option>Windows 10 Pro</option>
                <option>Windows 11 Home</option>
                <option>macOS</option>
                <option>Ubuntu Linux</option>
                <option>Other / Unknown</option>
              </select>
            </div>
            <div>
              <label className="mb-1.5 block text-sm font-medium">Serial number</label>
              <input value={serial} onChange={(e) => setSerial(e.target.value)}
                placeholder="Manufacturer serial" className="field" />
            </div>
          </div>
          {error && <p role="alert" className="text-sm text-red-600">{error}</p>}
          <div className="rounded-lg bg-blue-50 p-3 text-xs leading-5 text-blue-800">
            <strong>Monitoring setup:</strong> Adding a record registers the computer in this demo. Install and enrol a monitoring agent to collect actual hardware and process information.
          </div>
          <div className="flex flex-col-reverse gap-3 pt-1 sm:flex-row sm:justify-end">
            <button type="button" disabled={loading} onClick={onClose} className="btn-secondary">
              Cancel
            </button>
            <button type="submit" disabled={loading} className="btn-primary min-w-36">
              {loading ? <><LoaderCircle size={16} className="animate-spin" /> Registering...</> : <><Plus size={16} /> Add computer</>}
            </button>
          </div>
          {loading && (
            <div className="h-1 overflow-hidden rounded-full bg-blue-100">
              <div className="animate-progress h-full rounded-full bg-blue-600" />
            </div>
          )}
        </form>
      </motion.div>
    </motion.div>
  );
}

function ComputerDetails({ device, onBack }: { device: Device; onBack: () => void }) {
  const processes = device.state === "Online" ? demoProcesses : [];

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
          <span className="text-xs text-zinc-500">{processes.length} demo processes</span>
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
          Demo process figures only. Production data must come from an enrolled endpoint agent.
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
  const [devices, setDevices] = useState<Device[]>(initialDevices);
  const [query, setQuery] = useState("");
  const [stateFilter, setStateFilter] = useState("All states");
  const [ticketFilter, setTicketFilter] = useState("All tickets");
  const [activeMenu, setActiveMenu] = useState<string | null>(null);
  const [selected, setSelected] = useState<Device | null>(null);
  const [showModal, setShowModal] = useState(false);
  const [notice, setNotice] = useState("");
  const [section, setSection] = useState("Computers");
  const [mobileNav, setMobileNav] = useState(false);

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

  function addDevice(device: Device) {
    setDevices(prev => [device, ...prev]);
    setShowModal(false);
    setSection("Computers");
    notify(`${device.name} added to inventory`);
  }

  function changeState(device: Device, state: DeviceState) {
    setDevices(prev => prev.map(d => d.id === device.id ? { ...d, state } : d));
    if (selected?.id === device.id) setSelected({ ...device, state });
    setActiveMenu(null);
    notify(`${device.name} marked ${state.toLowerCase()}`);
  }

  function changeTicket(device: Device) {
    const count = device.ticketCount ? 0 : 1;
    const updated = { ...device, ticketCount: count, ticketState: count ? "Open" as const : "None" as const };
    setDevices(prev => prev.map(d => d.id === device.id ? updated : d));
    if (selected?.id === device.id) setSelected(updated);
    setActiveMenu(null);
    notify(count ? "Demo ticket created" : "Demo tickets cleared");
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
            <span className="hidden items-center gap-1.5 text-xs text-zinc-500 md:flex"><span className="h-2 w-2 rounded-full bg-emerald-500" /> Demo environment</span>
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
                  <button onClick={() => notify("Demo data refreshed")} className="btn-secondary"><RefreshCw size={15} /> Refresh</button>
                  <button onClick={() => setShowModal(true)} className="btn-primary"><Plus size={16} /> Add computer</button>
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
                      <p className="mt-1 text-xs text-zinc-500">Current status from the demo inventory</p>
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
                                  <button onClick={() => { changeTicket(d); }} className="menu-item"><Ticket size={15} /> {d.ticketCount ? "Clear demo tickets" : "Create demo ticket"}</button>
                                  <div className="my-1 border-t border-zinc-100" />
                                  <p className="px-3 py-1.5 text-[10px] font-semibold uppercase tracking-wider text-zinc-400">Set demo state</p>
                                  {(["Online", "Offline", "Maintenance"] as DeviceState[]).map(state => (
                                    <button key={state} onClick={() => changeState(d, state)} className="menu-item">
                                      <span className={`h-2 w-2 rounded-full ${state === "Online" ? "bg-emerald-500" : state === "Offline" ? "bg-red-500" : "bg-amber-500"}`} />Mark {state.toLowerCase()}
                                    </button>
                                  ))}
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
              <p className="text-center text-xs text-zinc-400">Techloom Service Desk · Prototype with simulated endpoint data</p>
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
              <div className="overflow-x-auto rounded-xl border border-zinc-200 bg-white"><table className="w-full min-w-[600px] text-left text-sm"><thead className="bg-zinc-50 text-xs text-zinc-500"><tr><th className="px-5 py-3">User</th><th className="px-5 py-3">Email</th><th className="px-5 py-3">Organisation</th><th className="px-5 py-3">Computers</th></tr></thead><tbody className="divide-y divide-zinc-100">{[...new Map(devices.filter(d => d.user !== "Unassigned").map(d => [d.user, d])).values()].map(d => <tr key={d.user}><td className="px-5 py-4 font-medium">{d.user}</td><td className="px-5 py-4 text-zinc-500">{d.email}</td><td className="px-5 py-4">{d.organisation}</td><td className="px-5 py-4">{devices.filter(x => x.user === d.user).length}</td></tr>)}</tbody></table></div>
            </section>
          ) : (
            <section className="max-w-2xl space-y-5">
              <h1 className="text-2xl font-semibold">Settings</h1>
              <div className="rounded-xl border border-zinc-200 bg-white p-5">
                <h2 className="font-semibold">Monitoring configuration</h2>
                <p className="mt-2 text-sm leading-6 text-zinc-500">This frontend prototype does not connect to endpoint agents, a database, or a ticketing service yet. Configure the backend API, device heartbeat interval, authentication and alert thresholds before deploying.</p>
                <div className="mt-4 flex items-center gap-2 text-sm text-amber-700"><AlertCircle size={17} /> Live monitoring is not configured.</div>
              </div>
            </section>
          )}
        </main>
      </div>

      <AnimatePresence>
        {showModal && <DeviceModal onClose={() => setShowModal(false)} onAdd={addDevice} />}
      </AnimatePresence>
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
