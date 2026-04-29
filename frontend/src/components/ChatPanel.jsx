import { useState, useEffect, useRef } from "react";
import ReactMarkdown from "react-markdown";
import { createChatSocket } from "../api/client";

const STORAGE_KEY = "sportmind_chat_history";
const MAX_STORED  = 60;

const WELCOME = {
  role: "assistant",
  content: "Hey! I'm **SportMind** 🏀 Ask me anything about NBA history from 2013–2023 — stats, championships, player stories, or win predictions.",
};

const SUGGESTIONS = [
  "What happened in the 2016 NBA Finals?",
  "Tell me about Curry's style and his stats",
  "Who won MVP in 2019-20?",
  "How did Gregg Popovich coach the 2014 Spurs?",
  "Predict win: Warriors vs Celtics",
  "Tell me about the Warriors dynasty",
  "LeBron James career averages",
  "Who were the top scorers in 2022-23?",
];

function loadHistory() {
  try {
    const raw = localStorage.getItem(STORAGE_KEY);
    if (raw) {
      const parsed = JSON.parse(raw);
      if (Array.isArray(parsed) && parsed.length > 0) return parsed;
    }
  } catch (_) {}
  return [WELCOME];
}

function saveHistory(messages) {
  try {
    const toSave = messages
      .filter(m => m.content && m.content.trim())
      .slice(-MAX_STORED);
    localStorage.setItem(STORAGE_KEY, JSON.stringify(toSave));
  } catch (_) {}
}

export default function ChatPanel() {
  const [messages, setMessages]   = useState(loadHistory);
  const [input, setInput]         = useState("");
  const [loading, setLoading]     = useState(false);
  const wsRef        = useRef(null);
  const bottomRef    = useRef(null);
  const streamIdxRef = useRef(null);

  // Persist whenever messages settle (not mid-stream)
  useEffect(() => {
    if (!loading) saveHistory(messages);
  }, [messages, loading]);

  // Auto-scroll
  useEffect(() => {
    bottomRef.current?.scrollIntoView({ behavior: "smooth" });
  }, [messages]);

  function clearHistory() {
    localStorage.removeItem(STORAGE_KEY);
    setMessages([WELCOME]);
  }

  function sendMessage(text) {
    const msg = (text || input).trim();
    if (!msg || loading) return;
    setInput("");
    setMessages(prev => [...prev, { role: "user", content: msg }]);
    setLoading(true);

    setMessages(prev => {
      streamIdxRef.current = prev.length;
      return [...prev, { role: "assistant", content: "" }];
    });

    wsRef.current = createChatSocket(
      (token) => {
        setMessages(prev => {
          const updated = [...prev];
          updated[streamIdxRef.current] = {
            ...updated[streamIdxRef.current],
            content: updated[streamIdxRef.current].content + token,
          };
          return updated;
        });
      },
      (_fullText, sources) => {
        setLoading(false);
        if (sources && sources.length > 0) {
          setMessages(prev => {
            const updated = [...prev];
            updated[streamIdxRef.current] = {
              ...updated[streamIdxRef.current],
              sources,
            };
            return updated;
          });
        }
        wsRef.current?.close();
      },
      () => {
        setLoading(false);
        setMessages(prev => {
          const updated = [...prev];
          updated[streamIdxRef.current] = {
            role: "assistant",
            content: "Connection error — make sure the backend is running on port 8000.",
          };
          return updated;
        });
      }
    );

    wsRef.current.onopen = () => wsRef.current.send(msg);
  }

  const showSuggestions = messages.length <= 1;

  return (
    <div className="chat-panel">
      <div className="chat-header">
        <span className="chat-title">Chat</span>
        {messages.length > 1 && (
          <button className="clear-btn" onClick={clearHistory}>Clear history</button>
        )}
      </div>

      <div className="messages">
        {messages.map((m, i) => (
          <div key={i} className={`message ${m.role}`}>
            <div className="bubble">
              <ReactMarkdown>{m.content || " "}</ReactMarkdown>
              {i === streamIdxRef.current && loading && <span className="cursor">▋</span>}
              {m.sources && m.sources.length > 0 && (
                <div className="sources-row">
                  <span className="sources-label">Sources:</span>
                  {[...new Map(m.sources.map(s => [s.entity || s.file, s])).values()]
                    .slice(0, 5)
                    .map((s, j) => (
                      <span key={j} className="source-tag">
                        {s.entity
                          ? s.entity.replace(/_/g, " ").replace(/\b\w/g, c => c.toUpperCase())
                          : s.file}
                      </span>
                    ))}
                </div>
              )}
            </div>
          </div>
        ))}
        <div ref={bottomRef} />
      </div>

      {showSuggestions && (
        <div className="suggestions">
          {SUGGESTIONS.map((s, i) => (
            <button key={i} onClick={() => sendMessage(s)} className="suggestion-chip">{s}</button>
          ))}
        </div>
      )}

      <div className="input-row">
        <input
          value={input}
          onChange={e => setInput(e.target.value)}
          onKeyDown={e => e.key === "Enter" && !e.shiftKey && sendMessage()}
          placeholder="Ask about NBA history, stats, or predictions..."
          disabled={loading}
        />
        <button onClick={() => sendMessage()} disabled={loading || !input.trim()}>
          {loading ? "···" : "Send"}
        </button>
      </div>
    </div>
  );
}
