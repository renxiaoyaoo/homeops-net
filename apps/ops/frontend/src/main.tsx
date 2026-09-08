import React, { useEffect, useMemo, useState } from "react";
import { createRoot } from "react-dom/client";
import {
  AlertTriangle,
  ArrowUpRight,
  CheckCircle2,
  Compass,
  Globe2,
  Home,
  Layers3,
  Laptop,
  RadioTower,
  RefreshCw,
  Save,
  Search,
  Trash2,
  Wifi,
  Wrench,
  XCircle
} from "lucide-react";
import "./styles.css";

type Status = "ok" | "warn" | "bad" | "down" | "tracked" | "unknown" | string;
type View = "home" | "topology" | "devices" | "routing" | "services";

type ConsoleLayer = {
  id?: string;
  title?: string;
  status?: Status;
  label?: string;
  detail?: string;
  next_action?: string;
  entry?: string;
};

type ConsoleEntry = {
  id?: string;
  label?: string;
  name?: string;
  status?: Status;
  local_href?: string;
  href?: string;
  role?: string;
};

type ConsoleSummary = {
  ok?: boolean;
  severity?: Status;
  headline?: string;
  active_problem?: ConsoleLayer | null;
  layers?: ConsoleLayer[];
  entries?: ConsoleEntry[];
  unmanaged_ports?: number[];
  unmanaged_port_count?: number;
  current_error_count?: number;
  historical_error_count?: number;
  foundation_checks?: ConsoleLayer[];
  network_diagnostics?: ConsoleLayer[];
  network_diagnostics_summary?: string;
  room_side_entry?: string;
};

type Service = {
  key?: string;
  name?: string;
  kind?: string;
  role?: string;
  href?: string;
  local_href?: string;
  status?: Status;
  latency_ms?: number;
  detail?: string;
  ports?: Port[];
};

type Port = {
  host?: string;
  port?: string;
  proto?: string;
  service?: string;
  owner?: string;
  scope?: string;
  note?: string;
};

type RoutingRule = {
  id?: string;
  policy?: string;
  value?: string;
  rule?: string;
  expires_at?: number | null;
};

type RoutingCandidate = {
  id?: string;
  policy?: string;
  value?: string;
  rule?: string;
  status?: string;
};

type RoutingState = {
  ok?: boolean;
  policies?: Array<{ id: string; label: string }>;
  entries?: RoutingRule[];
  permanent_candidates?: RoutingCandidate[];
  error?: string;
};

type Device = {
  id?: string;
  name?: string;
  role?: string;
  network?: string;
  ip?: string;
  current_ip?: string;
  expected?: boolean;
  presence?: string;
  expected_macs?: string[];
  current_mac?: string;
  lease_mac?: string;
  neighbor_mac?: string;
  hostname?: string;
  neighbor_state?: string;
  status?: Status;
  detail?: string;
  evidence?: string[];
  via_room_relay?: boolean;
};

type State = {
  ok?: boolean;
  updated_at?: number;
  errors?: string[];
  error_events?: string[];
  wan?: { down_mbps?: number; up_mbps?: number };
  mihomo?: { down_mbps?: number; up_mbps?: number };
  home_services?: Service[];
  ports?: Port[];
  devices?: { ok?: boolean; summary?: { total?: number; online?: number; attention?: number; standby?: number }; items?: Device[] };
  console?: ConsoleSummary;
  foundation_checks?: { ok?: boolean; checks?: ConsoleLayer[]; room_side_entry?: string };
  network_diagnostics?: { ok?: boolean; summary?: string; checks?: ConsoleLayer[]; updated_at?: number };
  instance?: {
    site?: { display_name?: string; name?: string; domain?: string };
    networks?: Record<string, { cidr?: string; purpose?: string; dns_mode?: string; proxy_mode?: string }>;
    wifi?: Record<string, { ssid?: string; network?: string; band?: string; purpose?: string; broadcast_by?: string[] }>;
  };
  remote_access?: { clients?: Array<{ status?: Status; endpoint_scope?: string; name?: string }> };
  ops_network?: { ok?: boolean; ssid?: string; gateway?: string; dns?: string; clients?: Array<{ ip?: string; name?: string }> };
};

const emptyState: State = {
  home_services: [],
  ports: [],
  devices: { summary: {}, items: [] },
  console: { layers: [], entries: [], unmanaged_ports: [] },
  instance: { networks: {}, wifi: {} },
  remote_access: { clients: [] },
  ops_network: {}
};

const tabs: Array<{ id: View; label: string; icon: React.ReactNode }> = [
  { id: "home", label: "首页", icon: <Compass size={16} /> },
  { id: "topology", label: "拓扑", icon: <RadioTower size={16} /> },
  { id: "devices", label: "设备", icon: <Laptop size={16} /> },
  { id: "routing", label: "分流", icon: <Globe2 size={16} /> },
  { id: "services", label: "服务", icon: <Layers3 size={16} /> }
];

const layerOrder = ["gateway-wan", "main-wifi-5g", "room-ap", "dns-proxy", "server-runtime", "remote-access"];
const layerLabels: Record<string, string> = {
  "gateway-wan": "WAN / Gateway",
  "main-wifi-5g": "Wi-Fi / Radio",
  "room-ap": "Room AP",
  "dns-proxy": "DNS / Proxy",
  "server-runtime": "Pi Runtime",
  "remote-access": "Remote Access",
  "rescue-path": "Rescue Path",
  "client-device": "Client Device"
};

const groupOrder = ["network-core", "remote-entry", "home-core", "daily-app", "system-task", "maintenance-entry", "control-core", "other"];
const groupLabels: Record<string, string> = {
  "network-core": "网络核心",
  "remote-entry": "远程入口",
  "home-core": "智能家居",
  "daily-app": "日常应用",
  "system-task": "后台任务",
  "maintenance-entry": "维护入口",
  "control-core": "控制组件",
  other: "其他"
};

const groupDescriptions: Record<string, string> = {
  "network-core": "路由、DNS、Proxy、卧室 AP 等基础能力。",
  "remote-entry": "Cloudflare、WireGuard、Caddy、DDNS 等外部回家入口。",
  "home-core": "Home Assistant、HomeKit、MQTT、Zigbee、摄像头相关服务。",
  "daily-app": "日常会打开的自建应用和文件入口。",
  "system-task": "更新、同步、presence、采集、备份等无 UI 任务。",
  "maintenance-entry": "OpenWrt、WRT Room、Pi SSH、HomeNet Console 等排障入口。",
  "control-core": "支撑监控、告警、同步和控制面的组件。",
  other: "暂未归类。"
};

function cls(status?: Status) {
  if (status === "ok") return "ok";
  if (status === "warn") return "warn";
  if (status === "bad" || status === "down" || status === "offline") return "bad";
  if (status === "tracked" || status === "sleeping") return "warn";
  return "unknown";
}

function icon(status?: Status) {
  const c = cls(status);
  if (c === "ok") return <CheckCircle2 size={16} />;
  if (c === "bad") return <XCircle size={16} />;
  if (c === "warn") return <AlertTriangle size={16} />;
  return <Wrench size={16} />;
}

function label(status?: Status) {
  if (status === "offline") return "离线";
  if (status === "sleeping" || status === "tracked") return "离线";
  const c = cls(status);
  if (c === "ok") return "正常";
  if (c === "bad") return "异常";
  if (c === "warn") return "注意";
  return "等待";
}

function statusRank(status?: Status) {
  const c = cls(status);
  if (c === "bad") return 4;
  if (c === "warn") return 3;
  if (c === "unknown") return 2;
  return 0;
}

function allChecks(state: State) {
  const summary = state.console || {};
  return [
    ...(summary.network_diagnostics || []),
    ...(state.network_diagnostics?.checks || []),
    ...(summary.foundation_checks || []),
    ...(state.foundation_checks?.checks || []),
    ...(summary.layers || [])
  ];
}

function checkById(state: State, id: string) {
  return allChecks(state).find((item) => item.id === id);
}

function statusIsProblem(status?: Status) {
  return ["bad", "warn", "down", "offline"].includes(cls(status));
}

type HomeIncident = {
  status: Status;
  title: string;
  summary: string;
  action: string;
  entry?: string;
  evidence: string[];
};

function buildHomeIncident(state: State): HomeIncident {
  const get = (id: string) => checkById(state, id);
  const wanRecovery = get("wan-recovery");
  const wan = get("wan-domestic") || get("gateway-wan");
  const domestic = get("http-domestic");
  const google = get("http-google");
  const github = get("http-github");
  const room = get("wifi-room-backhaul") || get("room-ap");
  const mihomo = get("mihomo-current");
  const pi = get("server-runtime");
  const dns = get("dns-proxy");
  const reboot = get("router-reboot-detected");

  const evidence = (...items: Array<ConsoleLayer | undefined>) =>
    items
      .filter(Boolean)
      .slice(0, 4)
      .map((item) => `${item!.title || item!.id}: ${item!.detail || label(item!.status)}`);

  if (wanRecovery && cls(wanRecovery.status) === "bad") {
    return {
      status: "bad",
      title: "宽带恢复失败",
      summary: "主路由拿到地址但外网不通，自动只重拨 WAN 也没有恢复。",
      action: "进 OpenWrt 看 WAN/PPPoE；必要时手动重拨或重启主路由。",
      entry: wanRecovery.entry || "http://192.168.10.1/cgi-bin/luci",
      evidence: evidence(wanRecovery, wan, domestic)
    };
  }

  if (wanRecovery && cls(wanRecovery.status) === "warn") {
    return {
      status: "warn",
      title: "宽带疑似假在线",
      summary: "网关还活着，但公网连通异常。系统会连续确认后只重拨 WAN，不动 Wi-Fi/Pi/Docker。",
      action: "先等自动重拨；如果仍无网，再进 OpenWrt 处理 WAN。",
      entry: wanRecovery.entry || "http://192.168.10.1/cgi-bin/luci",
      evidence: evidence(wanRecovery, wan, domestic)
    };
  }

  if (statusIsProblem(wan?.status) || statusIsProblem(domestic?.status)) {
    return {
      status: "bad",
      title: "基础上网异常",
      summary: "国内直连或主路由 WAN 不正常，这类问题通常不是代理、不是 Home Assistant。",
      action: "先看 OpenWrt 的 WAN、PPPoE、DNS；不要先重启 Pi 上的服务。",
      entry: wan?.entry || domestic?.entry || "http://192.168.10.1/cgi-bin/luci",
      evidence: evidence(wan, domestic, reboot)
    };
  }

  if (statusIsProblem(room?.status)) {
    return {
      status: "warn",
      title: "卧室覆盖不稳",
      summary: "主网络可能正常，但卧室 WRT 与主路由之间的无线回程偏弱，卧室设备会慢或断续。",
      action: "卧室出问题时先确认设备是否连到 WRT Room；长期解法是调整位置或换更稳定回程。",
      entry: room?.entry || state.console?.room_side_entry || "http://192.168.10.2",
      evidence: evidence(room, wan, domestic)
    };
  }

  if (statusIsProblem(google?.status) || statusIsProblem(github?.status) || statusIsProblem(mihomo?.status)) {
    return {
      status: "warn",
      title: "代理路径异常",
      summary: "国内网络正常，但 Google/GitHub 或当前出口异常，问题集中在 Mihomo 节点/分流。",
      action: "打开 Mihomo，切换 PROXY / PROXY-JAPAN / AI-AUTO 当前节点。",
      entry: mihomo?.entry || "http://192.168.10.5:9090/ui/#/proxies",
      evidence: evidence(google, github, mihomo)
    };
  }

  if (statusIsProblem(pi?.status) || statusIsProblem(dns?.status)) {
    return {
      status: "warn",
      title: "Pi 或 DNS/Proxy 服务异常",
      summary: "路由层正常，但 Pi 上的 DNS、代理、Docker 或应用可能有问题。",
      action: "先看 Pi 服务和 Docker 状态，再看具体应用。",
      entry: pi?.entry || dns?.entry || "http://192.168.10.5:9999",
      evidence: evidence(pi, dns, wan)
    };
  }

  return {
    status: "ok",
    title: "当前网络正常",
    summary: "国内直连、代理路径、Pi 服务、卧室 WRT 都没有发现会阻断上网的异常。",
    action: "不用处理。某个 App 慢时再去分流或 Mihomo 切换节点。",
    entry: "http://192.168.10.5:9999",
    evidence: evidence(wan, domestic, google, room)
  };
}

function mbps(value?: number) {
  return Number(value || 0).toFixed(2);
}

function age(ts?: number | null) {
  if (!ts) return "直到删除";
  const delta = Math.max(0, Math.round(ts - Date.now() / 1000));
  if (delta < 60) return `${delta}s 后`;
  if (delta < 3600) return `${Math.round(delta / 60)}m 后`;
  return `${Math.round(delta / 3600)}h 后`;
}

function serviceGroup(service: Service) {
  const key = service.key || "";
  if (["openwrt-luci", "openwrt-ssh", "wrt-room-luci", "wrt-room-ssh", "pi-ssh", "homenet-ops"].includes(key)) return "maintenance-entry";
  if (["asset-guardian", "shadowbroker", "balcony-grow", "private-music-library", "filebrowser"].includes(key)) return "daily-app";
  if (service.kind === "storage") return "daily-app";
  if (service.kind === "udp-entry") return "remote-entry";
  return service.kind || "other";
}

function portScope(scope?: string) {
  const s = (scope || "").toLowerCase();
  if (!s) return "未标注";
  if (s === "local" || s === "localhost") return "仅本机";
  if (s.includes("wan") && s.includes("lan")) return "局域网/远程";
  if (s.includes("wan")) return "远程";
  if (s.includes("router")) return "路由内部";
  if (s.includes("lan")) return "局域网";
  return scope || "未标注";
}

function links(item: Service | ConsoleEntry) {
  return [
    item.href ? { label: "外部", href: item.href } : null,
    item.local_href ? { label: "局域网", href: item.local_href } : null
  ].filter(Boolean) as Array<{ label: string; href: string }>;
}

function useHomeState() {
  const [state, setState] = useState<State>(emptyState);
  const [connected, setConnected] = useState(false);

  useEffect(() => {
    let closed = false;
    let events: EventSource | null = null;
    let reconnectAt = 0;

    const load = async () => {
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

    const connect = () => {
      if (closed || events || Date.now() < reconnectAt) return;
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
          reconnectAt = Date.now() + 8000;
        };
      } catch {
        reconnectAt = Date.now() + 8000;
      }
    };

    load();
    connect();
    const timer = window.setInterval(() => {
      if (!events) {
        load();
        connect();
      }
    }, 4000);

    return () => {
      closed = true;
      events?.close();
      window.clearInterval(timer);
    };
  }, []);

  return { state, connected };
}

function App() {
  const { state, connected } = useHomeState();
  const [view, setView] = useState<View>("home");
  const [query, setQuery] = useState("");
  const siteName = state.instance?.site?.display_name || state.instance?.site?.name || "HomeNet";

  return (
    <main className="shell">
      <header className="topbar">
        <div className="brand">
          <span><Home size={22} /></span>
          <div>
            <h1>{siteName}</h1>
            <p>HomeNet Console · open core + private instance</p>
          </div>
        </div>
        <div className={`live ${connected ? "ok" : "bad"}`}><span />{connected ? "Live" : "Reconnect"}</div>
      </header>

      <nav className="tabs" aria-label="HomeNet views">
        {tabs.map((tab) => (
          <button className={view === tab.id ? "active" : ""} key={tab.id} onClick={() => setView(tab.id)}>
            {tab.icon}{tab.label}
          </button>
        ))}
      </nav>

      {view === "home" && <HomeView state={state} />}
      {view === "topology" && <TopologyView state={state} />}
      {view === "devices" && <DevicesView state={state} query={query} setQuery={setQuery} />}
      {view === "routing" && <RoutingView />}
      {view === "services" && <ServicesView state={state} query={query} setQuery={setQuery} />}
    </main>
  );
}

function HomeView({ state }: { state: State }) {
  const incident = buildHomeIncident(state);
  const entries = state.console?.entries || [];
  const entryMap = new Map(entries.map((entry) => [entry.id || entry.name || entry.label, entry]));
  const quickEntries = [
    entryMap.get("openwrt-luci") || { id: "openwrt-luci", label: "主路由", role: "WAN / Wi-Fi", local_href: "http://192.168.10.1/cgi-bin/luci", status: "ok" },
    entryMap.get("mihomo") || { id: "mihomo", label: "Mihomo", role: "代理节点", local_href: "http://192.168.10.5:9090/ui/#/proxies", status: "ok" },
    entryMap.get("homenet-ops") || { id: "homenet-ops", label: "Ops", role: "当前页面", local_href: "http://192.168.10.5:9999", status: "ok" },
    entryMap.get("home-assistant") || { id: "home-assistant", label: "Home Assistant", role: "智能家居", local_href: "http://192.168.10.5:8123", status: "ok" }
  ];
  const rescue = (state.console?.layers || []).find((layer) => layer.id === "rescue-path");

  return (
    <section className="homeSimple">
      <div className={`answerCard ${cls(incident.status)}`}>
        <div className="answerIcon">{icon(incident.status)}</div>
        <div>
          <span>{label(incident.status)}</span>
          <h2>{incident.title}</h2>
          <p>{incident.summary}</p>
        </div>
      </div>

      <div className="actionGrid">
        <Panel title="下一步" icon={<Wrench size={18} />}>
          <div className="nextAction">
            <b>{incident.action}</b>
            {incident.entry && <a href={incident.entry} target="_blank" rel="noreferrer">打开处理入口<ArrowUpRight size={14} /></a>}
          </div>
        </Panel>

        <Panel title="关键入口" icon={<Home size={18} />}>
          <div className="quickLinks">
            {quickEntries.map((entry) => <QuickEntry key={entry.id || entry.label} entry={entry} />)}
          </div>
        </Panel>
      </div>

      <div className="actionGrid">
        <Panel title="关键证据" icon={<Search size={18} />}>
          <ul className="evidenceList">
            {incident.evidence.map((item) => <li key={item}>{item}</li>)}
            {!incident.evidence.length && <li>等待采样。</li>}
          </ul>
        </Panel>

        <Panel title="检修通道" icon={<Wifi size={18} />}>
          <div className={`rescueLine ${cls(rescue?.status || (state.ops_network?.ok ? "ok" : "unknown"))}`}>
            {icon(rescue?.status || (state.ops_network?.ok ? "ok" : "unknown"))}
            <div>
              <b>{rescue?.title || "Ops Wi-Fi / Pi"}</b>
              <p>{rescue?.detail || "主网络复杂路径坏了：设备连检修 Wi-Fi，自己开代理访问 Codex，再让 Codex 进 Pi 排查。"}</p>
            </div>
          </div>
        </Panel>
      </div>

      <Panel title="详细排查" icon={<Layers3 size={18} />}>
        <div className="detailHint">
          <div>
            <b>首页只给结论。</b>
            <p>需要看二层、设备 MAC、服务端口、分流规则时，再进上面的拓扑 / 设备 / 分流 / 服务。</p>
          </div>
          <span>详细数据不放首页</span>
        </div>
      </Panel>
    </section>
  );
}

function TopologyView({ state }: { state: State }) {
  const layers = state.console?.layers || [];
  const byId = new Map(layers.map((layer) => [layer.id, layer]));
  const domains = layerOrder.map((id) => byId.get(id) || { id, title: layerLabels[id], status: "unknown" });
  const foundationChecks = state.console?.foundation_checks?.length
    ? state.console.foundation_checks
    : state.foundation_checks?.checks?.length
      ? state.foundation_checks.checks
      : ["gateway-wan", "main-wifi-5g", "room-ap", "server-runtime"].map((id) => byId.get(id) || { id, title: layerLabels[id], status: "unknown" });
  const networks = state.instance?.networks || {};
  const wifi = state.instance?.wifi || {};

  return (
    <section className="pageStack">
      <PageHeader title="拓扑" text="只看六个故障域。低层异常时，先修低层，不被上层服务告警淹没。" />
      <div className="topologyGrid">
        {domains.map((domain, index) => (
          <article className={`domainCard ${cls(domain.status)}`} key={domain.id}>
            <header>
              <span>{index + 1}</span>
              <div>
                <h3>{domain.title || layerLabels[domain.id || ""] || domain.id}</h3>
                <p>{domain.detail || "等待证据。"}</p>
              </div>
              <b>{label(domain.status)}</b>
            </header>
            <p>{domain.next_action || "无动作。"}</p>
          </article>
        ))}
      </div>

      <Panel title="网络和 Wi-Fi" icon={<Wifi size={18} />}>
        <div className="miniGrid">
          {Object.entries(networks).map(([id, item]) => (
            <article key={id}>
              <b>{id}</b>
              <span>{item.cidr}</span>
              <p>{item.dns_mode || "dns"} · {item.proxy_mode || "proxy"}</p>
            </article>
          ))}
        </div>
        <div className="miniGrid">
          {Object.entries(wifi).map(([id, item]) => (
            <article key={id}>
              <b>{item.ssid || id}</b>
              <span>{item.network} · {item.band}</span>
              <p>{item.purpose}</p>
            </article>
          ))}
        </div>
      </Panel>

      <Panel title="基础链路检查" icon={<RadioTower size={18} />}>
        <div className="recoveryGrid">
          {foundationChecks.map((item) => <LayerFocus key={item.id || item.title} layer={item} />)}
        </div>
        {state.console?.room_side_entry && <p className="note">连在卧室 WRT 下方时，房间侧管理入口：{state.console.room_side_entry}</p>}
      </Panel>
    </section>
  );
}

function DevicesView({ state, query, setQuery }: { state: State; query: string; setQuery: (value: string) => void }) {
  const devices = state.devices?.items || [];
  const summary = state.devices?.summary || {};
  const visible = query.trim()
    ? devices.filter((device) => `${device.ip} ${device.current_ip} ${device.name} ${device.id} ${device.role} ${device.current_mac} ${(device.expected_macs || []).join(" ")}`.toLowerCase().includes(query.trim().toLowerCase()))
    : devices;

  return (
    <section className="pageStack">
      <PageHeader title="设备" text="按 IP 查看设备是谁、当前是否在线，以及当前二层证据来自 DHCP、neighbor 还是 WRT Room 中继。" />
      <div className="summaryStrip">
        <span><b>{summary.total ?? devices.length}</b> 总数</span>
        <span><b>{summary.online ?? 0}</b> 在线</span>
        <span><b>{summary.standby ?? 0}</b> 可离线</span>
        <span><b>{summary.attention ?? 0}</b> 注意</span>
      </div>
      <label className="search">
        <Search size={16} />
        <input value={query} onChange={(event) => setQuery(event.target.value)} placeholder="搜索 IP、设备、MAC" />
      </label>
      <div className="deviceList">
        {visible.map((device) => <DeviceRow key={device.id || device.ip} device={device} />)}
        {!visible.length && <EmptyLine text="没有匹配的设备。" />}
      </div>
    </section>
  );
}

function ServicesView({ state, query, setQuery }: { state: State; query: string; setQuery: (value: string) => void }) {
  const services = state.home_services || [];
  const visible = query.trim()
    ? services.filter((service) => `${service.name} ${service.key} ${service.kind} ${service.role}`.toLowerCase().includes(query.trim().toLowerCase()))
    : services;
  const groups = useMemo(() => {
    const result = new Map<string, Service[]>();
    visible.forEach((service) => {
      const key = serviceGroup(service);
      result.set(key, [...(result.get(key) || []), service]);
    });
    return Array.from(result.entries()).sort(([a], [b]) => {
      const ai = groupOrder.indexOf(a);
      const bi = groupOrder.indexOf(b);
      return (ai === -1 ? 99 : ai) - (bi === -1 ? 99 : bi);
    });
  }, [visible]);

  return (
    <section className="pageStack">
      <PageHeader title="服务" text="这里回答：我家有什么、怎么进、谁负责。端口只是摘要，不做主视图。" />
      <label className="search">
        <Search size={16} />
        <input value={query} onChange={(event) => setQuery(event.target.value)} placeholder="搜索服务" />
      </label>

      {groups.map(([group, items]) => (
        <section className="serviceGroup" key={group}>
          <h2>{groupLabels[group] || group}</h2>
          <p>{groupDescriptions[group] || ""}</p>
          <div className="serviceGrid">
            {items.map((service) => <ServiceCard key={service.key || service.name} service={service} />)}
          </div>
        </section>
      ))}
      {!visible.length && <EmptyLine text="没有匹配的服务。" />}
      {!!state.console?.unmanaged_port_count && (
        <Panel title="端口提醒" icon={<AlertTriangle size={18} />}>
          <p className="note">这些端口正在监听，但没有写进服务清单；它们不是当前故障，只是后续整理项。</p>
          <div className="chipRow">
            {(state.console.unmanaged_ports || []).map((port) => <span key={port}>tcp/{port}</span>)}
          </div>
        </Panel>
      )}
    </section>
  );
}

function RoutingView() {
  const [rules, setRules] = useState<RoutingState>({ entries: [], permanent_candidates: [] });
  const [target, setTarget] = useState("");
  const [policy, setPolicy] = useState("PROXY");
  const [duration, setDuration] = useState("1h");
  const [busy, setBusy] = useState(false);
  const [message, setMessage] = useState("");

  const load = async () => {
    const response = await fetch("/api/routing-rules", { cache: "no-store" });
    setRules(await response.json());
  };

  useEffect(() => {
    load().catch(() => setRules({ error: "无法读取分流规则。" }));
  }, []);

  const submit = async (permanent: boolean) => {
    if (permanent && !window.confirm(`确认把 ${target.trim()} 加入永久规则？\n\n永久规则进入待提交队列，不会立刻改变当前流量。`)) return;
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
      setRules({ ...rules, entries: data.entries || [], permanent_candidates: data.permanent_candidates || [] });
      setMessage(permanent ? "已加入永久待提交。" : "临时规则已生效。");
    } catch (error) {
      setMessage(error instanceof Error ? error.message : "操作失败。");
    } finally {
      setBusy(false);
    }
  };

  const remove = async (id?: string, permanent = false) => {
    if (!id) return;
    setBusy(true);
    try {
      const url = permanent ? `/api/routing-permanent/${encodeURIComponent(id)}` : `/api/routing-rules/${encodeURIComponent(id)}`;
      const response = await fetch(url, { method: "DELETE" });
      const data = await response.json();
      if (!response.ok || !data.ok) throw new Error(data.error || data.detail || `HTTP ${response.status}`);
      setRules({ ...rules, entries: data.entries || [], permanent_candidates: data.permanent_candidates || [] });
      setMessage("已删除。");
    } catch (error) {
      setMessage(error instanceof Error ? error.message : "删除失败。");
    } finally {
      setBusy(false);
    }
  };

  const promote = async (id?: string) => {
    if (!id || !window.confirm("确认转为永久？\n\n临时规则会继续保留，永久规则进入待提交队列。")) return;
    setBusy(true);
    try {
      const response = await fetch(`/api/routing-rules/${encodeURIComponent(id)}/promote`, { method: "POST" });
      const data = await response.json();
      if (!response.ok || !data.ok) throw new Error(data.error || data.detail || `HTTP ${response.status}`);
      setRules({ ...rules, entries: data.entries || [], permanent_candidates: data.permanent_candidates || [] });
      setMessage("已加入永久待提交。");
    } catch (error) {
      setMessage(error instanceof Error ? error.message : "转永久失败。");
    } finally {
      setBusy(false);
    }
  };

  return (
    <section className="pageStack">
      <PageHeader title="分流" text="某个网站临时走某个出口。临时规则写 runtime；永久规则先进入待提交队列，再走 git。" />
      <Panel title="添加规则" icon={<Globe2 size={18} />}>
        <div className="routingForm">
          <label><span>网站</span><input value={target} onChange={(event) => setTarget(event.target.value)} placeholder="example.com 或完整网址" /></label>
          <label><span>出口</span><select value={policy} onChange={(event) => setPolicy(event.target.value)}>
            {(rules.policies || [{ id: "PROXY", label: "PROXY" }, { id: "PROXY-JAPAN", label: "PROXY-JAPAN" }, { id: "DIRECT", label: "DIRECT" }]).map((item) => <option key={item.id} value={item.id}>{item.label}</option>)}
          </select></label>
          <label><span>有效期</span><select value={duration} onChange={(event) => setDuration(event.target.value)}>
            <option value="1h">1 小时</option>
            <option value="today">今天</option>
            <option value="7d">7 天</option>
            <option value="forever">直到删除</option>
          </select></label>
          <div className="actions">
            <button disabled={busy || !target.trim()} onClick={() => submit(false)}><RefreshCw size={16} />临时</button>
            <button disabled={busy || !target.trim()} onClick={() => submit(true)}><Save size={16} />永久</button>
          </div>
        </div>
        {message && <p className="note">{message}</p>}
      </Panel>

      <div className="twoCols">
        <RuleList title="临时生效" entries={rules.entries || []} onDelete={(id) => remove(id)} onPromote={promote} />
        <CandidateList entries={rules.permanent_candidates || []} onDelete={(id) => remove(id, true)} />
      </div>
    </section>
  );
}

function Panel({ title, icon, children }: { title: string; icon: React.ReactNode; children: React.ReactNode }) {
  return <section className="panel"><header>{icon}<h2>{title}</h2></header>{children}</section>;
}

function PageHeader({ title, text }: { title: string; text: string }) {
  return <header className="pageHeader"><div><h2>{title}</h2><p>{text}</p></div></header>;
}

function LayerFocus({ layer }: { layer: ConsoleLayer }) {
  return (
    <article className={`layerFocus ${cls(layer.status)}`}>
      {icon(layer.status)}
      <div>
        <b>{layer.title}</b>
        <p>{layer.detail || "等待证据。"}</p>
        {layer.next_action && <em>{layer.next_action}</em>}
      </div>
      <strong>{label(layer.status)}</strong>
    </article>
  );
}

function Entry({ entry }: { entry: ConsoleEntry }) {
  return (
    <article className={`entry ${cls(entry.status)}`}>
      {icon(entry.status)}
      <span><b>{entry.label || entry.name || entry.id}</b><p>{entry.role}</p></span>
      <div>{links(entry).map((link) => <a href={link.href} target="_blank" rel="noreferrer" key={link.label}>{link.label}<ArrowUpRight size={13} /></a>)}</div>
    </article>
  );
}

function QuickEntry({ entry }: { entry: ConsoleEntry }) {
  const link = links(entry)[0];
  if (!link) {
    return <span className={`quickEntry ${cls(entry.status)}`}>{icon(entry.status)}{entry.label || entry.name || entry.id}</span>;
  }
  return (
    <a className={`quickEntry ${cls(entry.status)}`} href={link.href} target="_blank" rel="noreferrer">
      {icon(entry.status)}
      <span>{entry.label || entry.name || entry.id}</span>
      <ArrowUpRight size={13} />
    </a>
  );
}

function ServiceCard({ service }: { service: Service }) {
  const scopes = Array.from(new Set((service.ports || []).map((port) => portScope(port.scope))));
  return (
    <article className={`serviceCard ${cls(service.status)}`}>
      <header>{icon(service.status)}<b>{service.name || service.key}</b><span>{label(service.status)}</span></header>
      <p>{service.role || service.kind || "service"}</p>
      <div className="meta">
        <span>{service.detail || "tracked"}</span>
        {typeof service.latency_ms === "number" && service.latency_ms > 0 && <span>{service.latency_ms} ms</span>}
        <span>{scopes.length ? scopes.join(" / ") : "无监听端口"}</span>
      </div>
      {!!service.ports?.length && <div className="chipRow">{service.ports.map((port, index) => <span key={`${service.key}-${index}`}>{port.port}/{port.proto} · {portScope(port.scope)}</span>)}</div>}
      {!!links(service).length && <div className="actions inline">{links(service).map((link) => <a href={link.href} target="_blank" rel="noreferrer" key={link.label}>{link.label}<ArrowUpRight size={13} /></a>)}</div>}
    </article>
  );
}

function DeviceRow({ device }: { device: Device }) {
  return (
    <article className={`deviceRow ${cls(device.status)}`}>
      <div className="deviceMain">
        {icon(device.status)}
        <span>
          <b>{device.current_ip && device.current_ip !== device.ip ? `${device.ip} -> ${device.current_ip}` : device.ip}</b>
          <p>{device.name || device.id} · {device.role || device.network || "device"}</p>
        </span>
        <strong>{label(device.status)}</strong>
      </div>
      <div className="deviceMeta">
        <span>{device.detail || "等待证据"}</span>
        {device.hostname && <span>host: {device.hostname}</span>}
        {device.current_mac && <span>current: {device.current_mac}</span>}
        {!!device.expected_macs?.length && <span>expected: {device.expected_macs.join(", ")}</span>}
        {!!device.evidence?.length && <span>{device.evidence.join(" / ")}</span>}
      </div>
    </article>
  );
}

function RuleList({ title, entries, onDelete, onPromote }: { title: string; entries: RoutingRule[]; onDelete: (id?: string) => void; onPromote: (id?: string) => void }) {
  return (
    <Panel title={title} icon={<Layers3 size={18} />}>
      <div className="ruleList">
        {entries.map((item) => (
          <article key={item.id || item.value}>
            <span><b>{item.value}</b><p>{item.policy} · {item.rule}</p><em>{age(item.expires_at)}</em></span>
            <div><button onClick={() => onPromote(item.id)}><Save size={15} /></button><button onClick={() => onDelete(item.id)}><Trash2 size={15} /></button></div>
          </article>
        ))}
        {!entries.length && <EmptyLine text="暂无临时规则。" />}
      </div>
    </Panel>
  );
}

function CandidateList({ entries, onDelete }: { entries: RoutingCandidate[]; onDelete: (id?: string) => void }) {
  return (
    <Panel title="永久待提交" icon={<Save size={18} />}>
      <div className="ruleList">
        {entries.map((item) => (
          <article key={item.id || item.value}>
            <span><b>{item.value}</b><p>{item.policy} · {item.rule}</p><em>{item.status || "pending"}</em></span>
            <div><button onClick={() => onDelete(item.id)}><Trash2 size={15} /></button></div>
          </article>
        ))}
        {!entries.length && <EmptyLine text="暂无永久待提交。" />}
      </div>
    </Panel>
  );
}

function EmptyLine({ text }: { text: string }) {
  return <p className="empty">{text}</p>;
}

createRoot(document.getElementById("root")!).render(<App />);
