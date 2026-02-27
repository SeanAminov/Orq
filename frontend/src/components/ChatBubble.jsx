import { motion } from "framer-motion";
import ReactMarkdown from "react-markdown";

export default function ChatBubble({ role, content, sender, runId }) {
  const isUser = role === "user";
  return (
    <motion.div
      className={`chat-bubble ${isUser ? "user" : "assistant"}`}
      initial={{ opacity: 0, y: 10 }}
      animate={{ opacity: 1, y: 0 }}
      transition={{ duration: 0.15 }}
    >
      <span className="chat-sender">
        {sender}
        {runId && !isUser && <span style={{ opacity: 0.5, marginLeft: 6, fontSize: "0.6rem" }}>via @orq</span>}
      </span>
      <div className="chat-content">
        {isUser ? (
          <p>{content}</p>
        ) : (
          <ReactMarkdown
            components={{
              // render code blocks with syntax styling
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
              // keep tables readable
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
        )}
      </div>
    </motion.div>
  );
}
