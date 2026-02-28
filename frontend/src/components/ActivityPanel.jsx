import { useState } from "react";
import RunPanel from "./RunPanel";
import DocsPanel from "./DocsPanel";

const INTENT_COLORS = {
  crew:   { bg: "rgba(108, 92, 231, 0.15)", color: "#6c5ce7", label: "Crew" },
  action: { bg: "rgba(0, 206, 201, 0.15)",  color: "#00cec9", label: "Action" },
  data:   { bg: "rgba(9, 132, 227, 0.15)",  color: "#0984e3", label: "Data" },
  pay:    { bg: "rgba(253, 203, 110, 0.2)", color: "#f39c12", label: "Pay" },
  chat:   { bg: "rgba(150, 150, 170, 0.15)",color: "#999", label: "Chat" },
};

function IntentBadge({ intent }) {
  const style = INTENT_COLORS[intent?.toLowerCase()] || INTENT_COLORS.chat;
  return (
    <span className="ap-badge" style={{ background: style.bg, color: style.color }}>
      {style.label}
    </span>
  );
}

function StatusDot({ status }) {
  const color = status === "completed" ? "#00cec9" : status === "failed" ? "#ff6b6b" : "#f39c12";
  return <span className="ap-status-dot" style={{ background: color }} />;
}

export default function ActivityPanel({ runs, tools, room, onClearChat, onClearActivity }) {
  const [tab, setTab] = useState("activity");

  return (
    <div className="activity-panel">
      <div className="ap-tabs">
        <button className={`ap-tab ${tab === "activity" ? "active" : ""}`} onClick={() => setTab("activity")}>
          Activity
        </button>
        <button className={`ap-tab ${tab === "workflows" ? "active" : ""}`} onClick={() => setTab("workflows")}>
          Workflows
        </button>
        <button className={`ap-tab ${tab === "docs" ? "active" : ""}`} onClick={() => setTab("docs")}>
          Docs
        </button>
      </div>

      <div className="ap-content">
        {tab === "activity" && (
          <>
            {/* Agent Runs */}
            <div className="ap-section">
              <h4>Agent Runs</h4>
              {runs.length === 0 ? (
                <p className="ap-empty">No agent runs yet. Use @orq to trigger the AI.</p>
              ) : (
                <div className="ap-runs">
                  {runs.map((r) => (
                    <div key={r.id} className="ap-run-card">
                      <div className="ap-run-top">
                        <IntentBadge intent={r.intent} />
                        <StatusDot status={r.status} />
                        <span className="ap-run-status">{r.status}</span>
                      </div>
                      <div className="ap-run-user">{r.user_name}</div>
                      <div className="ap-run-input">{r.input_text}</div>
                      {r.status === "running" && (
                        <div className="ap-run-progress">
                          <div className="ap-progress-bar"><div className="ap-progress-fill" /></div>
                        </div>
                      )}
                      {r.cost_usd && parseFloat(r.cost_usd) > 0 && (
                        <div className="ap-run-cost">
                          ${parseFloat(r.cost_usd).toFixed(4)} &middot; {r.tokens_used || 0} tokens
                        </div>
                      )}
                      <div className="ap-run-time">
                        {new Date(r.created_at).toLocaleTimeString([], { hour: "2-digit", minute: "2-digit" })}
                      </div>
                    </div>
                  ))}
                </div>
              )}
            </div>

            {/* Integrations */}
            <div className="ap-section">
              <h4>Integrations</h4>
              <div className="ap-tools">
                {Object.entries(tools).map(([key, t]) => (
                  <div key={key} className={`ap-tool ${t.active ? "active" : "inactive"}`}>
                    <span className="ap-tool-dot" />
                    <div>
                      <strong>{t.label}</strong>
                      <span>{t.description}</span>
                    </div>
                  </div>
                ))}
              </div>
            </div>

            {/* Actions */}
            <div className="ap-section ap-actions">
              <button className="ap-clear-btn" onClick={onClearChat}>Clear My Chat</button>
              <button className="ap-clear-btn" onClick={onClearActivity}>Clear My Activity</button>
            </div>
          </>
        )}

        {tab === "workflows" && (
          <div className="ap-workflows">
            <RunPanel />
          </div>
        )}

        {tab === "docs" && (
          <div className="ap-docs">
            <DocsPanel />
          </div>
        )}
      </div>
    </div>
  );
}
