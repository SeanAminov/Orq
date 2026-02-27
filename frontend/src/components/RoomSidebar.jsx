import { motion } from "framer-motion";
import ThemeToggle from "./ThemeToggle";

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
        <button className="rs-logout" onClick={onLogout}>Logout</button>
      </div>

      <div className="rs-label">Rooms</div>

      <div className="rs-rooms">
        {rooms.map((room) => (
          <button
            key={room.id}
            className={`rs-room ${activeRoom === room.id ? "active" : ""}`}
            onClick={() => onSelectRoom(room.id)}
          >
            <span className="rs-room-icon">{room.icon}</span>
            <div className="rs-room-info">
              <span className="rs-room-name">{room.name}</span>
              {room.github_repo && (
                <span className="rs-room-repo">{room.github_repo}</span>
              )}
            </div>
          </button>
        ))}
      </div>

      <button className="rs-create" onClick={onCreateRoom}>
        <span>+</span> New Room
      </button>
    </motion.aside>
  );
}
