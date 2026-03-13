"use client";

import { useState, useEffect } from "react";
import SettingsPanel from "./settings-panel";
import WebhooksPanel from "./webhooks-panel";

/* ─── SVG Icons (Lucide-style, stroke-based) ─── */

function IconDashboard({ size = 18 }: { size?: number }) {
  return (
    <svg width={size} height={size} viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.8" strokeLinecap="round" strokeLinejoin="round">
      <rect x="3" y="3" width="7" height="9" rx="1" />
      <rect x="14" y="3" width="7" height="5" rx="1" />
      <rect x="14" y="12" width="7" height="9" rx="1" />
      <rect x="3" y="16" width="7" height="5" rx="1" />
    </svg>
  );
}

function IconPipeline({ size = 18 }: { size?: number }) {
  return (
    <svg width={size} height={size} viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.8" strokeLinecap="round" strokeLinejoin="round">
      <path d="M12 2v4" />
      <path d="M12 18v4" />
      <path d="M4.93 4.93l2.83 2.83" />
      <path d="M16.24 16.24l2.83 2.83" />
      <path d="M2 12h4" />
      <path d="M18 12h4" />
      <path d="M4.93 19.07l2.83-2.83" />
      <path d="M16.24 7.76l2.83-2.83" />
      <circle cx="12" cy="12" r="4" />
    </svg>
  );
}

function IconCampaign({ size = 18 }: { size?: number }) {
  return (
    <svg width={size} height={size} viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.8" strokeLinecap="round" strokeLinejoin="round">
      <rect x="2" y="4" width="20" height="16" rx="2" />
      <path d="M22 7l-10 7L2 7" />
    </svg>
  );
}

function IconSettings({ size = 18 }: { size?: number }) {
  return (
    <svg width={size} height={size} viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.8" strokeLinecap="round" strokeLinejoin="round">
      <path d="M12.22 2h-.44a2 2 0 0 0-2 2v.18a2 2 0 0 1-1 1.73l-.43.25a2 2 0 0 1-2 0l-.15-.08a2 2 0 0 0-2.73.73l-.22.38a2 2 0 0 0 .73 2.73l.15.1a2 2 0 0 1 1 1.72v.51a2 2 0 0 1-1 1.74l-.15.09a2 2 0 0 0-.73 2.73l.22.38a2 2 0 0 0 2.73.73l.15-.08a2 2 0 0 1 2 0l.43.25a2 2 0 0 1 1 1.73V20a2 2 0 0 0 2 2h.44a2 2 0 0 0 2-2v-.18a2 2 0 0 1 1-1.73l.43-.25a2 2 0 0 1 2 0l.15.08a2 2 0 0 0 2.73-.73l.22-.39a2 2 0 0 0-.73-2.73l-.15-.08a2 2 0 0 1-1-1.74v-.5a2 2 0 0 1 1-1.74l.15-.09a2 2 0 0 0 .73-2.73l-.22-.38a2 2 0 0 0-2.73-.73l-.15.08a2 2 0 0 1-2 0l-.43-.25a2 2 0 0 1-1-1.73V4a2 2 0 0 0-2-2z" />
      <circle cx="12" cy="12" r="3" />
    </svg>
  );
}

function IconWebhook({ size = 18 }: { size?: number }) {
  return (
    <svg width={size} height={size} viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.8" strokeLinecap="round" strokeLinejoin="round">
      <path d="M18 8A6 6 0 0 0 6 8c0 7-3 9-3 9h18s-3-2-3-9" />
      <path d="M13.73 21a2 2 0 0 1-3.46 0" />
    </svg>
  );
}

function IconActivity({ size = 20 }: { size?: number }) {
  return (
    <svg width={size} height={size} viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.8" strokeLinecap="round" strokeLinejoin="round">
      <polyline points="22 12 18 12 15 21 9 3 6 12 2 12" />
    </svg>
  );
}

function IconUsers({ size = 20 }: { size?: number }) {
  return (
    <svg width={size} height={size} viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.8" strokeLinecap="round" strokeLinejoin="round">
      <path d="M16 21v-2a4 4 0 0 0-4-4H6a4 4 0 0 0-4 4v2" />
      <circle cx="9" cy="7" r="4" />
      <path d="M22 21v-2a4 4 0 0 0-3-3.87" />
      <path d="M16 3.13a4 4 0 0 1 0 7.75" />
    </svg>
  );
}

function IconMailCheck({ size = 20 }: { size?: number }) {
  return (
    <svg width={size} height={size} viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.8" strokeLinecap="round" strokeLinejoin="round">
      <path d="M22 13V6a2 2 0 0 0-2-2H4a2 2 0 0 0-2 2v12c0 1.1.9 2 2 2h8" />
      <path d="M22 7l-8.97 5.7a1.94 1.94 0 0 1-2.06 0L2 7" />
      <path d="M16 19l2 2 4-4" />
    </svg>
  );
}

function IconRocket({ size = 20 }: { size?: number }) {
  return (
    <svg width={size} height={size} viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.8" strokeLinecap="round" strokeLinejoin="round">
      <path d="M4.5 16.5c-1.5 1.26-2 5-2 5s3.74-.5 5-2c.71-.84.7-2.13-.09-2.91a2.18 2.18 0 0 0-2.91-.09z" />
      <path d="M12 15l-3-3a22 22 0 0 1 2-3.95A12.88 12.88 0 0 1 22 2c0 2.72-.78 7.5-6 11a22.35 22.35 0 0 1-4 2z" />
      <path d="M9 12H4s.55-3.03 2-4c1.62-1.08 5 0 5 0" />
      <path d="M12 15v5s3.03-.55 4-2c1.08-1.62 0-5 0-5" />
    </svg>
  );
}

function IconSun({ size = 16 }: { size?: number }) {
  return (
    <svg width={size} height={size} viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
      <circle cx="12" cy="12" r="5" />
      <line x1="12" y1="1" x2="12" y2="3" />
      <line x1="12" y1="21" x2="12" y2="23" />
      <line x1="4.22" y1="4.22" x2="5.64" y2="5.64" />
      <line x1="18.36" y1="18.36" x2="19.78" y2="19.78" />
      <line x1="1" y1="12" x2="3" y2="12" />
      <line x1="21" y1="12" x2="23" y2="12" />
      <line x1="4.22" y1="19.78" x2="5.64" y2="18.36" />
      <line x1="18.36" y1="5.64" x2="19.78" y2="4.22" />
    </svg>
  );
}

function IconMoon({ size = 16 }: { size?: number }) {
  return (
    <svg width={size} height={size} viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
      <path d="M21 12.79A9 9 0 1 1 11.21 3 7 7 0 0 0 21 12.79z" />
    </svg>
  );
}

function IconPlus({ size = 16 }: { size?: number }) {
  return (
    <svg width={size} height={size} viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2.5" strokeLinecap="round" strokeLinejoin="round">
      <line x1="12" y1="5" x2="12" y2="19" />
      <line x1="5" y1="12" x2="19" y2="12" />
    </svg>
  );
}

/* ─── Mock Data ─── */
const MOCK_STATS = {
  activePipelines: 3,
  totalLeads: 2847,
  validEmails: 1923,
  deployedToday: 312,
  creditsVayne: { used: 7200, total: 10000 },
  creditsAmf: { used: 680, total: 1000 },
};

const MOCK_BATCHES = [
  {
    id: 1, name: "SaaS CEOs — US West", status: "deploying",
    total: 842, validated: 842, valid: 623, researched: 623, generated: 580, deployed: 312,
    createdAt: "2026-03-10",
  },
  {
    id: 2, name: "Agency Founders — UK", status: "researching",
    total: 1205, validated: 1205, valid: 890, researched: 445, generated: 0, deployed: 0,
    createdAt: "2026-03-11",
  },
  {
    id: 3, name: "E-commerce Directors", status: "validating",
    total: 800, validated: 310, valid: 210, researched: 0, generated: 0, deployed: 0,
    createdAt: "2026-03-12",
  },
];

const MOCK_EVENTS = [
  { type: "batch.deployed", msg: "312 leads deployed to 'SaaS CEOs'", time: "2 min ago" },
  { type: "batch.emails_generated", msg: "580 email sequences generated", time: "18 min ago" },
  { type: "credits.low", msg: "Anymailfinder credits below 35%", time: "1 hr ago" },
  { type: "batch.validation_progress", msg: "310/800 leads validated", time: "3 hr ago" },
];

/* ─── Helpers ─── */
function stagePercent(batch: typeof MOCK_BATCHES[0]) {
  const t = batch.total || 1;
  return {
    deployed: (batch.deployed / t) * 100,
    generated: ((batch.generated - batch.deployed) / t) * 100,
    researched: ((batch.researched - batch.generated) / t) * 100,
    validated: ((batch.valid - batch.researched) / t) * 100,
    skipped: ((batch.validated - batch.valid) / t) * 100,
    pending: ((t - batch.validated) / t) * 100,
  };
}

function statusBadge(status: string) {
  const map: Record<string, { cls: string; label: string }> = {
    scraping: { cls: "badge-info", label: "Scraping" },
    validating: { cls: "badge-info", label: "Validating" },
    researching: { cls: "badge-primary", label: "Researching" },
    generating: { cls: "badge-primary", label: "Generating" },
    deploying: { cls: "badge-warning", label: "Deploying" },
    complete: { cls: "badge-success", label: "Complete" },
    paused: { cls: "badge-danger", label: "Paused" },
  };
  const b = map[status] || { cls: "badge-info", label: status };
  return <span className={`badge ${b.cls}`}>{b.label}</span>;
}

/* ─── NAV CONFIG ─── */
const NAV_ITEMS = [
  { id: "dashboard", icon: <IconDashboard />, label: "Dashboard" },
  { id: "pipelines", icon: <IconPipeline />, label: "Pipelines" },
  { id: "campaigns", icon: <IconCampaign />, label: "Campaigns" },
  { id: "settings", icon: <IconSettings />, label: "Settings" },
  { id: "webhooks", icon: <IconWebhook />, label: "Webhooks" },
];

/* ─── STAT CONFIG ─── */
const STAT_CARDS = [
  {
    icon: <IconActivity />,
    value: MOCK_STATS.activePipelines,
    label: "Active Pipelines",
    color: "var(--brand-primary)",
  },
  {
    icon: <IconUsers />,
    value: MOCK_STATS.totalLeads.toLocaleString(),
    label: "Total Leads",
    color: "var(--brand-accent)",
  },
  {
    icon: <IconMailCheck />,
    value: MOCK_STATS.validEmails.toLocaleString(),
    label: "Valid Emails",
    color: "var(--brand-success)",
    change: "↑ 67.5% hit rate",
  },
  {
    icon: <IconRocket />,
    value: MOCK_STATS.deployedToday,
    label: "Deployed Today",
    color: "var(--brand-warning)",
  },
];

/* ─── Main Page ─── */
export default function DashboardPage() {
  const [activeNav, setActiveNav] = useState("dashboard");
  const [isDark, setIsDark] = useState(false);

  useEffect(() => {
    const saved = localStorage.getItem("theme");
    if (saved === "dark") {
      setIsDark(true);
      document.documentElement.setAttribute("data-theme", "dark");
    } else if (saved === "light") {
      setIsDark(false);
      document.documentElement.removeAttribute("data-theme");
    } else if (window.matchMedia("(prefers-color-scheme: dark)").matches) {
      setIsDark(true);
      document.documentElement.setAttribute("data-theme", "dark");
    }

    // Auto-navigate to settings on Google OAuth return
    const params = new URLSearchParams(window.location.search);
    if (params.get("google") === "connected") {
      setActiveNav("settings");
    }
  }, []);

  function toggleTheme() {
    const next = !isDark;
    setIsDark(next);
    if (next) {
      document.documentElement.setAttribute("data-theme", "dark");
      localStorage.setItem("theme", "dark");
    } else {
      document.documentElement.removeAttribute("data-theme");
      localStorage.setItem("theme", "light");
    }
  }

  return (
    <div className="app-layout">
      {/* ─── Sidebar ─── */}
      <nav className="sidebar">
        <div className="sidebar-header">
          <div className="sidebar-logo">
            <div className="logo-placeholder">EO</div>
            <span>Email Optimizer</span>
          </div>
        </div>

        <div className="sidebar-nav">
          <div className="nav-section-label">Overview</div>
          {NAV_ITEMS.slice(0, 3).map((item) => (
            <div
              key={item.id}
              id={`nav-${item.id}`}
              className={`nav-item ${activeNav === item.id ? "active" : ""}`}
              onClick={() => setActiveNav(item.id)}
            >
              <span className="nav-icon">{item.icon}</span>
              {item.label}
            </div>
          ))}
          <div className="nav-section-label">System</div>
          {NAV_ITEMS.slice(3).map((item) => (
            <div
              key={item.id}
              id={`nav-${item.id}`}
              className={`nav-item ${activeNav === item.id ? "active" : ""}`}
              onClick={() => setActiveNav(item.id)}
            >
              <span className="nav-icon">{item.icon}</span>
              {item.label}
            </div>
          ))}
        </div>

        {/* Credit gauges */}
        <div style={{ padding: "12px 16px", borderTop: "1px solid var(--border-default)" }}>
          <div className="credit-gauge" style={{ marginBottom: 10 }}>
            <div className="gauge-labels">
              <span>Vayne</span>
              <span>{MOCK_STATS.creditsVayne.used.toLocaleString()} / {MOCK_STATS.creditsVayne.total.toLocaleString()}</span>
            </div>
            <div className="gauge-bar">
              <div className="gauge-fill" style={{ width: `${(MOCK_STATS.creditsVayne.used / MOCK_STATS.creditsVayne.total) * 100}%` }} />
            </div>
          </div>
          <div className="credit-gauge">
            <div className="gauge-labels">
              <span>Anymailfinder</span>
              <span>{MOCK_STATS.creditsAmf.used} / {MOCK_STATS.creditsAmf.total}</span>
            </div>
            <div className="gauge-bar">
              <div
                className={`gauge-fill ${MOCK_STATS.creditsAmf.used / MOCK_STATS.creditsAmf.total > 0.6 ? "low" : ""}`}
                style={{ width: `${(MOCK_STATS.creditsAmf.used / MOCK_STATS.creditsAmf.total) * 100}%` }}
              />
            </div>
          </div>
        </div>

        {/* Theme toggle */}
        <div style={{ padding: "8px 12px", borderTop: "1px solid var(--border-default)" }}>
          <div className="theme-toggle" onClick={toggleTheme} id="theme-toggle">
            {isDark ? <IconMoon /> : <IconSun />}
            <span style={{ flex: 1 }}>{isDark ? "Dark mode" : "Light mode"}</span>
            <div className={`toggle-track ${isDark ? "active" : ""}`}>
              <div className="toggle-knob" />
            </div>
          </div>
        </div>
      </nav>

      {/* ─── Main Content ─── */}
      <main className="main-content grid-bg">
        <div className="page-header">
          <div className="page-header-row">
            <div>
              <h1 className="page-title">
                {activeNav === "settings" ? "Settings" : activeNav === "webhooks" ? "Webhooks" : "Dashboard"}
              </h1>
              <p className="page-subtitle">
                {activeNav === "settings"
                  ? "Manage integrations and API keys"
                  : activeNav === "webhooks"
                    ? "Configure real-time event notifications"
                    : "Real-time overview of your outreach pipeline"}
              </p>
            </div>
            {activeNav === "dashboard" && (
              <button id="btn-new-pipeline" className="btn btn-primary">
                <IconPlus size={15} />
                New Pipeline
              </button>
            )}
          </div>
        </div>

        <div className="page-body">
          {activeNav === "settings" ? (
            <SettingsPanel />
          ) : activeNav === "webhooks" ? (
            <WebhooksPanel />
          ) : (
            <>
              {/* Stat Cards */}
              <div className="stats-grid">
                {STAT_CARDS.map((stat, i) => (
                  <div
                    key={i}
                    className={`stat-card animate-fade-in delay-${i + 1}`}
                    style={{ "--stat-color": stat.color } as React.CSSProperties}
                  >
                    <div className="stat-icon-wrap" style={{ color: stat.color }}>
                      {stat.icon}
                    </div>
                    <div className="stat-value">{stat.value}</div>
                    <div className="stat-label">{stat.label}</div>
                    {stat.change && <div className="stat-change positive">{stat.change}</div>}
                  </div>
                ))}
              </div>

              {/* Pipeline Table */}
              <div className="card" style={{ marginBottom: 24 }}>
                <div className="card-header">
                  <div className="card-title">Active Pipelines</div>
                </div>
                <table className="data-table">
                  <thead>
                    <tr>
                      <th>Batch Name</th>
                      <th>Status</th>
                      <th>Progress</th>
                      <th>Leads</th>
                      <th>Deployed</th>
                      <th>Created</th>
                    </tr>
                  </thead>
                  <tbody>
                    {MOCK_BATCHES.map((batch) => {
                      const stages = stagePercent(batch);
                      return (
                        <tr key={batch.id} id={`batch-${batch.id}`}>
                          <td style={{ color: "var(--text-primary)", fontWeight: 600 }}>
                            {batch.name}
                          </td>
                          <td>{statusBadge(batch.status)}</td>
                          <td style={{ minWidth: 180 }}>
                            <div className="pipeline-stages">
                              <div className="pipeline-stage deployed" style={{ width: `${stages.deployed}%` }} />
                              <div className="pipeline-stage generated" style={{ width: `${stages.generated}%` }} />
                              <div className="pipeline-stage researched" style={{ width: `${stages.researched}%` }} />
                              <div className="pipeline-stage validated" style={{ width: `${stages.validated}%` }} />
                              <div className="pipeline-stage skipped" style={{ width: `${stages.skipped}%` }} />
                              <div className="pipeline-stage pending" style={{ width: `${stages.pending}%` }} />
                            </div>
                          </td>
                          <td>{batch.total.toLocaleString()}</td>
                          <td>{batch.deployed.toLocaleString()}</td>
                          <td style={{ color: "var(--text-muted)", fontSize: 13 }}>{batch.createdAt}</td>
                        </tr>
                      );
                    })}
                  </tbody>
                </table>
              </div>

              {/* Webhook Events */}
              <div className="card">
                <div className="card-header">
                  <div className="card-title">Recent Events</div>
                  <span className="badge badge-success">Live</span>
                </div>
                <div style={{ display: "flex", flexDirection: "column", gap: 8 }}>
                  {MOCK_EVENTS.map((event, i) => (
                    <div
                      key={i}
                      className="animate-slide-in"
                      style={{
                        animationDelay: `${i * 0.08}s`,
                        display: "flex",
                        justifyContent: "space-between",
                        alignItems: "center",
                        padding: "10px 14px",
                        background: "var(--bg-input)",
                        borderRadius: "var(--radius-sm)",
                        border: "1px solid var(--border-default)",
                      }}
                    >
                      <div style={{ display: "flex", alignItems: "center", gap: 10 }}>
                        <span style={{
                          width: 7, height: 7, borderRadius: "50%",
                          background: event.type === "credits.low" ? "var(--brand-warning)" : "var(--brand-success)",
                          flexShrink: 0,
                        }} />
                        <span style={{ fontSize: 13.5, color: "var(--text-secondary)" }}>
                          {event.msg}
                        </span>
                      </div>
                      <span style={{ fontSize: 12, color: "var(--text-muted)", whiteSpace: "nowrap", marginLeft: 16 }}>
                        {event.time}
                      </span>
                    </div>
                  ))}
                </div>
              </div>
            </>
          )}
        </div>
      </main>
    </div>
  );
}
