import { useNavigate } from "react-router-dom";
import { motion } from "framer-motion";
import ThemeToggle from "../components/ThemeToggle";
import "../styles/landing.css";

const FEATURES = [
  { icon: "🤖", title: "CrewAI Agents", desc: "Multi-agent teams that research, plan, and execute autonomously" },
  { icon: "🔗", title: "Composio Actions", desc: "Connect Gmail, Docs, Slack, GitHub — agents act on your behalf" },
  { icon: "❄️", title: "Snowflake Data", desc: "Natural language queries powered by Cortex AI" },
  { icon: "💸", title: "Skyfire Payments", desc: "AI-native payment rails for agent-to-agent commerce" },
];

export default function Landing() {
  const nav = useNavigate();
  return (
    <div className="landing">
      <ThemeToggle />
      <motion.div
        className="landing-hero"
        initial={{ opacity: 0, y: 30 }}
        animate={{ opacity: 1, y: 0 }}
        transition={{ duration: 0.6 }}
      >
        <h1 className="landing-title">Orq</h1>
        <p className="landing-subtitle">
          Autonomous agents that orchestrate, reason, and act — coordinated into your daily workflow.
        </p>
        <div className="landing-buttons">
          <button className="btn-primary" onClick={() => nav("/login")}>Log In</button>
          <button className="btn-secondary" onClick={() => nav("/signup")}>Sign Up</button>
        </div>
      </motion.div>

      <div className="landing-features">
        {FEATURES.map((f, i) => (
          <motion.div
            key={f.title}
            className="feature-card"
            initial={{ opacity: 0, y: 20 }}
            animate={{ opacity: 1, y: 0 }}
            transition={{ delay: 0.2 + i * 0.1 }}
          >
            <span className="feature-icon">{f.icon}</span>
            <h3>{f.title}</h3>
            <p>{f.desc}</p>
          </motion.div>
        ))}
      </div>
    </div>
  );
}
