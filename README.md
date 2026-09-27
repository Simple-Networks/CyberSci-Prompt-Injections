# CyberSci Crash Course on Prompt Injections

A **deliberately vulnerable** FastAPI service that fronts a [llama.cpp](https://github.com/ggml-org/llama.cpp)

## Setup

```bash
docker compose up --build   # first run downloads ~750MB of GGUF
# UI at http://localhost:8000  (API docs at /docs); llama.cpp on 127.0.0.1:8080
```

Compose starts two services: `llama`, the vendored `llama-b10909` build serving
`LiquidAI/LFM2.5-1.2B-Instruct-GGUF:Q4_K_M` and `app`, the FastAPI service. 

Without Docker, a two-terminal path still works: `uv sync`, start a tool-capable
llama.cpp server on `http://localhost:8080`, then `uv run main.py`.

