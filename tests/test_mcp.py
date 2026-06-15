"""MCP server 協定驗證測試"""
import subprocess, json, sys, os, time, re
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "src"))

POOL = os.path.join(os.path.dirname(__file__), "..", "tests", "fixtures")
SERVER_SCRIPT = os.path.join(os.path.dirname(__file__), "..", "src", "hypermemory", "mcp_server.py")


def send_request(proc, method, params=None, req_id=1):
    req = {"jsonrpc": "2.0", "id": req_id, "method": method}
    if params:
        req["params"] = params
    body = json.dumps(req)
    proc.stdin.write(f"Content-Length: {len(body.encode())}\r\n\r\n{body}")
    proc.stdin.flush()

    # Read header line
    line = proc.stdout.readline()
    m = re.search(r"Content-Length:\s*(\d+)", line)
    if not m:
        return None
    cl = int(m.group(1))
    proc.stdout.readline()  # blank line
    body = proc.stdout.read(cl)
    return json.loads(body)


def test_mcp_protocol():
    # Prepare test fixtures
    os.makedirs(POOL, exist_ok=True)
    with open(os.path.join(POOL, "index.md"), "w") as f:
        f.write("# HyperMemory Pool Index\n\n")
        f.write('《cluster: [test, sample]》 → [[test-node.md]]\n')
    with open(os.path.join(POOL, "test-node.md"), "w") as f:
        f.write("""---
type: episodic_memory
timestamp: 2026-06-15T10:00:00+08:00
node_type: 1
prenode: null
nextnodes: null
ref_by: null
intensity: 5
total_mentions: 1
tags: [test]
---

# Test Node

Test content body.
""")

    proc = subprocess.Popen(
        [sys.executable, SERVER_SCRIPT, "--pool", POOL],
        stdin=subprocess.PIPE, stdout=subprocess.PIPE, stderr=subprocess.PIPE,
        text=True,
    )

    passed = 0
    failed = 0

    try:
        time.sleep(0.5)

        # 1. Initialize
        resp = send_request(proc, "initialize")
        if resp and resp.get("result", {}).get("serverInfo", {}).get("name") == "hypermemory":
            print(f"  OK  initialize")
            passed += 1
        else:
            print(f"  FAIL initialize: {resp}")
            failed += 1

        # 2. tools/list
        resp = send_request(proc, "tools/list", req_id=2)
        if resp:
            tools = resp.get("result", {}).get("tools", [])
            tool_names = {t["name"] for t in tools}
            expected = {"hm_list", "hm_recall", "hm_think", "hm_inspect", "hm_imprint"}
            if expected.issubset(tool_names):
                print(f"  OK  tools/list ({len(tools)} tools)")
                passed += 1
            else:
                missing = expected - tool_names
                print(f"  FAIL tools/list: missing {missing}")
                failed += 1
        else:
            print(f"  FAIL tools/list: no response")
            failed += 1

        # 3. hm_list
        resp = send_request(proc, "tools/call", {"name": "hm_list", "arguments": {}}, req_id=3)
        if resp:
            text = resp.get("result", {}).get("content", [{}])[0].get("text", "")
            if "test" in text:
                print(f"  OK  hm_list")
                passed += 1
            else:
                print(f"  FAIL hm_list: {text[:100]}")
                failed += 1
        else:
            print(f"  FAIL hm_list: no response")
            failed += 1

        # 4. hm_recall
        resp = send_request(proc, "tools/call", {"name": "hm_recall", "arguments": {"keywords": "test"}}, req_id=4)
        if resp:
            text = resp.get("result", {}).get("content", [{}])[0].get("text", "")
            if "found" in text:
                print(f"  OK  hm_recall")
                passed += 1
            else:
                print(f"  FAIL hm_recall: {text[:100]}")
                failed += 1
        else:
            print(f"  FAIL hm_recall: no response")
            failed += 1

        # 5. hm_think
        resp = send_request(proc, "tools/call", {"name": "hm_think", "arguments": {"query": "test sample"}}, req_id=5)
        if resp:
            text = resp.get("result", {}).get("content", [{}])[0].get("text", "")
            if "found" in text:
                print(f"  OK  hm_think")
                passed += 1
            else:
                print(f"  FAIL hm_think: {text[:100]}")
                failed += 1
        else:
            print(f"  FAIL hm_think: no response")
            failed += 1

        # 6. hm_inspect
        resp = send_request(proc, "tools/call", {"name": "hm_inspect", "arguments": {"node": "test-node.md"}}, req_id=6)
        if resp:
            text = resp.get("result", {}).get("content", [{}])[0].get("text", "")
            if "Test Node" in text:
                print(f"  OK  hm_inspect")
                passed += 1
            else:
                print(f"  FAIL hm_inspect: {text[:100]}")
                failed += 1
        else:
            print(f"  FAIL hm_inspect: no response")
            failed += 1

        # 7. hm_imprint
        imprint_content = """---
type: episodic_memory
timestamp: 2026-06-15T11:00:00+08:00
node_type: 1
prenode: null
intensity: 6
total_mentions: 1
tags: [mcp-test]
---

# MCP Imprint Test

Created by MCP server test.
"""
        resp = send_request(proc, "tools/call", {
            "name": "hm_imprint",
            "arguments": {"content": imprint_content, "filename": "mcp-imprint-test.md"}
        }, req_id=7)
        if resp:
            text = resp.get("result", {}).get("content", [{}])[0].get("text", "")
            if "success" in text:
                print(f"  OK  hm_imprint")
                passed += 1
            else:
                print(f"  FAIL hm_imprint: {text[:200]}")
                failed += 1
        else:
            print(f"  FAIL hm_imprint: no response")
            failed += 1

        # 8. Verify imprint created the file
        node_path = os.path.join(POOL, "mcp-imprint-test.md")
        if os.path.exists(node_path):
            print(f"  OK  hm_imprint file created")
            passed += 1
        else:
            print(f"  FAIL hm_imprint: file not created")
            failed += 1

    finally:
        proc.terminate()
        proc.wait()

    # Cleanup
    import shutil
    shutil.rmtree(POOL, ignore_errors=True)

    print(f"\n{passed} passed, {failed} failed")
    return failed == 0


if __name__ == "__main__":
    success = test_mcp_protocol()
    sys.exit(0 if success else 1)
