"""HyperMemory MCP Server — hm serve"""

import sys
import os
import json
import re
import traceback
from pathlib import Path

# Add src to path
sys.path.insert(0, str(Path(__file__).parent.parent / "src"))

from hypermemory.core.pool import resolve_pool, ensure_pool, index_path, list_nodes, node_path
from hypermemory.core.index import parse_index
from hypermemory.core.cluster import find_best_cluster
from hypermemory.core.node import parse_frontmatter, extract_title
from hypermemory.core.weight import calc_weight, format_score


class HMTools:
    """HM MCP tool implementations"""

    def __init__(self, pool_path=None):
        self.pool = resolve_pool(pool_path)
        ensure_pool(self.pool)

    def _read_index(self):
        idx = index_path(self.pool)
        if not idx.exists():
            return []
        with open(idx, encoding="utf-8") as f:
            return parse_index(f.read())

    def list_clusters(self):
        entries = self._read_index()
        results = []
        for keywords, node_file in entries:
            node_path = self.pool / node_file
            exists = node_path.exists()
            weight = 0
            title = ""
            if exists:
                with open(node_path, encoding="utf-8") as f:
                    content = f.read()
                fm = parse_frontmatter(content)
                title = extract_title(content)
                weight = calc_weight(
                    fm.get("intensity", 1),
                    fm.get("total_mentions", 0),
                    fm.get("timestamp"),
                )
            results.append({
                "cluster": ", ".join(keywords),
                "node": node_file,
                "exists": exists,
                "weight": round(weight, 2),
                "title": title,
            })
        return results

    def recall(self, keywords):
        entries = self._read_index()
        kw_list = [k.strip() for k in keywords.split(",")]
        result = find_best_cluster(kw_list, entries)
        if not result or not result[0]:
            return {"found": False, "message": "No matching memory found."}

        _, node_file, score = result
        node_path = self.pool / node_file
        if not node_path.exists():
            return {"found": False, "message": f"Node file missing: {node_file}"}

        with open(node_path, encoding="utf-8") as f:
            content = f.read()

        fm = parse_frontmatter(content)
        title = extract_title(content)
        weight = calc_weight(
            fm.get("intensity", 1),
            fm.get("total_mentions", 0),
            fm.get("timestamp"),
        )

        # Update total_mentions
        mentions = fm.get("total_mentions", 0) + 1
        import re
        new_content = re.sub(r'(total_mentions:\s*)\d+', rf'\g<1>{mentions}', content)
        with open(node_path, "w", encoding="utf-8") as f:
            f.write(new_content)

        return {
            "found": True,
            "node": node_file,
            "title": title,
            "type": fm.get("node_type"),
            "intensity": fm.get("intensity"),
            "weight": round(weight, 2),
            "total_mentions": mentions,
            "prenode": fm.get("prenode"),
            "nextnodes": fm.get("nextnodes", []),
            "score": round(score, 2),
        }

    def think(self, query):
        """Think-triggered recall: 回答前的習慣性回憶。回傳相關經驗。"""
        entries = self._read_index()
        kw_list = [k.strip() for k in query.replace(",", " ").split()]
        result = find_best_cluster(kw_list, entries)

        if not result or not result[0]:
            return {"found": False, "message": "No relevant experience found."}

        _, node_file, score = result
        node_path = self.pool / node_file
        if not node_path.exists():
            return {"found": False, "message": f"Node file missing: {node_file}"}

        with open(node_path, encoding="utf-8") as f:
            content = f.read()

        fm = parse_frontmatter(content)
        title = extract_title(content)
        weight = calc_weight(
            fm.get("intensity", 1),
            fm.get("total_mentions", 0),
            fm.get("timestamp"),
        )

        # Update total_mentions
        mentions = fm.get("total_mentions", 0) + 1
        import re
        new_content = re.sub(r'(total_mentions:\s*)\d+', rf'\g<1>{mentions}', content)
        with open(node_path, "w", encoding="utf-8") as f:
            f.write(new_content)

        # Extract body preview
        body_lines = []
        body_start = False
        for line in content.split("\n"):
            if body_start:
                if line.startswith("## ") and "關聯" in line:
                    continue
                if line.strip():
                    body_lines.append(line.strip()[:200])
                    if len(body_lines) >= 5:
                        break
            elif line.startswith("## 正文") or (line.startswith("## ") and "關聯" not in line):
                body_start = True

        return {
            "found": True,
            "title": title,
            "type": fm.get("node_type"),
            "intensity": fm.get("intensity"),
            "weight": round(weight, 2),
            "summary": " | ".join(body_lines) if body_lines else title,
            "prenode": fm.get("prenode"),
            "tags": fm.get("tags", []),
        }

    def inspect(self, node_name):
        node_path = self.pool / node_name
        if not node_path.exists():
            node_path = self.pool / f"{node_name}.md"
        if not node_path.exists():
            return {"found": False, "message": f"Node not found: {node_name}"}

        with open(node_path, encoding="utf-8") as f:
            content = f.read()

        fm = parse_frontmatter(content)
        title = extract_title(content)
        weight = calc_weight(
            fm.get("intensity", 1),
            fm.get("total_mentions", 0),
            fm.get("timestamp"),
        )

        # Check prenode and nextnodes file existence
        prenode = fm.get("prenode")
        nextnodes = fm.get("nextnodes", [])
        ref_by = fm.get("ref_by", [])

        return {
            "found": True,
            "node": node_path.name,
            "title": title,
            "type": fm.get("node_type"),
            "intensity": fm.get("intensity"),
            "mentions": fm.get("total_mentions", 0),
            "weight": round(weight, 2),
            "timestamp": fm.get("timestamp"),
            "tags": fm.get("tags", []),
            "prenode": prenode,
            "prenode_exists": prenode and (self.pool / prenode).exists(),
            "nextnodes": nextnodes,
            "ref_by": ref_by,
        }


TOOLS = {
    "hm_list": {
        "description": "列出記憶池中所有 cluster 與當前指向的 node（含權重、標題）",
        "input_schema": {
            "type": "object",
            "properties": {},
        },
    },
    "hm_recall": {
        "description": "搜尋個人經驗記憶，找出與關鍵字匹配的過往經歷。回傳最相關的 node 詳細內容。",
        "input_schema": {
            "type": "object",
            "properties": {
                "keywords": {
                    "type": "string",
                    "description": "逗號分隔的關鍵詞，用於匹配過往經驗",
                }
            },
            "required": ["keywords"],
        },
    },
    "hm_think": {
        "description": "回答使用者問題前呼叫此工具，回想相關的個人經驗記憶。如果找到相關經驗會回傳摘要，可將這些經驗整合進回答中。",
        "input_schema": {
            "type": "object",
            "properties": {
                "query": {
                    "type": "string",
                    "description": "使用者的問題或當前討論主題",
                }
            },
            "required": ["query"],
        },
    },
    "hm_inspect": {
        "description": "檢視單一記憶 node 的詳細資訊，包含 frontmatter、鏈結關係（prenode/nextnodes）。",
        "input_schema": {
            "type": "object",
            "properties": {
                "node": {
                    "type": "string",
                    "description": "Node 檔名，如 2026-06-11-buildout.md",
                }
            },
            "required": ["node"],
        },
    },
}


def handle_request(tools, request):
    req = json.loads(request)
    req_id = req.get("id")
    method = req.get("method")

    # JSON-RPC
    if method == "initialize":
        return json.dumps({
            "jsonrpc": "2.0",
            "id": req_id,
            "result": {
                "protocolVersion": "0.1.0",
                "capabilities": {
                    "tools": {}
                },
                "serverInfo": {
                    "name": "hypermemory",
                    "version": "1.0.0",
                },
            },
        })

    elif method == "notifications/initialized":
        return None

    elif method == "tools/list":
        return json.dumps({
            "jsonrpc": "2.0",
            "id": req_id,
            "result": {
                "tools": [
                    {
                        "name": name,
                        "description": info["description"],
                        "inputSchema": info["input_schema"],
                    }
                    for name, info in TOOLS.items()
                ],
            },
        })

    elif method == "tools/call":
        params = req.get("params", {})
        tool_name = params.get("name")
        arguments = params.get("arguments", {})

        try:
            if tool_name == "hm_list":
                result = tools.list_clusters()
                text = json.dumps(result, ensure_ascii=False, indent=2)

            elif tool_name == "hm_recall":
                keywords = arguments.get("keywords", "")
                result = tools.recall(keywords)
                text = json.dumps(result, ensure_ascii=False, indent=2)

            elif tool_name == "hm_think":
                query = arguments.get("query", "")
                result = tools.think(query)
                text = json.dumps(result, ensure_ascii=False, indent=2)

            elif tool_name == "hm_inspect":
                node = arguments.get("node", "")
                result = tools.inspect(node)
                text = json.dumps(result, ensure_ascii=False, indent=2)

            else:
                raise ValueError(f"Unknown tool: {tool_name}")

        except Exception as e:
            text = json.dumps({"error": str(e)}, ensure_ascii=False)

        return json.dumps({
            "jsonrpc": "2.0",
            "id": req_id,
            "result": {
                "content": [{"type": "text", "text": text}],
            },
        })

    else:
        return json.dumps({
            "jsonrpc": "2.0",
            "id": req_id,
            "error": {"code": -32601, "message": f"Method not found: {method}"},
        })


def main(pool=None):
    tools = HMTools(pool)

    # MCP stdio transport with Content-Length framing
    buffer = b""
    while True:
        try:
            chunk = sys.stdin.buffer.read(4096)
            if not chunk:
                break
            buffer += chunk

            while b"Content-Length:" in buffer:
                # Parse headers
                header_end = buffer.find(b"\r\n\r\n")
                if header_end == -1:
                    break

                headers = buffer[:header_end].decode()
                body_start = header_end + 4

                m = re.search(r"Content-Length:\s*(\d+)", headers)
                if not m:
                    buffer = buffer[body_start:]
                    continue

                content_length = int(m.group(1))
                if len(buffer) < body_start + content_length:
                    break  # Wait for more data

                body = buffer[body_start:body_start + content_length].decode()
                buffer = buffer[body_start + content_length:]

                response = handle_request(tools, body)
                if response:
                    resp_bytes = response.encode()
                    sys.stdout.buffer.write(f"Content-Length: {len(resp_bytes)}\r\n\r\n".encode())
                    sys.stdout.buffer.write(resp_bytes)
                    sys.stdout.buffer.flush()

        except (EOFError, KeyboardInterrupt):
            break
        except Exception as e:
            error_resp = json.dumps({
                "jsonrpc": "2.0",
                "id": None,
                "error": {"code": -32700, "message": str(e)},
            })
            sys.stdout.buffer.write(f"Content-Length: {len(error_resp)}\r\n\r\n".encode())
            sys.stdout.buffer.write(error_resp.encode())
            sys.stdout.buffer.flush()


if __name__ == "__main__":
    main()
