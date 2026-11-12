# mem0 + Gemini: Chatbot with Long-Term Memory

A tiny chatbot that remembers you **across runs**. It uses [mem0](https://github.com/mem0ai/mem0)
to store facts from each chat and Gemini to answer, using those facts as context.

## How it works

1. **Recall**: `memory.search()` finds facts relevant to your question.
2. **Answer**: Gemini replies, given those facts.
3. **Remember**: `memory.add()` extracts new facts from the exchange and stores them.

## Run it

```bash
cd mem0-gemini-memory
python -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt
cp .env.example .env   # set GOOGLE_API_KEY (get one at https://aistudio.google.com/apikey)
python demo.py
```

## Try it

Session 1:

```text
You: My name is Aditya and I love biryani.
You: I'm building a workshop on AI agents.
```

Quit (`quit`), then start again:

```text
You: What food do I like?
Bot: You love biryani!
```

Memories are saved to `.mem0_data/`.

## Troubleshooting

- **`Developer instruction is not enabled for api version v1`**: the Gemini SDK defaults to `v1`. `demo.py` sets `GOOGLE_GENAI_API_VERSION=v1beta` for you, so keep that line.
- **`spaCy is not installed`**: fixed by `requirements.txt`, which installs `mem0ai[nlp]`. If you still see it, run `pip install "mem0ai[nlp]"`. Then run `python -m spacy download en_core_web_sm` once to get the English model.
- **`fastembed not installed`**: harmless. It's an optional extra for better keyword search (`pip install "mem0ai[extras]"` if you want it). The demo runs fine without it.
