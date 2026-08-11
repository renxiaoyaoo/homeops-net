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
type View = "home" | "topology" | "routing" | "services";

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

type State = {
  ok?: boolean;
  updated_at?: number;
  errors?: string[];
  error_events?: string[];
  wan?: { down_mbps?: number; up_mbps?: number };
  mihomo?: { down_mbps?: number; up_mbps?: number };
  home_services?: Service[];
  ports?: Port[];
  console?: ConsoleSummary;
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
  console: { layers: [], entries: [], unmanaged_ports: [] },
  instance: { networks: {}, wifi: {} },
  remote_access: { clients: [] },
  ops_network: {}
};

const tabs: Array<{ id: View; label: string; icon: React.ReactNode }> = [
  { id: "home", label: "首页", icon: <Compass size={16} /> },
  { id: "topology", label: "拓扑", icon: <RadioTower size={16} /> },
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
  if (status === "bad" || status === "down") return "bad";
  if (status === "tracked") return "tracked";
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
  const c = cls(status);
  if (c === "ok") return "正常";
  if (c === "bad") return "异常";
  if (c === "warn") return "注意";
  if (c === "tracked") return "已记录";
  return "等待";
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
      {view === "routing" && <RoutingView />}
      {view === "services" && <ServicesView state={state} query={query} setQuery={setQuery} />}
    </main>
  );
}

function HomeView({ state }: { state: State }) {
  const summary = state.console || {};
  const layers = summary.layers || [];
  const problem = summary.active_problem || layers.find((layer) => ["bad", "warn"].includes(cls(layer.status)));
  const rescue = layers.find((layer) => layer.id === "rescue-path");
  const entries = summary.entries || [];
  const severity = summary.severity || (summary.ok ? "ok" : "unknown");

  return (
    <section className="homeGrid">
      <Panel title="现在" icon={<Compass size={18} />}>
        <div className={`verdict ${cls(severity)}`}>
          {icon(severity)}
          <div>
            <span>{label(severity)}</span>
            <b>{summary.headline || "等待状态"}</b>
            <p>{problem?.next_action || "关键链路正常。需要操作时从入口进入对应 source tool。"}</p>
          </div>
        </div>
      </Panel>

      <Panel title="坏在哪" icon={<AlertTriangle size={18} />}>
        {problem ? <LayerFocus layer={problem} /> : <EmptyLine text="没有当前故障域；历史波动只放在详情里。" />}
      </Panel>

      <Panel title="常用入口" icon={<Home size={18} />}>
        <div className="entryList">
          {entries.slice(0, 8).map((entry) => <Entry key={entry.id || entry.name} entry={entry} />)}
          {!entries.length && <EmptyLine text="等待服务入口。" />}
        </div>
      </Panel>

      <Panel title="下一步" icon={<Wrench size={18} />}>
        <div className="actionBox">
          <b>{problem ? problem.title : "不用处理"}</b>
          <p>{problem?.next_action || "当前只需要保持现状；不要因为历史 error_events 去改网络。"}</p>
          {problem?.entry && <code>{problem.entry}</code>}
        </div>
      </Panel>

      <Panel title="检修通道" icon={<Wifi size={18} />}>
        <LayerFocus layer={rescue || { title: "Maintenance Wi-Fi", status: state.ops_network?.ok ? "ok" : "unknown", detail: state.ops_network?.ssid || "等待检修网络状态" }} />
        <p className="note">主网络复杂路径坏了：连检修 Wi-Fi，设备自己开代理访问 Codex，再让 Codex 通过 Pi 排查。</p>
      </Panel>
    </section>
  );
}

function TopologyView({ state }: { state: State }) {
  const layers = state.console?.layers || [];
  const byId = new Map(layers.map((layer) => [layer.id, layer]));
  const domains = layerOrder.map((id) => byId.get(id) || { id, title: layerLabels[id], status: "unknown" });
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

      <Panel title="断电恢复" icon={<RadioTower size={18} />}>
        <div className="recoveryGrid">
          {["gateway-wan", "main-wifi-5g", "room-ap", "server-runtime"].map((id) => {
            const layer = byId.get(id) || { id, title: layerLabels[id], status: "unknown" };
            return <LayerFocus key={id} layer={layer} />;
          })}
        </div>
      </Panel>
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

      {!!state.console?.unmanaged_port_count && (
        <Panel title="未纳入实例的监听端口" icon={<AlertTriangle size={18} />}>
          <p className="note">这些端口实际在 Pi 上监听，但没有被 HomeNet instance 声明。需要确认是应纳入服务清单，还是应忽略。</p>
          <div className="chipRow">
            {(state.console.unmanaged_ports || []).map((port) => <span key={port}>tcp/{port}</span>)}
          </div>
        </Panel>
      )}

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
