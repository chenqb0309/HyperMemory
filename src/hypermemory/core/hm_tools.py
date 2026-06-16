"""HM Tool implementations — extracted from mcp_server.py"""

import sys
import os
import json
import re
from pathlib import Path

from hypermemory.core.pool import resolve_pool, ensure_pool, index_path, list_nodes, node_path
from hypermemory.core.index import parse_index
from hypermemory.core.cluster import find_best_cluster, find_all_clusters
from hypermemory.core.node import parse_frontmatter, extract_title, strip_body_links, generate_body_links, extract_keywords
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
                    node_type=fm.get("node_type", "經驗"),
                    ref_by_count=len(fm.get("ref_by", []) or []),
                )
            results.append({
                "cluster": ", ".join(keywords),
                "node": node_file,
                "exists": exists,
                "weight": round(weight, 2),
                "title": title,
            })
        from hypermemory.core.muscle_memory import pending_skill_count
        return {
            "clusters": results,
            "pending_skills": pending_skill_count(self.pool),
        }

    def recall(self, keywords, limit=5):
        """回憶與關鍵字匹配的經驗，按 recency 優先排序（最新在前）。"""
        from hypermemory.core.muscle_memory import pending_skill_count

        entries = self._read_index()
        kw_list = [k.strip() for k in keywords.split(",") if k.strip()]
        if not kw_list:
            return {"found": False, "message": "No keywords provided."}

        # Find ALL matching clusters
        matches = find_all_clusters(kw_list, entries, min_score=0.3)

        if not matches:
            return {"found": False, "message": "No matching memory found."}

        # Read all matched nodes, collect with timestamps
        nodes_with_ts = []
        for m in matches:
            node_file = m["node"]
            node_path = self.pool / node_file
            if not node_path.exists():
                continue
            with open(node_path, encoding="utf-8") as f:
                content = f.read()
            fm = parse_frontmatter(content)
            ts = fm.get("timestamp", "0000")
            title = extract_title(content)
            weight = calc_weight(
                fm.get("intensity", 1),
                fm.get("total_mentions", 0),
                fm.get("timestamp"),
                node_type=fm.get("node_type", "經驗"),
                ref_by_count=len(fm.get("ref_by", []) or []),
            )
            node_dims = parse_dimensions(fm)
            stats = get_confirmation_stats(self.pool, node_file)
            mat = calc_maturation(
                fm.get("intensity", 1),
                stats["positive"],
                stats["negative"],
                fm.get("timestamp"),
                node_dims=node_dims,
            )

            nodes_with_ts.append({
                "node": node_file,
                "title": title,
                "type": fm.get("node_type"),
                "intensity": fm.get("intensity"),
                "weight": round(weight, 2),
                "maturation": mat["score"],
                "timestamp": ts,
                "tags": fm.get("tags", []),
                "dimensions": node_dims,
                "cluster_score": m["score"],
                "cluster_keywords": m["keywords"],
                "prenode": fm.get("prenode"),
                "nextnodes": fm.get("nextnodes", []),
                "ref_by": fm.get("ref_by", []),
            })

        # Sort by timestamp descending (newest first)
        nodes_with_ts.sort(
            key=lambda n: n.get("timestamp", "0000") or "0000",
            reverse=True,
        )

        # 語義聯想（第三層）— 對 top result 做 associative recall
        if nodes_with_ts:
            try:
                from hypermemory.core.association import associative_recall
                assoc_result = associative_recall(
                    self.pool, nodes_with_ts[0]["node"], top_k=3
                )
                if assoc_result["found"] and assoc_result["suggestions"]:
                    nodes_with_ts[0]["suggestions"] = assoc_result["suggestions"]
            except Exception:
                pass  # Non-critical

        # Update total_mentions for the top result only
        if nodes_with_ts:
            top = nodes_with_ts[0]
            try:
                top_path = self.pool / top["node"]
                with open(top_path, encoding="utf-8") as f:
                    orig_content = f.read()
                mentions_match = re.search(r'total_mentions:\s*(\d+)', orig_content)
                mentions = (int(mentions_match.group(1)) if mentions_match else 0) + 1
                new_content = re.sub(
                    r'(total_mentions:\s*)\d+',
                    rf'\g<1>{mentions}',
                    orig_content,
                )
                with open(top_path, "w", encoding="utf-8") as f:
                    f.write(new_content)
            except Exception:
                pass  # Non-critical

        return {
            "found": True,
            "query": keywords,
            "total": len(nodes_with_ts),
            "results": nodes_with_ts[:limit],
            "pending_skills": pending_skill_count(self.pool),
        }

    def think(self, query):
        """習慣性回想：回傳最新 matching node（recency-first）。"""
        from hypermemory.core.muscle_memory import pending_skill_count

        entries = self._read_index()
        kw_list = [k.strip() for k in query.replace(",", " ").split() if k.strip()]
        if not kw_list:
            return {"found": False, "message": "No query provided."}

        # Find ALL matching clusters
        matches = find_all_clusters(kw_list, entries, min_score=0.3)

        if not matches:
            return {"found": False, "message": "No relevant experience found."}

        # Read all matched nodes, collect with timestamps
        candidates = []
        for m in matches:
            node_file = m["node"]
            node_path = self.pool / node_file
            if not node_path.exists():
                continue
            with open(node_path, encoding="utf-8") as f:
                content = f.read()
            fm = parse_frontmatter(content)
            title = extract_title(content)
            weight = calc_weight(
                fm.get("intensity", 1),
                fm.get("total_mentions", 0),
                fm.get("timestamp"),
                node_type=fm.get("node_type", "經驗"),
                ref_by_count=len(fm.get("ref_by", []) or []),
            )
            node_dims = parse_dimensions(fm)
            stats = get_confirmation_stats(self.pool, node_file)
            mat = calc_maturation(
                fm.get("intensity", 1),
                stats["positive"],
                stats["negative"],
                fm.get("timestamp"),
                node_dims=node_dims,
            )
            candidates.append({
                "node": node_file,
                "title": title,
                "type": fm.get("node_type"),
                "intensity": fm.get("intensity"),
                "weight": round(weight, 2),
                "maturation": mat["score"],
                "maturation_detail": mat,
                "timestamp": fm.get("timestamp", "0000"),
                "tags": fm.get("tags", []),
                "dimensions": node_dims,
                "cluster_score": m["score"],
                "prenode": fm.get("prenode"),
                "nextnodes": fm.get("nextnodes", []),
                "ref_by": fm.get("ref_by", []),
            })

        # Sort by timestamp descending (newest first)
        candidates.sort(
            key=lambda n: n.get("timestamp", "0000") or "0000",
            reverse=True,
        )

        best = candidates[0]

        # 語義聯想（第三層）— 對 top result 做 associative recall
        try:
            from hypermemory.core.association import associative_recall
            assoc_result = associative_recall(self.pool, best["node"], top_k=3)
            if assoc_result["found"] and assoc_result["suggestions"]:
                best["suggestions"] = assoc_result["suggestions"]
        except Exception:
            pass  # Non-critical

        # Read full content for body preview
        try:
            with open(self.pool / best["node"], encoding="utf-8") as f:
                full_content = f.read()
        except Exception:
            full_content = ""

        # Extract body preview
        body_lines = []
        body_start = False
        for line in full_content.split("\n"):
            if body_start:
                if line.startswith("## ") and "關聯" in line:
                    continue
                if line.strip():
                    body_lines.append(line.strip()[:200])
                    if len(body_lines) >= 5:
                        break
            elif line.startswith("## 正文") or (line.startswith("## ") and "關聯" not in line):
                body_start = True

        best["summary"] = " | ".join(body_lines) if body_lines else best["title"]

        # Update total_mentions
        try:
            mentions_match = re.search(r'total_mentions:\s*(\d+)', full_content)
            mentions = (int(mentions_match.group(1)) if mentions_match else 0) + 1
            new_content = re.sub(r'(total_mentions:\s*)\d+', rf'\g<1>{mentions}', full_content)
            with open(self.pool / best["node"], "w", encoding="utf-8") as f:
                f.write(new_content)
        except Exception:
            pass

        return {
            "found": True,
            "result": best,
            "total_candidates": len(candidates),
            "pending_skills": pending_skill_count(self.pool),
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
            node_type=fm.get("node_type", "經驗"),
            ref_by_count=len(fm.get("ref_by", []) or []),
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

    def explore(self, node_name, depth=3, min_weight=0.0, direction="forward"):
        """從一個 node 出發遍歷鏈。"""
        from hypermemory.core.explore import explore_chain
        result = explore_chain(
            self.pool, node_name,
            direction=direction, depth=depth, min_weight=min_weight,
        )
        return result

    def maintain_now(self, action):
        """立即觸發維護循環"""
        from hypermemory.commands.daemon import run_maintain
        try:
            run_maintain(self.pool, action)
            return {"success": True, "action": action}
        except Exception as e:
            return {"success": False, "action": action, "error": str(e)}

    def check_skill_candidates(self):
        """列出所有 skill_ready 的經驗 node"""
        from hypermemory.core.muscle_memory import check_candidates
        return check_candidates(self.pool)

    def register_skill(self, skill_json):
        """將一個經驗 node 轉換註冊為結構化 skill"""
        from hypermemory.core.muscle_memory import register_skill
        return register_skill(self.pool, skill_json)
