"""MCP server 協定驗證測試"""
import subprocess, json, sys, os, shutil

POOL = os.path.join(os.path.dirname(__file__), "fixtures", "mcp-test")


def send_once(method, params=None, req_id=1):
    req = {"jsonrpc": "2.0", "id": req_id, "method": method}
    if params:
        req["params"] = params
    body = json.dumps(req)
    header = f"Content-Length: {len(body.encode())}\r\n\r\n"
    return header + body, req


def test_mcp():
    os.makedirs(POOL, exist_ok=True)
    with open(os.path.join(POOL, "index.md"), "w") as f:
        f.write("# Pool\n《cluster: [test]》 → [[n.md]]\n")
    with open(os.path.join(POOL, "n.md"), "w") as f:
        f.write("---\ntype: episodic_memory\ntimestamp: 2026-06-15T10:00:00+08:00\nnode_type: 1\nprenode: null\nnextnodes: null\nref_by: null\nintensity: 5\ntotal_mentions: 1\ntags: [test]\n---\n\n# N\nbody\n")

    base_cmd = [sys.executable, "-u", "-m", "hypermemory", "serve", "--pool", POOL]
    passed = 0
    failed = 0

    def run_test(name, method, params=None, req_id=1, check_text=None, check=None):
        nonlocal passed, failed
        stdin, _ = send_once(method, params, req_id)
        p = subprocess.Popen(base_cmd, stdin=subprocess.PIPE, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)
        out, err = p.communicate(input=stdin, timeout=5)

        resp = None
        text_content = ""
        for line in out.strip().split("\n"):
            line = line.strip()
            if line.startswith("{"):
                try:
                    resp = json.loads(line)
                    # Extract text content from response
                    text_content = resp.get("result", {}).get("content", [{}])[0].get("text", "")
                    break
                except:
                    pass

        if resp and ((check_text and check_text in text_content) or (check and check(resp))):
            passed += 1
            print(f"  OK  {name}")
        else:
            failed += 1
            detail = err.strip()[:200] if err.strip() else (json.dumps(resp, ensure_ascii=False)[:200] if resp else "no response/empty")
            print(f"  FAIL {name}: {detail}")

    # 1. initialize
    run_test("initialize", "initialize", check=lambda r: r.get("result",{}).get("serverInfo",{}).get("name") == "hypermemory")

    # 2. tools/list
    run_test("tools/list", "tools/list", req_id=2, check=lambda r: {"hm_list","hm_recall","hm_think","hm_inspect","hm_imprint"}.issubset({t["name"] for t in r.get("result",{}).get("tools",[])}))

    # 3. hm_list
    run_test("hm_list", "tools/call", {"name":"hm_list","arguments":{}}, req_id=3, check_text="test")

    # 4. hm_recall
    run_test("hm_recall", "tools/call", {"name":"hm_recall","arguments":{"keywords":"test"}}, req_id=4, check_text='"found": true')

    # 5. hm_think
    run_test("hm_think", "tools/call", {"name":"hm_think","arguments":{"query":"test"}}, req_id=5, check_text='"found":')

    # 6. hm_inspect
    run_test("hm_inspect", "tools/call", {"name":"hm_inspect","arguments":{"node":"n.md"}}, req_id=6, check_text='"N"')

    # 7. hm_imprint
    ic = "---\ntype: episodic_memory\ntimestamp: 2026-06-15T11:00:00+08:00\nnode_type: 1\nprenode: null\nintensity: 6\ntotal_mentions: 1\ntags: [mcp-test]\n---\n\n# MCP Test\nbody\n"
    run_test("hm_imprint", "tools/call", {"name":"hm_imprint","arguments":{"content":ic,"filename":"mcp-test.md"}}, req_id=7, check_text="success")

    # 8. file created
    if os.path.exists(os.path.join(POOL, "mcp-test.md")):
        passed += 1
        print("  OK  hm_imprint file created")
    else:
        failed += 1
        print("  FAIL hm_imprint file: not found")

    shutil.rmtree(POOL, ignore_errors=True)
    print(f"\n{passed} passed, {failed} failed")
    return failed == 0


if __name__ == "__main__":
    ok = test_mcp()
    sys.exit(0 if ok else 1)
