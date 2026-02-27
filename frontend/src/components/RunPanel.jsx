import { useState } from "react";
import { motion } from "framer-motion";
import ReactMarkdown from "react-markdown";

const RUN_TYPES = [
  {
    key: "candidate",
    label: "Candidate Research",
    icon: "\u{1F50D}",
    desc: "Analyze a GitHub profile for a target role",
    fields: [
      { name: "github_username", label: "GitHub Username", placeholder: "e.g. torvalds", required: true },
      { name: "target_role", label: "Target Role", placeholder: "e.g. Backend Engineer", required: true },
      { name: "candidate_name", label: "Candidate Name", placeholder: "Optional" },
      { name: "company_context", label: "Company Context", placeholder: "e.g. We build AI tools for startups" },
    ],
  },
  {
    key: "digest",
    label: "Commit Digest",
    icon: "\u{1F4CA}",
    desc: "Generate a feature-grouped commit summary",
    fields: [
      { name: "repo", label: "Repository", placeholder: "owner/repo (e.g. SeanAminov/Orq)", required: true },
      { name: "author", label: "Author Filter", placeholder: "Optional (e.g. Sean)" },
      { name: "path_filter", label: "Path Filter", placeholder: "Optional (e.g. frontend/)" },
      { name: "since_days", label: "Days Back", placeholder: "7", type: "number" },
    ],
  },
];

export default function RunPanel() {
  const [runType, setRunType] = useState(null);
  const [formData, setFormData] = useState({});
  const [loading, setLoading] = useState(false);
  const [result, setResult] = useState(null);
  const [error, setError] = useState(null);

  const handleRun = async () => {
    if (!runType) return;
    setLoading(true);
    setError(null);
    setResult(null);

    const endpoint = runType === "candidate"
      ? "/api/runs/candidate-research"
      : "/api/runs/commit-digest";

    // transform form data
    const body = { ...formData };
    if (body.since_days) body.since_days = parseInt(body.since_days) || 7;
    if (runType === "candidate") body.generate_outreach = true;

    try {
      const res = await fetch(endpoint, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        credentials: "include",
        body: JSON.stringify(body),
      });

      if (!res.ok) {
        const err = await res.json();
        throw new Error(err.detail || `Error ${res.status}`);
      }

      const data = await res.json();
      setResult(data);
    } catch (e) {
      setError(e.message);
    } finally {
      setLoading(false);
    }
  };

  const config = RUN_TYPES.find((r) => r.key === runType);

  return (
    <div className="run-panel">
      {/* Type selector */}
      {!runType && (
        <div className="run-type-grid">
          <h3>Choose a Workflow</h3>
          <p className="run-subtitle">Multi-agent pipelines powered by CrewAI + Composio + Snowflake</p>
          <div className="run-type-cards">
            {RUN_TYPES.map((rt) => (
              <motion.div
                key={rt.key}
                className="run-type-card"
                whileHover={{ scale: 1.02 }}
                whileTap={{ scale: 0.98 }}
                onClick={() => { setRunType(rt.key); setFormData({}); setResult(null); }}
              >
                <span className="run-type-icon">{rt.icon}</span>
                <strong>{rt.label}</strong>
                <p>{rt.desc}</p>
              </motion.div>
            ))}
          </div>
        </div>
      )}

      {/* Form */}
      {runType && !result && (
        <div className="run-form">
          <button className="btn-back" onClick={() => { setRunType(null); setResult(null); }}>
            &larr; Back
          </button>
          <h3>{config.icon} {config.label}</h3>
          <p className="run-subtitle">{config.desc}</p>

          {config.fields.map((f) => (
            <div key={f.name} className="run-field">
              <label>{f.label} {f.required && <span className="required">*</span>}</label>
              <input
                type={f.type || "text"}
                placeholder={f.placeholder}
                value={formData[f.name] || ""}
                onChange={(e) => setFormData((prev) => ({ ...prev, [f.name]: e.target.value }))}
                disabled={loading}
              />
            </div>
          ))}

          {error && <div className="run-error">{error}</div>}

          <button
            className="btn-run"
            onClick={handleRun}
            disabled={loading || !config.fields.filter((f) => f.required).every((f) => formData[f.name]?.trim())}
          >
            {loading ? "Running crew..." : `Run ${config.label}`}
          </button>

          {loading && (
            <div className="run-progress">
              <div className="progress-bar"><div className="progress-fill" /></div>
              <p>Multi-agent crew is working. This may take 30-60 seconds...</p>
              <div className="agent-steps">
                {runType === "candidate" ? (
                  <>
                    <span className="step active">Planner</span>
                    <span className="step-arrow">&rarr;</span>
                    <span className="step">GitHub</span>
                    <span className="step-arrow">&rarr;</span>
                    <span className="step">Analysis</span>
                    <span className="step-arrow">&rarr;</span>
                    <span className="step">Role Fit</span>
                    <span className="step-arrow">&rarr;</span>
                    <span className="step">Brief</span>
                  </>
                ) : (
                  <>
                    <span className="step active">Fetch</span>
                    <span className="step-arrow">&rarr;</span>
                    <span className="step">Analyze</span>
                    <span className="step-arrow">&rarr;</span>
                    <span className="step">Digest</span>
                    <span className="step-arrow">&rarr;</span>
                    <span className="step">Publish</span>
                  </>
                )}
              </div>
            </div>
          )}
        </div>
      )}

      {/* Result */}
      {result && (
        <div className="run-result">
          <button className="btn-back" onClick={() => { setRunType(null); setResult(null); setFormData({}); }}>
            &larr; New Run
          </button>

          <div className="run-result-header">
            <h3>{config.icon} {config.label} Complete</h3>
            <span className="run-id">Run: {result.run_id}</span>
          </div>

          {/* Trace */}
          {result.trace && (
            <div className="run-trace">
              {result.trace.map((t, i) => (
                <span key={i} className={`trace-step ${t.status}`}>
                  {t.status === "success" ? "\u2705" : "\u274C"} {t.task}
                </span>
              ))}
            </div>
          )}

          {/* Main content */}
          <div className="run-content">
            <ReactMarkdown
              components={{
                code({ node, inline, className, children, ...props }) {
                  if (inline) return <code className="inline-code" {...props}>{children}</code>;
                  return <pre className="code-block"><code {...props}>{children}</code></pre>;
                },
              }}
            >
              {result.candidate_brief || result.digest_markdown || JSON.stringify(result, null, 2)}
            </ReactMarkdown>
          </div>

          {/* Outreach message */}
          {result.outreach_message && (
            <div className="run-outreach">
              <h4>Draft Outreach Message</h4>
              <div className="outreach-box">{result.outreach_message}</div>
            </div>
          )}

          {/* Metadata */}
          <div className="run-meta">
            {result.github_data && (
              <span>Repos analyzed: {result.github_data.repo_count} ({result.github_data.repos?.join(", ")})</span>
            )}
            {result.commit_count !== undefined && (
              <span>Commits analyzed: {result.commit_count}</span>
            )}
            {result.email_status && <span>Email: {result.email_status}</span>}
            {result.doc_status && <span>Google Doc: {result.doc_status}</span>}
          </div>
        </div>
      )}
    </div>
  );
}
