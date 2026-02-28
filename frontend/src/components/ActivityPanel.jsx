import { useState } from "react";
import RunPanel from "./RunPanel";
import DocsPanel from "./DocsPanel";

const INTENT_COLORS = {
  crew:   { bg: "rgba(139, 92, 246, 0.12)", color: "#8b5cf6", label: "Crew" },
  action: { bg: "rgba(34, 197, 94, 0.12)",  color: "#22c55e", label: "Action" },
  data:   { bg: "rgba(59, 130, 246, 0.12)", color: "#3b82f6", label: "Data" },
  pay:    { bg: "rgba(245, 158, 11, 0.12)", color: "#f59e0b", label: "Pay" },
  chat:   { bg: "rgba(161, 161, 170, 0.12)", color: "#a1a1aa", label: "Chat" },
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
  const color = status === "completed" ? "#22c55e" : status === "failed" ? "#ef4444" : "#f59e0b";
  return <span className="ap-status-dot" style={{ background: color }} />;
}

export default function ActivityPanel({ runs, tools, room, memories, onDeleteMemory, onClearChat, onClearActivity }) {
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

            {/* Learning Memory */}
            <div className="ap-section">
              <h4>Memory {memories && memories.length > 0 && <span className="ap-memory-count">{memories.length}</span>}</h4>
              {!memories || memories.length === 0 ? (
                <p className="ap-empty">No memories yet. Orq learns facts from your messages automatically.</p>
              ) : (
                <div className="ap-memories">
                  {memories.map((m) => (
                    <div key={m.id} className="ap-memory-card">
                      <div className="ap-memory-text">
                        <span className="ap-memory-subject">{m.subject}</span>
                        <span className="ap-memory-key">{m.key}</span>
                        <span className="ap-memory-value">{m.value}</span>
                      </div>
                      <button className="ap-memory-delete" onClick={() => onDeleteMemory && onDeleteMemory(m.id)} title="Forget this">
                        &times;
                      </button>
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

        <div className="ap-workflows" style={{ display: tab === "workflows" ? "block" : "none" }}>
          <RunPanel />
        </div>

        <div className="ap-docs" style={{ display: tab === "docs" ? "block" : "none" }}>
          <DocsPanel />
        </div>
      </div>
    </div>
  );
}
