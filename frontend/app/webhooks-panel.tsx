"use client";

import { useState, useEffect, useCallback } from "react";

/* ─── Icons ─── */
function IconWebhookBolt({ size = 20 }: { size?: number }) {
  return (
    <svg width={size} height={size} viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.8" strokeLinecap="round" strokeLinejoin="round">
      <path d="M18 8A6 6 0 0 0 6 8c0 7-3 9-3 9h18s-3-2-3-9" />
      <path d="M13.73 21a2 2 0 0 1-3.46 0" />
      <line x1="12" y1="2" x2="12" y2="5" />
    </svg>
  );
}

function IconCheck({ size = 14 }: { size?: number }) {
  return (
    <svg width={size} height={size} viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2.5" strokeLinecap="round" strokeLinejoin="round">
      <polyline points="20 6 9 17 4 12" />
    </svg>
  );
}

function IconX({ size = 14 }: { size?: number }) {
  return (
    <svg width={size} height={size} viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
      <line x1="18" y1="6" x2="6" y2="18" />
      <line x1="6" y1="6" x2="18" y2="18" />
    </svg>
  );
}

function IconRefresh({ size = 14 }: { size?: number }) {
  return (
    <svg width={size} height={size} viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
      <polyline points="23 4 23 10 17 10" />
      <path d="M20.49 15a9 9 0 1 1-2.12-9.36L23 10" />
    </svg>
  );
}

function IconSend({ size = 14 }: { size?: number }) {
  return (
    <svg width={size} height={size} viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
      <line x1="22" y1="2" x2="11" y2="13" />
      <polygon points="22 2 15 22 11 13 2 9 22 2" />
    </svg>
  );
}

function IconCopy({ size = 14 }: { size?: number }) {
  return (
    <svg width={size} height={size} viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
      <rect x="9" y="9" width="13" height="13" rx="2" ry="2" />
      <path d="M5 15H4a2 2 0 0 1-2-2V4a2 2 0 0 1 2-2h9a2 2 0 0 1 2 2v1" />
    </svg>
  );
}

/* ─── Types ─── */
interface WebhookEvent {
  id: number;
  event_type: string;
  delivered: boolean;
  attempts: number;
  response_status: number | null;
  payload: Record<string, unknown>;
  created_at: string;
}

/* ─── Constants ─── */
const API_BASE = process.env.NEXT_PUBLIC_API_URL || "http://localhost:8000";
const MOCK_USER_ID = "dev-user-001";

const EVENT_TYPES = [
  { type: "batch.deployed", desc: "Fired when leads are deployed to a campaign" },
  { type: "batch.complete", desc: "Fired when a batch finishes processing" },
  { type: "batch.emails_generated", desc: "Email sequences generated for a batch" },
  { type: "batch.validation_progress", desc: "Lead validation progress update" },
  { type: "credits.low", desc: "API credits are running low" },
  { type: "webhook.test", desc: "Test event for verifying webhook delivery" },
];

/* ─── Main Webhooks Panel ─── */
export default function WebhooksPanel() {
  const [webhookUrl, setWebhookUrl] = useState("");
  const [webhookSecret, setWebhookSecret] = useState("");
  const [isConfigured, setIsConfigured] = useState(false);
  const [hasSecret, setHasSecret] = useState(false);
  const [saving, setSaving] = useState(false);
  const [testing, setTesting] = useState(false);
  const [events, setEvents] = useState<WebhookEvent[]>([]);
  const [eventsLoading, setEventsLoading] = useState(true);
  const [toastMessage, setToastMessage] = useState<string | null>(null);
  const [showSecret, setShowSecret] = useState(false);
  const [expandedEvent, setExpandedEvent] = useState<number | null>(null);

  const fetchConfig = useCallback(async () => {
    try {
      const res = await fetch(`${API_BASE}/api/webhook-config?user_id=${MOCK_USER_ID}`);
      if (res.ok) {
        const data = await res.json();
        setWebhookUrl(data.url || "");
        setIsConfigured(data.configured);
        setHasSecret(data.has_secret);
      }
    } catch (e) {
      console.error("Failed to fetch webhook config:", e);
    }
  }, []);

  const fetchEvents = useCallback(async () => {
    setEventsLoading(true);
    try {
      const res = await fetch(`${API_BASE}/api/webhook-events?user_id=${MOCK_USER_ID}`);
      if (res.ok) {
        const data = await res.json();
        setEvents(data.events || []);
      }
    } catch (e) {
      console.error("Failed to fetch webhook events:", e);
    } finally {
      setEventsLoading(false);
    }
  }, []);

  useEffect(() => {
    fetchConfig();
    fetchEvents();
  }, [fetchConfig, fetchEvents]);

  function showToast(msg: string) {
    setToastMessage(msg);
    setTimeout(() => setToastMessage(null), 4000);
  }

  async function saveConfig() {
    setSaving(true);
    try {
      const res = await fetch(`${API_BASE}/api/webhook-config`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          user_id: MOCK_USER_ID,
          url: webhookUrl,
          secret: webhookSecret,
        }),
      });
      if (res.ok) {
        showToast("Webhook configuration saved");
        setIsConfigured(!!webhookUrl);
        setHasSecret(!!webhookSecret);
        setWebhookSecret("");
        setShowSecret(false);
      } else {
        showToast("Failed to save webhook configuration");
      }
    } catch (e) {
      showToast("Failed to connect to backend");
    } finally {
      setSaving(false);
    }
  }

  async function sendTest() {
    setTesting(true);
    try {
      const res = await fetch(`${API_BASE}/api/webhook-test`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ user_id: MOCK_USER_ID }),
      });
      if (res.ok) {
        showToast("Test event sent!");
        // Refresh events after a short delay
        setTimeout(fetchEvents, 1000);
      } else {
        const data = await res.json();
        showToast(data.detail || "Failed to send test event");
      }
    } catch (e) {
      showToast("Failed to connect to backend");
    } finally {
      setTesting(false);
    }
  }

  function formatTime(iso: string) {
    const d = new Date(iso);
    const now = new Date();
    const diffMs = now.getTime() - d.getTime();
    const diffMin = Math.floor(diffMs / 60000);

    if (diffMin < 1) return "Just now";
    if (diffMin < 60) return `${diffMin}m ago`;
    if (diffMin < 1440) return `${Math.floor(diffMin / 60)}h ago`;
    return d.toLocaleDateString();
  }

  function eventBadge(type: string) {
    const colors: Record<string, string> = {
      "batch.deployed": "var(--brand-success)",
      "batch.complete": "var(--brand-primary)",
      "batch.emails_generated": "var(--brand-accent)",
      "batch.validation_progress": "var(--brand-accent)",
      "credits.low": "var(--brand-warning)",
      "webhook.test": "var(--text-muted)",
    };
    return colors[type] || "var(--text-muted)";
  }

  return (
    <div className="settings-panel">
      {/* Toast */}
      {toastMessage && (
        <div className="settings-toast animate-slide-in">
          <IconCheck size={14} />
          {toastMessage}
        </div>
      )}

      {/* ─── Webhook Configuration ─── */}
      <div className="settings-section">
        <div className="settings-section-header">
          <h2 className="settings-section-title">Webhook Configuration</h2>
          <p className="settings-section-desc">
            Receive real-time notifications when pipeline events occur
          </p>
        </div>

        <div className="integration-card" id="webhook-config-card">
          <div className="integration-card-header">
            <div className="api-key-icon" style={{ "--svc-color": "var(--brand-accent)" } as React.CSSProperties}>
              <IconWebhookBolt size={22} />
            </div>
            <div className="integration-info">
              <div className="integration-name">Endpoint URL</div>
              <div className="integration-desc">
                We&apos;ll POST JSON payloads to this URL when events fire
              </div>
            </div>
            {isConfigured && (
              <span className="badge badge-success">
                <IconCheck size={12} />
                Active
              </span>
            )}
          </div>

          <div className="integration-card-body">
            <div className="webhook-form">
              <div className="api-key-input-row" style={{ marginBottom: 12 }}>
                <input
                  type="url"
                  className="input"
                  placeholder="https://your-app.com/webhooks/email-optimizer"
                  value={webhookUrl}
                  onChange={(e) => setWebhookUrl(e.target.value)}
                  id="webhook-url-input"
                />
              </div>

              <div className="webhook-secret-row" style={{ marginBottom: 16 }}>
                <div style={{ display: "flex", alignItems: "center", gap: 8, marginBottom: 6 }}>
                  <span style={{ fontSize: 12, fontWeight: 600, color: "var(--text-muted)", textTransform: "uppercase" as const, letterSpacing: "0.05em" }}>
                    Signing Secret
                  </span>
                  <span style={{ fontSize: 11, color: "var(--text-muted)" }}>(optional)</span>
                </div>
                <div className="api-key-input-row">
                  <input
                    type={showSecret ? "text" : "password"}
                    className="input api-key-input"
                    placeholder={hasSecret ? "••••••••••••••••" : "Optional HMAC-SHA256 signing secret"}
                    value={webhookSecret}
                    onChange={(e) => setWebhookSecret(e.target.value)}
                    id="webhook-secret-input"
                  />
                  <button
                    className="btn btn-ghost btn-sm"
                    onClick={() => setShowSecret(!showSecret)}
                    style={{ whiteSpace: "nowrap" }}
                  >
                    {showSecret ? "Hide" : "Show"}
                  </button>
                </div>
                <p style={{ fontSize: 11.5, color: "var(--text-muted)", marginTop: 6, lineHeight: 1.5 }}>
                  Events are signed with HMAC-SHA256. Verify using the <code style={{ fontSize: 11, background: "var(--bg-input)", padding: "1px 4px", borderRadius: 3 }}>X-Webhook-Signature</code> header.
                </p>
              </div>

              <div className="integration-actions">
                <button
                  className="btn btn-primary btn-sm"
                  onClick={saveConfig}
                  disabled={saving || !webhookUrl.trim()}
                  id="btn-save-webhook"
                >
                  {saving ? "Saving..." : "Save Configuration"}
                </button>
                {isConfigured && (
                  <button
                    className="btn btn-secondary btn-sm"
                    onClick={sendTest}
                    disabled={testing}
                    id="btn-test-webhook"
                  >
                    <IconSend size={13} />
                    {testing ? "Sending..." : "Send Test Event"}
                  </button>
                )}
              </div>
            </div>
          </div>
        </div>
      </div>

      {/* ─── Event Types ─── */}
      <div className="settings-section">
        <div className="settings-section-header">
          <h2 className="settings-section-title">Event Types</h2>
          <p className="settings-section-desc">
            Events your webhook will receive
          </p>
        </div>

        <div className="webhook-event-types">
          {EVENT_TYPES.map((evt) => (
            <div key={evt.type} className="webhook-event-type-row">
              <span
                className="webhook-event-dot"
                style={{ background: eventBadge(evt.type) }}
              />
              <div className="webhook-event-type-info">
                <code className="webhook-event-type-name">{evt.type}</code>
                <span className="webhook-event-type-desc">{evt.desc}</span>
              </div>
            </div>
          ))}
        </div>
      </div>

      {/* ─── Recent Events ─── */}
      <div className="settings-section">
        <div className="settings-section-header" style={{ display: "flex", justifyContent: "space-between", alignItems: "flex-start" }}>
          <div>
            <h2 className="settings-section-title">Event History</h2>
            <p className="settings-section-desc">
              Recent webhook delivery attempts
            </p>
          </div>
          <button
            className="btn btn-ghost btn-sm"
            onClick={fetchEvents}
            style={{ marginTop: 4 }}
          >
            <IconRefresh size={13} />
            Refresh
          </button>
        </div>

        <div className="card">
          {eventsLoading ? (
            <div style={{ padding: 32, textAlign: "center", color: "var(--text-muted)", fontSize: 14 }}>
              Loading events...
            </div>
          ) : events.length === 0 ? (
            <div style={{ padding: 32, textAlign: "center", color: "var(--text-muted)", fontSize: 14 }}>
              <IconWebhookBolt size={32} />
              <p style={{ marginTop: 12 }}>No webhook events yet</p>
              <p style={{ fontSize: 12.5, marginTop: 4 }}>
                Events will appear here when your pipeline processes leads
              </p>
            </div>
          ) : (
            <div className="webhook-events-list">
              {events.map((evt) => (
                <div
                  key={evt.id}
                  className={`webhook-event-row ${expandedEvent === evt.id ? "expanded" : ""}`}
                  onClick={() => setExpandedEvent(expandedEvent === evt.id ? null : evt.id)}
                >
                  <div className="webhook-event-main">
                    <span
                      className="webhook-event-dot"
                      style={{ background: eventBadge(evt.event_type) }}
                    />
                    <code className="webhook-event-type">{evt.event_type}</code>
                    <span className="webhook-event-status">
                      {evt.delivered ? (
                        <span className="badge badge-success" style={{ fontSize: 10.5, padding: "2px 6px" }}>
                          <IconCheck size={10} />
                          {evt.response_status || "OK"}
                        </span>
                      ) : (
                        <span className="badge badge-danger" style={{ fontSize: 10.5, padding: "2px 6px" }}>
                          <IconX size={10} />
                          Failed
                        </span>
                      )}
                    </span>
                    <span className="webhook-event-attempts" title={`${evt.attempts} attempt(s)`}>
                      ×{evt.attempts}
                    </span>
                    <span className="webhook-event-time">
                      {formatTime(evt.created_at)}
                    </span>
                  </div>

                  {expandedEvent === evt.id && evt.payload && (
                    <div className="webhook-event-payload animate-fade-in">
                      <div className="webhook-payload-header">
                        <span>Payload</span>
                        <button
                          className="btn btn-ghost btn-sm"
                          onClick={(e) => {
                            e.stopPropagation();
                            navigator.clipboard.writeText(JSON.stringify(evt.payload, null, 2));
                            showToast("Payload copied");
                          }}
                        >
                          <IconCopy size={12} />
                          Copy
                        </button>
                      </div>
                      <pre className="webhook-payload-json">
                        {JSON.stringify(evt.payload, null, 2)}
                      </pre>
                    </div>
                  )}
                </div>
              ))}
            </div>
          )}
        </div>
      </div>

      {/* ─── Payload Example ─── */}
      <div className="settings-section">
        <div className="settings-section-header">
          <h2 className="settings-section-title">Payload Format</h2>
          <p className="settings-section-desc">Example webhook payload structure</p>
        </div>
        <div className="card" style={{ padding: 0 }}>
          <pre className="webhook-payload-json" style={{ margin: 0, borderRadius: "var(--radius-md)" }}>
{`{
  "event": "batch.deployed",
  "timestamp": "2026-03-14T00:10:00.000Z",
  "data": {
    "batch_id": 42,
    "campaign_id": "cmp_abc123",
    "leads_added": 312
  }
}`}
          </pre>
        </div>
      </div>
    </div>
  );
}
