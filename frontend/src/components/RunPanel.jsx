import { useState, useEffect } from "react";
import { motion } from "framer-motion";
import ReactMarkdown from "react-markdown";

const RUN_TYPES = [
  {
    key: "candidate",
    label: "Candidate Research",
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
    desc: "Generate a feature-grouped commit summary",
    fields: [
      { name: "repo", label: "Repository", placeholder: "owner/repo (e.g. SeanAminov/Orq)", required: true },
      { name: "author", label: "Author Filter", placeholder: "Optional (e.g. Sean)" },
      { name: "path_filter", label: "Path Filter", placeholder: "Optional (e.g. frontend/)" },
      { name: "since_days", label: "Days Back", placeholder: "7", type: "number" },
    ],
  },
];

const STEP_TYPES = [
  { value: "chat", label: "Chat" },
  { value: "action", label: "Action (Composio)" },
  { value: "crew", label: "Crew (CrewAI)" },
  { value: "data", label: "Data (Snowflake)" },
  { value: "research", label: "Research (Skyfire)" },
  { value: "clean", label: "Clean Text (Skyfire)" },
];

const RUN_ACTIONS = {
  candidate: [
    { label: "Schedule Interview", command: "@action create a Google Calendar event for a candidate interview based on the research brief above" },
    { label: "Save as Google Doc", command: "@action create a Google Doc with the candidate research brief above" },
    { label: "Commit to GitHub", command: "@action commit the candidate research brief as a markdown file to GitHub" },
    { label: "Email to Team", command: "@action email room members the candidate research brief above" },
  ],
  digest: [
    { label: "Email Digest to Team", command: "@action email room members the commit digest above" },
    { label: "Save as Google Doc", command: "@action create a Google Doc with the commit digest above" },
    { label: "Schedule Review", command: "@action create a Google Calendar event for a code review meeting to discuss the commit digest above" },
  ],
};

export default function RunPanel({ onWorkflowChange, onAction }) {
  const [runType, setRunType] = useState(null);
  const [formData, setFormData] = useState({});
  const [loading, setLoading] = useState(false);
  const [result, setResult] = useState(null);
  const [error, setError] = useState(null);

  // Workflow form state (shared for create & edit)
  const [showWorkflowForm, setShowWorkflowForm] = useState(false);
  const [editingWorkflow, setEditingWorkflow] = useState(null); // null = create mode, object = edit mode
  const [wfName, setWfName] = useState("");
  const [wfTrigger, setWfTrigger] = useState("");
  const [wfDescription, setWfDescription] = useState("");
  const [wfSteps, setWfSteps] = useState([{ type: "chat", prompt: "", usePrevResult: false }]);
  const [wfSaving, setWfSaving] = useState(false);
  const [wfError, setWfError] = useState(null);

  // Workflow list
  const [workflows, setWorkflows] = useState([]);

  useEffect(() => {
    fetchWorkflows();
  }, []);

  const fetchWorkflows = () => {
    fetch("/api/workflows", { credentials: "include" })
      .then((r) => r.json())
      .then(setWorkflows)
      .catch(() => {});
  };

  const resetWorkflowForm = () => {
    setWfName("");
    setWfTrigger("");
    setWfDescription("");
    setWfSteps([{ type: "chat", prompt: "", usePrevResult: false }]);
    setWfError(null);
    setEditingWorkflow(null);
  };

  const openCreateForm = () => {
    resetWorkflowForm();
    setShowWorkflowForm(true);
  };

  const openEditForm = (wf) => {
    setEditingWorkflow(wf);
    setWfName(wf.name);
    setWfTrigger(wf.trigger);
    setWfDescription(wf.description || "");
    setWfSteps(wf.steps.map((s, i) => {
      const hasFlag = !!s.usePrevResult;
      const hasPlaceholder = s.prompt.includes("{{prev_result}}");
      return {
        type: s.type,
        prompt: hasPlaceholder && !hasFlag ? s.prompt.replace(/\{\{prev_result\}\}/g, "").trim() : s.prompt,
        usePrevResult: i > 0 && (hasFlag || hasPlaceholder),
      };
    }));
    setWfError(null);
    setShowWorkflowForm(true);
  };

  const handleRun = async () => {
    if (!runType) return;
    setLoading(true);
    setError(null);
    setResult(null);

    const endpoint = runType === "candidate"
      ? "/api/runs/candidate-research"
      : "/api/runs/commit-digest";

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
      setResult(await res.json());
    } catch (e) {
      setError(e.message);
    } finally {
      setLoading(false);
    }
  };

  const handleSaveWorkflow = async () => {
    if (!wfName.trim() || !wfTrigger.trim() || wfSteps.some((s) => !s.prompt.trim())) return;
    setWfSaving(true);
    setWfError(null);

    const isEdit = !!editingWorkflow;
    const url = isEdit ? `/api/workflows/${editingWorkflow.id}` : "/api/workflows";
    const method = isEdit ? "PUT" : "POST";

    try {
      const res = await fetch(url, {
        method,
        headers: { "Content-Type": "application/json" },
        credentials: "include",
        body: JSON.stringify({
          name: wfName,
          trigger: wfTrigger.replace(/^@/, ""),
          description: wfDescription,
          steps: wfSteps.map((s, i) => ({
            type: s.type,
            prompt: s.prompt,
            usePrevResult: i > 0 && !!s.usePrevResult,
          })),
        }),
      });
      if (!res.ok) {
        const err = await res.json();
        throw new Error(err.detail || `Error ${res.status}`);
      }
      resetWorkflowForm();
      setShowWorkflowForm(false);
      fetchWorkflows();
      onWorkflowChange?.();
    } catch (e) {
      setWfError(e.message);
    } finally {
      setWfSaving(false);
    }
  };

  const handleDeleteWorkflow = async (id) => {
    await fetch(`/api/workflows/${id}`, { method: "DELETE", credentials: "include" });
    fetchWorkflows();
    onWorkflowChange?.();
  };

  const addStep = () => setWfSteps((prev) => [...prev, { type: "chat", prompt: "", usePrevResult: true }]);
  const removeStep = (idx) => setWfSteps((prev) => prev.filter((_, i) => i !== idx));
  const updateStep = (idx, field, value) =>
    setWfSteps((prev) => prev.map((s, i) => (i === idx ? { ...s, [field]: value } : s)));

  const config = RUN_TYPES.find((r) => r.key === runType);

  return (
    <div className="run-panel">
      {/* Main menu: show run types + create workflow button + workflow list */}
      {!runType && !showWorkflowForm && (
        <div className="run-type-grid">
          <h3>Workflows</h3>
          <p className="run-subtitle">Built-in pipelines and custom automations</p>
          <div className="run-type-cards">
            {RUN_TYPES.map((rt) => (
              <motion.div
                key={rt.key}
                className="run-type-card"
                whileHover={{ scale: 1.02 }}
                whileTap={{ scale: 0.98 }}
                onClick={() => { setRunType(rt.key); setFormData({}); setResult(null); }}
              >
                <strong>{rt.label}</strong>
                <p>{rt.desc}</p>
              </motion.div>
            ))}
            <motion.div
              className="run-type-card wf-create-card"
              whileHover={{ scale: 1.02 }}
              whileTap={{ scale: 0.98 }}
              onClick={openCreateForm}
            >
              <strong>+ Create Workflow</strong>
              <p>Build a custom multi-step automation</p>
            </motion.div>
          </div>

          {/* Custom workflow list */}
          {workflows.length > 0 && (
            <div className="wf-list">
              <h4>Your Workflows</h4>
              {workflows.map((w) => (
                <div key={w.id} className="wf-card">
                  <div className="wf-card-header">
                    <span className="wf-trigger">@{w.trigger}</span>
                    <span className="wf-name">{w.name}</span>
                    <div className="wf-card-actions">
                      <button className="wf-edit" onClick={() => openEditForm(w)} title="Edit">&#9998;</button>
                      <button className="wf-delete" onClick={() => handleDeleteWorkflow(w.id)} title="Delete">&times;</button>
                    </div>
                  </div>
                  {w.description && <p className="wf-desc">{w.description}</p>}
                  <div className="wf-steps-preview">
                    {w.steps.map((s, i) => (
                      <span key={i} className="wf-step-badge">
                        {i + 1}. {s.type}
                      </span>
                    ))}
                  </div>
                </div>
              ))}
            </div>
          )}
        </div>
      )}

      {/* Create / Edit Workflow Form */}
      {showWorkflowForm && (
        <div className="run-form wf-create-form">
          <button className="btn-back" onClick={() => { setShowWorkflowForm(false); resetWorkflowForm(); }}>
            &larr; Back
          </button>
          <h3>{editingWorkflow ? "Edit Workflow" : "Create Workflow"}</h3>
          <p className="run-subtitle">
            {editingWorkflow
              ? `Editing @${editingWorkflow.trigger}`
              : "Define a custom multi-step automation triggered by @mention"}
          </p>

          <div className="run-field">
            <label>Workflow Name <span className="required">*</span></label>
            <input
              type="text"
              placeholder="e.g. Summary Send"
              value={wfName}
              onChange={(e) => setWfName(e.target.value)}
            />
          </div>

          <div className="run-field">
            <label>Trigger <span className="required">*</span></label>
            <div className="wf-trigger-input">
              <span className="wf-at">@</span>
              <input
                type="text"
                placeholder="e.g. SummarySend"
                value={wfTrigger}
                onChange={(e) => setWfTrigger(e.target.value.replace(/\s/g, ""))}
              />
            </div>
          </div>

          <div className="run-field">
            <label>Description</label>
            <input
              type="text"
              placeholder="e.g. Summarizes conversation and creates a Google Doc"
              value={wfDescription}
              onChange={(e) => setWfDescription(e.target.value)}
            />
          </div>

          <div className="wf-steps-builder">
            <label>Steps</label>
            {wfSteps.map((step, idx) => (
              <div key={idx} className="wf-step-block">
                <div className="wf-step-row">
                  <span className="wf-step-num">{idx + 1}</span>
                  <select
                    value={step.type}
                    onChange={(e) => updateStep(idx, "type", e.target.value)}
                  >
                    {STEP_TYPES.map((st) => (
                      <option key={st.value} value={st.value}>{st.label}</option>
                    ))}
                  </select>
                  <input
                    type="text"
                    placeholder={`Prompt for step ${idx + 1}...`}
                    value={step.prompt}
                    onChange={(e) => updateStep(idx, "prompt", e.target.value)}
                  />
                  {wfSteps.length > 1 && (
                    <button className="wf-step-remove" onClick={() => removeStep(idx)}>&times;</button>
                  )}
                </div>
                {idx > 0 && (
                  <label className="wf-chain-toggle">
                    <input
                      type="checkbox"
                      checked={!!step.usePrevResult}
                      onChange={(e) => updateStep(idx, "usePrevResult", e.target.checked)}
                    />
                    <span className="wf-chain-label">Use output from Step {idx}</span>
                  </label>
                )}
              </div>
            ))}
            <button className="wf-add-step" onClick={addStep}>+ Add Step</button>
          </div>

          {wfError && <div className="run-error">{wfError}</div>}

          <button
            className="btn-run"
            onClick={handleSaveWorkflow}
            disabled={wfSaving || !wfName.trim() || !wfTrigger.trim() || wfSteps.some((s) => !s.prompt.trim())}
          >
            {wfSaving ? "Saving..." : editingWorkflow ? "Save Changes" : "Create Workflow"}
          </button>
        </div>
      )}

      {/* Run form for built-in workflows */}
      {runType && !result && (
        <div className="run-form">
          <button className="btn-back" onClick={() => { setRunType(null); setResult(null); }}>
            &larr; Back
          </button>
          <h3>{config.label}</h3>
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

      {/* Run result */}
      {result && (
        <div className="run-result">
          <button className="btn-back" onClick={() => { setRunType(null); setResult(null); setFormData({}); }}>
            &larr; New Run
          </button>

          <div className="run-result-header">
            <h3>{config.label} Complete</h3>
            <span className="run-id">Run: {result.run_id}</span>
          </div>

          {result.trace && (
            <div className="run-trace">
              {result.trace.map((t, i) => (
                <span key={i} className={`trace-step ${t.status}`}>
                  {t.status === "success" ? "Done" : "Failed"} — {t.task}
                </span>
              ))}
            </div>
          )}

          <div className="run-content">
            <ReactMarkdown
              components={{
                code({ className, children, ...props }) {
                  const isBlock = /language-/.test(className || "");
                  if (!isBlock) return <code className="inline-code" {...props}>{children}</code>;
                  return <pre className="code-block"><code {...props}>{children}</code></pre>;
                },
              }}
            >
              {result.candidate_brief || result.digest_markdown || JSON.stringify(result, null, 2)}
            </ReactMarkdown>
          </div>

          {result.outreach_message && (
            <div className="run-outreach">
              <h4>Draft Outreach Message</h4>
              <div className="outreach-box">{result.outreach_message}</div>
            </div>
          )}

          {/* Action buttons */}
          {onAction && RUN_ACTIONS[runType] && (
            <div className="run-actions">
              {RUN_ACTIONS[runType].map((a, i) => (
                <button key={i} className="run-action-btn" onClick={() => {
                  const brief = result.candidate_brief || result.digest_markdown || "";
                  onAction(a.command, brief);
                }}>
                  {a.label}
                </button>
              ))}
            </div>
          )}

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
