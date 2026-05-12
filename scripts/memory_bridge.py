#!/usr/bin/env python3
"""
Memory Bridge — hybrid memory with automatic fallback.
Layer 1 (BASE): Memory Palace — always works, file-based
Layer 2 (ULTRA): agentmemory — fast hybrid search, best effort

Usage:
    python3 memory_bridge.py query "topic" "search terms"
    python3 memory_bridge.py store "topic" "title" "content" [--tags tag1,tag2]
    python3 memory_bridge.py health
    python3 memory_bridge.py sync  # push Memory Palace to agentmemory
"""

import os, sys, json, time, subprocess, urllib.request, urllib.error
from pathlib import Path

# === CONFIG ===
AGENTMEMORY_URL = os.environ.get("AGENTMEMORY_URL", "http://127.0.0.1:3111")
AGENTMEMORY_ENABLED = os.environ.get("AGENTMEMORY_ENABLED", "true").lower() == "true"
MEMORY_PALACE_PATH = Path(os.environ.get("MEMORY_PALACE_PATH", os.path.expanduser("~/.mempalace/palace")))
FALLBACK_LOG = Path(os.path.expanduser("~/.hermes/memories/fallback.log"))

def log(msg):
    timestamp = time.strftime("%Y-%m-%d %H:%M:%S")
    with open(FALLBACK_LOG, "a") as f:
        f.write(f"[{timestamp}] {msg}\n")

# === HEALTH CHECK ===
def is_agentmemory_alive():
    if not AGENTMEMORY_ENABLED:
        return False
    try:
        req = urllib.request.Request(f"{AGENTMEMORY_URL}/health")
        resp = urllib.request.urlopen(req, timeout=2)
        return resp.status == 200
    except:
        return False

# === LAYER 2: AGENTMEMORY (ULTRA) ===
def agentmemory_search(query_text):
    try:
        data = json.dumps({"query": query_text}).encode()
        req = urllib.request.Request(
            f"{AGENTMEMORY_URL}/agentmemory/search",
            data=data,
            headers={"Content-Type": "application/json"}
        )
        resp = urllib.request.urlopen(req, timeout=5)
        return json.loads(resp.read())
    except Exception as e:
        log(f"agentmemory search failed: {e}")
        raise

def agentmemory_store(topic, title, content, tags=None):
    try:
        data = json.dumps({
            "topic": topic, "title": title,
            "content": content, "tags": tags or []
        }).encode()
        req = urllib.request.Request(
            f"{AGENTMEMORY_URL}/agentmemory/store",
            data=data,
            headers={"Content-Type": "application/json"}
        )
        resp = urllib.request.urlopen(req, timeout=5)
        return json.loads(resp.read())
    except Exception as e:
        log(f"agentmemory store failed: {e}")
        raise

# === LAYER 1: MEMORY PALACE (BASE) ===
def mempalace_query(topic, query_text):
    """Use existing mempalace_query.py script."""
    script = Path(os.path.expanduser("~/.hermes/skills/system-bridge/scripts/mempalace_query.py"))
    if script.exists():
        result = subprocess.run(
            ["python3", str(script), "--topic", topic, "--query", query_text],
            capture_output=True, text=True, timeout=30
        )
        return {"source": "memory_palace", "results": result.stdout.strip()}
    # Fallback: grep markdown files
    topic_dir = MEMORY_PALACE_PATH / topic
    if topic_dir.exists():
        result = subprocess.run(
            ["grep", "-rIl", query_text, str(topic_dir)],
            capture_output=True, text=True, timeout=10
        )
        return {"source": "memory_palace", "files": result.stdout.strip().split("\n")}
    return {"source": "memory_palace", "results": "no results"}

def mempalace_write(topic, title, content, tags=None):
    """Write to Memory Palace markdown files."""
    topic_dir = MEMORY_PALACE_PATH / topic
    topic_dir.mkdir(parents=True, exist_ok=True)
    slug = title.lower().replace(" ", "-")[:50]
    filepath = topic_dir / f"{slug}.md"
    
    frontmatter = f"""---
title: {title}
tags: {json.dumps(tags or [])}
date: {time.strftime('%Y-%m-%d')}
source: memory-bridge
---

{content}
"""
    filepath.write_text(frontmatter)
    return {"source": "memory_palace", "file": str(filepath), "status": "ok"}

# === BRIDGE: MAIN INTERFACE ===
def query(topic, query_text):
    # Try ULTRA layer
    if is_agentmemory_alive():
        try:
            result = agentmemory_search(query_text)
            result["layer"] = "ultra"
            return result
        except:
            log(f"ULTRA fallback triggered for query: {topic}/{query_text}")
    
    # Fallback to BASE layer
    result = mempalace_query(topic, query_text)
    result["layer"] = "base"
    return result

def store(topic, title, content, tags=None):
    # ALWAYS write to BASE first (source of truth)
    base_result = mempalace_write(topic, title, content, tags)
    
    # Try ULTRA layer (best effort)
    if is_agentmemory_alive():
        try:
            ultra_result = agentmemory_store(topic, title, content, tags)
            return {"layer": "both", "base": base_result, "ultra": ultra_result}
        except:
            log(f"ULTRA store failed for: {topic}/{title}")
    
    return {"layer": "base_only", "base": base_result, "warning": "ULTRA layer unavailable"}

def sync_all():
    """Push all Memory Palace data to agentmemory."""
    if not is_agentmemory_alive():
        return {"error": "agentmemory not available"}
    
    count = 0
    for md_file in MEMORY_PALACE_PATH.rglob("*.md"):
        try:
            topic = md_file.parent.name
            content = md_file.read_text()
            title = md_file.stem
            agentmemory_store(topic, title, content)
            count += 1
        except Exception as e:
            log(f"sync failed for {md_file}: {e}")
    
    return {"synced": count}

# === CLI ===
if __name__ == "__main__":
    import argparse
    parser = argparse.ArgumentParser(description="Memory Bridge")
    sub = parser.add_subparsers(dest="command")
    
    q = sub.add_parser("query")
    q.add_argument("topic")
    q.add_argument("query")
    
    s = sub.add_parser("store")
    s.add_argument("topic")
    s.add_argument("title")
    s.add_argument("content")
    s.add_argument("--tags", default="")
    
    sub.add_parser("health")
    sub.add_parser("sync")
    
    args = parser.parse_args()
    
    if args.command == "query":
        result = query(args.topic, args.query)
        print(json.dumps(result, indent=2))
    elif args.command == "store":
        tags = [t.strip() for t in args.tags.split(",") if t.strip()]
        result = store(args.topic, args.title, args.content, tags)
        print(json.dumps(result, indent=2))
    elif args.command == "health":
        alive = is_agentmemory_alive()
        print(json.dumps({
            "agentmemory": "alive" if alive else "dead",
            "memory_palace": "alive" if MEMORY_PALACE_PATH.exists() else "dead",
            "layer": "ultra" if alive else "base"
        }, indent=2))
    elif args.command == "sync":
        result = sync_all()
        print(json.dumps(result, indent=2))
    else:
        parser.print_help()
