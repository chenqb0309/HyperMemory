"""Minimal debug test for update_index_entry"""
import sys
sys.path.insert(0, "src")

from hypermemory.core.index import update_index_entry

SAMPLE = '《cluster: [deadlock, concurrency, transaction, lock]》 → [[2026-06-10-deadlock.md]]\n《cluster: [door-lock, key, stuck]》 → [[2026-06-09-door-lock.md]]'

result = update_index_entry(SAMPLE, "2026-06-10-deadlock.md", "2026-06-11-new-deadlock.md", new_keywords=["sql"])

print(f"Input:  {SAMPLE}")
print(f"Output: {result}")
print(f"Old in result: {'2026-06-10-deadlock.md' in result}")
print(f"New in result: {'2026-06-11-new-deadlock.md' in result}")
print(f"SQL in result: {'sql' in result}")
print(f"Changed: {result != SAMPLE}")
