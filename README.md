<div align="center">

# Hybrid Agent Memory 🧠⟁💾

**Two-Layer AI Memory System — Semantic Search with File-System Fallback**

[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](LICENSE)
[![GitHub Stars](https://img.shields.io/github/stars/nerudek/hybrid-agent-memory?style=flat-square)](https://github.com/nerudek/hybrid-agent-memory/stargazers)
[![PRs Welcome](https://img.shields.io/badge/PRs-welcome-brightgreen.svg)](https://github.com/nerudek/hybrid-agent-memory/pulls)

A hybrid memory bridge that combines agentmemory (REST API, vector search) with Memory Palace (file-based markdown) — delivering semantic retrieval speed with bulletproof file-system reliability. Never lose a memory.

</div>

---

## Table of Contents

- [Problem Statement](#1-problem-statement)
- [Solution Overview](#2-solution-overview)
- [Architecture](#3-architecture)
- [Quick Start](#4-quick-start)
- [Layer 1: Memory Palace (Base)](#5-layer-1-memory-palace-base)
- [Layer 2: Agentmemory (Ultra)](#6-layer-2-agentmemory-ultra)
- [The Bridge](#7-the-bridge)
- [Use Cases](#8-use-cases)
- [Best Practices & Pitfalls](#9-best-practices--pitfalls)
- [FAQ](#10-faq)
- [Contributing & Support](#11-contributing--support)

---

## 1. Problem Statement

AI agents need memory. They need to store facts, retrieve past context, and search across topics. But every memory solution makes a trade-off:

| Approach | Problem |
|----------|---------|
| **Vector databases** (ChromaDB, Pinecone) | Fast semantic search, but fragile — crashes, incompatible Python versions, silent failures |
| **REST API backends** (agentmemory, iii-engine) | Structured and powerful, but dependent on external services that may go down |
| **Flat files / markdown** | Bulletproof reliability, but slow for semantic search — no embeddings, no similarity ranking |
| **In-memory only** | Gone on restart — useless for persistent agent workflows |

You pick one layer and accept its failure mode. Vector DB breaks silently? Your agent hallucinates answers from an empty index. REST API is down? Your agent can't store anything. Files only? Your agent can't find related concepts.

**You should not have to choose.** A memory system should be fast AND reliable — with graceful degradation when the fast path fails.

## 2. Solution Overview

Hybrid Agent Memory provides two complementary layers, orchestrated by a bridge:

| Layer | Name | Storage | Speed | Reliability | Role |
|-------|------|---------|-------|-------------|------|
| **Layer 2 (Ultra)** | agentmemory | REST API + vector embeddings | Fast | Best-effort (depends on iii-engine) | Accelerator — hybrid search, embeddings, knowledge graph |
| **Layer 1 (Base)** | Memory Palace | Markdown files on disk | Medium | Always works | Source of truth — synchronous writes, no external deps |
| **Orchestrator** | Memory Bridge | N/A | N/A | N/A | Health check, fallback, sync between layers |

The key insight: **Memory Palace is always written to first** (synchronous, on-disk). agentmemory is updated as a best-effort cache. If agentmemory is down, the bridge still stores your data and returns results from the file layer. Zero data loss.

## 3. Architecture

```
Agent (Hermes / Claude / OpenClaw)
         │
         ▼
   Memory Bridge
         │
         ├── query("topic")
         │       │
         │       ├── try: agentmemory REST API (ULTRA)
         │       │       │
         │       │       └── OK → return results (layer: ultra)
         │       │
         │       └── catch: Memory Palace filesystem (BASE)
         │               │
         │               └── return results + log fallback (layer: base)
         │
         └── store("topic", "title", "content")
                 │
                 ├── ALWAYS write → Memory Palace (source of truth)
                 │       │
                 │       └── markdown file on disk ✓
                 │
                 └── try → agentmemory (best effort)
                         │
                         └── fail → log fallback, data still safe
```

### Data Flow

```
Agent discovers insight
        │
        ▼
Memory Bridge.store()
        │
        ├── Write to Memory Palace (markdown) ─── always, synchronous
        │       │
        │       └── topic/title-slug.md on disk ✓
        │
        └── If agentmemory alive → POST to /agentmemory/store
                │
                └── If fails → log warning, data still in Memory Palace
```

### Query Flow

```
Memory Bridge.query(topic, search_terms)
        │
        ├── health check on agentmemory (2-second timeout)
        │       │
        │       ├── Alive → search agentmemory → return ULTRA results
        │       │
        │       └── Dead/hanging → log fallback
        │
        └── Fallback → Memory Palace query
                │
                ├── Try mempalace_query.py script
                └── Fallback to grep on markdown files
```

## 4. Quick Start

```bash
# 1. Clone this repository
git clone https://github.com/nerudek/hybrid-agent-memory.git
cd hybrid-agent-memory

# 2. Configure environment
export AGENTMEMORY_URL="http://127.0.0.1:3111"
export AGENTMEMORY_ENABLED="true"
export MEMORY_PALACE_PATH="$HOME/.mempalace/palace"

# 3. Query the bridge
python3 scripts/memory_bridge.py query "technical" "kimi bridge gateway"

# 4. Store a memory
python3 scripts/memory_bridge.py store "technical" "Tytul" "Tresc markdown" --tags "kimi,bridge"

# 5. Check health
python3 scripts/memory_bridge.py health

# 6. Sync all Memory Palace data to agentmemory
python3 scripts/memory_bridge.py sync
```

## 5. Layer 1: Memory Palace (Base)

The Memory Palace is a file-based memory system using markdown files with YAML frontmatter. It is the **source of truth** — always written to, never skipped.

### Structure

```
~/.mempalace/palace/
├── technical/
│   ├── kimi-bridge-gateway.md
│   └── api-design.md
├── architecture/
│   ├── system-overview.md
│   └── decisions.md
└── general/
    └── notes.md
```

### File Format

Every memory is a markdown file with standard frontmatter:

```yaml
---
title: Kimi Bridge Gateway
tags: ["kimi", "bridge", "gateway"]
date: 2026-05-28
source: memory-bridge
---

Content of the memory in markdown format.
```

### Why File-Based First

- **No external dependencies** — if the disk works, Memory Palace works
- **Human-readable** — open any file in a text editor or Obsidian
- **Git-friendly** — version control your memory
- **Portable** — rsync, Tailscale, or cloud drive to move between machines
- **Always available** — no server to start, no port to configure

### Query Without agentmemory

```bash
# grep across memory files
grep -rIl "kimi" ~/.mempalace/palace/technical/

# List by topic
ls ~/.mempalace/palace/technical/

# Read a specific memory
cat ~/.mempalace/palace/technical/kimi-bridge-gateway.md
```

## 6. Layer 2: Agentmemory (Ultra)

agentmemory is the **accelerator layer** — it provides hybrid search (vector + keyword), embeddings, and knowledge graph capabilities via a REST API backed by iii-engine.

### Setup

```bash
# Requires iii-engine
# See: https://github.com/rohitg00/agentmemory

# Start iii-engine + agentmemory
cd agentmemory && node dist/cli.mjs start

# The server listens on the configured port (default: 3111)
```

### What It Provides

| Feature | Description |
|---------|-------------|
| Semantic search | Vector embeddings for meaning-based retrieval |
| Keyword search | Traditional text search |
| Hybrid search | Combined vector + keyword ranking |
| Knowledge graph | Entity relationships between memories |
| REST API | JSON interface for programmatic access |

### When It's Used

agentmemory is used as a **best-effort cache**:

- **On query**: If health check passes, query agentmemory first for fast, ranked results
- **On store**: After Memory Palace write succeeds, try agentmemory asynchronously
- **On sync**: Bulk push all Memory Palace files to agentmemory

### Failures Are Safe

If agentmemory is down, hangs, or returns errors:

1. The bridge logs the failure to `~/.hermes/memories/fallback.log`
2. Queries fall through to Memory Palace
3. Stores were already written to Memory Palace — no data lost

## 7. The Bridge

`scripts/memory_bridge.py` is the orchestrator that ties both layers together.

### CLI Commands

```bash
python3 scripts/memory_bridge.py query <topic> <query>
python3 scripts/memory_bridge.py store <topic> <title> <content> [--tags tags]
python3 scripts/memory_bridge.py health
python3 scripts/memory_bridge.py sync
```

### Health Check Logic

```python
def is_agentmemory_alive():
    try:
        r = requests.get(f"{AGENTMEMORY_URL}/health", timeout=2)
        return r.status_code == 200
    except:
        return False  # Down, hanging, or unreachable = trigger fallback
```

Health check uses a 2-second timeout. If the iii-engine hangs (not fully down), the timeout catches it and triggers the Memory Palace fallback.

### Store Flow (Guaranteed Safety)

```python
def store(topic, title, content, tags=[]):
    # ALWAYS write to Memory Palace first (source of truth)
    mempalace_write(topic, title, content, tags)

    # Then try agentmemory (best effort)
    if AGENTMEMORY_ENABLED and is_agentmemory_alive():
        try:
            agentmemory_store(topic, title, content, tags)
        except:
            log_fallback("agentmemory store failed")
    # Data is safe — written to Memory Palace
```

### Query Flow (Graceful Degradation)

```python
def query(topic, search_terms):
    if AGENTMEMORY_ENABLED and is_agentmemory_alive():
        try:
            return agentmemory_search(topic, search_terms)  # Layer: ultra
        except:
            log_fallback("agentmemory query failed")
    # Fallback to Memory Palace
    return mempalace_query(topic, search_terms)  # Layer: base
```

### Launchd Integration (macOS)

For persistent operation, use launchd to keep the bridge available:

```xml
<!-- ~/Library/LaunchAgents/com.nerudek.memory-bridge.plist -->
<key>Label</key><string>com.nerudek.memory-bridge</string>
<key>ProgramArguments</key>
<array>
  <string>/usr/bin/python3</string>
  <string>/path/to/scripts/memory_bridge_daemon.py</string>
</array>
<key>RunAtLoad</key><true/>
<key>KeepAlive</key><true/>
```

## 8. Use Cases

| Scenario | What Happens | Benefit |
|----------|-------------|---------|
| agentmemory is down | Bridge queries Memory Palace | Agent still gets answers |
| iii-engine hangs | 2-second timeout triggers fallback | No infinite wait |
| Store operation | Memory Palace written first, then agentmemory | Zero data loss |
| Agent wants semantic search | agentmemory returns ranked results | Fast, relevant answers |
| Sync old data | Push all Memory Palace files to agentmemory | Keep both layers in sync |
| Human reads memory | Open markdown files in any editor | Readable without tools |
| New agent joins | Read Memory Palace files directly | No agentmemory dependency |

## 9. Best Practices & Pitfalls

1. **Memory Palace is the source of truth** — never write to agentmemory without writing to Memory Palace first
2. **Check fallback logs** — `~/.hermes/memories/fallback.log` shows when agentmemory was unavailable
3. **Monitor health** — use `health` command regularly in scripts and workflows
4. **Sync periodically** — run `sync` after bulk imports or manual markdown edits
5. **2-second timeout** — a hanging iii-engine is treated as "down", not "slow"
6. **No external deps for base layer** — Memory Palace works with zero dependencies (just Python stdlib)
7. **agentmemory requires iii-engine** — agentmemory's REST API is not standalone; it depends on the full iii-engine stack
8. **Keep Memory Palace path consistent** — set `MEMORY_PALACE_PATH` in `.env` or profile to avoid duplicate memory silos
9. **Backup Memory Palace** — the markdown files are your only guaranteed persistent data. Back them up.

## 10. FAQ

**Q: Why both layers? Why not just files?**
A: Files are reliable but slow for semantic search. agentmemory provides vector embeddings and hybrid ranking. The bridge gives you both.

**Q: What if both layers are down?**
A: Memory Palace is file-based. If the disk works, it works. No external dependencies.

**Q: What if iii-engine hangs (not fully down)?**
A: Health check has a 2-second timeout. Hangs count as "down" and trigger fallback.

**Q: Is there data loss risk on agentmemory failure during store?**
A: No. Memory Palace is always written first, synchronously. agentmemory is updated best-effort afterward.

**Q: How do I sync old data to agentmemory?**
A: Run `python3 scripts/memory_bridge.py sync` — reads all Memory Palace files and pushes to agentmemory.

**Q: Can I use this without agentmemory at all?**
A: Yes. Set `AGENTMEMORY_ENABLED=false`. The bridge uses Memory Palace exclusively.

**Q: What happens on concurrent writes from multiple agents?**
A: Each Memory Palace file is uniquely named by slug. For higher contention, use file-level locking or a write queue.

**Q: Can humans read the memories?**
A: Yes — they're markdown files. Open in any editor or Obsidian.

**Q: Is this portable across machines?**
A: Yes. Sync `MEMORY_PALACE_PATH` via rsync, Tailscale, or cloud drive. agentmemory state can be re-synced from Memory Palace.

**Q: Can I use a different vector store instead of agentmemory?**
A: The bridge architecture is adapter-based. Swap agentmemory for any REST API vector store by modifying the `agentmemory_search` and `agentmemory_store` functions.

**Q: What about sensitive data?**
A: Don't write secrets or PII to Memory Palace. Use environment variables or a secrets manager. Memory Palace is not encrypted at rest.

## 11. Contributing & Support

Contributions are welcome! Here's how to help:

1. **Fork** the repository
2. **Create a feature branch:** `git checkout -b feat/my-feature`
3. **Commit your changes:** `git commit -am 'feat: add new storage adapter'`
4. **Push:** `git push origin feat/my-feature`
5. **Open a Pull Request**

Please ensure your changes maintain backward compatibility with both Base (Memory Palace) and Ultra (agentmemory) layers.

---

**License:** MIT — see [LICENSE](LICENSE) for details.

**Issues:** [GitHub Issues](https://github.com/nerudek/hybrid-agent-memory/issues)

**Author:** [@nerudek](https://github.com/nerudek) on GitHub

---

<div align="center">

If this saved you time: [PayPal.me/nerudek](https://www.paypal.me/nerudek)

⭐ Star the repo if you find this useful!

</div>

---

See [SKILL.md](./SKILL.md) for the skill reference card (Claude Code / Hermes Agent skill manifest).
