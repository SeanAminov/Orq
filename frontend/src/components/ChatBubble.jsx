import { motion } from "framer-motion";
import ReactMarkdown from "react-markdown";

// Detect if an AI response is about candidate research, commit digest, or conversation summary
function getFollowUpActions(content, role, runId) {
  if (role !== "assistant" || !runId || !content) return [];
  const lower = content.toLowerCase();
  const actions = [];

  // Candidate research brief -> offer to create a doc or generate interview questions
  if (
    (lower.includes("candidate research") || lower.includes("research brief") ||
     lower.includes("hiring signal") || lower.includes("role alignment")) &&
    lower.includes("interview")
  ) {
    actions.push(
      { label: "Save as Google Doc", command: "@action create a Google Doc with the candidate research brief above" },
      { label: "Commit to GitHub", command: "@action commit the candidate research brief as a markdown file to GitHub" },
    );
  }

  // Commit digest -> offer to email or create doc
  if (
    lower.includes("commit") &&
    (lower.includes("digest") || lower.includes("summary") || lower.includes("changes"))
  ) {
    actions.push(
      { label: "Email Digest to Team", command: "@action email room members the commit digest above" },
      { label: "Save as Google Doc", command: "@action create a Google Doc with the commit digest above" },
    );
  }

  // Conversation or meeting summary -> offer to save or email
  if (
    (lower.includes("conversation") || lower.includes("meeting") || lower.includes("transcript")) &&
    (lower.includes("summary") || lower.includes("overview"))
  ) {
    actions.push(
      { label: "Save Transcript as Doc", command: "@action create a Google Doc with the conversation transcript above" },
      { label: "Email Summary to Team", command: "@action email room members the conversation summary above" },
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
