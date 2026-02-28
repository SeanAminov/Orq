import { motion } from "framer-motion";
import ReactMarkdown from "react-markdown";

export default function ChatBubble({ role, content, sender, senderId, currentUserId, runId, cost, tokens }) {
  const isAssistant = role === "assistant";
  const isOwnMessage = !isAssistant && senderId === currentUserId;
  const bubbleClass = isAssistant ? "assistant" : isOwnMessage ? "own" : "other";
  const hasCost = cost && parseFloat(cost) > 0;

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
              code({ node, inline, className, children, ...props }) {
                if (inline) {
                  return <code className="inline-code" {...props}>{children}</code>;
                }
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
      {hasCost && isAssistant && (
        <span className="chat-cost">
          ${parseFloat(cost).toFixed(4)} &middot; {tokens || 0} tokens
        </span>
      )}
    </motion.div>
  );
}
