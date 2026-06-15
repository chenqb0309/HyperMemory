"""Run all tests"""
import sys, os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "src"))
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "tests"))

import test_weight
import test_index
import test_node
import test_cluster

modules = [
    ("test_weight", test_weight),
    ("test_index", test_index),
    ("test_node", test_node),
    ("test_cluster", test_cluster),
]

passed = 0
failed = 0
for name, mod in modules:
    tests = [f for f in dir(mod) if f.startswith("test_")]
    for t in tests:
        try:
            getattr(mod, t)()
            print(f"  OK  {name}.{t}")
            passed += 1
        except AssertionError as e:
            print(f"  FAIL {name}.{t}: {e}")
            failed += 1
        except Exception as e:
            print(f"  ERROR {name}.{t}: {e}")
            failed += 1

print(f"\n{passed} passed, {failed} failed")
sys.exit(0 if failed == 0 else 1)
