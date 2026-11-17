"use client";

import { useEffect, useRef, useState, type FormEvent, type KeyboardEvent } from "react";
import { streamAnswer, type Source } from "@/lib/api";
import AnswerText from "./AnswerText";

type Message = {
  id: number;
  role: "user" | "assistant";
  text: string;
  sources: Source[];
  status: "streaming" | "done" | "error";
  error?: string;
};

const STARTERS = [
  "How many sick leaves do I get?",
  "Can I work from home in my first month?",
  "What is the notice period for a Senior Engineer?",
];

let nextId = 1;

export default function Chat() {
  const [messages, setMessages] = useState<Message[]>([]);
  const [input, setInput] = useState("");
  const [loading, setLoading] = useState(false);
  const [highlight, setHighlight] = useState<{ messageId: number; index: number } | null>(null);
  const bottomRef = useRef<HTMLDivElement>(null);

  useEffect(() => {
    bottomRef.current?.scrollIntoView({ behavior: "smooth", block: "end" });
  }, [messages]);

  function update(id: number, change: (m: Message) => Partial<Message>) {
    setMessages((prev) => prev.map((m) => (m.id === id ? { ...m, ...change(m) } : m)));
  }

  async function ask(question: string) {
    const q = question.trim();
    if (!q || loading) return;

    const userMsg: Message = { id: nextId++, role: "user", text: q, sources: [], status: "done" };
    const botMsg: Message = { id: nextId++, role: "assistant", text: "", sources: [], status: "streaming" };
    setMessages((prev) => [...prev, userMsg, botMsg]);
    setInput("");
    setLoading(true);

    try {
      await streamAnswer(q, {
        onSources: (sources) => update(botMsg.id, () => ({ sources })),
        onToken: (t) => update(botMsg.id, (m) => ({ text: m.text + t })),
      });
      update(botMsg.id, () => ({ status: "done" }));
    } catch (e) {
      const error = e instanceof Error ? e.message : "Something went wrong.";
      update(botMsg.id, () => ({ status: "error", error }));
    } finally {
      setLoading(false);
    }
  }

  function onSubmit(e: FormEvent) {
    e.preventDefault();
    ask(input);
  }

  function onKeyDown(e: KeyboardEvent<HTMLTextAreaElement>) {
    // Enter sends, Shift+Enter adds a new line
    if (e.key === "Enter" && !e.shiftKey && !e.nativeEvent.isComposing) {
      e.preventDefault();
      ask(input);
    }
  }

  function cite(messageId: number, index: number) {
    setHighlight({ messageId, index });
    document
      .getElementById(`source-${messageId}-${index}`)
      ?.scrollIntoView({ behavior: "smooth", block: "nearest" });
  }

  return (
    <div className="mx-auto flex h-dvh w-full max-w-3xl flex-col px-4">
      <header className="border-b border-zinc-200 py-4 dark:border-zinc-800">
        <h1 className="text-lg font-semibold">HR Policy Assistant</h1>
        <p className="text-sm text-zinc-500">Answers come from the company HR policy, with page citations.</p>
      </header>

      <main className="flex-1 space-y-6 overflow-y-auto py-6">
        {messages.length === 0 && (
          <div className="pt-10 text-center">
            <p className="mb-4 text-zinc-500">Ask anything about the HR policy, or try one of these:</p>
            <div className="flex flex-wrap justify-center gap-2">
              {STARTERS.map((s) => (
                <button
                  key={s}
                  type="button"
                  onClick={() => ask(s)}
                  disabled={loading}
                  className="rounded-full border border-zinc-300 px-4 py-2 text-sm hover:bg-zinc-100 disabled:opacity-50 dark:border-zinc-700 dark:hover:bg-zinc-900"
                >
                  {s}
                </button>
              ))}
            </div>
          </div>
        )}

        {messages.map((m) =>
          m.role === "user" ? (
            <div key={m.id} className="flex justify-end">
              <div className="max-w-[85%] whitespace-pre-wrap rounded-2xl bg-blue-600 px-4 py-2 text-white">
                {m.text}
              </div>
            </div>
          ) : (
            <div key={m.id} className="space-y-3">
              <div className="rounded-2xl bg-zinc-100 px-4 py-3 dark:bg-zinc-900">
                {m.text ? (
                  <AnswerText text={m.text} sourceCount={m.sources.length} onCite={(i) => cite(m.id, i)} />
                ) : m.status === "streaming" ? (
                  <span className="animate-pulse text-zinc-500">Searching the policy…</span>
                ) : null}
                {m.status === "error" && (
                  <p className="mt-2 rounded-lg border border-red-300 bg-red-50 px-3 py-2 text-sm text-red-700 dark:border-red-900 dark:bg-red-950 dark:text-red-300">
                    {m.error}
                  </p>
                )}
              </div>

              {m.sources.length > 0 && (
                <div className="grid gap-2 sm:grid-cols-3">
                  {m.sources.map((s, i) => {
                    const active = highlight?.messageId === m.id && highlight.index === i;
                    return (
                      <div
                        key={i}
                        id={`source-${m.id}-${i}`}
                        className={`rounded-xl border p-3 text-xs transition ${
                          active
                            ? "border-blue-500 bg-blue-50 ring-2 ring-blue-500 dark:bg-blue-950"
                            : "border-zinc-200 dark:border-zinc-800"
                        }`}
                      >
                        <div className="mb-1 font-semibold">
                          [{i + 1}] Page {s.page}
                        </div>
                        <p className="line-clamp-4 text-zinc-600 dark:text-zinc-400">{s.snippet}</p>
                      </div>
                    );
                  })}
                </div>
              )}
            </div>
          ),
        )}
        <div ref={bottomRef} />
      </main>

      <form onSubmit={onSubmit} className="flex gap-2 border-t border-zinc-200 py-4 dark:border-zinc-800">
        <textarea
          value={input}
          onChange={(e) => setInput(e.target.value)}
          onKeyDown={onKeyDown}
          rows={1}
          placeholder="Ask a question about the HR policy…"
          className="flex-1 resize-none rounded-xl border border-zinc-300 bg-transparent px-4 py-2 outline-none focus:border-blue-500 dark:border-zinc-700"
        />
        <button
          type="submit"
          disabled={loading || !input.trim()}
          className="rounded-xl bg-blue-600 px-5 py-2 font-medium text-white hover:bg-blue-700 disabled:opacity-50"
        >
          {loading ? "…" : "Send"}
        </button>
      </form>
    </div>
  );
}
