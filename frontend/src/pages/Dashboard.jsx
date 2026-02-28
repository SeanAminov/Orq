import { useState, useEffect } from "react";
import { useNavigate } from "react-router-dom";
import RoomSidebar from "../components/RoomSidebar";
import ChatPanel from "../components/ChatPanel";
import ActivityPanel from "../components/ActivityPanel";
import CreateRoomModal from "../components/CreateRoomModal";
import "../styles/dashboard.css";

export default function Dashboard() {
  const nav = useNavigate();

  const [user, setUser] = useState(null);
  const [rooms, setRooms] = useState([]);
  const [activeRoom, setActiveRoom] = useState(null);
  const [messages, setMessages] = useState([]);
  const [runs, setRuns] = useState([]);
  const [tools, setTools] = useState({});
  const [loading, setLoading] = useState(false);
  const [loadingIntent, setLoadingIntent] = useState("");
  const [showCreateRoom, setShowCreateRoom] = useState(false);
  const [users, setUsers] = useState([]);
  const [memories, setMemories] = useState([]);
  const [workflowTriggers, setWorkflowTriggers] = useState([]);

  // auth check
  useEffect(() => {
    fetch("/api/auth/me", { credentials: "include" })
      .then((r) => (r.ok ? r.json() : Promise.reject()))
      .then(setUser)
      .catch(() => nav("/login"));
  }, [nav]);

  // load rooms + tools + users on login
  useEffect(() => {
    if (!user) return;
    fetch("/api/rooms", { credentials: "include" })
      .then((r) => r.json())
      .then((data) => {
        setRooms(data);
        if (data.length > 0 && !activeRoom) {
          setActiveRoom(data[0].id);
        }
      })
      .catch(() => {});
    fetch("/api/tools/status", { credentials: "include" })
      .then((r) => r.json())
      .then(setTools)
      .catch(() => {});
    fetch("/api/users", { credentials: "include" })
      .then((r) => r.json())
      .then(setUsers)
      .catch(() => {});
    fetchMemories();
    fetchWorkflowTriggers();
  }, [user]);

  const fetchMemories = () => {
    fetch("/api/memories", { credentials: "include" })
      .then((r) => r.json())
      .then(setMemories)
      .catch(() => {});
  };

  const fetchWorkflowTriggers = () => {
    fetch("/api/workflows/triggers", { credentials: "include" })
      .then((r) => r.json())
      .then(setWorkflowTriggers)
      .catch(() => {});
  };

  // load messages + runs when room changes
  useEffect(() => {
    if (!activeRoom) return;
    fetchRoomData(activeRoom);
  }, [activeRoom]);

  // Poll for new messages every 3 seconds so multi-user chat is real-time
  useEffect(() => {
    if (!activeRoom || loading) return;
    const interval = setInterval(() => {
      fetch(`/api/rooms/${activeRoom}/messages`, { credentials: "include" })
        .then((r) => r.json())
        .then((data) => {
          setMessages((prev) => {
            // Only update if message count changed (avoids unnecessary re-renders)
            if (data.length !== prev.length) return data;
            // Also check if last message content differs
            if (data.length > 0 && prev.length > 0 && data[data.length - 1].id !== prev[prev.length - 1].id) return data;
            return prev;
          });
        })
        .catch(() => {});
    }, 3000);
    return () => clearInterval(interval);
  }, [activeRoom, loading]);

  const fetchRoomData = (roomId) => {
    fetch(`/api/rooms/${roomId}/messages`, { credentials: "include" })
      .then((r) => r.json())
      .then(setMessages)
      .catch(() => setMessages([]));
    fetch(`/api/rooms/${roomId}/runs`, { credentials: "include" })
      .then((r) => r.json())
      .then(setRuns)
      .catch(() => setRuns([]));
  };

  const handleSend = async (text, isAiTrigger = false, intentHint = null) => {
    if (!activeRoom || loading) return;

    // strip built-in @mentions from the text sent to backend (but preserve custom workflow triggers)
    const cleanText = text.replace(/@(orq|crew|action|data|pay|summary|research|clean)\s*/gi, "").trim();
    if (!cleanText) return;

    // optimistic add user message
    const tempId = `temp-${Date.now()}`;
    setMessages((prev) => [
      ...prev,
      { id: tempId, role: "user", content: text, sender_name: user.name, sender_id: user.id },
    ]);
    setLoading(true);
    setLoadingIntent(isAiTrigger ? (intentHint || "thinking") : "");

    try {
      if (isAiTrigger) {
        // AI agent run
        const body = { message: cleanText };
        if (intentHint) body.intent_hint = intentHint;

        const res = await fetch(`/api/rooms/${activeRoom}/run`, {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          credentials: "include",
          body: JSON.stringify(body),
        });
        const data = await res.json();
        setLoadingIntent(data.intent || "");

        // refresh full room data to get server-side messages + updated costs
        fetchRoomData(activeRoom);
        // refresh rooms to update budget badge in sidebar
        fetch("/api/rooms", { credentials: "include" })
          .then((r) => r.json())
          .then(setRooms)
          .catch(() => {});
        // refresh memories (AI may have learned something)
        fetchMemories();
        fetchWorkflowTriggers();
      } else {
        // plain message
        await fetch(`/api/rooms/${activeRoom}/messages`, {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          credentials: "include",
          body: JSON.stringify({ message: text }),
        });
        // refresh messages
        fetch(`/api/rooms/${activeRoom}/messages`, { credentials: "include" })
          .then((r) => r.json())
          .then(setMessages);
      }
    } catch {
      setMessages((prev) => [
        ...prev,
        { id: `err-${Date.now()}`, role: "assistant", content: "Something went wrong.", sender_name: "Orq" },
      ]);
    } finally {
      setLoading(false);
      setLoadingIntent("");
    }
  };

  const handleCreateRoom = async (roomData) => {
    try {
      const res = await fetch("/api/rooms", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        credentials: "include",
        body: JSON.stringify(roomData),
      });
      const newRoom = await res.json();
      // refresh room list
      const roomsRes = await fetch("/api/rooms", { credentials: "include" });
      const updatedRooms = await roomsRes.json();
      setRooms(updatedRooms);
      setActiveRoom(newRoom.id);
    } catch {}
  };

  const handleClearChat = async () => {
    await fetch("/api/messages", { method: "DELETE", credentials: "include" });
    if (activeRoom) fetchRoomData(activeRoom);
  };

  const handleClearActivity = async () => {
    await fetch("/api/activity", { method: "DELETE", credentials: "include" });
    if (activeRoom) fetchRoomData(activeRoom);
  };

  const handleDeleteMemory = async (memoryId) => {
    await fetch(`/api/memories/${memoryId}`, { method: "DELETE", credentials: "include" });
    fetchMemories();
  };

  const handleResetAll = async () => {
    await fetch("/api/reset", { method: "POST", credentials: "include" });
    if (activeRoom) fetchRoomData(activeRoom);
    fetchMemories();
    fetchWorkflowTriggers();
    setRuns([]);
  };

  // Handle follow-up action buttons (e.g., "Save as Google Doc")
  const handleAction = (command) => {
    if (!activeRoom || loading) return;
    handleSend(command, true, "action");
  };

  const handleLogout = async () => {
    await fetch("/api/auth/logout", { method: "POST", credentials: "include" });
    nav("/login");
  };

  const currentRoom = rooms.find((r) => r.id === activeRoom);

  // build a map of run_id -> cost info for ChatBubble
  const runCostMap = {};
  for (const r of runs) {
    if (r.id && r.cost_usd) {
      runCostMap[r.id] = { cost: r.cost_usd, tokens: r.tokens_used };
    }
  }

  if (!user) return null;

  return (
    <div className="dashboard">
      <RoomSidebar
        rooms={rooms}
        activeRoom={activeRoom}
        onSelectRoom={setActiveRoom}
        onCreateRoom={() => setShowCreateRoom(true)}
        user={user}
        onLogout={handleLogout}
      />

      <ChatPanel
        room={currentRoom}
        messages={messages}
        loading={loading}
        loadingIntent={loadingIntent}
        onSend={handleSend}
        runCostMap={runCostMap}
        currentUserId={user?.id}
        onAction={handleAction}
        workflowTriggers={workflowTriggers}
      />

      <ActivityPanel
        runs={runs}
        tools={tools}
        room={currentRoom}
        memories={memories}
        onDeleteMemory={handleDeleteMemory}
        onClearChat={handleClearChat}
        onClearActivity={handleClearActivity}
        onWorkflowChange={fetchWorkflowTriggers}
        onResetAll={handleResetAll}
        onAction={handleAction}
      />

      <CreateRoomModal
        open={showCreateRoom}
        onClose={() => setShowCreateRoom(false)}
        onCreate={handleCreateRoom}
        users={users}
      />
    </div>
  );
}
