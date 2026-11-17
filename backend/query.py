import chromadb

client = chromadb.PersistentClient(path="./chroma_db")
collection = client.get_collection("policies")

question = input("Ask a question: ")

results = collection.query(query_texts=[question], n_results=3)

for i in range(3):
    print(f"\n--- Result {i+1} | page {results['metadatas'][0][i]['page']} "
          f"| distance {results['distances'][0][i]:.3f} ---")
    print(results["documents"][0][i][:300])