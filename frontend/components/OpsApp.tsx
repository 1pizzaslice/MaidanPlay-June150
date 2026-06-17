"use client";

import { useEffect, useMemo, useState, type ReactNode } from "react";
import { api, loadBootstrap, login as loginApi, UnauthorizedError } from "../lib/api";
import type { AppConfig, Bootstrap, FieldDef, Stage, Student, User, Workflow } from "../lib/types";

const TOKEN_KEY = "june_one50_token";

type Route =
  | { name: "dashboard" }
  | { name: "me" }
  | { name: "mine" }
  | { name: "admin" }
  | { name: "batch"; batch: string }
  | { name: "group"; kind: "coach" | "emp"; nameValue: string }
  | { name: "student"; id: string }
  | { name: "search"; query: string };

type Counts = { g: number; p: number; d: number; t: number; pct: number };

function parseRoute(): Route {
  if (typeof window === "undefined") return { name: "dashboard" };
  const raw = window.location.hash.replace(/^#\/?/, "");
  const [path, queryString] = raw.split("?");
  const parts = path.split("/").filter(Boolean).map(decodeURIComponent);
  if (parts[0] === "me") return { name: "me" };
  if (parts[0] === "mine") return { name: "mine" };
  if (parts[0] === "admin") return { name: "admin" };
  if (parts[0] === "batch") return { name: "batch", batch: parts[1] || "" };
  if (parts[0] === "group") return { name: "group", kind: parts[1] === "coach" ? "coach" : "emp", nameValue: parts[2] || "" };
  if (parts[0] === "student") return { name: "student", id: parts[1] || "" };
  if (parts[0] === "search") {
    const query = new URLSearchParams(queryString || "").get("q") || "";
    return { name: "search", query };
  }
  return { name: "dashboard" };
}

function go(hash: string) {
  window.location.hash = hash;
}

function normNum(value: unknown) {
  return String(value || "").replace(/\D/g, "");
}

function maskNum(value: string) {
  const digits = normNum(value);
  return digits.length >= 4 ? `*** *** ${digits.slice(-4)}` : digits;
}

function fullName(student: Student) {
  return `${student.first || ""} ${student.last || ""}`.trim() || student.id;
}

function stageOf(record?: Workflow): Stage {
  return (record?.stage || "draft") as Stage;
}

function statusOf(record?: Workflow): "r" | "p" | "g" {
  const stage = stageOf(record);
  if (stage === "approved") return "g";
  if (stage === "draft") return "r";
  return "p";
}

function stageOrder(stage: Stage) {
  return stage === "draft" ? 0 : stage === "pending_amit" ? 1 : stage === "pending_akash" ? 2 : 3;
}

function pctClass(pct: number) {
  return pct < 50 ? "lo" : pct < 80 ? "mid" : "hi";
}

function fieldString(value: unknown) {
  if (value === null || value === undefined || value === "") return "-";
  return String(value);
}

function fmtDate(value: unknown) {
  if (!value) return "-";
  const date = new Date(String(value));
  if (Number.isNaN(date.getTime())) return String(value);
  return date.toLocaleDateString("en-IN", { day: "2-digit", month: "short", year: "numeric" });
}

function inr(value: unknown) {
  if (value === null || value === undefined || value === "") return "-";
  const num = Number(String(value).replace(/[^0-9.-]/g, ""));
  if (!Number.isFinite(num)) return String(value);
  return `INR ${num.toLocaleString("en-IN")}`;
}

function confirmGreen(record: Workflow, field: FieldDef) {
  const current = record.confirm?.[field.key] || {};
  if (current.opt === "o1") return true;
  if (current.opt === "o2") return field.o3 ? Boolean(String(current.val || "").trim()) : true;
  return false;
}

function confirmCount(record: Workflow, config: AppConfig) {
  return config.confirmFields.filter((field) => confirmGreen(record, field)).length;
}

function confirmDone(record: Workflow, config: AppConfig) {
  return config.confirmFields.every((field) => confirmGreen(record, field));
}

function condMet(record: Workflow, field: FieldDef, section: "amit" | "akash" | "kyp") {
  if (!field.when) return true;
  const [key, expected] = field.when.split("=");
  return (record[section] || {})[key] === expected;
}

function valueGreen(record: Workflow, field: FieldDef, section: "amit" | "akash" | "kyp") {
  if (!condMet(record, field, section)) return true;
  const value = (record[section] || {})[field.key];
  if (field.type === "cleared") return value === true;
  if (field.type === "yesno") return field.greenOn ? value === field.greenOn : value === "Yes" || value === "No";
  if (field.type === "choice" || field.type === "select") return Boolean(value);
  if (field.type === "value") return value !== null && value !== undefined && String(value).trim() !== "";
  return Boolean(value);
}

function sectionDone(record: Workflow, fields: FieldDef[], section: "amit" | "akash" | "kyp") {
  return fields.every((field) => valueGreen(record, field, section));
}

function tally(students: Student[], verify: Record<string, Workflow>): Counts {
  const counts = students.reduce(
    (acc, student) => {
      const status = statusOf(verify[student.id]);
      if (status === "g") acc.g += 1;
      else if (status === "p") acc.p += 1;
      else acc.d += 1;
      return acc;
    },
    { g: 0, p: 0, d: 0 }
  );
  const t = students.length;
  return { ...counts, t, pct: t ? Math.round((counts.g / t) * 100) : 0 };
}

function coachOf(config: AppConfig, batch: string) {
  return config.batchcfg[batch]?.coach || "Unassigned";
}

function empList(config: AppConfig, batch: string) {
  return config.batchcfg[batch]?.employees?.filter(Boolean) || [];
}

function empLabel(config: AppConfig, batch: string) {
  const list = empList(config, batch);
  return list.length ? list.join(" + ") : "Unassigned";
}

function isSuper(user: User | null, config: AppConfig) {
  return Boolean(user && config.super.includes(user.name));
}

function isAdmin(user: User | null) {
  return user?.role === "admin";
}

function canManageUsers(user: User | null, config: AppConfig) {
  return isAdmin(user) || isSuper(user, config);
}

function ownsBatch(user: User | null, batch: string, config: AppConfig) {
  if (!user) return false;
  if (user.role === "kush") return true;
  if (user.role === "employee") return empList(config, batch).includes(user.name);
  if (user.role === "coach") return coachOf(config, batch) === user.name;
  return false;
}

function canFillConfirm(user: User | null, student: Student, record: Workflow, config: AppConfig) {
  if (isSuper(user, config)) return true;
  return Boolean(user && user.access === "edit" && stageOf(record) === "draft" && ownsBatch(user, student.batch, config));
}

function canCoachConfirm(user: User | null, student: Student, record: Workflow, config: AppConfig) {
  return Boolean(user && user.role === "coach" && stageOf(record) === "draft" && coachOf(config, student.batch) === user.name);
}

function canKyp(user: User | null, config: AppConfig) {
  return Boolean(user && (isSuper(user, config) || user.role === "kush" || user.role === "coach"));
}

function canAmitEdit(user: User | null, record: Workflow, config: AppConfig) {
  return Boolean(user && (isSuper(user, config) || (user.role === "amit" && stageOf(record) === "pending_amit")));
}

function canAkashEdit(user: User | null, record: Workflow, config: AppConfig) {
  return Boolean(user && (isSuper(user, config) || (user.role === "akash" && stageOf(record) === "pending_akash")));
}

function pendingForUser(user: User | null, student: Student, record: Workflow, config: AppConfig) {
  if (!user) return false;
  const stage = stageOf(record);
  if (isSuper(user, config)) return stage === "pending_amit" || stage === "pending_akash";
  switch (user.role) {
    case "kush":
      return stage === "draft";
    case "amit":
      return stage === "pending_amit";
    case "akash":
      return stage === "pending_akash";
    case "coach":
      return stage === "draft" && coachOf(config, student.batch) === user.name && !record.coachConfirm?.ok;
    case "employee":
      return stage === "draft" && empList(config, student.batch).includes(user.name);
    default:
      return false;
  }
}

function touchedByUser(user: User | null, record: Workflow) {
  if (!user) return false;
  const name = user.name;
  if (record.submittedBy === name) return true;
  if (record.amitBy === name) return true;
  if (record.akashBy === name) return true;
  if (record.coachConfirm?.by === name) return true;
  if (record.kyp?.publishedBy === name) return true;
  return false;
}

function hasMyQueue(user: User | null, config: AppConfig) {
  if (!user) return false;
  if (isSuper(user, config)) return true;
  return ["kush", "amit", "akash", "coach", "employee"].includes(user.role);
}

function srcVal(student: Student, fieldKey: string) {
  if (fieldKey === "dob") return fmtDate(student.dob);
  if (fieldKey === "amount") return inr(student.amount);
  return fieldString(student[fieldKey as keyof Student]);
}

function AppBar({ title, sub, back, pill }: { title: ReactNode; sub?: string; back?: string; pill?: string }) {
  return (
    <div className="appbar">
      {back ? (
        <button className="back" onClick={() => (back === "history" ? history.back() : go(back))} aria-label="Back">
          {"<"}
        </button>
      ) : null}
      <div className="titleWrap">
        {sub ? <div className="eyebrow sub">{sub}</div> : null}
        <div className="title">{title}</div>
      </div>
      {pill ? <div className="pill">{pill}</div> : null}
    </div>
  );
}

function ProgressRing({ pct, size = 96 }: { pct: number; size?: number }) {
  const radius = size / 2 - 8;
  const circumference = 2 * Math.PI * radius;
  const offset = circumference * (1 - pct / 100);
  return (
    <div className="ring" style={{ width: size, height: size }}>
      <svg width={size} height={size}>
        <circle cx={size / 2} cy={size / 2} r={radius} fill="none" stroke="var(--ink-700)" strokeWidth="8" />
        <circle
          cx={size / 2}
          cy={size / 2}
          r={radius}
          fill="none"
          stroke={pct < 50 ? "var(--red)" : pct < 80 ? "var(--bronze-300)" : "var(--green)"}
          strokeWidth="8"
          strokeLinecap="round"
          strokeDasharray={circumference}
          strokeDashoffset={offset}
        />
      </svg>
      <div className="pct">{pct}%</div>
    </div>
  );
}

function ProgressBar({ stats }: { stats: Counts }) {
  const green = stats.t ? (stats.g / stats.t) * 100 : 0;
  const pending = stats.t ? (stats.p / stats.t) * 100 : 0;
  return (
    <div className="bar">
      <i className="g" style={{ width: `${green}%` }} />
      <i className="p" style={{ width: `${pending}%` }} />
    </div>
  );
}

function CountsRow({ stats }: { stats: Counts }) {
  return (
    <div className="counts">
      <span className="g">{stats.g} green</span>
      {stats.p ? <span className="p">{stats.p} pending</span> : null}
      <span className="d">{stats.d} open</span>
      <span className="t">{stats.t}</span>
    </div>
  );
}

function StatCard({
  name,
  role,
  stats,
  onClick
}: {
  name: string;
  role?: string;
  stats: Counts;
  onClick?: () => void;
}) {
  return (
    <button className={`bcard ${onClick ? "tap" : ""}`} onClick={onClick}>
      {role ? <div className="roleLabel">{role}</div> : null}
      <div className="row1">
        <div className="name">{name}</div>
        <div className={`pctnum ${pctClass(stats.pct)}`}>{stats.pct}%</div>
      </div>
      <ProgressBar stats={stats} />
      <CountsRow stats={stats} />
    </button>
  );
}

export function OpsApp() {
  const [token, setToken] = useState<string | null>(null);
  const [data, setData] = useState<Bootstrap | null>(null);
  const [route, setRoute] = useState<Route>({ name: "dashboard" });
  const [loading, setLoading] = useState(true);
  const [toast, setToast] = useState("");
  const [dashboardTab, setDashboardTab] = useState<"batch" | "coach" | "org">("batch");
  const [detailTab, setDetailTab] = useState<"details" | "confirm" | "amit" | "akash">("details");

  useEffect(() => {
    setRoute(parseRoute());
    const saved = window.localStorage.getItem(TOKEN_KEY);
    setToken(saved);
    setLoading(false);
    const onHash = () => setRoute(parseRoute());
    window.addEventListener("hashchange", onHash);
    return () => window.removeEventListener("hashchange", onHash);
  }, []);

  useEffect(() => {
    if (!token) return;
    void refresh(token);
  }, [token]);

  function forceLogout(message: string) {
    window.localStorage.removeItem(TOKEN_KEY);
    setToken(null);
    setData(null);
    setToast(message);
    go("#/");
  }

  async function refresh(activeToken = token) {
    if (!activeToken) return;
    setLoading(true);
    try {
      const payload = await loadBootstrap(activeToken);
      setData(payload);
    } catch (error) {
      if (error instanceof UnauthorizedError) {
        forceLogout(error.message || "Session expired - please log in again");
      } else {
        setToast(error instanceof Error ? error.message : "Session expired");
        window.localStorage.removeItem(TOKEN_KEY);
        setToken(null);
        setData(null);
      }
    } finally {
      setLoading(false);
    }
  }

  function showToast(message: string) {
    setToast(message);
    window.setTimeout(() => setToast(""), 1800);
  }

  function setRecord(studentId: string, record: Workflow) {
    setData((current) =>
      current ? { ...current, verify: { ...current.verify, [studentId]: record } } : current
    );
  }

  async function runMutation<T>(work: Promise<T>, success?: string) {
    try {
      const result = await work;
      if (success) showToast(success);
      return result;
    } catch (error) {
      if (error instanceof UnauthorizedError) {
        forceLogout(error.message || "Session expired - please log in again");
        return null;
      }
      showToast(error instanceof Error ? error.message : "Request failed");
      return null;
    }
  }

  async function mutateConfirm(studentId: string, body: Record<string, unknown>) {
    const result = await runMutation(
      api<{ ok: boolean; record: Workflow }>(`/workflows/${studentId}/confirm`, {
        token,
        method: "PATCH",
        body: JSON.stringify(body)
      })
    );
    if (result) setRecord(studentId, result.record);
  }

  async function mutateSection(studentId: string, section: "amit" | "akash" | "kyp", key: string, value: unknown) {
    const result = await runMutation(
      api<{ ok: boolean; record: Workflow }>(`/workflows/${studentId}/section`, {
        token,
        method: "PATCH",
        body: JSON.stringify({ section, key, value })
      })
    );
    if (result) setRecord(studentId, result.record);
  }

  async function simpleWorkflow(studentId: string, path: string, body?: Record<string, unknown>, success?: string) {
    const result = await runMutation(
      api<{ ok: boolean; record: Workflow }>(`/workflows/${studentId}/${path}`, {
        token,
        method: "POST",
        body: body ? JSON.stringify(body) : undefined
      }),
      success
    );
    if (result) setRecord(studentId, result.record);
  }

  async function approve(studentId: string, step: "kush" | "amit" | "akash") {
    const result = await runMutation(
      api<{ ok: boolean; record: Workflow }>(`/workflows/${studentId}/approve`, {
        token,
        method: "POST",
        body: JSON.stringify({ step })
      }),
      step === "kush" ? "Sent to Amit" : step === "amit" ? "Sent to Akash" : "Enrolled"
    );
    if (result) {
      setRecord(studentId, result.record);
      setDetailTab(step === "kush" ? "amit" : step === "amit" ? "akash" : "akash");
    }
  }

  async function doLogin(email: string, password: string) {
    try {
      const result = await loginApi(email, password);
      window.localStorage.setItem(TOKEN_KEY, result.token);
      setToken(result.token);
      setToast(`Welcome, ${result.user.name}`);
      go("#/");
    } catch (error) {
      setToast(error instanceof Error ? error.message : "Login failed");
    }
  }

  function logout() {
    window.localStorage.removeItem(TOKEN_KEY);
    setToken(null);
    setData(null);
    go("#/");
  }

  if (!token) {
    return (
      <main id="app">
        <LoginScreen onLogin={doLogin} />
        {toast ? <Toast message={toast} /> : null}
      </main>
    );
  }

  if (loading && !data) {
    return (
      <main id="app">
        <AppBar title={<>June <em>One50</em></>} sub="Academy Ops" />
        <div className="page">
          <div className="empty">
            <div className="big">Loading ops data</div>
          </div>
        </div>
      </main>
    );
  }

  if (!data) {
    return (
      <main id="app">
        <LoginScreen onLogin={doLogin} />
        {toast ? <Toast message={toast} /> : null}
      </main>
    );
  }

  const bootstrap: Bootstrap = data;
  const appConfig: AppConfig = bootstrap.config;
  const user: User = bootstrap.user;
  const activeToken: string = token;

  const view =
    route.name === "me" ? (
      <Account user={bootstrap.user} config={appConfig} logout={logout} />
    ) : route.name === "mine" ? (
      <MyQueue />
    ) : route.name === "admin" ? (
      <AdminPanel data={bootstrap} token={activeToken} refresh={() => refresh()} showToast={showToast} />
    ) : route.name === "batch" ? (
      <StudentList title={route.batch} sub="Batch Type" list={bootstrap.students.filter((student) => student.batch === route.batch)} />
    ) : route.name === "group" ? (
      <StudentList
        title={route.nameValue}
        sub={route.kind === "coach" ? "Coach" : "Maidan Employee"}
        list={bootstrap.students.filter((student) =>
          route.kind === "coach" ? coachOf(appConfig, student.batch) === route.nameValue : empList(appConfig, student.batch).includes(route.nameValue)
        )}
      />
    ) : route.name === "student" ? (
      <StudentDetail student={bootstrap.students.find((student) => student.id === route.id)} />
    ) : route.name === "search" ? (
      <SearchView query={route.query} />
    ) : (
      <Dashboard />
    );

  return (
    <main id="app">
      {view}
      {toast ? <Toast message={toast} /> : null}
    </main>
  );

  function LoginScreen({ onLogin }: { onLogin: (email: string, password: string) => void }) {
    const [email, setEmail] = useState("");
    const [password, setPassword] = useState("");
    return (
      <div className="login">
        <form
          className="loginCard"
          onSubmit={(event) => {
            event.preventDefault();
            onLogin(email.trim(), password);
          }}
        >
          <div className="eyebrow center">Academy Ops</div>
          <div className="loginBrand">
            June <em>One50</em>
          </div>
          <div className="loginSub">Sign in with your Maidan email and password.</div>
          <div className="loginField">
            <input
              value={email}
              onChange={(event) => setEmail(event.target.value)}
              type="email"
              autoComplete="email"
              placeholder="you@maidanplay.com"
            />
          </div>
          <div className="loginField">
            <input
              value={password}
              onChange={(event) => setPassword(event.target.value)}
              type="password"
              autoComplete="current-password"
              placeholder="Password"
            />
          </div>
          <button className="primaryBtn" type="submit">
            Log in
          </button>
          <div className="loginFoot">Need access? Ask a super-admin for your password.</div>
        </form>
      </div>
    );
  }

  function Toast({ message }: { message: string }) {
    return <div className="toast show">{message}</div>;
  }

  function RoleBar() {
    return (
      <button className="rolebar" onClick={() => go("#/me")}>
        <span>
          Welcome, <b>{user?.name}</b> - {user ? appConfig.accessLabel[user.access] : ""}
        </span>
        <span className="rbSwitch">{isAdmin(user) ? "Admin" : "Account"}</span>
      </button>
    );
  }

  function Dashboard() {
    const stats = tally(bootstrap.students, bootstrap.verify);
    const stageCounts = bootstrap.students.reduce(
      (acc, student) => {
        const stage = stageOf(bootstrap.verify[student.id]);
        if (stage === "pending_amit") acc.amit += 1;
        else if (stage === "pending_akash") acc.akash += 1;
        else if (stage === "approved") acc.done += 1;
        else acc.draft += 1;
        return acc;
      },
      { draft: 0, amit: 0, akash: 0, done: 0 }
    );
    const pendingMine = hasMyQueue(user, appConfig)
      ? bootstrap.students.filter((student) =>
          pendingForUser(user, student, bootstrap.verify[student.id] || {}, appConfig)
        ).length
      : 0;
    return (
      <>
        <AppBar title={<>June <em>One50</em></>} sub="Academy Ops - Closing Tracker" />
        <div className="page">
          <RoleBar />
          <SearchBox />
          {hasMyQueue(user, appConfig) ? (
            <button className="queueBar" onClick={() => go("#/mine")}>
              <span className="qLabel">My queue</span>
              <span className={`qCount ${pendingMine ? "hot" : ""}`}>{pendingMine}</span>
            </button>
          ) : null}
          <div className="eyebrow">June One50 - target {appConfig.greenTarget} greens</div>
          <div className="heroRing">
            <ProgressRing pct={Math.min(100, Math.round((stats.g / appConfig.greenTarget) * 100) || 0)} />
            <div className="meta">
              <h2>
                {stats.g} of {appConfig.greenTarget} <em>green</em>
              </h2>
              <div className="muted">{appConfig.greenTarget - stats.g > 0 ? `${appConfig.greenTarget - stats.g} to go` : "Target hit"}</div>
              <div className="legend">
                <span className="green">{stats.g}</span>
                <span className="bronze">{stats.p}</span>
                <span className="red">{stats.d}</span>
              </div>
            </div>
          </div>
          <div className="funnel">
            <FunnelChip label="Open" count={stageCounts.draft} status="r" />
            <FunnelChip label="With Amit" count={stageCounts.amit} status="p" />
            <FunnelChip label="With Akash" count={stageCounts.akash} status="p" />
            <FunnelChip label="Green" count={stageCounts.done} status="g" />
          </div>
          <div className="segmented">
            {(["batch", "coach", "org"] as const).map((tab) => (
              <button key={tab} className={dashboardTab === tab ? "active" : ""} onClick={() => setDashboardTab(tab)}>
                {tab[0].toUpperCase() + tab.slice(1)}
              </button>
            ))}
          </div>
          <Breakdown />
        </div>
      </>
    );
  }

  function FunnelChip({ label, count, status }: { label: string; count: number; status: "r" | "p" | "g" }) {
    return (
      <div className={`fchip ${status}`}>
        <div className="fn">{count}</div>
        <div className="fl">{label}</div>
      </div>
    );
  }

  function Breakdown() {
    if (dashboardTab === "batch") {
      return (
        <div className="cards">
          {appConfig.batchOrder
            .filter((batch) => bootstrap.students.some((student) => student.batch === batch))
            .map((batch) => {
              const list = bootstrap.students.filter((student) => student.batch === batch);
              const stats = tally(list, bootstrap.verify);
              return (
                <button key={batch} className="bcard tap" onClick={() => go(`#/batch/${encodeURIComponent(batch)}`)}>
                  <div className="row1">
                    <div className="name">{batch}</div>
                    <div className={`pctnum ${pctClass(stats.pct)}`}>{stats.pct}%</div>
                  </div>
                  <div className="subRow">
                    <span>{coachOf(appConfig, batch)}</span>
                    <span>{empLabel(appConfig, batch)}</span>
                  </div>
                  <ProgressBar stats={stats} />
                  <CountsRow stats={stats} />
                </button>
              );
            })}
        </div>
      );
    }
    if (dashboardTab === "coach") {
      const coaches = [...new Set(bootstrap.students.map((student) => coachOf(appConfig, student.batch)))];
      return (
        <div className="cards">
          {coaches.map((coach) => (
            <StatCard
              key={coach}
              name={coach}
              role="Coach"
              stats={tally(bootstrap.students.filter((student) => coachOf(appConfig, student.batch) === coach), bootstrap.verify)}
              onClick={() => go(`#/group/coach/${encodeURIComponent(coach)}`)}
            />
          ))}
        </div>
      );
    }
    const all = tally(bootstrap.students, bootstrap.verify);
    return (
      <div className="tree">
        <StatCard name={appConfig.org.founder.name} role={appConfig.org.founder.role} stats={all} />
        <div className="treeChild">
          <StatCard name={appConfig.org.director.name} role={appConfig.org.director.role} stats={all} />
        </div>
        <div className="treeChild deep">
          <StatCard name={appConfig.org.pnlHead.name} role={appConfig.org.pnlHead.role} stats={all} />
        </div>
      </div>
    );
  }

  function SearchBox({ initial = "" }: { initial?: string }) {
    const [query, setQuery] = useState(initial);
    const results = useMemo(() => searchStudents(query).slice(0, 6), [query]);
    return (
      <>
        <form
          className="search"
          onSubmit={(event) => {
            event.preventDefault();
            if (query.trim()) go(`#/search?q=${encodeURIComponent(query.trim())}`);
          }}
        >
          <span className="searchIcon">/</span>
          <input value={query} onChange={(event) => setQuery(event.target.value)} placeholder="Search name or mobile..." />
        </form>
        {query.trim() ? (
          results.length ? (
            <div className="slist compact">{results.map((student) => <StudentRow key={student.id} student={student} />)}</div>
          ) : (
            <div className="dividerNote">No match for "{query}".</div>
          )
        ) : null}
      </>
    );
  }

  function searchStudents(query: string) {
    const text = query.trim().toLowerCase();
    if (!text) return [];
    const digits = normNum(text);
    return bootstrap.students
      .map((student) => {
        const first = (student.first || "").toLowerCase();
        const last = (student.last || "").toLowerCase();
        const name = fullName(student).toLowerCase();
        const phone = normNum(student.phone);
        let score = 0;
        if (digits.length >= 3 && phone.includes(digits)) score = Math.max(score, digits.length >= 6 ? 100 : 70);
        if (first.startsWith(text)) score = Math.max(score, 90);
        if (last.startsWith(text)) score = Math.max(score, 80);
        if (name.includes(text)) score = Math.max(score, 60);
        if (first.includes(text) || last.includes(text)) score = Math.max(score, 50);
        return { student, score };
      })
      .filter((item) => item.score > 0)
      .sort((a, b) => b.score - a.score || fullName(a.student).localeCompare(fullName(b.student)))
      .map((item) => item.student);
  }

  function SearchView({ query }: { query: string }) {
    const results = searchStudents(query);
    return (
      <>
        <AppBar title="Search" sub="Results" back="#/" pill={String(results.length)} />
        <div className="page">
          <SearchBox initial={query} />
          <div className="eyebrow">{results.length} matches</div>
          <div className="slist">{results.map((student) => <StudentRow key={student.id} student={student} />)}</div>
        </div>
      </>
    );
  }

  function StudentRow({ student }: { student: Student }) {
    const record = bootstrap.verify[student.id] || {};
    const status = statusOf(record);
    const stamp =
      status === "g"
        ? "Green"
        : stageOf(record) === "pending_amit"
          ? "Amit"
          : stageOf(record) === "pending_akash"
            ? "Akash"
            : `${confirmCount(record, appConfig)}/${appConfig.confirmFields.length}`;
    return (
      <button className="srow" onClick={() => go(`#/student/${encodeURIComponent(student.id)}`)}>
        <span className={`statusDot ${status}`} />
        <span className="who">
          <span className={`nm ${status}`}>{fullName(student)}</span>
          <span className="meta">
            {student.batch} - {student.phone || "-"}
          </span>
        </span>
        <span className={`stamp ${status}`}>{stamp}</span>
        <span className="chev">{">"}</span>
      </button>
    );
  }

  function StudentList({ title, sub, list }: { title: string; sub: string; list: Student[] }) {
    const sorted = [...list].sort((a, b) => {
      const order = { r: 0, p: 1, g: 2 };
      const delta = order[statusOf(bootstrap.verify[a.id])] - order[statusOf(bootstrap.verify[b.id])];
      return delta || fullName(a).localeCompare(fullName(b));
    });
    const stats = tally(list, bootstrap.verify);
    return (
      <>
        <AppBar title={title} sub={sub} back="#/" pill={`${stats.pct}%`} />
        <div className="page">
          <div className="heroRing tight">
            <ProgressRing pct={stats.pct} size={76} />
            <div className="meta">
              <h2>
                {stats.g}/{stats.t} <em>green</em>
              </h2>
              <div className="legend">
                <span className="green">{stats.g}</span>
                <span className="bronze">{stats.p}</span>
                <span className="red">{stats.d}</span>
              </div>
            </div>
          </div>
          <div className="eyebrow">Students - open first</div>
          <div className="slist">{sorted.map((student) => <StudentRow key={student.id} student={student} />)}</div>
        </div>
      </>
    );
  }

  function MyQueue() {
    const queueLabel = (() => {
      if (!user) return "Awaiting you";
      if (isSuper(user, appConfig)) return "Currently in flight";
      switch (user.role) {
        case "kush":
          return "Drafts to submit";
        case "amit":
          return "Pending your approval";
        case "akash":
          return "Pending your approval";
        case "coach":
          return "Cross-checks pending";
        case "employee":
          return "Drafts to fill";
        default:
          return "Awaiting you";
      }
    })();
    const pending = bootstrap.students.filter((student) =>
      pendingForUser(user, student, bootstrap.verify[student.id] || {}, appConfig)
    );
    const activity = bootstrap.students
      .filter((student) => touchedByUser(user, bootstrap.verify[student.id] || {}))
      .sort((a, b) => {
        const order = { r: 0, p: 1, g: 2 };
        return order[statusOf(bootstrap.verify[a.id])] - order[statusOf(bootstrap.verify[b.id])] || fullName(a).localeCompare(fullName(b));
      });
    return (
      <>
        <AppBar title="My Queue" sub={user?.name || ""} back="#/" pill={String(pending.length)} />
        <div className="page">
          <div className="eyebrow">
            {queueLabel} - {pending.length}
          </div>
          {pending.length ? (
            <div className="slist">{pending.map((student) => <StudentRow key={student.id} student={student} />)}</div>
          ) : (
            <div className="dividerNote">Nothing waiting on you right now.</div>
          )}
          <div className="eyebrow">Your activity - {activity.length}</div>
          {activity.length ? (
            <div className="slist">{activity.map((student) => <StudentRow key={student.id} student={student} />)}</div>
          ) : (
            <div className="dividerNote">No students you've moved forward yet.</div>
          )}
        </div>
      </>
    );
  }

  function StudentDetail({ student }: { student?: Student }) {
    if (!student) return <Dashboard />;
    const record = bootstrap.verify[student.id] || {};
    const stage = stageOf(record);
    const status = statusOf(record);
    const activeTab: "details" | "confirm" | "amit" | "akash" = detailTab;
    return (
      <>
        <AppBar title={fullName(student)} sub="Verify & Approve" back="history" />
        <div className="page">
          <div className="detailHero">
            <div>
              <div className="detailName">{fullName(student)}</div>
              <div className="detailId">
                {student.id} - {student.batch} - Age {student.age || "-"}
              </div>
            </div>
            <div className={`statebadge ${status}`}>{appConfig.stageLabel[stage]}</div>
          </div>
          <div className="eyebrow">Approval Flow</div>
          <Stepper record={record} />
          {record.sentBackBy ? (
            <div className="sentback">
              Sent back by <b>{record.sentBackBy}</b>
              {record.sentBack ? <div>{record.sentBack}</div> : null}
            </div>
          ) : null}
          <div className="dtabs">
            {(["details", "confirm", "amit", "akash"] as const).map((tab) => (
              <button key={tab} className={activeTab === tab ? "active" : ""} onClick={() => setDetailTab(tab)}>
                {tab}
              </button>
            ))}
          </div>
          <div className="dtabBody">
            {activeTab === "details" ? <DetailsTab student={student} /> : null}
            {activeTab === "confirm" ? <ConfirmTab student={student} record={record} /> : null}
            {activeTab === "amit" ? <StageTab student={student} record={record} fields={appConfig.amitFields} section="amit" /> : null}
            {activeTab === "akash" ? <StageTab student={student} record={record} fields={appConfig.akashFields} section="akash" /> : null}
          </div>
        </div>
        <div className="closeCta">
          <div className="networkStrip">
            <span>Batch: {student.batch}</span>
            <span>Coach: {coachOf(appConfig, student.batch)}</span>
            <span>Maidan: {empLabel(appConfig, student.batch)}</span>
          </div>
        </div>
      </>
    );
  }

  function Stepper({ record }: { record: Workflow }) {
    const order = stageOrder(stageOf(record));
    const steps = [
      { label: "Confirmed by Kush", done: order > 0, sub: order > 0 ? `${record.submittedBy || "Kush"} - ${record.submittedAt || ""}` : "" },
      { label: "Confirmed by Amit", done: order > 1, sub: order > 1 ? `${record.amitBy || "Amit"} - ${record.amitAt || ""}` : "" },
      { label: "Confirmed by Akash", done: order > 2, sub: order > 2 ? `${record.akashBy || "Akash"} - ${record.akashAt || ""}` : "" },
      { label: "Student Enrolled on The Maidan Project", done: order > 2, sub: order > 2 ? "Enrolled" : "" }
    ];
    const current = steps.findIndex((step) => !step.done);
    return (
      <div className="stepper">
        {steps.map((step, index) => (
          <div key={step.label} className={`vstep ${step.done ? "done" : index === current ? "cur" : ""}`}>
            <div className="vdot">{step.done ? "✓" : index + 1}</div>
            <div>
              <div className="vlab">{step.label}</div>
              {step.sub ? <div className="vsub">{step.sub}</div> : null}
            </div>
          </div>
        ))}
      </div>
    );
  }

  function DetailsTab({ student }: { student: Student }) {
    const labels = Object.fromEntries(appConfig.confirmFields.map((field) => [field.key, field.label]));
    return (
      <div className="fieldgrid">
        {appConfig.detailFields.map((key) => (
          <div key={key} className={`field ${["school", "parent", "phone", "email"].includes(key) ? "full" : ""}`}>
            <div className="k">{labels[key] || key}</div>
            <div className="v">{srcVal(student, key)}</div>
          </div>
        ))}
      </div>
    );
  }

  function ConfirmTab({ student, record }: { student: Student; record: Workflow }) {
    const editable = canFillConfirm(user, student, record, appConfig);
    const kypEditable = canKyp(user, appConfig);
    return (
      <>
        <div className="vlist">
          <CoachCard student={student} record={record} />
          {appConfig.confirmFields.map((field) => (
            <ConfirmField key={field.key} student={student} record={record} field={field} editable={editable} />
          ))}
        </div>
        <ApproveBlock student={student} record={record} which="confirm" />
        <div className="eyebrow kypHead">Know Your Player - Coach</div>
        <div className="vlist">
          {appConfig.kypFields.map((field) => (
            <ValueField key={field.key} studentId={student.id} record={record} field={field} section="kyp" editable={kypEditable} />
          ))}
        </div>
        <button
          className={`btnClose ${sectionDone(record, appConfig.kypFields, "kyp") ? "ready" : "notready"}`}
          disabled={!sectionDone(record, appConfig.kypFields, "kyp") || !kypEditable}
          onClick={() => simpleWorkflow(student.id, "kyp/publish", undefined, "KYP published")}
        >
          {record.kyp?.published ? "Published - update" : `Know Your Player (${appConfig.kypFields.filter((field) => valueGreen(record, field, "kyp")).length}/${appConfig.kypFields.length})`}
        </button>
      </>
    );
  }

  function CoachCard({ student, record }: { student: Student; record: Workflow }) {
    const green = Boolean(record.coachConfirm?.ok);
    const allowed = canCoachConfirm(user, student, record, appConfig);
    return (
      <div className={`vfield coachrow ${green ? "green" : ""}`}>
        <div className="vfTop">
          <div className="vfLabel">Coach cross-check</div>
          <div className={`vfDot ${green ? "g" : ""}`} />
        </div>
        <div className="vfOnfile">Coach: {coachOf(appConfig, student.batch)}</div>
        <button className={`optb wide ${green ? "on" : ""}`} disabled={!allowed} onClick={() => simpleWorkflow(student.id, "coach-confirm")}>
          {green ? "Confirmed" : "Confirm details cross-checked"}
        </button>
      </div>
    );
  }

  function ConfirmField({ student, record, field, editable }: { student: Student; record: Workflow; field: FieldDef; editable: boolean }) {
    const current = record.confirm?.[field.key] || {};
    const green = confirmGreen(record, field);
    return (
      <div className={`vfield ${green ? "green" : ""}`}>
        <div className="vfTop">
          <div className="vfLabel">{field.label}</div>
          <div className={`vfDot ${green ? "g" : ""}`} />
        </div>
        <div className="vfOnfile">On file: {srcVal(student, field.key)}</div>
        <div className="optbtns">
          <button className={`optb ${current.opt === "o1" ? "on" : ""}`} disabled={!editable} onClick={() => mutateConfirm(student.id, { key: field.key, opt: "o1" })}>
            {field.o1 || "Correct"}
          </button>
          <button className={`optb ${current.opt === "o2" ? "on warn" : ""}`} disabled={!editable} onClick={() => mutateConfirm(student.id, { key: field.key, opt: "o2" })}>
            {field.o2 || "Incorrect"}
          </button>
        </div>
        {field.o3 && current.opt === "o2" ? (
          field.input === "select" ? (
            <select className="vfInput" value={current.val || ""} disabled={!editable} onChange={(event) => mutateConfirm(student.id, { key: field.key, val: event.target.value })}>
              <option value="">{field.o3}</option>
              {(field.choices || []).map((choice) => (
                <option key={choice} value={choice}>
                  {choice}
                </option>
              ))}
            </select>
          ) : (
            <input
              className="vfInput"
              type={field.input === "date" ? "date" : "text"}
              inputMode={field.input === "num" ? "numeric" : "text"}
              defaultValue={current.val || ""}
              disabled={!editable}
              placeholder={field.o3}
              onBlur={(event) => mutateConfirm(student.id, { key: field.key, val: event.currentTarget.value })}
            />
          )
        ) : null}
        {field.extra ? (
          <input
            className="vfInput"
            defaultValue={current.rel || ""}
            disabled={!editable}
            placeholder={field.extra}
            onBlur={(event) => mutateConfirm(student.id, { key: field.key, rel: event.currentTarget.value })}
          />
        ) : null}
      </div>
    );
  }

  function StageTab({
    student,
    record,
    fields,
    section
  }: {
    student: Student;
    record: Workflow;
    fields: FieldDef[];
    section: "amit" | "akash";
  }) {
    const editable = section === "amit" ? canAmitEdit(user, record, appConfig) : canAkashEdit(user, record, appConfig);
    return (
      <>
        <div className="vlist">
          {fields.map((field) => (
            <ValueField key={field.key} studentId={student.id} record={record} field={field} section={section} editable={editable} />
          ))}
        </div>
        <ApproveBlock student={student} record={record} which={section} />
      </>
    );
  }

  function ValueField({
    studentId,
    record,
    field,
    section,
    editable
  }: {
    studentId: string;
    record: Workflow;
    field: FieldDef;
    section: "amit" | "akash" | "kyp";
    editable: boolean;
  }) {
    const applicable = condMet(record, field, section);
    const green = valueGreen(record, field, section);
    const value = (record[section] || {})[field.key];
    return (
      <div className={`vfield ${green ? "green" : ""} ${applicable ? "" : "mutedField"}`}>
        <div className="vfTop">
          <div className="vfLabel">{field.label}</div>
          <div className={`vfDot ${green ? "g" : ""}`} />
        </div>
        {!applicable ? (
          <div className="vfNa">Not required</div>
        ) : field.type === "cleared" ? (
          <button className={`optb wide ${value === true ? "on" : ""}`} disabled={!editable} onClick={() => mutateSection(studentId, section, field.key, value !== true)}>
            {value === true ? "Cleared" : "Mark cleared"}
          </button>
        ) : field.type === "yesno" ? (
          <div className="optbtns">
            {["Yes", "No"].map((choice) => (
              <button key={choice} className={`optb ${value === choice ? "on" : ""}`} disabled={!editable} onClick={() => mutateSection(studentId, section, field.key, choice)}>
                {choice}
              </button>
            ))}
          </div>
        ) : field.type === "choice" ? (
          <div className="optbtns">
            {(field.choices || []).map((choice) => (
              <button key={choice} className={`optb ${value === choice ? "on" : ""}`} disabled={!editable} onClick={() => mutateSection(studentId, section, field.key, choice)}>
                {choice}
              </button>
            ))}
          </div>
        ) : field.type === "select" ? (
          <select className="vfInput" value={String(value || "")} disabled={!editable} onChange={(event) => mutateSection(studentId, section, field.key, event.target.value)}>
            <option value="">Select</option>
            {(field.choices || []).map((choice) => (
              <option key={choice} value={choice}>
                {choice}
              </option>
            ))}
          </select>
        ) : (
          <input
            className="vfInput"
            inputMode="numeric"
            defaultValue={String(value || "")}
            disabled={!editable}
            placeholder="Enter value"
            onBlur={(event) => mutateSection(studentId, section, field.key, event.currentTarget.value)}
          />
        )}
      </div>
    );
  }

  function ApproveBlock({ student, record, which }: { student: Student; record: Workflow; which: "confirm" | "amit" | "akash" }) {
    const stage = stageOf(record);
    if (which === "confirm") {
      const ready = Boolean(user && (user.role === "kush" || isSuper(user, appConfig)) && stage === "draft" && confirmDone(record, appConfig));
      if (stage !== "draft") return <button className="btnClose isclosed">Approved by Kush</button>;
      return (
        <button className={`btnClose ${ready ? "ready" : "notready"}`} disabled={!ready} onClick={() => approve(student.id, "kush")}>
          Approve by Kush ({confirmCount(record, appConfig)}/{appConfig.confirmFields.length})
        </button>
      );
    }
    if (which === "amit") {
      const ready = Boolean(user && (user.role === "amit" || isSuper(user, appConfig)) && stage === "pending_amit" && sectionDone(record, appConfig.amitFields, "amit"));
      if (stageOrder(stage) > 1) return <button className="btnClose isclosed">Amit approved</button>;
      return (
        <div className="approw">
          <button className={`btnClose ${ready ? "ready" : "notready"}`} disabled={!ready} onClick={() => approve(student.id, "amit")}>
            {stage === "draft" ? "Waiting for Kush" : "Approve to Akash"}
          </button>
          {stage === "pending_amit" && user && (user.role === "amit" || isSuper(user, appConfig)) ? (
            <button className="btnSoft" onClick={() => simpleWorkflow(student.id, "send-back", { note: window.prompt("Send back note") || "" }, "Sent back")}>
              Send back
            </button>
          ) : null}
        </div>
      );
    }
    const ready = Boolean(user && (user.role === "akash" || isSuper(user, appConfig)) && stage === "pending_akash" && sectionDone(record, appConfig.akashFields, "akash"));
    if (stage === "approved") {
      return (
        <>
          <button className="btnClose isclosed">Student enrolled</button>
          {user && (user.role === "akash" || user.role === "kush" || isSuper(user, appConfig)) ? (
            <button className="btnClose ghost" onClick={() => simpleWorkflow(student.id, "reopen", undefined, "Re-opened")}>
              Re-open for edits
            </button>
          ) : null}
        </>
      );
    }
    return (
      <div className="approw">
        <button className={`btnClose ${ready ? "ready" : "notready"}`} disabled={!ready} onClick={() => approve(student.id, "akash")}>
          {stageOrder(stage) < 2 ? "Waiting for earlier approvals" : "Approve and enrol"}
        </button>
        {stage === "pending_akash" && user && (user.role === "akash" || isSuper(user, appConfig)) ? (
          <button className="btnSoft" onClick={() => simpleWorkflow(student.id, "send-back", { note: window.prompt("Send back note") || "" }, "Sent back")}>
            Send back
          </button>
        ) : null}
      </div>
    );
  }

  function Account({ user, config, logout }: { user: User; config: AppConfig; logout: () => void }) {
    return (
      <>
        <AppBar title="Account" sub="Signed in" back="#/" />
        <div className="page">
          <div className="detailHero stack">
            <div className="detailName">{user.name}</div>
            <div className="detailId">{user.email}</div>
            <div className="fieldgrid">
              <div className="field">
                <div className="k">Role</div>
                <div className="v">{config.roleLabel[user.role]}{isSuper(user, config) ? " · Super-admin" : ""}</div>
              </div>
              <div className="field">
                <div className="k">Access</div>
                <div className="v">{config.accessLabel[user.access]}</div>
              </div>
              {user.mobile ? (
                <div className="field">
                  <div className="k">Mobile</div>
                  <div className="v">{maskNum(user.mobile)}</div>
                </div>
              ) : null}
            </div>
          </div>
          {canManageUsers(user, config) ? (
            <button className="btnClose ready" onClick={() => go("#/admin")}>
              Open Admin Panel
            </button>
          ) : null}
          <button className="btnClose ghost" onClick={logout}>
            Log out
          </button>
        </div>
      </>
    );
  }

  function AdminPanel({
    data,
    token,
    refresh,
    showToast
  }: {
    data: Bootstrap;
    token: string | null;
    refresh: () => Promise<void>;
    showToast: (message: string) => void;
  }) {
    const [newUser, setNewUser] = useState<User>({ name: "", email: "", mobile: "", access: "edit", role: "viewer" });
    const [importText, setImportText] = useState("");
    const [replace, setReplace] = useState(false);
    if (!canManageUsers(data.user, data.config)) {
      return <Dashboard />;
    }
    const superMode = isSuper(data.user, data.config);

    async function updateUser(email: string, patch: Partial<User>) {
      await runMutation(
        api(`/users/${encodeURIComponent(email)}`, {
          token,
          method: "PATCH",
          body: JSON.stringify(patch)
        }),
        "Saved"
      );
      await refresh();
    }

    async function addUser() {
      if (!newUser.email.trim()) {
        showToast("Email is required");
        return;
      }
      await runMutation(
        api("/users", {
          token,
          method: "POST",
          body: JSON.stringify(newUser)
        }),
        "Person added"
      );
      setNewUser({ name: "", email: "", mobile: "", access: "edit", role: "viewer" });
      await refresh();
    }

    async function removeUser(email: string) {
      if (!window.confirm("Remove this person's access?")) return;
      await runMutation(api(`/users/${encodeURIComponent(email)}`, { token, method: "DELETE" }), "Removed");
      await refresh();
    }

    async function resetPassword(email: string, name: string) {
      const next = window.prompt(`New password for ${name}`, "");
      if (!next) return;
      if (next.length < 6) {
        showToast("Password must be at least 6 characters");
        return;
      }
      await runMutation(
        api(`/users/${encodeURIComponent(email)}/password`, {
          token,
          method: "POST",
          body: JSON.stringify({ password: next })
        }),
        "Password updated"
      );
    }

    async function updateBatch(batch: string, patch: { coach?: string; employees?: string[] }) {
      await runMutation(
        api(`/batches/${encodeURIComponent(batch)}`, {
          token,
          method: "PATCH",
          body: JSON.stringify(patch)
        }),
        "Saved"
      );
      await refresh();
    }

    async function importJson() {
      try {
        const parsed = JSON.parse(importText || "{}");
        await runMutation(
          api("/students/import", {
            token,
            method: "POST",
            body: JSON.stringify({ ...parsed, replace })
          }),
          "Imported"
        );
        setImportText("");
        await refresh();
      } catch {
        showToast("Invalid JSON");
      }
    }

    async function resetDefaults() {
      if (!window.confirm("Reset users and batch allocation to defaults?")) return;
      await runMutation(api("/admin/reset-config", { token, method: "POST" }), "Reset");
      await refresh();
    }

    return (
      <>
        <AppBar title={<>Admin <em>Panel</em></>} sub="Access and allocation" back="#/" />
        <div className="page">
          <div className="eyebrow">People and Access - {data.config.users.length}</div>
          <div className="cards">
            {data.config.users.map((person) => (
              <div className="acard" key={person.email}>
                <div className="acTop">
                  <div>
                    <div className="acName">{person.name}{data.config.super.includes(person.name) ? " ★" : ""}</div>
                    <div className="acNum">{person.email}</div>
                    {person.mobile ? <div className="acNum">{maskNum(person.mobile)}</div> : null}
                  </div>
                  <button className="iconBtn danger" onClick={() => removeUser(person.email)}>
                    x
                  </button>
                </div>
                <label>
                  Email
                  <input
                    defaultValue={person.email}
                    onBlur={(event) => {
                      const next = event.currentTarget.value.trim().toLowerCase();
                      if (next && next !== person.email) updateUser(person.email, { email: next });
                    }}
                  />
                </label>
                <label>
                  Mobile
                  <input
                    defaultValue={person.mobile || ""}
                    inputMode="numeric"
                    onBlur={(event) => updateUser(person.email, { mobile: event.currentTarget.value })}
                  />
                </label>
                <div className="acRow">
                  <label>
                    Access
                    <select value={person.access} onChange={(event) => updateUser(person.email, { access: event.target.value as User["access"] })}>
                      {Object.keys(data.config.accessLabel).map((key) => (
                        <option key={key} value={key}>
                          {data.config.accessLabel[key]}
                        </option>
                      ))}
                    </select>
                  </label>
                  <label>
                    Role
                    <select value={person.role} onChange={(event) => updateUser(person.email, { role: event.target.value as User["role"] })}>
                      {Object.keys(data.config.roleLabel).map((key) => (
                        <option key={key} value={key}>
                          {data.config.roleLabel[key]}
                        </option>
                      ))}
                    </select>
                  </label>
                </div>
                {person.role === "employee" ? (
                  <label>
                    Batch
                    <select value={person.batch || data.config.batchOrder[0]} onChange={(event) => updateUser(person.email, { batch: event.target.value })}>
                      {data.config.batchOrder.map((batch) => (
                        <option key={batch} value={batch}>
                          {batch}
                        </option>
                      ))}
                    </select>
                  </label>
                ) : null}
                {superMode ? (
                  <button className="btnSoft" onClick={() => resetPassword(person.email, person.name)}>
                    Reset password
                  </button>
                ) : null}
              </div>
            ))}
          </div>

          <div className="eyebrow">Add a Person</div>
          <div className="acard">
            <label>
              Name
              <input value={newUser.name} onChange={(event) => setNewUser({ ...newUser, name: event.target.value })} />
            </label>
            <label>
              Email
              <input value={newUser.email} onChange={(event) => setNewUser({ ...newUser, email: event.target.value })} type="email" placeholder="person@maidanplay.com" />
            </label>
            <label>
              Mobile (optional)
              <input value={newUser.mobile || ""} onChange={(event) => setNewUser({ ...newUser, mobile: event.target.value })} inputMode="numeric" />
            </label>
            <div className="acRow">
              <label>
                Access
                <select value={newUser.access} onChange={(event) => setNewUser({ ...newUser, access: event.target.value as User["access"] })}>
                  {Object.keys(data.config.accessLabel).map((key) => (
                    <option key={key} value={key}>
                      {data.config.accessLabel[key]}
                    </option>
                  ))}
                </select>
              </label>
              <label>
                Role
                <select value={newUser.role} onChange={(event) => setNewUser({ ...newUser, role: event.target.value as User["role"] })}>
                  {Object.keys(data.config.roleLabel).map((key) => (
                    <option key={key} value={key}>
                      {data.config.roleLabel[key]}
                    </option>
                  ))}
                </select>
              </label>
            </div>
            <button className="btnClose ready" onClick={addUser}>
              Add person
            </button>
            <div className="hint">New people get the default password until a super-admin resets it.</div>
          </div>

          <div className="eyebrow">Batch Allocation</div>
          <div className="cards">
            {data.config.batchOrder.map((batch) => (
              <div className="acard" key={batch}>
                <div className="acName">{batch}</div>
                <label>
                  Coach
                  <input defaultValue={coachOf(data.config, batch)} onBlur={(event) => updateBatch(batch, { coach: event.currentTarget.value })} />
                </label>
                <label>
                  Maidan employees
                  <input
                    defaultValue={empList(data.config, batch).join(", ")}
                    onBlur={(event) => updateBatch(batch, { employees: event.currentTarget.value.split(",").map((item) => item.trim()).filter(Boolean) })}
                  />
                </label>
              </div>
            ))}
          </div>

          <div className="eyebrow">Data Import</div>
          <div className="acard">
            <label>
              Legacy JSON
              <textarea value={importText} onChange={(event) => setImportText(event.target.value)} rows={8} placeholder='{"students":[],"verify":{},"config":{}}' />
            </label>
            <label className="checkline">
              <input type="checkbox" checked={replace} onChange={(event) => setReplace(event.target.checked)} />
              Replace current students
            </label>
            <button className="btnClose ready" onClick={importJson}>
              Import data
            </button>
          </div>

          <div className="eyebrow">Reset</div>
          <button className="btnClose ghost" onClick={resetDefaults}>
            Reset users and batches to defaults
          </button>
        </div>
      </>
    );
  }
}
