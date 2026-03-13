"use client";

import { useState, useEffect, useCallback } from "react";

/* ─── Types ─── */
interface ServiceStatus {
  connected: boolean;
  email?: string;
  sheet_id?: string;
  sheet_name?: string;
  expires_at?: string;
  created_at?: string;
  key_preview?: string;
}

interface ConnectionStatus {
  services: {
    google: ServiceStatus;
    openai: ServiceStatus;
    instantly: ServiceStatus;
    vayne: ServiceStatus;
    anymailfinder: ServiceStatus;
  };
}

interface SheetInfo {
  id: string;
  title: string;
  url: string;
}

/* ─── Icons ─── */
function IconGoogle({ size = 20 }: { size?: number }) {
  return (
    <svg width={size} height={size} viewBox="0 0 24 24" fill="none">
      <path d="M22.56 12.25c0-.78-.07-1.53-.2-2.25H12v4.26h5.92a5.06 5.06 0 0 1-2.2 3.32v2.77h3.57c2.08-1.92 3.28-4.74 3.28-8.1z" fill="#4285F4"/>
      <path d="M12 23c2.97 0 5.46-.98 7.28-2.66l-3.57-2.77c-.98.66-2.23 1.06-3.71 1.06-2.86 0-5.29-1.93-6.16-4.53H2.18v2.84C3.99 20.53 7.7 23 12 23z" fill="#34A853"/>
      <path d="M5.84 14.09c-.22-.66-.35-1.36-.35-2.09s.13-1.43.35-2.09V7.07H2.18C1.43 8.55 1 10.22 1 12s.43 3.45 1.18 4.93l2.85-2.22.81-.62z" fill="#FBBC05"/>
      <path d="M12 5.38c1.62 0 3.06.56 4.21 1.64l3.15-3.15C17.45 2.09 14.97 1 12 1 7.7 1 3.99 3.47 2.18 7.07l3.66 2.84c.87-2.6 3.3-4.53 6.16-4.53z" fill="#EA4335"/>
    </svg>
  );
}

function IconOpenAI({ size = 20 }: { size?: number }) {
  return (
    <svg width={size} height={size} viewBox="0 0 24 24" fill="currentColor">
      <path d="M22.282 9.821a5.985 5.985 0 0 0-.516-4.91 6.046 6.046 0 0 0-6.51-2.9A6.065 6.065 0 0 0 4.981 4.18a5.998 5.998 0 0 0-3.998 2.9 6.046 6.046 0 0 0 .743 7.097 5.98 5.98 0 0 0 .51 4.911 6.051 6.051 0 0 0 6.515 2.9A5.985 5.985 0 0 0 13.26 24a6.056 6.056 0 0 0 5.772-4.206 5.99 5.99 0 0 0 3.997-2.9 6.056 6.056 0 0 0-.747-7.073zM13.26 22.43a4.476 4.476 0 0 1-2.876-1.04l.141-.081 4.779-2.758a.795.795 0 0 0 .392-.681v-6.737l2.02 1.168a.071.071 0 0 1 .038.052v5.583a4.504 4.504 0 0 1-4.494 4.494zM3.6 18.304a4.47 4.47 0 0 1-.535-3.014l.142.085 4.783 2.759a.771.771 0 0 0 .78 0l5.843-3.369v2.332a.08.08 0 0 1-.033.062L9.74 19.95a4.5 4.5 0 0 1-6.14-1.646zM2.34 7.896a4.485 4.485 0 0 1 2.366-1.973V11.6a.766.766 0 0 0 .388.676l5.815 3.355-2.02 1.168a.076.076 0 0 1-.071 0l-4.83-2.786A4.504 4.504 0 0 1 2.34 7.872zm16.597 3.855l-5.833-3.387L15.119 7.2a.076.076 0 0 1 .071 0l4.83 2.791a4.494 4.494 0 0 1-.676 8.105v-5.678a.79.79 0 0 0-.407-.667zm2.01-3.023l-.141-.085-4.774-2.782a.776.776 0 0 0-.785 0L9.409 9.23V6.897a.066.066 0 0 1 .028-.061l4.83-2.787a4.5 4.5 0 0 1 6.68 4.66zm-12.64 4.135l-2.02-1.164a.08.08 0 0 1-.038-.057V6.075a4.5 4.5 0 0 1 7.375-3.453l-.142.08L8.704 5.46a.795.795 0 0 0-.393.681zm1.097-2.365l2.602-1.5 2.602 1.5v3.003l-2.602 1.5-2.602-1.5z"/>
    </svg>
  );
}

function IconKey({ size = 20 }: { size?: number }) {
  return (
    <svg width={size} height={size} viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.8" strokeLinecap="round" strokeLinejoin="round">
      <path d="M21 2l-2 2m-7.61 7.61a5.5 5.5 0 1 1-7.778 7.778 5.5 5.5 0 0 1 7.777-7.777zm0 0L15.5 7.5m0 0l3 3L22 7l-3-3m-3.5 3.5L19 4" />
    </svg>
  );
}

function IconCheck({ size = 16 }: { size?: number }) {
  return (
    <svg width={size} height={size} viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2.5" strokeLinecap="round" strokeLinejoin="round">
      <polyline points="20 6 9 17 4 12" />
    </svg>
  );
}

function IconX({ size = 16 }: { size?: number }) {
  return (
    <svg width={size} height={size} viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
      <line x1="18" y1="6" x2="6" y2="18" />
      <line x1="6" y1="6" x2="18" y2="18" />
    </svg>
  );
}

function IconExternalLink({ size = 14 }: { size?: number }) {
  return (
    <svg width={size} height={size} viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
      <path d="M18 13v6a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2V8a2 2 0 0 1 2-2h6" />
      <polyline points="15 3 21 3 21 9" />
      <line x1="10" y1="14" x2="21" y2="3" />
    </svg>
  );
}

function IconShield({ size = 16 }: { size?: number }) {
  return (
    <svg width={size} height={size} viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.8" strokeLinecap="round" strokeLinejoin="round">
      <path d="M12 22s8-4 8-10V5l-8-3-8 3v7c0 6 8 10 8 10z" />
    </svg>
  );
}

function IconSpreadsheet({ size = 18 }: { size?: number }) {
  return (
    <svg width={size} height={size} viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.8" strokeLinecap="round" strokeLinejoin="round">
      <rect x="3" y="3" width="18" height="18" rx="2" ry="2" />
      <line x1="3" y1="9" x2="21" y2="9" />
      <line x1="3" y1="15" x2="21" y2="15" />
      <line x1="9" y1="3" x2="9" y2="21" />
    </svg>
  );
}

/* ─── Constants ─── */
const API_BASE = process.env.NEXT_PUBLIC_API_URL || "http://localhost:8000";
// TODO: Replace with actual user auth
const MOCK_USER_ID = "dev-user-001";

const API_KEY_SERVICES = [
  {
    id: "openai",
    name: "OpenAI",
    icon: <IconOpenAI />,
    description: "Powers AI email generation and company research",
    placeholder: "sk-...",
    helpUrl: "https://platform.openai.com/api-keys",
    helpText: "Get your API key from OpenAI Platform",
    color: "#10a37f",
  },
  {
    id: "instantly",
    name: "Instantly",
    icon: <IconKey />,
    description: "Sends and manages cold email campaigns",
    placeholder: "Your Instantly API key",
    helpUrl: "https://app.instantly.ai/api",
    helpText: "Find your key in Instantly settings",
    color: "#5b5fc7",
  },
  {
    id: "vayne",
    name: "Vayne",
    icon: <IconKey />,
    description: "Scrapes leads from Sales Navigator",
    placeholder: "Your Vayne API token",
    helpUrl: "",
    helpText: "Contact Vayne for API access",
    color: "#0ea5e9",
  },
  {
    id: "anymailfinder",
    name: "Anymailfinder",
    icon: <IconKey />,
    description: "Finds and validates email addresses",
    placeholder: "Your Anymailfinder API key",
    helpUrl: "https://anymailfinder.com/dashboard",
    helpText: "Get your key from the dashboard",
    color: "#f59e0b",
  },
];

/* ─── Main Settings Panel ─── */
export default function SettingsPanel() {
  const [status, setStatus] = useState<ConnectionStatus | null>(null);
  const [loading, setLoading] = useState(true);
  const [sheets, setSheets] = useState<SheetInfo[]>([]);
  const [sheetsLoading, setSheetsLoading] = useState(false);
  const [apiKeyInputs, setApiKeyInputs] = useState<Record<string, string>>({});
  const [savingService, setSavingService] = useState<string | null>(null);
  const [savedService, setSavedService] = useState<string | null>(null);
  const [toastMessage, setToastMessage] = useState<string | null>(null);

  const fetchStatus = useCallback(async () => {
    try {
      const res = await fetch(`${API_BASE}/auth/status?user_id=${MOCK_USER_ID}`);
      if (res.ok) {
        const data = await res.json();
        setStatus(data);
      }
    } catch (e) {
      console.error("Failed to fetch connection status:", e);
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    fetchStatus();

    // Check for OAuth callback success
    const params = new URLSearchParams(window.location.search);
    if (params.get("google") === "connected") {
      showToast("Google Sheets connected successfully!");
      window.history.replaceState({}, "", window.location.pathname);
      fetchStatus();
    }
  }, [fetchStatus]);

  function showToast(msg: string) {
    setToastMessage(msg);
    setTimeout(() => setToastMessage(null), 4000);
  }

  /* ─── Google OAuth Actions ─── */
  async function connectGoogle() {
    try {
      const res = await fetch(`${API_BASE}/auth/google/login?user_id=${MOCK_USER_ID}`);
      const data = await res.json();
      if (data.auth_url) {
        window.location.href = data.auth_url;
      }
    } catch (e) {
      showToast("Failed to start Google authorization");
    }
  }

  async function disconnectGoogle() {
    try {
      const res = await fetch(
        `${API_BASE}/auth/google/disconnect?user_id=${MOCK_USER_ID}`,
        { method: "DELETE" }
      );
      if (res.ok) {
        showToast("Google Sheets disconnected");
        fetchStatus();
        setSheets([]);
      }
    } catch (e) {
      showToast("Failed to disconnect Google");
    }
  }

  async function loadSheets() {
    setSheetsLoading(true);
    try {
      const res = await fetch(`${API_BASE}/auth/google/sheets?user_id=${MOCK_USER_ID}`);
      if (res.ok) {
        const data = await res.json();
        setSheets(data.sheets || []);
      }
    } catch (e) {
      showToast("Failed to load spreadsheets");
    } finally {
      setSheetsLoading(false);
    }
  }

  async function selectSheet(sheetId: string, sheetName: string) {
    try {
      const res = await fetch(`${API_BASE}/auth/google/sheets/select`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ user_id: MOCK_USER_ID, sheet_id: sheetId, sheet_name: sheetName }),
      });
      if (res.ok) {
        showToast(`Selected sheet: ${sheetName}`);
        fetchStatus();
      }
    } catch (e) {
      showToast("Failed to select sheet");
    }
  }

  /* ─── API Key Actions ─── */
  async function saveApiKey(service: string) {
    const key = apiKeyInputs[service];
    if (!key?.trim()) return;

    setSavingService(service);
    try {
      const res = await fetch(`${API_BASE}/auth/api-keys`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ user_id: MOCK_USER_ID, service, api_key: key.trim() }),
      });
      if (res.ok) {
        setSavedService(service);
        setApiKeyInputs((prev) => ({ ...prev, [service]: "" }));
        showToast(`${service.charAt(0).toUpperCase() + service.slice(1)} key saved securely`);
        fetchStatus();
        setTimeout(() => setSavedService(null), 2000);
      }
    } catch (e) {
      showToast("Failed to save API key");
    } finally {
      setSavingService(null);
    }
  }

  async function deleteApiKey(service: string) {
    try {
      const res = await fetch(
        `${API_BASE}/auth/api-keys/${service}?user_id=${MOCK_USER_ID}`,
        { method: "DELETE" }
      );
      if (res.ok) {
        showToast(`${service.charAt(0).toUpperCase() + service.slice(1)} key removed`);
        fetchStatus();
      }
    } catch (e) {
      showToast("Failed to remove API key");
    }
  }

  /* ─── Render ─── */
  const googleStatus = status?.services?.google;
  const isGoogleConnected = googleStatus?.connected || false;

  return (
    <div className="settings-panel">
      {/* Toast */}
      {toastMessage && (
        <div className="settings-toast animate-slide-in">
          <IconCheck size={14} />
          {toastMessage}
        </div>
      )}

      {/* ─── Section: Integrations ─── */}
      <div className="settings-section">
        <div className="settings-section-header">
          <h2 className="settings-section-title">Integrations</h2>
          <p className="settings-section-desc">
            Connect your accounts to enable the full pipeline
          </p>
        </div>

        {/* Google Sheets Card */}
        <div className={`integration-card ${isGoogleConnected ? "connected" : ""}`} id="integration-google">
          <div className="integration-card-header">
            <div className="integration-icon google">
              <IconGoogle size={22} />
            </div>
            <div className="integration-info">
              <div className="integration-name">Google Sheets</div>
              <div className="integration-desc">
                Sync deployed leads to your Google spreadsheet
              </div>
            </div>
            <div className="integration-status-badge">
              {isGoogleConnected ? (
                <span className="badge badge-success">
                  <IconCheck size={12} />
                  Connected
                </span>
              ) : (
                <span className="badge badge-info">Not connected</span>
              )}
            </div>
          </div>

          {isGoogleConnected ? (
            <div className="integration-card-body">
              <div className="integration-connected-info">
                <div className="connected-detail">
                  <span className="connected-label">Account</span>
                  <span className="connected-value">{googleStatus?.email || "—"}</span>
                </div>
                {googleStatus?.sheet_name && (
                  <div className="connected-detail">
                    <span className="connected-label">Syncing to</span>
                    <span className="connected-value">
                      <IconSpreadsheet size={14} />
                      {googleStatus.sheet_name}
                    </span>
                  </div>
                )}
              </div>

              <div className="integration-actions">
                <button
                  className="btn btn-secondary btn-sm"
                  onClick={loadSheets}
                  disabled={sheetsLoading}
                  id="btn-browse-sheets"
                >
                  <IconSpreadsheet size={14} />
                  {sheetsLoading ? "Loading..." : "Choose Sheet"}
                </button>
                <button
                  className="btn btn-ghost btn-sm btn-danger-text"
                  onClick={disconnectGoogle}
                  id="btn-disconnect-google"
                >
                  Disconnect
                </button>
              </div>

              {/* Sheet picker */}
              {sheets.length > 0 && (
                <div className="sheet-picker animate-fade-in">
                  <div className="sheet-picker-header">Select a spreadsheet</div>
                  <div className="sheet-list">
                    {sheets.map((sheet) => (
                      <div
                        key={sheet.id}
                        className={`sheet-item ${googleStatus?.sheet_id === sheet.id ? "selected" : ""}`}
                        onClick={() => selectSheet(sheet.id, sheet.title)}
                      >
                        <IconSpreadsheet size={16} />
                        <span className="sheet-title">{sheet.title}</span>
                        {googleStatus?.sheet_id === sheet.id && (
                          <IconCheck size={14} />
                        )}
                      </div>
                    ))}
                  </div>
                </div>
              )}
            </div>
          ) : (
            <div className="integration-card-body">
              <button
                className="btn btn-google"
                onClick={connectGoogle}
                id="btn-connect-google"
              >
                <IconGoogle size={18} />
                Connect Google Sheets
              </button>
            </div>
          )}
        </div>
      </div>

      {/* ─── Section: API Keys ─── */}
      <div className="settings-section">
        <div className="settings-section-header">
          <h2 className="settings-section-title">API Keys</h2>
          <p className="settings-section-desc">
            Your keys are encrypted at rest and never leave this server
          </p>
          <div className="security-badge">
            <IconShield size={13} />
            AES-256 encrypted
          </div>
        </div>

        <div className="api-keys-grid">
          {API_KEY_SERVICES.map((svc) => {
            const svcStatus = status?.services?.[svc.id as keyof typeof status.services];
            const isConnected = svcStatus?.connected || false;
            const isSaving = savingService === svc.id;
            const justSaved = savedService === svc.id;

            return (
              <div
                key={svc.id}
                className={`api-key-card ${isConnected ? "connected" : ""}`}
                id={`api-key-${svc.id}`}
              >
                <div className="api-key-header">
                  <div
                    className="api-key-icon"
                    style={{ "--svc-color": svc.color } as React.CSSProperties}
                  >
                    {svc.icon}
                  </div>
                  <div className="api-key-info">
                    <div className="api-key-name">{svc.name}</div>
                    <div className="api-key-desc">{svc.description}</div>
                  </div>
                </div>

                {isConnected ? (
                  <div className="api-key-connected">
                    <div className="api-key-preview">
                      <IconCheck size={14} />
                      <span>Key saved: <code>{(svcStatus as ServiceStatus)?.key_preview}</code></span>
                    </div>
                    <div className="api-key-actions">
                      <button
                        className="btn btn-ghost btn-sm"
                        onClick={() => {
                          /* Toggle to show input for update */
                          setApiKeyInputs((prev) => ({
                            ...prev,
                            [svc.id]: prev[svc.id] !== undefined ? "" : " ",
                          }));
                        }}
                      >
                        Update
                      </button>
                      <button
                        className="btn btn-ghost btn-sm btn-danger-text"
                        onClick={() => deleteApiKey(svc.id)}
                      >
                        Remove
                      </button>
                    </div>
                  </div>
                ) : null}

                {(!isConnected || apiKeyInputs[svc.id]) && (
                  <div className="api-key-input-row">
                    <input
                      type="password"
                      className="input api-key-input"
                      placeholder={svc.placeholder}
                      value={apiKeyInputs[svc.id] || ""}
                      onChange={(e) =>
                        setApiKeyInputs((prev) => ({ ...prev, [svc.id]: e.target.value }))
                      }
                      onKeyDown={(e) => e.key === "Enter" && saveApiKey(svc.id)}
                    />
                    <button
                      className={`btn btn-primary btn-sm ${justSaved ? "btn-success-flash" : ""}`}
                      onClick={() => saveApiKey(svc.id)}
                      disabled={isSaving || !apiKeyInputs[svc.id]?.trim()}
                    >
                      {isSaving ? "Saving..." : justSaved ? "Saved!" : "Save"}
                    </button>
                  </div>
                )}

                {svc.helpUrl && (
                  <a
                    href={svc.helpUrl}
                    target="_blank"
                    rel="noopener noreferrer"
                    className="api-key-help"
                  >
                    {svc.helpText}
                    <IconExternalLink size={12} />
                  </a>
                )}
              </div>
            );
          })}
        </div>
      </div>
    </div>
  );
}
