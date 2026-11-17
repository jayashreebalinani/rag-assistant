import os
import chromadb
from dotenv import load_dotenv
from groq import Groq

load_dotenv()  # reads backend/.env locally; on Render the env vars are set in the dashboard
if not os.getenv("GROQ_API_KEY"):
    raise RuntimeError("GROQ_API_KEY is not set. Add it to backend/.env or the Render environment.")
llm = Groq(api_key=os.getenv("GROQ_API_KEY"))
MODEL = os.getenv("MODEL", "openai/gpt-oss-120b")

# Chroma L2 distance (0 = identical, lower = more similar). If even the closest chunk is
# farther than this, the question isn't about the policy and the LLM is skipped.
# Placeholder: policy questions scored 0.83-1.31 and off-topic ones 1.64+ in a quick test.
RELEVANCE_THRESHOLD = 1.5
NOT_FOUND = "I couldn't find this in the HR policy."

db = chromadb.PersistentClient(path="./chroma_db")
collection = db.get_collection("policies")


def retrieve(question, k=3):
    r = collection.query(
        query_texts=[question], n_results=k, include=["documents", "metadatas", "distances"]
    )
    chunks = [
        {"text": doc, "page": meta["page"], "distance": dist}
        for doc, meta, dist in zip(r["documents"][0], r["metadatas"][0], r["distances"][0])
    ]
    print(f"\nQ: {question}")
    for i, c in enumerate(chunks, start=1):
        print(f"  [{i}] page {c['page']}  distance {c['distance']:.3f}")
    return chunks


def is_relevant(chunks):
    best = min((c["distance"] for c in chunks), default=None)
    relevant = best is not None and best <= RELEVANCE_THRESHOLD
    if not relevant:
        print(f"  -> best distance {best} is above {RELEVANCE_THRESHOLD}, skipping LLM")
    return relevant


def build_messages(question, chunks):
    context = "\n\n".join(
        f"[{i + 1}] (page {c['page']})\n{c['text']}" for i, c in enumerate(chunks)
    )
    system = (
        "You answer questions about the company HR policy using ONLY the context below. "
        "After each fact, cite it like [1, page 2]. "
        "If the answer is not in the context, say: I couldn't find that in the policy.\n\n"
        f"Context:\n{context}"
    )
    return [
        {"role": "system", "content": system},
        {"role": "user", "content": question},
    ]


def to_sources(chunks):
    return [{"page": c["page"], "snippet": c["text"][:200]} for c in chunks]


def answer(question):
    chunks = retrieve(question)
    if not is_relevant(chunks):
        return NOT_FOUND, []
    res = llm.chat.completions.create(model=MODEL, messages=build_messages(question, chunks))
    return res.choices[0].message.content, chunks


def answer_stream(question, chunks):
    # Yields the answer text piece by piece as Groq generates it
    stream = llm.chat.completions.create(
        model=MODEL, messages=build_messages(question, chunks), stream=True
    )
    for part in stream:
        text = part.choices[0].delta.content if part.choices else None
        if text:
            yield text


if __name__ == "__main__":
    while True:
        q = input("\nAsk (or 'quit'): ")
        if q.lower() == "quit":
            break
        text, chunks = answer(q)
        print("\n" + text)
        print("\nSources:", ", ".join(f"page {c['page']}" for c in chunks))