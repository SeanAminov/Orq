import { useRef, useEffect, useState } from "react";
import { motion } from "framer-motion";
import ChatBubble from "./ChatBubble";

const MENTION_OPTIONS = [
  { trigger: "@orq",     label: "@orq",     desc: "AI auto-detects intent",        hint: null },
  { trigger: "@crew",    label: "@crew",    desc: "Multi-agent task (CrewAI)",      hint: "crew" },
  { trigger: "@action",  label: "@action",  desc: "Gmail, Docs, Drive (Composio)", hint: "action" },
  { trigger: "@data",    label: "@data",    desc: "Cortex NLP (Snowflake)",        hint: "data" },
  { trigger: "@pay",     label: "@pay",     desc: "Payments (Skyfire)",            hint: "pay" },
  { trigger: "@summary", label: "@summary", desc: "Summarize text (Cortex)",       hint: "summary" },
];

function DateSeparator({ date }) {
  return (
    <div className="date-separator">
      <span>{date}</span>
    </div>
  );
}

function insertDateSeparators(messages) {
  const items = [];
  let lastDate = null;
  for (const m of messages) {
    const dateStr = m.created_at
      ? new Date(m.created_at).toLocaleDateString("en-US", { month: "short", day: "numeric", year: "numeric" })
      : null;
    if (dateStr && dateStr !== lastDate) {
      items.push({ type: "date", date: dateStr, id: `date-${dateStr}` });
      lastDate = dateStr;
    }
    items.push({ type: "message", ...m });
  }
  return items;
}

export default function ChatPanel({ room, messages, loading, loadingIntent, onSend, runCostMap = {}, currentUserId, onAction, workflowTriggers = [] }) {
  const bottomRef = useRef(null);
  const inputRef = useRef(null);
  const [input, setInput] = useState("");
  const [showMentions, setShowMentions] = useState(false);
  const [mentionFilter, setMentionFilter] = useState("");
  const [mentionIndex, setMentionIndex] = useState(0);

  useEffect(() => {
    bottomRef.current?.scrollIntoView({ behavior: "smooth" });
  }, [messages, loading]);

  // Merge built-in mentions with custom workflow triggers
  const allMentionOptions = [
    ...MENTION_OPTIONS,
    ...workflowTriggers.map((wt) => ({
      trigger: `@${wt.trigger}`,
      label: `@${wt.trigger}`,
      desc: wt.description || wt.name,
      hint: "workflow",
      isWorkflow: true,
    })),
  ];

  const filteredMentions = allMentionOptions.filter((opt) =>
    opt.trigger.toLowerCase().startsWith(`@${mentionFilter.toLowerCase()}`)
  );

  const hasAnyMention = allMentionOptions.some((opt) => input.includes(opt.trigger));

  const handleInputChange = (e) => {
    const val = e.target.value;
    setInput(val);
    const cursorPos = e.target.selectionStart;
    const textBeforeCursor = val.slice(0, cursorPos);
    const atMatch = textBeforeCursor.match(/@(\w*)$/);
    if (atMatch) {
      setShowMentions(true);
      setMentionFilter(atMatch[1]);
      setMentionIndex(0);
    } else {
      setShowMentions(false);
      setMentionFilter("");
    }
  };

  const handleSelectMention = (option) => {
    const cursorPos = inputRef.current?.selectionStart || input.length;
    const textBeforeCursor = input.slice(0, cursorPos);
    const atPos = textBeforeCursor.lastIndexOf("@");
    const before = input.slice(0, atPos);
    const after = input.slice(cursorPos);
    setInput(before + option.trigger + " " + after);
    setShowMentions(false);
    setMentionFilter("");
    setTimeout(() => inputRef.current?.focus(), 0);
  };

  const handleKeyDown = (e) => {
    if (showMentions && filteredMentions.length > 0) {
      if (e.key === "ArrowDown") {
        e.preventDefault();
        setMentionIndex((i) => Math.min(i + 1, filteredMentions.length - 1));
      } else if (e.key === "ArrowUp") {
        e.preventDefault();
        setMentionIndex((i) => Math.max(i - 1, 0));
      } else if (e.key === "Enter" || e.key === "Tab") {
        e.preventDefault();
        handleSelectMention(filteredMentions[mentionIndex]);
      } else if (e.key === "Escape") {
        setShowMentions(false);
      }
      return;
    }
    if (e.key === "Enter") handleSend();
  };

  const handleSend = () => {
    if (!input.trim() || loading) return;
    const text = input.trim();
    setInput("");
    setShowMentions(false);

    let intentHint = null;
    let isAiTrigger = false;
    for (const opt of allMentionOptions) {
      if (text.includes(opt.trigger)) {
        intentHint = opt.hint;
        isAiTrigger = true;
        break;
      }
    }
    // Custom workflow triggers: send the full text (with @trigger) to backend
    // The backend will detect the trigger and run the workflow
    onSend(text, isAiTrigger, isAiTrigger && intentHint === "workflow" ? null : intentHint);
  };

  const itemsWithDates = insertDateSeparators(messages);

  return (
    <div className="chat-panel">
      <div className="cp-header">
        <div className="cp-header-left">
          <div className="cp-room-dot" />
          <div>
            <h3 className="cp-room-name">{room?.name || "Select a room"}</h3>
            {room?.description && (
              <span className="cp-room-desc">{room.description}</span>
            )}
          </div>
        </div>
        {room?.github_repo && (
          <span className="cp-repo-badge">{room.github_repo}</span>
        )}
      </div>

      <div className="cp-messages">
        {messages.length === 0 && room && (
          <div className="cp-empty">
            <h3>#{room.name}</h3>
            <p>{room.description || "Start a conversation"}</p>
            <div className="cp-empty-hint">
              <p>Type a message to chat with your team.</p>
              <p>Type <code>@</code> to see AI commands.</p>
            </div>
            <div className="cp-examples">
              <div className="cp-example" onClick={() => setInput("@orq what is agentic AI?")}>
                @orq what is agentic AI?
              </div>
              <div className="cp-example" onClick={() => setInput("@action send an email to team@company.com about the project update")}>
                @action send an email
              </div>
              <div className="cp-example" onClick={() => setInput("@data analyze sentiment: I love this product!")}>
                @data analyze sentiment
              </div>
              <div className="cp-example" onClick={() => setInput("@pay check my Skyfire balance")}>
                @pay check Skyfire balance
              </div>
            </div>
          </div>
        )}

        {itemsWithDates.map((item) => {
          if (item.type === "date") {
            return <DateSeparator key={item.id} date={item.date} />;
          }
          const costInfo = item.run_id ? runCostMap[item.run_id] : null;
          return (
            <ChatBubble
              key={item.id}
              role={item.role}
              content={item.content}
              sender={item.sender_name}
              senderId={item.sender_id}
              currentUserId={currentUserId}
              runId={item.run_id}
              cost={costInfo?.cost}
              tokens={costInfo?.tokens}
              onAction={onAction}
            />
          );
        })}

        {loading && (
          <div className="cp-loading">
            <span className="dot-pulse" />
            <span className="loading-label">
              {loadingIntent === "crew" ? "Crew is working..." :
               loadingIntent === "action" ? "Executing action..." :
               loadingIntent === "data" ? "Querying Snowflake..." :
               loadingIntent === "pay" ? "Processing with Skyfire..." :
               loadingIntent === "summary" ? "Summarizing with Cortex..." :
               loadingIntent === "workflow" ? "Running workflow..." :
               "Processing..."}
            </span>
          </div>
        )}

        <div ref={bottomRef} />
      </div>

      {room && (
        <div className="cp-input-area">
          <div className="cp-input-hint">
            {hasAnyMention
              ? "AI agent will process this message"
              : "Type @ to see AI commands"}
          </div>

          {showMentions && filteredMentions.length > 0 && (
            <div className="mention-dropdown">
              {filteredMentions.map((opt, i) => (
                <div
                  key={opt.trigger}
                  className={`mention-option ${i === mentionIndex ? "active" : ""}`}
                  onClick={() => handleSelectMention(opt)}
                  onMouseEnter={() => setMentionIndex(i)}
                >
                  <span className="mention-trigger">{opt.label}</span>
                  <span className="mention-desc">{opt.desc}</span>
                </div>
              ))}
            </div>
          )}

          <div className="cp-input-row">
            <input
              ref={inputRef}
              type="text"
              className={`cp-input ${hasAnyMention ? "orq-active" : ""}`}
              placeholder={`Message #${room.name}...`}
              value={input}
              onChange={handleInputChange}
              onKeyDown={handleKeyDown}
              disabled={loading}
            />
            <button
              className={`cp-send ${hasAnyMention ? "orq-active" : ""}`}
              onClick={handleSend}
              disabled={loading || !input.trim()}
            >
              {hasAnyMention ? "Run" : "Send"}
            </button>
          </div>
        </div>
      )}
    </div>
  );
}
