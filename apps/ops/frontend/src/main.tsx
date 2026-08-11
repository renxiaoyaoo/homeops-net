import React, { useEffect, useMemo, useState } from "react";
import { createRoot } from "react-dom/client";
import {
  Activity,
  AlertTriangle,
  ArrowUpRight,
  CheckCircle2,
  Compass,
  Globe2,
  Home,
  Layers3,
  RadioTower,
  RefreshCw,
  Save,
  Search,
  Sparkles,
  Trash2,
  Wifi,
  Wrench,
  XCircle
} from "lucide-react";
import "./styles.css";

type Status = "ok" | "warn" | "bad" | "unknown" | string;
type View = "status" | "topology" | "services" | "routing";

type Rate = {
  up_mbps?: number;
  down_mbps?: number;
};

type Insight = {
  level?: Status;
  title?: string;
  text?: string;
};

type Device = Rate & {
  ip?: string;
  mac?: string;
  name?: string;
  host?: string;
};

type DeviceInventoryItem = {
  id?: string;
  name?: string;
  role?: string;
  ip?: string;
  network?: string;
  status?: Status;
  label?: string;
  detail?: string;
};

type RouteSummary = Rate & {
  chain?: string;
  connections?: number;
  rules?: string[];
};

type HomeService = {
  key?: string;
  name?: string;
  kind?: string;
  role?: string;
  href?: string;
  local_href?: string;
  status?: Status;
  latency_ms?: number;
  detail?: string;
  ports?: PortEntry[];
};

type PortEntry = {
  host?: string;
  port?: string;
  proto?: string;
  service?: string;
  owner?: string;
  scope?: string;
  note?: string;
};

type Ingress = {
  key?: string;
  name?: string;
  kind?: string;
  href?: string;
  target?: string;
  status?: Status;
  detail?: string;
};

type HealthCheck = {
  status?: Status;
  title?: string;
  detail?: string;
};

type PresenceAp = {
  clients?: string[];
  remote_addr?: string;
  updated_at?: number;
  age_seconds?: number | null;
};

type Presence = {
  ok?: boolean;
  seen_all?: boolean;
  expected_aps?: string[];
  fresh_aps?: string[];
  merged_clients?: string[];
  aps?: Record<string, PresenceAp>;
  last_ha_push?: { clients?: string[]; count?: number; updated_at?: number; fresh_aps?: string[] };
  updated_at?: number;
  age_seconds?: number | null;
  error?: string;
};

type RemoteClient = {
  name?: string;
  enabled?: boolean;
  ipv4_address?: string;
  ipv6_address?: string;
  endpoint_scope?: string;
  has_endpoint?: boolean;
  latest_handshake?: string;
  latest_handshake_seconds?: number | null;
  last_seen_at?: number | null;
  age_seconds?: number | null;
  status?: Status;
  transfer?: string;
};

type RemoteAccess = {
  ok?: boolean;
  clients?: RemoteClient[];
  updated_at?: number;
  active_after_seconds?: number;
  stale_after_seconds?: number;
  error?: string;
};

type OpsNetwork = {
  ok?: boolean;
  ssid?: string;
  iface?: string;
  network?: string;
  gateway?: string;
  netmask?: string;
  dhcp_range?: string;
  dns?: string;
  proxy_bypassed?: boolean;
  clients?: Array<{ mac?: string; ip?: string; name?: string }>;
  checks?: HealthCheck[];
  updated_at?: number;
  error?: string;
};

type WifiDiagnostics = {
  ok?: boolean;
  radio1?: { up?: boolean; retry_setup_failed?: boolean; disabled?: boolean; ssids?: string[] };
  room_reachable?: boolean;
  backhaul_assoc_count?: number;
  backhaul_assoc_sample?: string;
  guard?: string;
  checks?: HealthCheck[];
  updated_at?: number;
  error?: string;
};

type IncidentDomain = {
  id?: string;
  title?: string;
  status?: Status;
  detail?: string;
  evidence?: string;
  next_action?: string;
  commands?: string[];
};

type IncidentDecisionStep = {
  id?: string;
  order?: number;
  domain?: string;
  status?: Status;
  question?: string;
  why_first?: string;
  if_bad?: string[];
  entries?: string[];
};

type IncidentRecoveryRow = {
  symptom?: string;
  start_domain?: string;
  status?: Status;
  first_probe?: string;
  then_probe?: string;
  likely_owner?: string;
  do_not_start_with?: string;
};

type Incident = {
  ok?: boolean;
  severity?: Status;
  headline?: string;
  summary?: string;
  domains?: IncidentDomain[];
  decision_flow?: IncidentDecisionStep[];
  recovery_matrix?: IncidentRecoveryRow[];
  runbook?: string[];
  updated_at?: number;
};

type InstanceDevice = {
  id?: string;
  name?: string;
  role?: string;
  network?: string;
  ip?: string;
  hostnames?: string[];
  expected?: boolean;
  presence?: string;
  notes?: string;
};

type InstanceState = {
  ok?: boolean;
  site?: { name?: string; display_name?: string; domain?: string; locale?: string };
  networks?: Record<string, { cidr?: string; gateway?: string; purpose?: string; dns_mode?: string; proxy_mode?: string }>;
  wifi?: Record<string, { ssid?: string; network?: string; band?: string; purpose?: string; broadcast_by?: string[] }>;
  devices?: InstanceDevice[];
  services?: Array<{ id?: string; name?: string; category?: string; role?: string; host?: string; runtime?: string; owner?: string }>;
  updated_at?: number;
};

type ModulePlan = {
  id?: string;
  title?: string;
  placement?: string;
  inputs?: string[];
  outputs?: string[];
  checks?: string[];
  rollback?: string[];
};

type HomeNetPlan = {
  ok?: boolean;
  schema?: string;
  profile?: string;
  modules?: ModulePlan[];
  apply?: { read_only?: boolean; status?: string; message?: string };
  error?: string;
  updated_at?: number;
};

type BlueprintCapability = {
  id?: string;
  title?: string;
  status?: Status;
  required?: boolean;
  placement?: string;
  fallback?: string;
};

type Blueprint = {
  ok?: boolean;
  schema?: string;
  profile?: string;
  position?: string;
  problem?: string[];
  provides?: string[];
  non_goals?: string[];
  operational_questions?: Array<{ question?: string; surface?: string }>;
  active_capabilities?: BlueprintCapability[];
  service_summary?: { total?: number; by_category?: Record<string, number> };
  source_of_truth?: Array<{ area?: string; owner?: string }>;
  updated_at?: number;
};

type RoutingRule = {
  id?: string;
  scope?: "temporary" | "permanent" | string;
  policy?: string;
  kind?: string;
  value?: string;
  rule?: string;
  duration?: string;
  created_at?: number;
  expires_at?: number | null;
};

type RoutingPermanentCandidate = {
  id?: string;
  status?: string;
  policy?: string;
  value?: string;
  rule?: string;
};

type RoutingRulesState = {
  ok?: boolean;
  policies?: Array<{ id: string; label: string }>;
  durations?: string[];
  entries?: RoutingRule[];
  permanent_candidates?: RoutingPermanentCandidate[];
  error?: string;
};

type State = {
  ok?: boolean;
  updated_at?: number;
  errors?: string[];
  wan?: Rate;
  mihomo?: Rate;
  devices?: Device[];
  domains?: Array<Rate & { host?: string; domain?: string; rule?: string; chain?: string }>;
  dns_queries?: Array<{ host?: string; name?: string; ip?: string; age_seconds?: number; type?: string }>;
  dns_top_devices?: Array<{ device?: string; count?: number }>;
  dns_top_hosts?: Array<{ host?: string; count?: number; devices?: string[] }>;
  route_summary?: RouteSummary[];
  connections?: Array<Rate & { host?: string; source_ip?: string; source_name?: string; rule?: string; chain?: string }>;
  insights?: Insight[];
  health?: { updated_at?: number; checks?: HealthCheck[] };
  history?: Array<{ time?: number; wan_down?: number; wan_up?: number; mihomo_down?: number; mihomo_up?: number; device_count?: number; dns_count_5m?: number }>;
  home_services?: HomeService[];
  ingress?: Ingress[];
  ports?: PortEntry[];
  presence?: Presence;
  remote_access?: RemoteAccess;
  ops_network?: OpsNetwork;
  wifi_diagnostics?: WifiDiagnostics;
  incident?: Incident;
  instance?: InstanceState;
  plan?: HomeNetPlan;
  blueprint?: Blueprint;
};

const emptyState: State = {
  ok: false,
  updated_at: 0,
  errors: [],
  wan: {},
  mihomo: {},
  devices: [],
  domains: [],
  dns_queries: [],
  dns_top_devices: [],
  route_summary: [],
  insights: [],
  health: { checks: [] },
  history: [],
  home_services: [],
  ingress: [],
  ports: [],
  presence: { merged_clients: [], fresh_aps: [], aps: {} },
  remote_access: { clients: [] },
  ops_network: { checks: [], clients: [] },
  wifi_diagnostics: { checks: [] },
  incident: { domains: [], decision_flow: [], recovery_matrix: [], runbook: [] },
  instance: { networks: {}, wifi: {}, devices: [], services: [] },
  plan: { modules: [] },
  blueprint: { active_capabilities: [], operational_questions: [], source_of_truth: [] }
};

const viewLabels: Array<{ id: View; label: string; icon: React.ReactNode }> = [
  { id: "status", label: "状态", icon: <Compass size={16} /> },
  { id: "topology", label: "拓扑", icon: <RadioTower size={16} /> },
  { id: "routing", label: "分流", icon: <Globe2 size={16} /> },
  { id: "services", label: "服务", icon: <Layers3 size={16} /> }
];

function number(value?: number, digits = 2) {
  return Number(value || 0).toFixed(digits);
}

function relativeTime(ts?: number) {
  if (!ts) return "waiting";
  const seconds = Math.max(0, Math.round(Date.now() / 1000 - ts));
  if (seconds < 5) return "just now";
  if (seconds < 60) return `${seconds}s ago`;
  const minutes = Math.round(seconds / 60);
  if (minutes < 60) return `${minutes}m ago`;
  return `${Math.round(minutes / 60)}h ago`;
}

function statusClass(status?: Status) {
  if (status === "ok") return "ok";
  if (status === "warn") return "warn";
  if (status === "bad" || status === "down") return "bad";
  if (status === "tracked") return "tracked";
  return "unknown";
}

function statusIcon(status?: Status) {
  const cls = statusClass(status);
  if (cls === "ok") return <CheckCircle2 size={16} />;
  if (cls === "bad") return <XCircle size={16} />;
  if (cls === "warn") return <AlertTriangle size={16} />;
  return <Activity size={16} />;
}

function serviceLinks(service: HomeService | Ingress) {
  const links: Array<{ label: string; href: string }> = [];
  if (service.href) links.push({ label: "外部", href: service.href });
  if ("local_href" in service && service.local_href && service.local_href !== service.href) {
    links.push({ label: "局域网", href: service.local_href });
  }
  if (service.key === "wrt-room-luci") links.push({ label: "房间侧", href: "http://192.168.1.1/" });
  return links;
}

function serviceDescription(service: HomeService | Ingress) {
  const homeService = service as HomeService;
  const ingress = service as Ingress;
  return homeService.role || ingress.target || service.kind || "";
}

function serviceGroups(services: HomeService[]) {
  return services.reduce<Record<string, HomeService[]>>((groups, service) => {
    const key = displayServiceGroup(service);
    groups[key] = groups[key] || [];
    groups[key].push(service);
    return groups;
  }, {});
}

function displayServiceGroup(service?: HomeService | string) {
  const kind = typeof service === "string" ? service : service?.kind;
  const key = typeof service === "string" ? "" : service?.key;
  if (["openwrt-luci", "openwrt-ssh", "wrt-room-luci", "wrt-room-ssh", "pi-ssh", "homenet-ops"].includes(key || "")) return "maintenance-entry";
  if (kind === "storage") return "control-core";
  if (kind === "udp-entry") return "remote-entry";
  return kind || "other";
}

function serviceGroupEntries(services: HomeService[]) {
  const order = ["network-core", "maintenance-entry", "remote-entry", "home-core", "control-core", "system-task", "other"];
  const groups = serviceGroups(services);
  return Object.entries(groups).sort(([a], [b]) => {
    const ai = order.indexOf(a);
    const bi = order.indexOf(b);
    return (ai === -1 ? 99 : ai) - (bi === -1 ? 99 : bi) || a.localeCompare(b);
  });
}

function groupLabel(kind: string) {
  const labels: Record<string, string> = {
    "network-core": "网络核心",
    "maintenance-entry": "维护入口",
    "remote-entry": "远程入口",
    "home-core": "智能家居",
    "control-core": "日常应用",
    "system-task": "后台任务",
    other: "其他"
  };
  return labels[kind] || kind;
}

function groupDescription(kind: string) {
  const descriptions: Record<string, string> = {
    "network-core": "路由、DNS、Proxy、卧室 AP 这类网络基础能力；这里异常会影响大部分设备。",
    "maintenance-entry": "日常排查首先打开的入口，例如 OpenWrt、卧室 WRT、Pi SSH 和 HomeNet Ops。",
    "remote-entry": "从外面回家或公网访问的入口；本地目标正常后再查 Cloudflare、Caddy 或 WireGuard。",
    "home-core": "Home Assistant、摄像头、MQTT、Zigbee 和家庭自动化相关服务。",
    "control-core": "日常会打开的管理入口、自建应用和文件入口。",
    "system-task": "后台同步、更新、presence 上报等任务，通常没有 Web UI。",
    other: "暂未归类的服务。"
  };
  return descriptions[kind] || "按 instance 中声明的服务类别分组。";
}

function portScopeLabel(scope?: string) {
  const value = (scope || "").toLowerCase();
  if (!value) return "未标注";
  if (value === "local" || value === "localhost") return "仅本机";
  if (value.includes("wan") && value.includes("lan")) return "局域网/远程";
  if (value.includes("wan")) return "远程入口";
  if (value.includes("router")) return "路由器转发";
  if (value.includes("lan")) return "局域网";
  return scope || "未标注";
}

function portSummary(ports: PortEntry[]) {
  if (!ports.length) return "无监听端口";
  const scopes = Array.from(new Set(ports.map((port) => portScopeLabel(port.scope))));
  return scopes.join(" / ");
}

function deviceInventory(state: State): DeviceInventoryItem[] {
  const activeByIp = new Map((state.devices || []).filter((device) => device.ip).map((device) => [device.ip, device]));
  return (state.instance?.devices || []).map((device) => {
    const active = device.ip ? activeByIp.get(device.ip) : undefined;
    if (active) {
      const speed = `${number(active.down_mbps)} / ${number(active.up_mbps)} Mbps`;
      return { ...device, status: "ok", label: "在线", detail: speed };
    }
    if (device.expected === false) {
      return { ...device, status: "tracked", label: "预期离线", detail: device.notes || "保留记录；不要求日常在线" };
    }
    if (device.presence === "optional") {
      return { ...device, status: "tracked", label: "可离线", detail: device.notes || "可休眠、备用链路或非当前连接" };
    }
    if (device.presence === "intermittent") {
      return { ...device, status: "tracked", label: "间歇在线", detail: device.notes || "IoT/摄像头可能按需唤醒或短时离线" };
    }
    const role = `${device.role || ""}`.toLowerCase();
    if (role.includes("laptop") || role.includes("desktop")) {
      return { ...device, status: "tracked", label: "可能休眠", detail: device.notes || "电脑休眠或关机不一定是网络故障" };
    }
    if (role.includes("phone")) {
      return { ...device, status: "tracked", label: "可能外出", detail: device.notes || "手机离家或切到蜂窝网络不算故障" };
    }
    return { ...device, status: "warn", label: "未看到", detail: device.notes || "未在当前流量/DHCP 证据中出现" };
  });
}

function statusSummary(items: Array<{ status?: Status }>) {
  const ok = items.filter((item) => statusClass(item.status) === "ok").length;
  const bad = items.filter((item) => statusClass(item.status) === "bad").length;
  const warn = items.filter((item) => statusClass(item.status) === "warn").length;
  const tracked = items.filter((item) => statusClass(item.status) === "tracked").length;
  return { ok, bad, warn, tracked, total: ok + bad + warn };
}

function shortStatus(status?: Status) {
  const cls = statusClass(status);
  if (cls === "ok") return "正常";
  if (cls === "bad") return "异常";
  if (cls === "warn") return "注意";
  if (cls === "tracked") return "已记录";
  return "等待";
}

function firstAction(state: State, ops: OpsModel) {
  const domains = state.incident?.domains || [];
  const badDomain = domains.find((domain) => statusClass(domain.status) === "bad");
  const warnDomain = domains.find((domain) => statusClass(domain.status) === "warn");
  const domain = badDomain || warnDomain;
  if (domain?.next_action) return domain.next_action;
  if (ops.badServices.length) return `先检查 ${ops.badServices[0].name || ops.badServices[0].key}`;
  if (ops.badHealth.length) return ops.badHealth[0].detail || ops.badHealth[0].title || "检查健康项";
  if (!ops.opsNetwork.ok) return "检修 Wi-Fi 需要确认";
  return "无需处理";
}

function useOpsModel(state: State, query: string) {
  return useMemo(() => {
    const services = state.home_services || [];
    const ingress = state.ingress || [];
    const serviceStats = statusSummary([...services, ...ingress]);
    const badServices = services.filter((service) => statusClass(service.status) === "bad");
    const presence = state.presence || {};
    const remoteAccess = state.remote_access || {};
    const opsNetwork = state.ops_network || {};
    const remoteClients = (remoteAccess.clients || []).filter((client) => client.enabled !== false && client.status !== "idle");
    const activeRemoteClients = remoteClients.filter((client) => client.endpoint_scope === "outside" && (client.status === "active" || client.status === "recent"));
    const activeDevices = (state.devices || []).filter((device) => (device.up_mbps || 0) + (device.down_mbps || 0) > 0.01);
    const inventory = deviceInventory(state);
    const serviceHosts = Array.from(new Map(
      services
        .flatMap((service) => (service.ports || []).map((port) => ({
          host: port.host || "unknown",
          owner: port.owner || service.name || service.key || "service",
          service: port.service || service.name || service.key || "service"
        })))
        .filter((item) => item.host !== "unknown")
        .map((item) => [item.host, item])
    ).values());
    const badHealth = (state.health?.checks || []).filter((check) => statusClass(check.status) !== "ok");
    const q = query.trim().toLowerCase();
    const visibleServices = q
      ? services.filter((service) => `${service.name} ${service.kind} ${service.role} ${service.href} ${service.local_href}`.toLowerCase().includes(q))
      : services;

    const issues = [
      ...badServices.slice(0, 4).map((service) => ({
        title: service.name || service.key || "Service",
        detail: service.detail || service.role || "service check failed",
        status: service.status || "bad"
      })),
      ...badHealth.slice(0, 4).map((check) => ({
        title: check.title || "Health check",
        detail: check.detail || "",
        status: check.status || "warn"
      }))
    ].slice(0, 6);
    const allGood = state.ok && !issues.length && (opsNetwork.ok !== false);

    return {
      services,
      ingress,
      visibleServices,
      badServices,
      badHealth,
      issues,
      allGood,
      activeDevices,
      deviceInventory: inventory,
      serviceHosts,
      topRoute: (state.route_summary || [])[0],
      serviceStats,
      ports: state.ports || [],
      presence,
      remoteAccess,
      opsNetwork,
      homeClients: presence.merged_clients || [],
      remoteClients,
      activeRemoteClients,
      hasDevices: (state.devices || []).length > 0,
      hasRoutes: (state.route_summary || []).length > 0,
      hasDomains: (state.domains || []).length > 0,
      hasDnsHotspots: (state.dns_top_devices || []).length > 0
    };
  }, [query, state]);
}

type OpsModel = ReturnType<typeof useOpsModel>;

function App() {
  const [state, setState] = useState<State>(emptyState);
  const [view, setView] = useState<View>("status");
  const [query, setQuery] = useState("");
  const [connected, setConnected] = useState(false);

  useEffect(() => {
    let closed = false;
    let events: EventSource | null = null;
    let reconnectAfter = 0;

    const refreshHealth = async () => {
      try {
        const response = await fetch("/api/health", { cache: "no-store" });
        if (!response.ok) return;
        const data = await response.json();
        if (!closed) {
          setState((current) => ({
            ...current,
            health: { updated_at: data.updated_at, checks: data.checks || [] },
            errors: data.errors || current.errors
          }));
        }
      } catch {
        // The live sampler still owns the main connection state.
      }
    };

    const loadOnce = async () => {
      try {
        const response = await fetch("/api/state", { cache: "no-store" });
        if (!response.ok) throw new Error(`HTTP ${response.status}`);
        const data = await response.json();
        if (!closed) {
          setState({ ...emptyState, ...data });
          setConnected(true);
        }
      } catch {
        if (!closed) setConnected(false);
      }
    };

    const connectEvents = () => {
      if (closed || events || Date.now() < reconnectAfter) return;
      try {
        events = new EventSource("/events");
        events.onmessage = (event) => {
          setState({ ...emptyState, ...JSON.parse(event.data) });
          setConnected(true);
        };
        events.onerror = () => {
          setConnected(false);
          events?.close();
          events = null;
          reconnectAfter = Date.now() + 10000;
        };
      } catch {
        setConnected(false);
        reconnectAfter = Date.now() + 10000;
      }
    };

    loadOnce();
    refreshHealth();
    connectEvents();

    const timer = window.setInterval(() => {
      if (!events) {
        loadOnce();
        connectEvents();
      }
    }, 3500);

    return () => {
      closed = true;
      window.clearInterval(timer);
      events?.close();
    };
  }, []);

  const ops = useOpsModel(state, query);

  return (
    <main className="appShell">
      <header className="topbar">
        <div className="brand">
          <span><Home size={22} /></span>
          <div>
            <h1>HomeNet</h1>
            <p>家庭网络入口</p>
          </div>
        </div>
        <div className={`livePill ${connected ? "ok" : "bad"}`}>
          <span />
          {connected ? "Live" : "Reconnecting"}
        </div>
      </header>

      <nav className="segmented" aria-label="HomeNet views">
        {viewLabels.map((item) => (
          <button className={view === item.id ? "active" : ""} key={item.id} onClick={() => setView(item.id)}>
            {item.icon}
            {item.label}
          </button>
        ))}
      </nav>

      {view === "status" && (
        <OverviewView state={state} ops={ops} />
      )}

      {view === "topology" && (
        <section className="topologyView">
          <div className="sectionHeader">
            <div>
              <h2>家庭网络拓扑</h2>
              <p>按真实使用场景看路径：日常上网、卧室覆盖、外部回家、检修通道。</p>
            </div>
          </div>
          <Topology state={state} />
        </section>
      )}

      {view === "services" && (
        <ServicesView ops={ops} query={query} onQueryChange={setQuery} />
      )}

      {view === "routing" && (
        <RoutingView />
      )}
    </main>
  );
}

function OverviewView({ state, ops }: { state: State; ops: OpsModel }) {
  const primaryServices = ["homenet-ops", "openwrt-luci", "wrt-room-luci", "mihomo", "adguard"]
    .map((key) => ops.services.find((service) => service.key === key))
    .filter(Boolean) as HomeService[];
  const issueCount = ops.issues.length + (state.errors || []).length;
  const overall = ops.allGood ? "正常" : issueCount ? "需要处理" : "需要确认";
  const nextStep = (state.incident?.decision_flow || []).find((step) => ["bad", "warn"].includes(statusClass(step.status)));
  const activeDomains = (state.incident?.domains || []).filter((domain) => ["bad", "warn"].includes(statusClass(domain.status)));
  const domain = (id: string) => state.incident?.domains?.find((item) => item.id === id);
  const nextEntries = nextStep?.entries || [];

  return (
    <section className="simpleBoard">
      <Panel title="现在" icon={<Sparkles size={18} />}>
        <div className={`bigVerdict ${ops.allGood ? "ok" : "warn"}`}>
          {ops.allGood ? <CheckCircle2 size={30} /> : <AlertTriangle size={30} />}
          <div>
            <span>{overall}</span>
            <b>{state.incident?.headline || "家庭网络状态"}</b>
            <p>{firstAction(state, ops)}</p>
          </div>
        </div>
        <div className="plainChecks">
          <PlainCheck label="主路由/WAN" status={domain("gateway-wan")?.status || (state.ok ? "ok" : "warn")} detail={`${number(state.wan?.down_mbps)} Mbps down`} />
          <PlainCheck label="Wi-Fi/卧室" status={domain("room-ap")?.status || (state.wifi_diagnostics?.ok ? "ok" : "warn")} detail={state.wifi_diagnostics?.room_reachable ? "卧室 WRT 可达" : "等待卧室 WRT"} />
          <PlainCheck label="DNS/代理" status={domain("dns-proxy")?.status || "unknown"} detail={ops.topRoute?.chain || "当前无明显代理流量"} />
          <PlainCheck label="Pi 服务" status={domain("server-runtime")?.status || (ops.badServices.length ? "warn" : "ok")} detail={`${ops.serviceStats.ok}/${ops.serviceStats.total || 0} 正常`} />
          <PlainCheck label="外部回家" status={domain("remote-access")?.status || (ops.remoteAccess.ok ? "ok" : "warn")} detail={`${ops.activeRemoteClients.length} 台外部设备`} />
          <PlainCheck label="检修通道" status={domain("rescue-path")?.status || (ops.opsNetwork.ok ? "ok" : "warn")} detail={ops.opsNetwork.ssid || "Maintenance Wi-Fi"} />
        </div>
      </Panel>

      <Panel title="排障" icon={<Wrench size={18} />}>
        <div className="nextStep">
          {nextStep ? (
            <article className={statusClass(nextStep.status)}>
              {statusIcon(nextStep.status)}
              <span>
                <b>{nextStep.question}</b>
                <p>{(nextStep.if_bad || [])[0] || nextStep.why_first || "先定位故障域。"}</p>
                {!!nextEntries.length && <code>{nextEntries.slice(0, 2).join(" · ")}</code>}
              </span>
            </article>
          ) : (
            <article className="ok">
              <CheckCircle2 size={18} />
              <span>
                <b>不用处理</b>
                <p>关键链路正常；需要操作时从常用入口进入 source tool。</p>
              </span>
            </article>
          )}
        </div>
        <div className="simpleList condensed">
          {activeDomains.slice(0, 2).map((item) => <SimpleDomain domain={item} key={item.id || item.title} />)}
          {ops.issues.slice(0, 2).map((item, index) => <SimpleIssue item={item} key={`${item.title}-${index}`} />)}
          {!activeDomains.length && !ops.issues.length && <EmptyLine text="没有明显异常。" />}
        </div>
      </Panel>

      <Panel title="常用入口" icon={<Home size={18} />}>
        <div className="entryList">
          {primaryServices.map((service) => <ServiceRow key={service.key || service.name} service={service} compact />)}
        </div>
      </Panel>
    </section>
  );
}

function PlainCheck({ label, status, detail }: { label: string; status?: Status; detail: string }) {
  return (
    <article className={statusClass(status)}>
      {statusIcon(status)}
      <span>{label}</span>
      <b>{shortStatus(status)}</b>
      <p>{detail}</p>
    </article>
  );
}

function SimpleIssue({ item }: { item: { title?: string; detail?: string; status?: Status } }) {
  return (
    <article className={statusClass(item.status)}>
      {statusIcon(item.status)}
      <span>
        <b>{item.title || "需要确认"}</b>
        <p>{item.detail || "没有详细信息"}</p>
      </span>
    </article>
  );
}

function SimpleDomain({ domain }: { domain: IncidentDomain }) {
  return (
    <article className={statusClass(domain.status)}>
      {statusIcon(domain.status)}
      <span>
        <b>{domain.title}</b>
        <p>{domain.next_action || domain.detail || domain.evidence || shortStatus(domain.status)}</p>
      </span>
    </article>
  );
}

function ServicesView({ ops, query, onQueryChange }: { ops: OpsModel; query: string; onQueryChange: (value: string) => void }) {
  return (
    <section className="servicesView">
      <div className="sectionHeader">
        <div>
          <h2>Services</h2>
          <p>Service Directory 按职责分组；服务可以运行在 Pi、OpenWrt、Mac 或其他 LAN host 上。</p>
        </div>
        <label className="searchBox">
          <Search size={16} />
          <input value={query} onChange={(event) => onQueryChange(event.target.value)} placeholder="Filter services" />
        </label>
      </div>
      {!!ops.serviceHosts.length && (
        <section className="hostStrip" aria-label="Service hosts">
          {ops.serviceHosts.slice(0, 8).map((host) => (
            <article key={host.host}>
              <b>{host.host}</b>
              <span>{host.owner}</span>
            </article>
          ))}
        </section>
      )}
      {serviceGroupEntries(ops.visibleServices).map(([kind, items]) => (
        <section className="serviceGroup" key={kind}>
          <div className="serviceGroupHeader">
            <h3>{groupLabel(kind)}</h3>
            <p>{groupDescription(kind)}</p>
          </div>
          <div className="serviceGrid">
            {items.map((service) => <ServiceCard key={service.key || service.name} service={service} />)}
          </div>
        </section>
      ))}
      {!ops.visibleServices.length && <EmptyBlock title="No services" text="没有匹配的服务。" />}
    </section>
  );
}

function RoutingView() {
  const [rules, setRules] = useState<RoutingRulesState>({ entries: [] });
  const [target, setTarget] = useState("");
  const [policy, setPolicy] = useState("PROXY");
  const [duration, setDuration] = useState("1h");
  const [busy, setBusy] = useState(false);
  const [message, setMessage] = useState("");

  const loadRules = async () => {
    const response = await fetch("/api/routing-rules", { cache: "no-store" });
    const data = await response.json();
    setRules(data);
  };

  useEffect(() => {
    loadRules().catch(() => setRules({ entries: [], error: "无法读取分流规则。" }));
  }, []);

  const submitRule = async (permanent: boolean) => {
    if (permanent && !window.confirm(`确认把 ${target.trim()} 加入永久规则？\n\n永久规则会进入待提交队列，不会立刻改变当前流量。`)) return;
    setBusy(true);
    setMessage("");
    try {
      const response = await fetch("/api/routing-rules", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ target, policy, duration, permanent })
      });
      const data = await response.json();
      if (!response.ok || !data.ok) throw new Error(data.error || data.detail || `HTTP ${response.status}`);
      setTarget("");
      setRules({ ...rules, entries: data.entries || [], permanent_candidates: data.permanent_candidates || rules.permanent_candidates || [] });
      setMessage(permanent ? "已加入永久待提交，当前流量未改变。" : "临时规则已生效。");
    } catch (error) {
      setMessage(error instanceof Error ? error.message : "操作失败。");
    } finally {
      setBusy(false);
    }
  };

  const deleteRule = async (id?: string) => {
    if (!id) return;
    setBusy(true);
    setMessage("");
    try {
      const response = await fetch(`/api/routing-rules/${encodeURIComponent(id)}`, { method: "DELETE" });
      const data = await response.json();
      if (!response.ok || !data.ok) throw new Error(data.error || data.detail || `HTTP ${response.status}`);
      setRules({ ...rules, entries: data.entries || [], permanent_candidates: data.permanent_candidates || rules.permanent_candidates || [] });
      setMessage("已删除。");
    } catch (error) {
      setMessage(error instanceof Error ? error.message : "删除失败。");
    } finally {
      setBusy(false);
    }
  };

  const promoteRule = async (id?: string) => {
    if (!id) return;
    if (!window.confirm("确认转为永久？\n\n临时规则会继续保留，永久规则会进入待提交队列。")) return;
    setBusy(true);
    setMessage("");
    try {
      const response = await fetch(`/api/routing-rules/${encodeURIComponent(id)}/promote`, { method: "POST" });
      const data = await response.json();
      if (!response.ok || !data.ok) throw new Error(data.error || data.detail || `HTTP ${response.status}`);
      setRules({ ...rules, entries: data.entries || [], permanent_candidates: data.permanent_candidates || rules.permanent_candidates || [] });
      setMessage("已加入永久待提交，临时规则保持不变。");
    } catch (error) {
      setMessage(error instanceof Error ? error.message : "转永久失败。");
    } finally {
      setBusy(false);
    }
  };

  const deletePermanent = async (id?: string) => {
    if (!id) return;
    setBusy(true);
    setMessage("");
    try {
      const response = await fetch(`/api/routing-permanent/${encodeURIComponent(id)}`, { method: "DELETE" });
      const data = await response.json();
      if (!response.ok || !data.ok) throw new Error(data.error || `HTTP ${response.status}`);
      setRules({ ...rules, entries: data.entries || [], permanent_candidates: data.permanent_candidates || [] });
      setMessage("已移除永久待提交。");
    } catch (error) {
      setMessage(error instanceof Error ? error.message : "删除失败。");
    } finally {
      setBusy(false);
    }
  };

  const entries = rules.entries || [];
  const tempEntries = entries;
  const permanentCandidates = rules.permanent_candidates || [];

  return (
    <section className="routingView">
      <div className="sectionHeader">
        <div>
          <h2>临时分流</h2>
          <p>把某个网站切到指定出口。临时规则立即生效；永久规则会先进入待提交队列。</p>
        </div>
      </div>

      <Panel title="添加规则" icon={<Globe2 size={18} />} description="粘贴完整网址或域名即可，系统会自动提取主域名。">
        <div className="routingForm">
          <label>
            <span>网站</span>
            <input value={target} onChange={(event) => setTarget(event.target.value)} placeholder="example.com 或 https://example.com/page" />
          </label>
          <label>
            <span>出口</span>
            <select value={policy} onChange={(event) => setPolicy(event.target.value)}>
              {(rules.policies || [
                { id: "PROXY", label: "PROXY" },
                { id: "PROXY-JAPAN", label: "PROXY-JAPAN" },
                { id: "DIRECT", label: "DIRECT" }
              ]).map((item) => <option value={item.id} key={item.id}>{item.label}</option>)}
            </select>
          </label>
          <label>
            <span>有效期</span>
            <select value={duration} onChange={(event) => setDuration(event.target.value)}>
              <option value="1h">1 小时</option>
              <option value="today">今天</option>
              <option value="7d">7 天</option>
              <option value="forever">直到删除</option>
            </select>
          </label>
          <div className="routingActions">
            <button disabled={busy || !target.trim()} onClick={() => submitRule(false)}><RefreshCw size={16} />临时生效</button>
            <button disabled={busy || !target.trim()} onClick={() => submitRule(true)}><Save size={16} />永久</button>
          </div>
        </div>
        {!!message && <p className="formMessage">{message}</p>}
      </Panel>

      <div className="routingColumns">
        <RoutingRuleList title="临时生效" entries={tempEntries} onDelete={deleteRule} onPromote={promoteRule} />
        <RoutingPermanentList entries={permanentCandidates} onDelete={deletePermanent} />
      </div>
    </section>
  );
}

function RoutingRuleList({ title, entries, onDelete, onPromote }: { title: string; entries: RoutingRule[]; onDelete: (id?: string) => void; onPromote?: (id?: string) => void }) {
  return (
    <Panel title={title} icon={<Layers3 size={18} />}>
      <div className="routingList">
        {entries.map((item) => (
          <article key={item.id || item.value}>
            <span>
              <b>{item.value}</b>
              <p>{item.policy} · {item.rule}</p>
              <em>{item.expires_at ? `到期 ${relativeTime(item.expires_at).replace("ago", "后")}` : "直到删除"}</em>
            </span>
            <div>
              {onPromote && <button onClick={() => onPromote(item.id)} title="转永久"><Save size={15} /></button>}
              <button onClick={() => onDelete(item.id)} title="删除"><Trash2 size={15} /></button>
            </div>
          </article>
        ))}
        {!entries.length && <EmptyLine text="暂无规则。" />}
      </div>
    </Panel>
  );
}

function RoutingPermanentList({ entries, onDelete }: { entries: RoutingPermanentCandidate[]; onDelete: (id?: string) => void }) {
  return (
    <Panel title="永久待提交" icon={<Save size={18} />}>
      <div className="routingList">
        {entries.map((item) => (
          <article key={item.id || `${item.policy}-${item.value}`}>
            <span>
              <b>{item.value}</b>
              <p>{item.policy} · {item.rule}</p>
              <em>等待确认提交</em>
            </span>
            <div>
              <button onClick={() => onDelete(item.id)} title="删除"><Trash2 size={15} /></button>
            </div>
          </article>
        ))}
        {!entries.length && <EmptyLine text="暂无永久待提交。" />}
      </div>
    </Panel>
  );
}

function Topology({ state }: { state: State }) {
  const domainStatus = (id: string, fallback: Status = "unknown") => state.incident?.domains?.find((item) => item.id === id)?.status || fallback;
  const ops = state.ops_network || {};
  const roomOk = state.wifi_diagnostics?.room_reachable;
  const roomIp = state.instance?.devices?.find((device) => device.id === "wrt-room")?.ip || "声明的管理地址";
  const devices = deviceInventory(state);
  const macStudio = devices.find((device) => device.id === "macstudio" || device.id === "macstudio-wifi");
  const wifiChecks = state.wifi_diagnostics?.checks || [];
  const radioCheck = wifiChecks.find((check) => `${check.title || ""}`.includes("radio1"));
  const roomCheck = wifiChecks.find((check) => `${check.title || ""}`.includes("卧室 WRT")) || state.incident?.domains?.find((item) => item.id === "room-ap");
  const serverDomain = state.incident?.domains?.find((item) => item.id === "server-runtime");
  const powerRecovery = [
    {
      title: "主路由 5G",
      status: radioCheck?.status || domainStatus("main-wifi-5g", state.wifi_diagnostics?.ok ? "ok" : "warn"),
      detail: radioCheck?.detail || "确认 radio1、主 Wi-Fi 5G 和卧室回程 SSID。",
      action: "5G 不起时只处理 radio1，不改 DNS/Proxy。"
    },
    {
      title: "卧室 WRT",
      status: roomCheck?.status || (roomOk ? "ok" : "warn"),
      detail: roomCheck?.detail || (roomOk ? `${roomIp} 可达` : `${roomIp} 暂不可达`),
      action: "主 5G 正常后再看回程、电源和房间侧后台。"
    },
    {
      title: "Pi 服务",
      status: serverDomain?.status || (state.ok ? "ok" : "warn"),
      detail: serverDomain?.evidence || `${state.home_services?.filter((service) => statusClass(service.status) === "ok").length || 0}/${state.home_services?.length || 0} 服务正常`,
      action: "多个服务一起坏时先看 Docker/systemd。"
    },
    {
      title: "Mac Studio",
      status: macStudio?.status || "unknown",
      detail: macStudio?.detail || "未在当前 DHCP/流量证据中看到",
      action: "关机或 FileVault 登录前不可远程桌面，先确认电源和系统登录状态。"
    }
  ];
  const paths = [
    {
      id: "daily",
      title: "日常上网",
      status: domainStatus("dns-proxy", state.ok ? "ok" : "warn"),
      route: ["手机/电脑", "Main Wi-Fi", "OpenWrt 主路由", "AdGuard / Mihomo", "公网"],
      note: `WAN ${number(state.wan?.down_mbps)} Mbps，代理 ${state.route_summary?.[0]?.chain || "空闲"}`,
      action: "国内慢看 DIRECT/DNS，国外慢看 Mihomo 代理组。"
    },
    {
      id: "room",
      title: "卧室覆盖",
      status: domainStatus("room-ap", roomOk ? "ok" : "warn"),
      route: ["手机/电脑", "Main Wi-Fi", "卧室 WRT", "主路由"],
      note: roomOk ? `主网侧 ${roomIp} 可达` : "卧室 WRT 等待确认",
      action: "主网侧用声明的管理地址；直接连房间 AP 时看本机网关。"
    },
    {
      id: "remote",
      title: "外部回家",
      status: domainStatus("remote-access", state.remote_access?.ok ? "ok" : "warn"),
      route: ["外部设备", "Cloudflare / WireGuard", "Pi", "家庭服务"],
      note: `${state.remote_access?.clients?.filter((client) => client.status === "active" || client.status === "recent").length || 0} 台近期连接`,
      action: "外部打不开时先确认 LAN 入口，再看 Cloudflare/WireGuard。"
    },
    {
      id: "rescue",
      title: "检修通道",
      status: domainStatus("rescue-path", ops.ok ? "ok" : "warn"),
      route: ["维护设备", ops.ssid || "Maintenance Wi-Fi", "公共 DNS / 直出", "Pi :9999"],
      note: ops.ok ? "检修 Wi-Fi 就绪" : "检修 Wi-Fi 需要确认",
      action: "主网络复杂路径坏了，用它进 Pi 和 Codex 排查。"
    }
  ];

  return (
    <>
      <div className="simpleTopology" aria-label="Home network topology">
        {paths.map((path) => (
          <article className={statusClass(path.status)} key={path.id}>
            <header>
              {statusIcon(path.status)}
              <div>
                <h3>{path.title}</h3>
                <p>{path.note}</p>
              </div>
              <b>{shortStatus(path.status)}</b>
            </header>
            <div className="routeLine">
              {path.route.map((item) => <span key={`${path.id}-${item}`}>{item}</span>)}
            </div>
            <p>{path.action}</p>
          </article>
        ))}
      </div>

      <Panel title="断电恢复" icon={<RadioTower size={18} />} description="来电后只看这四项；它们正常后，再处理单个服务或设备。">
        <div className="recoveryGrid">
          {powerRecovery.map((item) => (
            <article className={statusClass(item.status)} key={item.title}>
              <header>
                {statusIcon(item.status)}
                <span>{item.title}</span>
                <b>{shortStatus(item.status)}</b>
              </header>
              <p>{item.detail}</p>
              <em>{item.action}</em>
            </article>
          ))}
        </div>
      </Panel>
    </>
  );
}

function Panel({ title, icon, description, children }: { title: string; icon: React.ReactNode; description?: string; children: React.ReactNode }) {
  return (
    <section className="panel">
      <header className="panelTitle">{icon}<h2>{title}</h2></header>
      {description && <p className="panelIntro">{description}</p>}
      {children}
    </section>
  );
}

function ServiceCard({ service }: { service: HomeService }) {
  const links = serviceLinks(service);
  const hasWebUi = links.length > 0;
  return (
    <article className={`serviceCard ${statusClass(service.status)}`}>
      <div className="serviceHead">
        <span>{statusIcon(service.status)}</span>
        <b>{service.name || service.key || "Service"}</b>
      </div>
      <p>{service.role || service.kind || "service"}</p>
      <div className="serviceMeta">
        <span>{service.detail || service.status || "unknown"}</span>
        <span>{portSummary(service.ports || [])}</span>
        {!hasWebUi && <span>无 Web UI</span>}
        {typeof service.latency_ms === "number" && <span>{service.latency_ms} ms</span>}
      </div>
      <ServicePorts ports={service.ports || []} />
      {!!links.length && (
        <div className="serviceActions">
          {links.map((link) => <a key={`${service.key}-${link.label}`} href={link.href} target="_blank" rel="noreferrer">{link.label} <ArrowUpRight size={14} /></a>)}
        </div>
      )}
    </article>
  );
}

function ServicePorts({ ports }: { ports: PortEntry[] }) {
  if (!ports.length) return null;
  return (
    <div className="portChips">
      {ports.map((port, index) => (
        <span key={`${port.host}-${port.port}-${port.proto}-${index}`} title={`${port.service || ""} · ${port.scope || ""} · ${port.note || ""}`}>
          {port.port || ""}/{port.proto || ""} · {portScopeLabel(port.scope)}
        </span>
      ))}
    </div>
  );
}

function ServiceRow({ service, compact = false }: { service: HomeService | Ingress; compact?: boolean }) {
  const links = serviceLinks(service);
  return (
    <article className={`serviceRow ${compact ? "compact" : ""} ${statusClass(service.status)}`}>
      {statusIcon(service.status)}
      <span>
        <b>{service.name || service.key || "Entry"}</b>
        <p>{serviceDescription(service)}</p>
      </span>
      <div className="serviceActions compact">
        {links.map((link) => <a key={`${service.key}-${link.label}`} href={link.href} target="_blank" rel="noreferrer">{link.label}</a>)}
      </div>
    </article>
  );
}

function EmptyLine({ text }: { text: string }) {
  return <p className="emptyLine">{text}</p>;
}

function EmptyBlock({ title, text }: { title: string; text: string }) {
  return (
    <section className="emptyBlock">
      <Wifi size={28} />
      <h2>{title}</h2>
      <p>{text}</p>
    </section>
  );
}

createRoot(document.getElementById("root")!).render(<App />);
