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
from hypermemory.core.dimensions import parse_dimensions, is_compatible, dimension_overlap_score
from hypermemory.core.maturation import (
    create_confirmation,
    get_confirmation_stats,
    calc_maturation,
    list_confirmations,
    scan_maturation_all,
)


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
            "dimensions": parse_dimensions(fm),
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

        # Maturation info
        node_dims = parse_dimensions(fm)
        stats = get_confirmation_stats(self.pool, node_file)
        mat = calc_maturation(
            fm.get("intensity", 1),
            stats["positive"],
            stats["negative"],
            fm.get("timestamp"),
            node_dims=node_dims,
        )

        return {
            "found": True,
            "title": title,
            "type": fm.get("node_type"),
            "intensity": fm.get("intensity"),
            "weight": round(weight, 2),
            "maturation": mat["score"],
            "maturation_detail": mat,
            "summary": " | ".join(body_lines) if body_lines else title,
            "prenode": fm.get("prenode"),
            "tags": fm.get("tags", []),
            "dimensions": node_dims,
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

        node_dims = parse_dimensions(fm)
        stats = get_confirmation_stats(self.pool, node_path.name)
        mat = calc_maturation(
            fm.get("intensity", 1),
            stats["positive"],
            stats["negative"],
            fm.get("timestamp"),
            node_dims=node_dims,
        )

        return {
            "found": True,
            "node": node_path.name,
            "title": title,
            "type": fm.get("node_type"),
            "intensity": fm.get("intensity"),
            "mentions": fm.get("total_mentions", 0),
            "weight": round(weight, 2),
            "maturation": mat["score"],
            "maturation_detail": mat,
            "timestamp": fm.get("timestamp"),
            "tags": fm.get("tags", []),
            "prenode": prenode,
            "prenode_exists": prenode and (self.pool / prenode).exists(),
            "nextnodes": nextnodes,
            "ref_by": ref_by,
            "dimensions": node_dims,
        }

    def imprint(self, content, filename=None):
        """從文字內容刻錄新 node（MCP 版本，無檔案路徑）"""
        from hypermemory.core.node import strip_body_links, generate_body_links, extract_keywords
        from hypermemory.core.index import sync_parent_links, format_index_entry

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

        content = strip_body_links(content)
        content = generate_body_links(content)

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
        new_keywords = extract_keywords(fm, dest_name)

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
                sync_parent_links(self.pool, prenode, dest_name)
            else:
                index_content += format_index_entry(new_keywords, dest_name) + "\n"
        else:
            index_content += format_index_entry(new_keywords, dest_name) + "\n"

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

    def confirm(self, source_node, result, agent, context_summary="", dimensions=None):
        """回報確認事件。source_node + result 為必填。"""
        dims = dimensions or {}
        outcome = create_confirmation(
            self.pool, source_node, result,
            agent=agent or "unknown",
            context_summary=context_summary or "",
            dimensions=dims,
        )
        if not outcome["success"]:
            return {"success": False, "error": outcome.get("error", "Unknown error")}

        # 回傳更新後的 maturation 資訊
        with open(self.pool / source_node, encoding="utf-8") as f:
            content = f.read()
        fm = parse_frontmatter(content)
        intensity = fm.get("intensity", 1)
        stats = get_confirmation_stats(self.pool, source_node)
        node_dims = parse_dimensions(fm)
        mat = calc_maturation(
            intensity, stats["positive"], stats["negative"],
            fm.get("timestamp"),
            context_dims=dims,
            node_dims=node_dims,
        )

        return {
            "success": True,
            "confirmation_id": outcome["confirmation_id"],
            "source": source_node,
            "result": result,
            "maturation": mat,
        }

    def daemon_status(self):
        """查詢 daemon 狀態"""
        from hypermemory.commands.daemon import _pid_path, _log_path, _sched_path, ACTION_NAMES
        from datetime import datetime, timedelta
        import json

        pid_path = _pid_path()
        log_path = _log_path()
        sched_path = _sched_path()

        # Check if running
        running = False
        pid = None
        if pid_path.exists():
            try:
                pid = int(pid_path.read_text().strip())
                import os
                os.kill(pid, 0)
                running = True
            except (OSError, ValueError):
                pass

        result = {
            "running": running,
            "pid": pid,
        }

        # Next schedule
        if sched_path.exists():
            try:
                with open(sched_path) as f:
                    schedule = json.load(f)
                now = datetime.now()
                tasks = []
                for action, cfg in schedule.items():
                    target = now.replace(hour=cfg["hour"], minute=cfg["minute"], second=0, microsecond=0)
                    if target <= now:
                        target += timedelta(days=1)
                    if cfg.get("dow") is not None:
                        days_ahead = cfg["dow"] - target.weekday()
                        if days_ahead <= 0:
                            days_ahead += 7
                        target += timedelta(days=days_ahead)
                    tasks.append({
                        "action": action,
                        "label": ACTION_NAMES.get(action, action),
                        "next_run": target.isoformat(),
                        "next_run_human": target.strftime("%Y-%m-%d %H:%M"),
                    })
                result["schedule"] = sorted(tasks, key=lambda t: t["next_run"])
            except Exception as e:
                result["schedule_error"] = str(e)

        # Recent log
        if log_path.exists():
            try:
                with open(log_path) as f:
                    lines = f.readlines()
                result["recent_log"] = [l.rstrip() for l in lines[-10:]]
            except OSError:
                pass

        return result

    def pool_info(self):
        """記憶池健康狀態"""
        from hypermemory.core.pool import index_path, list_nodes, node_path

        idx = index_path(self.pool)
        entries = []
        if idx.exists():
            from hypermemory.core.index import parse_index
            entries = parse_index(idx.read_text(encoding="utf-8"))

        nodes = list(list_nodes(self.pool))
        orphan_count = 0
        for kw, node_file in entries:
            if not (self.pool / node_file).exists():
                orphan_count += 1

        return {
            "pool": str(self.pool),
            "cluster_count": len(entries),
            "node_count": len(nodes),
            "index_exists": idx.exists(),
            "orphan_clusters": orphan_count,
        }

    def maintain_now(self, action):
        """立即觸發維護循環"""
        from hypermemory.commands.daemon import run_maintain
        try:
            run_maintain(self.pool, action)
            return {"success": True, "action": action}
        except Exception as e:
            return {"success": False, "action": action, "error": str(e)}


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
    "hm_daemon_status": {
        "description": "查詢內建排程器（hm daemon）是否存活、下次排程時間與最近日誌",
        "input_schema": {
            "type": "object",
            "properties": {},
        },
    },
    "hm_pool_info": {
        "description": "記憶池健康狀態：node 總數、cluster 總數、index 完整性",
        "input_schema": {
            "type": "object",
            "properties": {},
        },
    },
    "hm_maintain_now": {
        "description": "立即觸發維護循環。action 可為 recalc / dreamloop / reflect / all",
        "input_schema": {
            "type": "object",
            "properties": {
                "action": {
                    "type": "string",
                    "description": "維護動作：recalc（權重重算）、dreamloop（關鍵字去重）、reflect（自動刻錄）、all（全部）",
                }
            },
            "required": ["action"],
        },
    },
    "hm_confirm": {
        "description": "回報經驗 node 的事實驗證結果。agent 套用經驗後，根據事實結果呼叫此 tool 回報正/負反饋，累積 maturation score。",
        "input_schema": {
            "type": "object",
            "properties": {
                "source": {
                    "type": "string",
                    "description": "被確認的源 node 檔名，如 2026-06-15-build-env.md",
                },
                "result": {
                    "type": "string",
                    "description": "驗證結果：positive（成功）、negative（失敗）、neutral（無明確事實回饋）",
                },
                "agent": {
                    "type": "string",
                    "description": "回報的 agent 名稱，如 hermes / opencode / claude-code",
                },
                "context_summary": {
                    "type": "string",
                    "description": "驗證時的 context 摘要，供日後回溯",
                },
                "dimensions": {
                    "type": "object",
                    "description": "驗證時的環境維度，如 {機: WSL, 料: Python 3.11, 法: uv-install, 環: venv}。用於 5M1E 維度碰撞比對與打分篩選。",
                },
            },
            "required": ["source", "result"],
        },
    },
}


def handle_request(tools, request):
    req = json.loads(request)
    req_id = req.get("id")
    method = req.get("method")

    # JSON-RPC
    if method == "initialize":
        params = req.get("params", {})
        client_version = params.get("protocolVersion", "2024-11-05")
        return json.dumps({
            "jsonrpc": "2.0",
            "id": req_id,
            "result": {
                "protocolVersion": client_version,
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

            elif tool_name == "hm_daemon_status":
                result = tools.daemon_status()
                text = json.dumps(result, ensure_ascii=False, indent=2)

            elif tool_name == "hm_pool_info":
                result = tools.pool_info()
                text = json.dumps(result, ensure_ascii=False, indent=2)

            elif tool_name == "hm_maintain_now":
                action = arguments.get("action", "all")
                result = tools.maintain_now(action)
                text = json.dumps(result, ensure_ascii=False, indent=2)

            elif tool_name == "hm_confirm":
                source = arguments.get("source", "")
                result_val = arguments.get("result", "neutral")
                agent = arguments.get("agent", "unknown")
                ctx_summary = arguments.get("context_summary", "")
                dims = arguments.get("dimensions", {})
                result = tools.confirm(source, result_val, agent, ctx_summary, dims)
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

    # MCP stdio transport with newline-delimited JSON (Python MCP SDK format)
    buffer = b""
    while True:
        try:
            chunk = sys.stdin.buffer.read1(4096)
            if not chunk:
                break
            buffer += chunk

            # Process complete lines (newline-delimited JSON)
            while b"\n" in buffer:
                line, buffer = buffer.split(b"\n", 1)
                line = line.strip()
                if not line:
                    continue
                body = line.decode()
                response = handle_request(tools, body)
                if response:
                    resp_bytes = response.encode()
                    sys.stdout.buffer.write(resp_bytes + b"\n")
                    sys.stdout.buffer.flush()

        except (EOFError, KeyboardInterrupt):
            break
        except Exception as e:
            error_resp = json.dumps({
                "jsonrpc": "2.0",
                "id": None,
                "error": {"code": -32700, "message": str(e)},
            })
            sys.stdout.buffer.write(error_resp.encode() + b"\n")
            sys.stdout.buffer.flush()


if __name__ == "__main__":
    main()
