---
name: memory-bridge
version: 1.0.0
description: Hybrid memory system — agentmemory (iii-engine) accelerator with Memory Palace fallback. Zero data loss on iii-engine failure. Never lose memory.
compatible-with: [hermes, openclaw]
---

# Memory Bridge — Hybrid Memory with Fallback

**Never lose memory. Agentmemory accelerates, Memory Palace catches.**

## Architecture

```
Agent (Hermes / Claude / OpenClaw)
         │
         ▼
   memory-bridge.query("topic")
         │
         ├── try: agentmemory REST API (fast, hybrid search)
         │         │
         │         └── OK → return results
         │
         └── catch: Memory Palace file system (always works)
                   │
                   └── return results + log fallback
```

## Why Hybrid

| Layer | Role | Speed | Reliability |
|-------|------|-------|-------------|
| agentmemory | Accelerator — hybrid search, embeddings, knowledge graph | Fast | Depends on iii-engine |
| Memory Palace | Source of truth — markdown files, always available | Medium | Always works |
| bridge | Orchestrator — health check, fallback, sync | N/A | N/A |

## Quick Start

```bash
# Install agentmemory (requires iii-engine)
# See: https://github.com/rohitg00/agentmemory

# Start iii-engine + agentmemory
cd agentmemory && node dist/cli.mjs start

# Configure Hermes
export AGENTMEMORY_URL="http://127.0.0.1:3111"
export AGENTMEMORY_ENABLED="true"

# Use the bridge
python3 scripts/memory_bridge.py query "kimi bridge gateway"
python3 scripts/memory_bridge.py store "technical" "Tytul" "Tresc markdown"
```

## How It Works

### Health Check (every query)
```python
def is_agentmemory_alive():
    try:
        r = requests.get(f"{AGENTMEMORY_URL}/health", timeout=2)
        return r.status_code == 200
    except:
        return False
```

### Query Flow
```python
def query(topic, search_terms):
    if AGENTMEMORY_ENABLED and is_agentmemory_alive():
        try:
            return agentmemory_search(topic, search_terms)
        except:
            log_fallback("agentmemory query failed")
    # Fallback to Memory Palace
    return mempalace_query(topic, search_terms)
```

### Store Flow
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

## Configuration

### .env
```bash
AGENTMEMORY_URL=http://127.0.0.1:3111
AGENTMEMORY_ENABLED=true
MEMORY_PALACE_PATH=~/.mempalace/palace
```

### Launchd (optional)
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

## What Never Fails

- Memory Palace writes are synchronous to disk — always succeed
- agentmemory is best-effort — if down, data still in Memory Palace
- Bridge logs every fallback for monitoring
- Health check is lightweight (2-second timeout)

## FAQ

**Q: What if both are down?**  
A: Memory Palace is file-based. If the disk works, it works. No external dependencies.

**Q: How do I sync old data to agentmemory?**  
A: `python3 scripts/sync.py` — reads all Memory Palace files, pushes to agentmemory.

**Q: What if iii-engine hangs (not down)?**  
A: Health check has 2-second timeout. Hangs count as "down", fallback triggers.

---

*Never lose a memory.*
[PayPal](https://www.paypal.me/nerudek)
