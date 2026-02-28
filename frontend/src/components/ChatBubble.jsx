import { motion } from "framer-motion";
import ReactMarkdown from "react-markdown";

// Detect if an AI response is about candidate research, commit digest, or conversation summary
function getFollowUpActions(content, role, runId) {
  if (role !== "assistant" || !runId || !content) return [];
  const lower = content.toLowerCase();
  const actions = [];

  // Candidate research brief -> offer to create a doc, schedule interview, commit
  if (
    (lower.includes("candidate research") || lower.includes("research brief") ||
     lower.includes("hiring signal") || lower.includes("role alignment")) &&
    lower.includes("interview")
  ) {
    actions.push(
      { label: "Schedule Interview", command: "@action create a Google Calendar event for a candidate interview based on the research brief above" },
      { label: "Save as Google Doc", command: "@action create a Google Doc with the candidate research brief above" },
      { label: "Commit to GitHub", command: "@action commit the candidate research brief as a markdown file to GitHub" },
    );
  }

  // Commit digest -> offer to email, create doc, or schedule review
  if (
    lower.includes("commit") &&
    (lower.includes("digest") || lower.includes("summary") || lower.includes("changes"))
  ) {
    actions.push(
      { label: "Email Digest to Team", command: "@action email room members the commit digest above" },
      { label: "Save as Google Doc", command: "@action create a Google Doc with the commit digest above" },
      { label: "Schedule Review", command: "@action create a Google Calendar event for a code review meeting to discuss the commit digest above" },
    );
  }

  // Conversation or meeting summary -> offer to save, email, or schedule follow-up
  if (
    (lower.includes("conversation") || lower.includes("meeting") || lower.includes("transcript")) &&
    (lower.includes("summary") || lower.includes("overview"))
  ) {
    actions.push(
      { label: "Save Transcript as Doc", command: "@action create a Google Doc with the conversation transcript above" },
      { label: "Email Summary to Team", command: "@action email room members the conversation summary above" },
      { label: "Schedule Follow-up", command: "@action create a Google Calendar event for a follow-up meeting based on the conversation above" },
    );
  }

  // Any response mentioning scheduling, interview, or calendar -> offer calendar invite
  if (
    !actions.some((a) => a.label.startsWith("Schedule")) &&
    (lower.includes("schedule") || lower.includes("calendar") || lower.includes("book a") ||
     lower.includes("set up a meeting") || lower.includes("set up an interview"))
  ) {
    actions.push(
      { label: "Send Calendar Invite", command: "@action create a Google Calendar event based on the details discussed above" },
    );
  }

  return actions;
}

export default function ChatBubble({ role, content, sender, senderId, currentUserId, runId, cost, tokens, onAction }) {
  const isAssistant = role === "assistant";
  const isOwnMessage = !isAssistant && senderId === currentUserId;
  const bubbleClass = isAssistant ? "assistant" : isOwnMessage ? "own" : "other";
  const hasCost = cost && parseFloat(cost) > 0;

  const followUps = getFollowUpActions(content, role, runId);

  return (
    <motion.div
      className={`chat-bubble ${bubbleClass}`}
      initial={{ opacity: 0, y: 8 }}
      animate={{ opacity: 1, y: 0 }}
      transition={{ duration: 0.12 }}
    >
      {(!isOwnMessage || isAssistant) && (
        <span className="chat-sender">
          {sender}
          {runId && isAssistant && <span className="chat-via">via @orq</span>}
        </span>
      )}
      <div className="chat-content">
        {isAssistant ? (
          <ReactMarkdown
            components={{
              code({ className, children, ...props }) {
                const isBlock = /language-/.test(className || "");
                if (!isBlock) return <code className="inline-code" {...props}>{children}</code>;
                return (
                  <pre className="code-block">
                    <code {...props}>{children}</code>
                  </pre>
                );
              },
              table({ children }) {
                return (
                  <div className="table-wrap">
                    <table>{children}</table>
                  </div>
                );
              },
            }}
          >
            {content}
          </ReactMarkdown>
        ) : (
          <p>{content}</p>
        )}
      </div>
      {followUps.length > 0 && onAction && (
        <div className="chat-actions">
          {followUps.map((a, i) => (
            <button
              key={i}
              className="chat-action-btn"
              onClick={() => onAction(a.command)}
            >
              {a.label}
            </button>
          ))}
        </div>
      )}
      {hasCost && isAssistant && (
        <span className="chat-cost">
          ${parseFloat(cost).toFixed(4)} &middot; {tokens || 0} tokens
        </span>
      )}
    </motion.div>
  );
}
