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

    def imprint(self, content, filename=None):
        """從文字內容刻錄新 node（MCP 版本，無檔案路徑）"""
        from hypermemory.commands.imprint import _strip_body_links, _generate_body_links, _extract_keywords, _sync_parent_links, _format_entry

        fm = parse_frontmatter(content)

        errors = []
        if not fm.get("type"): errors.append("Missing: type")
        if not fm.get("timestamp"): errors.append("Missing: timestamp")
        if fm.get("node_type") is None: errors.append("Missing: node_type")
        if fm.get("intensity") is None: errors.append("Missing: intensity")
        if errors:
            return {"success": False, "errors": errors}

        if filename:
            dest_name = filename
        else:
            import datetime
            ts = datetime.datetime.now().strftime("%Y-%m-%d")
            title = extract_title(content) or "untitled"
            slug = title.lower().replace(" ", "-")[:30]
            dest_name = f"{ts}-{slug}.md"

        if not dest_name.endswith(".md"):
            dest_name += ".md"

        dest_path = self.pool / dest_name
        if dest_path.exists():
            return {"success": False, "error": f"Node already exists: {dest_name}"}

        content = _strip_body_links(content)
        content = _generate_body_links(content)

        with open(dest_path, "w", encoding="utf-8") as f:
            f.write(content)

        idx_path = self.pool / "index.md"
        if idx_path.exists():
            with open(idx_path, encoding="utf-8") as f:
                index_content = f.read()
            from hypermemory.core.index import parse_index, update_index_entry
            entries = parse_index(index_content)
        else:
            index_content = "# HyperMemory Pool Index\n\n"
            entries = []

        prenode = fm.get("prenode")
        new_keywords = _extract_keywords(fm, dest_name)

        if prenode:
            pre_entry = None
            for kw_list, node_file in entries:
                if node_file == prenode:
                    pre_entry = (kw_list, node_file)
                    break
            if pre_entry:
                old_node = pre_entry[1]
                new_weight = calc_weight(fm.get("intensity", 1), fm.get("total_mentions", 1), fm.get("timestamp"))
                old_path = self.pool / old_node
                old_weight = 0
                if old_path.exists():
                    with open(old_path, encoding="utf-8") as f:
                        old_content = f.read()
                    old_fm = parse_frontmatter(old_content)
                    old_weight = calc_weight(old_fm.get("intensity", 1), old_fm.get("total_mentions", 0), old_fm.get("timestamp"))
                pointer = dest_name if new_weight > old_weight else old_node
                index_content = update_index_entry(index_content, old_node, pointer, new_keywords)
                _sync_parent_links(self.pool, prenode, dest_name)
            else:
                index_content += _format_entry(new_keywords, dest_name) + "\n"
        else:
            index_content += _format_entry(new_keywords, dest_name) + "\n"

        with open(idx_path, "w", encoding="utf-8") as f:
            f.write(index_content)

        weight = calc_weight(fm.get("intensity", 1), fm.get("total_mentions", 1), fm.get("timestamp"))
        return {
            "success": True,
            "node": dest_name,
            "title": extract_title(content),
            "type": fm.get("node_type"),
            "weight": round(weight, 2),
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
    "hm_imprint": {
        "description": "將一段經驗儲存為新的記憶 node。需要提供含 frontmatter 的完整 markdown 內容。CLI 用法：hm imprint <file>",
        "input_schema": {
            "type": "object",
            "properties": {
                "content": {
                    "type": "string",
                    "description": "含 frontmatter 的完整 markdown 內容。必須包含 type, timestamp, node_type, intensity, total_mentions 欄位。",
                },
                "filename": {
                    "type": "string",
                    "description": "Node 檔名（如 2026-06-15-experience.md）。預設自動產生。",
                },
            },
            "required": ["content"],
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

            elif tool_name == "hm_imprint":
                content = arguments.get("content", "")
                filename = arguments.get("filename", None)
                result = tools.imprint(content, filename)
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
