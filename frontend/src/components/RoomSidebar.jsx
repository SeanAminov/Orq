import { motion } from "framer-motion";
import ThemeToggle from "./ThemeToggle";

const ROOM_COLORS = ["#3b82f6", "#22c55e", "#f59e0b", "#ef4444", "#8b5cf6", "#06b6d4", "#ec4899"];

function getRoomColor(name) {
  let hash = 0;
  for (let i = 0; i < name.length; i++) hash = name.charCodeAt(i) + ((hash << 5) - hash);
  return ROOM_COLORS[Math.abs(hash) % ROOM_COLORS.length];
}

export default function RoomSidebar({ rooms, activeRoom, onSelectRoom, onCreateRoom, user, onLogout }) {
  return (
    <motion.aside
      className="room-sidebar"
      initial={{ x: -260 }}
      animate={{ x: 0 }}
      transition={{ type: "spring", stiffness: 300, damping: 30 }}
    >
      <div className="rs-header">
        <h2 className="rs-logo">Orq</h2>
        <ThemeToggle />
      </div>

      <div className="rs-user">
        <div className="rs-user-info">
          <span className="rs-avatar">{user?.name?.[0] || "?"}</span>
          <span className="rs-user-name">{user?.name}</span>
        </div>
        <button className="rs-logout" onClick={onLogout}>Sign out</button>
      </div>

      <div className="rs-label">Rooms</div>

      <div className="rs-rooms">
        {rooms.map((room) => (
          <button
            key={room.id}
            className={`rs-room ${activeRoom === room.id ? "active" : ""}`}
            onClick={() => onSelectRoom(room.id)}
          >
            <span className="rs-room-dot" style={{ background: getRoomColor(room.name) }} />
            <div className="rs-room-info">
              <div className="rs-room-name-row">
                <span className="rs-room-name">{room.name}</span>
                {room.skyfire_budget && parseFloat(room.skyfire_budget) > 0 && (
                  <span className="rs-budget">${parseFloat(room.skyfire_budget).toFixed(4)}</span>
                )}
              </div>
              {room.github_repo && (
                <span className="rs-room-repo">{room.github_repo}</span>
              )}
            </div>
          </button>
        ))}
      </div>

      <button className="rs-create" onClick={onCreateRoom}>
        + New Room
      </button>
    </motion.aside>
  );
}
