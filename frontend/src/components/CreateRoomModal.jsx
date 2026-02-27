import { useState } from "react";
import { motion, AnimatePresence } from "framer-motion";

const ICON_OPTIONS = [
  "\u{1F4AC}", "\u{1F6E0}\u{FE0F}", "\u{1F50D}", "\u{2744}\u{FE0F}",
  "\u{1F680}", "\u{1F4CA}", "\u{1F3AF}", "\u{1F4A1}",
  "\u{1F5C2}\u{FE0F}", "\u{1F916}", "\u{1F517}", "\u{1F4B8}",
];

export default function CreateRoomModal({ open, onClose, onCreate, users = [] }) {
  const [name, setName] = useState("");
  const [icon, setIcon] = useState("\u{1F4AC}");
  const [description, setDescription] = useState("");
  const [githubRepo, setGithubRepo] = useState("");
  const [selectedMembers, setSelectedMembers] = useState([]);

  const toggleMember = (userId) => {
    setSelectedMembers((prev) =>
      prev.includes(userId)
        ? prev.filter((id) => id !== userId)
        : [...prev, userId]
    );
  };

  const handleCreate = () => {
    if (!name.trim()) return;
    onCreate({
      name: name.trim(),
      icon,
      description: description.trim(),
      github_repo: githubRepo.trim() || null,
      member_ids: selectedMembers.length > 0 ? selectedMembers : null,
    });
    setName("");
    setIcon("\u{1F4AC}");
    setDescription("");
    setGithubRepo("");
    setSelectedMembers([]);
    onClose();
  };

  return (
    <AnimatePresence>
      {open && (
        <motion.div
          className="modal-overlay"
          initial={{ opacity: 0 }}
          animate={{ opacity: 1 }}
          exit={{ opacity: 0 }}
          onClick={onClose}
        >
          <motion.div
            className="modal-content"
            initial={{ scale: 0.9, opacity: 0 }}
            animate={{ scale: 1, opacity: 1 }}
            exit={{ scale: 0.9, opacity: 0 }}
            onClick={(e) => e.stopPropagation()}
          >
            <h3>Create Room</h3>

            <div className="modal-field">
              <label>Icon</label>
              <div className="icon-picker">
                {ICON_OPTIONS.map((ic) => (
                  <button
                    key={ic}
                    className={`icon-option ${icon === ic ? "active" : ""}`}
                    onClick={() => setIcon(ic)}
                  >
                    {ic}
                  </button>
                ))}
              </div>
            </div>

            <div className="modal-field">
              <label>Room Name *</label>
              <input
                type="text"
                placeholder="e.g. Project Alpha"
                value={name}
                onChange={(e) => setName(e.target.value)}
                autoFocus
              />
            </div>

            <div className="modal-field">
              <label>Description</label>
              <input
                type="text"
                placeholder="What's this room for?"
                value={description}
                onChange={(e) => setDescription(e.target.value)}
              />
            </div>

            <div className="modal-field">
              <label>GitHub Repo (optional)</label>
              <input
                type="text"
                placeholder="owner/repo"
                value={githubRepo}
                onChange={(e) => setGithubRepo(e.target.value)}
              />
            </div>

            {users.length > 0 && (
              <div className="modal-field">
                <label>Invite Members</label>
                <div className="member-picker">
                  {users.map((u) => (
                    <label key={u.id} className="member-option">
                      <input
                        type="checkbox"
                        checked={selectedMembers.includes(u.id)}
                        onChange={() => toggleMember(u.id)}
                      />
                      <span className="member-avatar">{u.name[0]}</span>
                      <span className="member-name">{u.name}</span>
                      <span className="member-email">{u.email}</span>
                    </label>
                  ))}
                </div>
                <span className="member-hint">
                  {selectedMembers.length === 0
                    ? "No members selected \u2014 room will be personal"
                    : `${selectedMembers.length} member${selectedMembers.length > 1 ? "s" : ""} + you`}
                </span>
              </div>
            )}

            <div className="modal-actions">
              <button className="modal-cancel" onClick={onClose}>Cancel</button>
              <button className="modal-create" onClick={handleCreate} disabled={!name.trim()}>
                Create Room
              </button>
            </div>
          </motion.div>
        </motion.div>
      )}
    </AnimatePresence>
  );
}
