import { useTheme } from "../context/ThemeContext";

export default function ThemeToggle() {
  const { theme, toggle } = useTheme();
  return (
    <button className="theme-toggle" onClick={toggle} title="Toggle theme">
      {theme === "dark" ? "☀️" : "🌙"}
    </button>
  );
}
