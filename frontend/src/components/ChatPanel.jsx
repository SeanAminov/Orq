import { useRef, useEffect, useState } from "react";
import { motion } from "framer-motion";
import ChatBubble from "./ChatBubble";

const MENTION_OPTIONS = [
  { trigger: "@orq",     label: "@Orq",     desc: "Ask the AI (auto-detects intent)", hint: null },
  { trigger: "@crew",    label: "@crew",    desc: "Multi-agent task (CrewAI)",         hint: "crew" },
  { trigger: "@action",  label: "@action",  desc: "Gmail, Docs, Drive (Composio)",    hint: "action" },
  { trigger: "@data",    label: "@data",    desc: "Sentiment, Translate, Summarize",   hint: "data" },
  { trigger: "@pay",     label: "@pay",     desc: "Payments & tokens (Skyfire)",       hint: "pay" },
  { trigger: "@summary", label: "@summary", desc: "Summarize text (Cortex)",           hint: "summary" },
];

export default function ChatPanel({ room, messages, loading, loadingIntent, onSend }) {
  const bottomRef = useRef(null);
  const inputRef = useRef(null);
  const [input, setInput] = useState("");
  const [showMentions, setShowMentions] = useState(false);
  const [mentionFilter, setMentionFilter] = useState("");
  const [mentionIndex, setMentionIndex] = useState(0);

  useEffect(() => {
    bottomRef.current?.scrollIntoView({ behavior: "smooth" });
  }, [messages, loading]);

  // filtered mention suggestions
  const filteredMentions = MENTION_OPTIONS.filter((opt) =>
    opt.trigger.toLowerCase().startsWith(`@${mentionFilter.toLowerCase()}`)
  );

  // check if any @mention is in the current input
  const hasAnyMention = MENTION_OPTIONS.some((opt) => input.includes(opt.trigger));

  const handleInputChange = (e) => {
    const val = e.target.value;
    setInput(val);

    // detect @ mention trigger at cursor position
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

    // detect which @mention is used (if any)
    let intentHint = null;
    let isAiTrigger = false;
    for (const opt of MENTION_OPTIONS) {
      if (text.includes(opt.trigger)) {
        intentHint = opt.hint; // null for @orq (auto-classify)
        isAiTrigger = true;
        break;
      }
    }

    onSend(text, isAiTrigger, intentHint);
  };

  return (
    <div className="chat-panel">
      {/* Room header */}
      <div className="cp-header">
        <div className="cp-header-left">
          <span className="cp-room-icon">{room?.icon}</span>
          <div>
            <h3 className="cp-room-name">{room?.name || "Select a room"}</h3>
            {room?.description && (
              <span className="cp-room-desc">{room.description}</span>
            )}
          </div>
        </div>
        {room?.github_repo && (
          <span className="cp-repo-badge">
            <span>&#128193;</span> {room.github_repo}
          </span>
        )}
      </div>

      {/* Messages */}
      <div className="cp-messages">
        {messages.length === 0 && room && (
          <div className="cp-empty">
            <div className="cp-empty-icon">{room.icon}</div>
            <h3>Welcome to #{room.name}</h3>
            <p>{room.description || "Start a conversation"}</p>
            <div className="cp-empty-hint">
              <p>Type a message to chat with your team.</p>
              <p>Type <code>@</code> to see AI commands.</p>
            </div>
            <div className="cp-examples">
              <div className="cp-example" onClick={() => setInput("@orq what is agentic AI?")}>
                <span>&#128172;</span> @orq what is agentic AI?
              </div>
              <div className="cp-example" onClick={() => setInput("@action send an email to team@company.com about the project update")}>
                <span>&#128231;</span> @action send an email
              </div>
              <div className="cp-example" onClick={() => setInput("@data analyze sentiment: I love this product!")}>
                <span>&#10052;&#65039;</span> @data analyze sentiment
              </div>
              <div className="cp-example" onClick={() => setInput("@pay check my Skyfire balance")}>
                <span>&#128184;</span> @pay check Skyfire balance
              </div>
            </div>
          </div>
        )}

        {messages.map((m) => (
          <ChatBubble
            key={m.id}
            role={m.role}
            content={m.content}
            sender={m.sender_name}
            runId={m.run_id}
          />
        ))}

        {loading && (
          <div className="cp-loading">
            <span className="dot-pulse" />
            <span className="loading-label">
              {loadingIntent === "crew" ? "Crew is working..." :
               loadingIntent === "action" ? "Executing action..." :
               loadingIntent === "data" ? "Querying Snowflake..." :
               loadingIntent === "pay" ? "Processing with Skyfire..." :
               loadingIntent === "summary" ? "Summarizing with Cortex..." :
               "Orq is thinking..."}
            </span>
          </div>
        )}

        <div ref={bottomRef} />
      </div>

      {/* Input */}
      {room && (
        <div className="cp-input-area">
          <div className="cp-input-hint">
            {hasAnyMention
              ? "AI agent will process this message"
              : "Type @ to see AI commands"}
          </div>

          {/* @ Mention Autocomplete */}
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
              placeholder={`Message #${room.name}... (type @ for AI)`}
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
