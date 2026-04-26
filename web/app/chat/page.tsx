"use client";
import { useEffect, useRef, useState } from "react";
import { Bot, Send, Trash2, Database, User } from "lucide-react";
import { sendChatMessage, ChatMessage } from "@/lib/api";
import { Button } from "@/components/ui/button";
import { Badge } from "@/components/ui/badge";
import { Card } from "@/components/ui/card";

const SUGGESTIONS = [
  "Which 5 districts have the highest average PM2.5?",
  "Which states have the most respiratory cases on average?",
  "Compare PM2.5 levels in winter (Nov–Feb) vs monsoon (Jul–Sep).",
  "Which districts have both high pollution and high respiratory burden?",
  "Show the year-by-year PM2.5 trend from 2018 to 2023.",
  "What are the key causal findings of this project?",
  "Which districts have the highest cardiovascular case burden?",
  "What policy changes would reduce respiratory disease the most?",
];

interface StoredMessage extends ChatMessage {
  queries?: string[];
  id: number;
}

let _id = 0;

export default function ChatPage() {
  const [messages, setMessages] = useState<StoredMessage[]>([]);
  const [input, setInput] = useState("");
  const [loading, setLoading] = useState(false);
  const bottomRef = useRef<HTMLDivElement>(null);
  const inputRef = useRef<HTMLTextAreaElement>(null);

  useEffect(() => {
    bottomRef.current?.scrollIntoView({ behavior: "smooth" });
  }, [messages, loading]);

  async function submit(text: string) {
    if (!text.trim() || loading) return;
    const userMsg: StoredMessage = { role: "user", content: text.trim(), id: ++_id };
    setMessages(prev => [...prev, userMsg]);
    setInput("");
    setLoading(true);

    try {
      const history: ChatMessage[] = [...messages, userMsg].map(m => ({
        role: m.role, content: m.content,
      }));
      const { reply, queries } = await sendChatMessage(history);
      setMessages(prev => [...prev, {
        role: "assistant", content: reply, queries, id: ++_id,
      }]);
    } catch (e: any) {
      setMessages(prev => [...prev, {
        role: "assistant",
        content: `⚠️ **Error:** ${e.message ?? "Failed to reach the AI assistant. Make sure the API server is running."}`,
        id: ++_id,
      }]);
    } finally {
      setLoading(false);
      setTimeout(() => inputRef.current?.focus(), 50);
    }
  }

  function handleKey(e: React.KeyboardEvent<HTMLTextAreaElement>) {
    if (e.key === "Enter" && !e.shiftKey) {
      e.preventDefault();
      submit(input);
    }
  }

  return (
    <div className="flex flex-col h-[calc(100vh-2rem)] max-w-3xl mx-auto">
      {/* Header */}
      <div className="flex items-center justify-between py-4 border-b border-border/60 flex-shrink-0">
        <div className="flex items-center gap-3">
          <div className="w-10 h-10 rounded-xl bg-gradient-to-br from-violet-500 to-sky-500 flex items-center justify-center">
            <Bot className="w-5 h-5 text-white" />
          </div>
          <div>
            <h1 className="font-bold text-lg leading-tight">AI Research Assistant</h1>
            <p className="text-xs text-muted-foreground">
              Powered by Groq · Llama 3.3 70B · queries live database
            </p>
          </div>
        </div>
        {messages.length > 0 && (
          <Button variant="ghost" size="sm" onClick={() => setMessages([])}>
            <Trash2 className="w-4 h-4 mr-1" /> Clear
          </Button>
        )}
      </div>

      {/* Messages */}
      <div className="flex-1 overflow-y-auto py-6 space-y-6 scroll-area">
        {messages.length === 0 && (
          <div className="space-y-6">
            <div className="text-center space-y-2 pt-4">
              <div className="w-16 h-16 rounded-2xl bg-gradient-to-br from-violet-500/20 to-sky-500/20 border border-border/60 flex items-center justify-center mx-auto">
                <Bot className="w-8 h-8 text-violet-400" />
              </div>
              <p className="text-muted-foreground text-sm max-w-sm mx-auto">
                Ask anything about air pollution, health outcomes, district comparisons,
                seasonal patterns, or policy insights.
                The assistant queries the live database in real time.
              </p>
            </div>

            <div className="grid grid-cols-1 sm:grid-cols-2 gap-2">
              {SUGGESTIONS.map((q, i) => (
                <button
                  key={i}
                  onClick={() => submit(q)}
                  className="text-left px-4 py-3 rounded-xl border border-border/60 bg-card/40 hover:bg-card/80 hover:border-primary/40 transition-all text-sm text-foreground/80 hover:text-foreground"
                >
                  {q}
                </button>
              ))}
            </div>
          </div>
        )}

        {messages.map(msg => (
          <div key={msg.id} className={`flex gap-3 ${msg.role === "user" ? "flex-row-reverse" : ""}`}>
            <div className={`w-8 h-8 rounded-lg flex-shrink-0 flex items-center justify-center ${
              msg.role === "user"
                ? "bg-primary/20 border border-primary/30"
                : "bg-violet-500/20 border border-violet-500/30"
            }`}>
              {msg.role === "user"
                ? <User className="w-4 h-4 text-primary" />
                : <Bot className="w-4 h-4 text-violet-400" />}
            </div>
            <div className={`flex-1 space-y-2 ${msg.role === "user" ? "items-end" : "items-start"} flex flex-col`}>
              {msg.queries && msg.queries.length > 0 && (
                <div className="flex flex-wrap gap-1">
                  {msg.queries.map((q, i) => (
                    <Badge key={i} variant="secondary" className="text-[10px] font-mono gap-1">
                      <Database className="w-2.5 h-2.5" />
                      {q.length > 60 ? q.slice(0, 60) + "…" : q}
                    </Badge>
                  ))}
                </div>
              )}
              <div className={`rounded-2xl px-4 py-3 text-sm leading-relaxed max-w-[90%] ${
                msg.role === "user"
                  ? "bg-primary/10 border border-primary/20 text-foreground"
                  : "bg-card/60 border border-border/60 text-foreground/90"
              }`}>
                <MarkdownText text={msg.content} />
              </div>
            </div>
          </div>
        ))}

        {loading && (
          <div className="flex gap-3">
            <div className="w-8 h-8 rounded-lg flex-shrink-0 flex items-center justify-center bg-violet-500/20 border border-violet-500/30">
              <Bot className="w-4 h-4 text-violet-400" />
            </div>
            <div className="rounded-2xl px-4 py-3 bg-card/60 border border-border/60 flex items-center gap-2">
              <Database className="w-3 h-3 text-violet-400 animate-pulse" />
              <span className="text-sm text-muted-foreground">Thinking and querying database…</span>
              <span className="flex gap-1">
                {[0, 1, 2].map(i => (
                  <span key={i} className="w-1.5 h-1.5 rounded-full bg-violet-400 animate-bounce"
                    style={{ animationDelay: `${i * 0.15}s` }} />
                ))}
              </span>
            </div>
          </div>
        )}

        <div ref={bottomRef} />
      </div>

      {/* Input */}
      <div className="flex-shrink-0 pb-4 pt-2 border-t border-border/60">
        <div className="relative">
          <textarea
            ref={inputRef}
            value={input}
            onChange={e => setInput(e.target.value)}
            onKeyDown={handleKey}
            disabled={loading}
            rows={2}
            placeholder="Ask about pollution, health outcomes, districts, trends… (Enter to send, Shift+Enter for newline)"
            className="w-full resize-none rounded-xl border border-border/60 bg-card/60 px-4 py-3 pr-14 text-sm placeholder:text-muted-foreground focus:outline-none focus:ring-2 focus:ring-primary/40 disabled:opacity-50"
          />
          <Button
            size="icon"
            disabled={!input.trim() || loading}
            onClick={() => submit(input)}
            className="absolute right-2 bottom-2 h-8 w-8 rounded-lg"
          >
            <Send className="w-3.5 h-3.5" />
          </Button>
        </div>
        <p className="text-[10px] text-muted-foreground mt-1.5 text-center">
          The assistant queries the live SQLite database. Only SELECT queries are permitted.
        </p>
      </div>
    </div>
  );
}

/* ── Minimal inline markdown renderer ── */
function MarkdownText({ text }: { text: string }) {
  const lines = text.split("\n");
  return (
    <div className="space-y-1.5">
      {lines.map((line, i) => {
        if (!line.trim()) return <div key={i} className="h-1" />;

        // Headers
        if (line.startsWith("### ")) return <h3 key={i} className="font-bold text-sm mt-2">{inlineFormat(line.slice(4))}</h3>;
        if (line.startsWith("## "))  return <h2 key={i} className="font-bold text-base mt-2">{inlineFormat(line.slice(3))}</h2>;
        if (line.startsWith("# "))   return <h1 key={i} className="font-bold text-lg mt-2">{inlineFormat(line.slice(2))}</h1>;

        // Bullet lists
        if (/^[-*•]\s/.test(line))
          return <div key={i} className="flex gap-2"><span className="text-primary mt-0.5">•</span><span>{inlineFormat(line.replace(/^[-*•]\s/, ""))}</span></div>;

        // Numbered list
        if (/^\d+\.\s/.test(line))
          return <div key={i} className="flex gap-2"><span className="text-muted-foreground w-5 text-right flex-shrink-0">{line.match(/^\d+/)?.[0]}.</span><span>{inlineFormat(line.replace(/^\d+\.\s/, ""))}</span></div>;

        // Horizontal rule
        if (/^---+$/.test(line.trim())) return <hr key={i} className="border-border/40 my-2" />;

        return <p key={i}>{inlineFormat(line)}</p>;
      })}
    </div>
  );
}

function inlineFormat(text: string): React.ReactNode {
  const parts = text.split(/(\*\*[^*]+\*\*|\*[^*]+\*|`[^`]+`)/g);
  return parts.map((part, i) => {
    if (part.startsWith("**") && part.endsWith("**"))
      return <strong key={i}>{part.slice(2, -2)}</strong>;
    if (part.startsWith("*") && part.endsWith("*"))
      return <em key={i}>{part.slice(1, -1)}</em>;
    if (part.startsWith("`") && part.endsWith("`"))
      return <code key={i} className="bg-muted/60 px-1 py-0.5 rounded text-xs font-mono">{part.slice(1, -1)}</code>;
    return part;
  });
}
