"""Demo: a Gemini chatbot with long-term memory, powered by mem0.

Run it once and tell the bot a few things about you. Quit, run it again,
and ask "what do you know about me?" - it remembers across sessions.
"""
import os

from dotenv import load_dotenv
from google import genai
from mem0 import Memory

load_dotenv()
# The GenAI SDK defaults to the v1 API, which rejects system instructions (mem0 uses them).
os.environ.setdefault("GOOGLE_GENAI_API_VERSION", "v1beta")

MODEL = "gemini-2.5-flash"
USER_ID = "workshop-user"
DATA_DIR = ".mem0_data"  # local vector store, lives next to this script

MEMORY_CONFIG = {
    "llm": {"provider": "gemini", "config": {"model": MODEL}},
    "embedder": {
        "provider": "gemini",
        "config": {"model": "models/gemini-embedding-001", "embedding_dims": 768},
    },
    "vector_store": {
        "provider": "qdrant",
        "config": {"collection_name": "memories", "embedding_model_dims": 768, "path": DATA_DIR},
    },
}

gemini = genai.Client()  # reads GOOGLE_API_KEY from the environment
memory = Memory.from_config(MEMORY_CONFIG)


def chat(question: str) -> str:
    # 1. Recall: find memories relevant to this question.
    found = memory.search(question, filters={"user_id": USER_ID}, top_k=5)
    facts = [item["memory"] for item in found["results"]]
    context = "\n".join(f"- {fact}" for fact in facts) or "- (nothing yet)"

    # 2. Answer: give Gemini the remembered facts plus the question.
    prompt = (
        "You are a friendly assistant. Use these remembered facts about the user when relevant:\n"
        f"{context}\n\n"
        f"User: {question}"
    )
    answer = gemini.models.generate_content(model=MODEL, contents=prompt).text

    # 3. Remember: let mem0 extract new facts from this exchange.
    exchange = [
        {"role": "user", "content": question},
        {"role": "assistant", "content": answer},
    ]
    memory.add(exchange, user_id=USER_ID)
    return answer


def main() -> None:
    print("Chat with Gemini + mem0 memory. Type 'quit' to exit.\n")
    while True:
        question = input("You: ").strip()
        if question.lower() in {"quit", "exit"}:
            break
        if question:
            print(f"Bot: {chat(question)}\n")


if __name__ == "__main__":
    main()
