"""HyperMemory MCP Server — hm serve"""

import sys
import json
from pathlib import Path

# Add src to path
sys.path.insert(0, str(Path(__file__).parent.parent / "src"))

from hypermemory.core.hm_tools import HMTools


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
    "hm_explore": {
        "description": "從一個記憶 node 出發，沿鏈向前（nextnodes）或向後（prenode）探索上下游 node。depth 控制層數，min_weight 過濾低權重 node。",
        "input_schema": {
            "type": "object",
            "properties": {
                "node": {
                    "type": "string",
                    "description": "起始 node 檔名，如 2026-06-11-buildout.md",
                },
                "depth": {
                    "type": "integer",
                    "description": "最大探索層數（預設 3）",
                },
                "min_weight": {
                    "type": "number",
                    "description": "最低權重，低於此值的 node 不回傳（預設 0 = 全部回傳）",
                },
                "direction": {
                    "type": "string",
                    "description": "探索方向：forward（下游）、backward（上游）、both（雙向）",
                },
            },
            "required": ["node"],
        },
    },
    "hm_check_skill_candidates": {
        "description": "列出所有 skill_ready 的經驗 node。當 weight + mentions + ref_by 達到門檻後，經驗可轉換為可重複使用的 skill。回傳每個 candidate 的 metadata 與 body 摘要。",
        "input_schema": {
            "type": "object",
            "properties": {},
        },
    },
    "hm_register_skill": {
        "description": "將一個經驗 node 轉換註冊為結構化 skill。需要提供 skill JSON，包含 skill_name、trigger、steps。HM 會驗證格式並儲存到技能庫。",
        "input_schema": {
            "type": "object",
            "properties": {
                "skill_json": {
                    "type": "object",
                    "description": "結構化 skill JSON，包含 skill_name, trigger, steps, source_node",
                }
            },
            "required": ["skill_json"],
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

            elif tool_name == "hm_explore":
                node = arguments.get("node", "")
                depth = arguments.get("depth", 3)
                min_weight = arguments.get("min_weight", 0.0)
                direction = arguments.get("direction", "forward")
                result = tools.explore(node, depth, min_weight, direction)
                text = json.dumps(result, ensure_ascii=False, indent=2)

            elif tool_name == "hm_check_skill_candidates":
                result = tools.check_skill_candidates()
                text = json.dumps(result, ensure_ascii=False, indent=2)

            elif tool_name == "hm_register_skill":
                skill_json = arguments.get("skill_json", {})
                result = tools.register_skill(skill_json)
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
