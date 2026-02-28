import { useNavigate } from "react-router-dom";
import { motion } from "framer-motion";
import "../styles/landing.css";

const FEATURES = [
  { title: "Multi-Agent Orchestration", desc: "CrewAI-powered teams that research, plan, and execute complex tasks autonomously.", tag: "CrewAI" },
  { title: "App Integrations", desc: "Connect Gmail, Google Docs, and Drive. Agents act on your behalf through Composio OAuth.", tag: "Composio" },
  { title: "Data Intelligence", desc: "Natural language queries, sentiment analysis, and translation powered by Snowflake Cortex.", tag: "Snowflake" },
  { title: "Payment Protocol", desc: "AI-native payment rails for pay-per-query access and programmable agent transactions.", tag: "Skyfire" },
];

export default function Landing() {
  const nav = useNavigate();
  return (
    <div className="landing">
      <motion.div
        className="landing-hero"
        initial={{ opacity: 0, y: 20 }}
        animate={{ opacity: 1, y: 0 }}
        transition={{ duration: 0.5 }}
      >
        <h1 className="landing-title">Orq</h1>
        <p className="landing-tagline">Agentic AI Workspace</p>
        <p className="landing-subtitle">
          Autonomous agents that orchestrate, reason, and act — coordinated into your daily workflow.
        </p>
        <div className="landing-buttons">
          <button className="btn-primary" onClick={() => nav("/login")}>Log In</button>
          <button className="btn-secondary" onClick={() => nav("/signup")}>Get Started</button>
        </div>
      </motion.div>

      <div className="landing-features">
        {FEATURES.map((f, i) => (
          <motion.div
            key={f.title}
            className="feature-card"
            initial={{ opacity: 0, y: 16 }}
            animate={{ opacity: 1, y: 0 }}
            transition={{ delay: 0.15 + i * 0.08 }}
          >
            <span className="feature-tag">{f.tag}</span>
            <h3>{f.title}</h3>
            <p>{f.desc}</p>
          </motion.div>
        ))}
      </div>

      <div className="landing-built">
        <span>Built with</span>
        <div className="landing-logos">
          <span>CrewAI</span>
          <span>Composio</span>
          <span>Snowflake</span>
          <span>Skyfire</span>
        </div>
      </div>
    </div>
  );
}
