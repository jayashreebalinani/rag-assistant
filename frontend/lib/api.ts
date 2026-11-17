// Set NEXT_PUBLIC_API_URL in Vercel to the Render URL; the localhost fallback is for local dev only
export const API_URL = (process.env.NEXT_PUBLIC_API_URL || "http://localhost:8000").replace(/\/+$/, "");

export type Source = { page: number; snippet: string };

type StreamHandlers = {
  onSources: (sources: Source[]) => void;
  onToken: (text: string) => void;
};

// POSTs the question to /ask/stream and reads the Server-Sent Events as they arrive.
// EventSource can't send a POST body, so the stream is parsed by hand.
export async function streamAnswer(question: string, handlers: StreamHandlers) {
  let res: Response;
  try {
    res = await fetch(`${API_URL}/ask/stream`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ question }),
    });
  } catch {
    throw new Error(`Can't reach the backend at ${API_URL}. Is the FastAPI server running?`);
  }

  if (!res.ok || !res.body) {
    const detail = await res.text().catch(() => "");
    throw new Error(`The backend returned ${res.status}${detail ? `: ${detail}` : ""}`);
  }

  const reader = res.body.pipeThrough(new TextDecoderStream()).getReader();
  let buffer = "";

  while (true) {
    const { value, done } = await reader.read();
    if (done) break;
    buffer += value.replace(/\r\n/g, "\n");

    // Events are separated by a blank line; keep any half-received event in the buffer
    let end;
    while ((end = buffer.indexOf("\n\n")) !== -1) {
      const raw = buffer.slice(0, end);
      buffer = buffer.slice(end + 2);

      let event = "message";
      let data = "";
      for (const line of raw.split("\n")) {
        if (line.startsWith("event:")) event = line.slice(6).trim();
        else if (line.startsWith("data:")) data += line.slice(5).trim();
      }
      const payload = data ? JSON.parse(data) : null;

      if (event === "sources") handlers.onSources(payload);
      else if (event === "token") handlers.onToken(payload);
      else if (event === "error") throw new Error(payload);
      else if (event === "done") return;
    }
  }

  throw new Error("The connection closed before the answer finished.");
}
