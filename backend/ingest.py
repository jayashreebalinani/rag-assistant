from pypdf import PdfReader
import chromadb

# 1. Read: open the PDF from the data folder
reader = PdfReader("../data/hr_policy.pdf")

# 2. Cut: split each page into overlapping chunks, remembering the page number
chunks, ids, metas = [], [], []
for page_num, page in enumerate(reader.pages, start=1):
    text = page.extract_text() or ""
    size, overlap = 800, 150
    for start in range(0, len(text), size - overlap):
        piece = text[start:start + size].strip()
        if piece:
            chunks.append(piece)
            ids.append(f"p{page_num}-{start}")
            metas.append({"source": "hr_policy.pdf", "page": page_num})

# 3 + 4. Convert and store: Chroma makes the embeddings and saves them
client = chromadb.PersistentClient(path="./chroma_db")
collection = client.get_or_create_collection("policies")
collection.upsert(documents=chunks, ids=ids, metadatas=metas)

print(f"Stored {len(chunks)} chunks")