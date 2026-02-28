import { useState } from "react";
import { motion, AnimatePresence } from "framer-motion";

export default function CreateRoomModal({ open, onClose, onCreate, users = [] }) {
  const [name, setName] = useState("");
  const [description, setDescription] = useState("");
  const [githubRepo, setGithubRepo] = useState("");
  const [selectedMembers, setSelectedMembers] = useState([]);

  const toggleMember = (userId) => {
    setSelectedMembers((prev) =>
      prev.includes(userId) ? prev.filter((id) => id !== userId) : [...prev, userId]
    );
  };

  const handleCreate = () => {
    if (!name.trim()) return;
    onCreate({
      name: name.trim(),
      icon: name.trim()[0]?.toUpperCase() || "R",
      description: description.trim(),
      github_repo: githubRepo.trim() || null,
      member_ids: selectedMembers.length > 0 ? selectedMembers : null,
    });
    setName("");
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
            initial={{ scale: 0.95, opacity: 0 }}
            animate={{ scale: 1, opacity: 1 }}
            exit={{ scale: 0.95, opacity: 0 }}
            onClick={(e) => e.stopPropagation()}
          >
            <h3>Create Room</h3>

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
              <label>GitHub Repository</label>
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
                    ? "No members selected — room will be personal"
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
