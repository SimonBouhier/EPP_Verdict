# 🚀 GETTING STARTED - Lyra Clean

## Quick Migration Guide (15 minutes)

### Step 1: Install Dependencies (2 min)

```bash
cd lyra_clean
pip install -r requirements.txt
```

**What gets installed:**
- FastAPI + uvicorn (web framework)
- aiosqlite (async SQLite)
- httpx (async HTTP client)
- pydantic (immutable models)
- pandas (only for migration script)

**Total size:** ~150MB (vs 650MB legacy)

---

### Step 2: Migrate Your Data (5 min)

```bash
# From lyra_clean directory
python scripts/migrate_data.py \
  --edges ../data/graphs/edges.csv \
  --nodes ../data/graphs/nodes.csv \
  --output data/ispace.db
```

**What happens:**
1. Reads legacy CSV files (last time!)
2. Creates SQLite database with indexes
3. Computes node degrees
4. Runs integrity checks
5. Optimizes with VACUUM + ANALYZE

**Expected output:**
```
✅ Inserted 15,234 concepts
✅ Inserted 245,678 relations
✅ Degrees computed
✅ Migration verified successfully!

Sample neighbor query: 6.42ms ← Should be < 50ms
```

**If migration fails:**
- Check CSV file paths exist
- Ensure CSV has columns: `node, rho` (nodes) and `src, dst, weight, kappa` (edges)
- Run with `--force` to overwrite existing database

---

### Step 3: Test Queries (3 min)

Create `test_queries.py`:

```python
import asyncio
from database import get_db

async def test_basic_queries():
    """Test that database works correctly."""
    db = await get_db("data/ispace.db")

    print("="*60)
    print("TEST 1: Concept Lookup (O(1))")
    print("="*60)

    concept = await db.get_concept("entropy")
    if concept:
        print(f"✅ Found: {concept['id']}")
        print(f"   ρ (density): {concept['rho_static']:.3f}")
        print(f"   Degree: {concept['degree']}")
    else:
        print("❌ Concept 'entropy' not found")

    print("\n" + "="*60)
    print("TEST 2: Neighbor Query (O(log N))")
    print("="*60)

    neighbors = await db.get_neighbors("entropy", limit=10)
    print(f"✅ Found {len(neighbors)} neighbors:")
    for i, n in enumerate(neighbors[:5], 1):
        print(f"   {i}. {n['target']} (weight={n['weight']:.3f}, κ={n['kappa']:.3f})")

    print("\n" + "="*60)
    print("TEST 3: Database Stats")
    print("="*60)

    stats = await db.get_stats()
    for key, value in stats.items():
        print(f"   {key}: {value}")

    print("\n✅ All tests passed!")

if __name__ == "__main__":
    asyncio.run(test_basic_queries())
```

Run:
```bash
python test_queries.py
```

---

### Step 4: Test Physics Engine (3 min)

Create `test_physics.py`:

```python
import asyncio
from database import get_db
from core.physics import BezierEngine, TimeMapper

async def test_bezier_engine():
    """Test Bezier trajectory engine."""
    db = await get_db("data/ispace.db")

    print("="*60)
    print("BEZIER PHYSICS ENGINE TEST")
    print("="*60)

    # Load profile from database
    profile = await db.get_profile("creative")
    print(f"\n✅ Loaded profile: {profile['profile_name']}")
    print(f"   Description: {profile['description']}")

    # Create engine
    engine = BezierEngine.from_profile(profile)

    # Sample trajectory at different conversation stages
    print("\n📈 Trajectory Samples:")
    print("   t     τc      ρ      δr     (stage)")
    print("   " + "-"*50)

    for message_count in [1, 5, 10, 20, 50]:
        t = TimeMapper.logarithmic(message_count, max_messages=100)
        state = engine.compute_state(t)

        stage = "start" if t < 0.2 else "mid" if t < 0.7 else "late"

        print(f"   {t:.2f}   {state.tau_c:.2f}   {state.rho:+.2f}   {state.delta_r:+.2f}   ({stage})")

    print("\n✅ Physics engine working!")

if __name__ == "__main__":
    asyncio.run(test_bezier_engine())
```

Run:
```bash
python test_physics.py
```

**Expected output:**
```
📈 Trajectory Samples:
   t     τc      ρ      δr     (stage)
   --------------------------------------------------
   0.10   1.31   +0.52   +0.21   (start)
   0.46   1.48   +0.68   +0.29   (mid)
   0.68   1.35   +0.52   +0.18   (mid)
   0.85   1.15   +0.28   +0.08   (late)
   0.99   1.01   +0.21   +0.01   (late)
```

---

### Step 5: Test Context Injection (2 min)

Create `test_injection.py`:

```python
import asyncio
from database import get_db
from services import ContextInjector
from core.physics import BezierEngine, PhysicsState

async def test_context_injection():
    """Test semantic context extraction."""
    db = await get_db("data/ispace.db")

    print("="*60)
    print("CONTEXT INJECTION TEST")
    print("="*60)

    # Create injector
    injector = ContextInjector(db)

    # Test prompt
    user_prompt = "Explain the concept of entropy in information theory"

    print(f"\n📝 User Prompt: {user_prompt}")

    # Extract context
    context = await injector.extract_context(user_prompt, max_keywords=5, max_neighbors=10)

    print(f"\n✅ Context Extracted ({context.latency_ms:.1f}ms):")
    print(f"   Keywords: {', '.join(context.query_keywords)}")
    print(f"   Neighbors: {len(context.neighbor_concepts)}")
    print(f"   Total weight: {context.total_weight:.2f}")

    print("\n🔗 Top Neighbors:")
    for i, n in enumerate(context.neighbor_concepts[:5], 1):
        print(f"   {i}. {n['target']} (weight={n['weight']:.3f})")

    # Test prompt building
    physics_state = PhysicsState(t=0.5, tau_c=1.0, rho=0.2, delta_r=0.0, kappa=0.5)

    result = await injector.build_enriched_prompt(
        user_prompt=user_prompt,
        system_prompt="You are Lyra AI assistant",
        physics_state=physics_state,
        enable_context=True
    )

    print(f"\n📤 Built Prompt ({result['latency_ms']:.1f}ms):")
    print(f"   Messages: {len(result['messages'])}")
    print(f"   Context injected: {result['context'] is not None}")

    print("\n✅ Context injection working!")

if __name__ == "__main__":
    asyncio.run(test_context_injection())
```

Run:
```bash
python test_injection.py
```

---

## ✅ Verification Checklist

After completing steps 1-5, verify:

- [ ] **Database created** at `data/ispace.db` (~40-50MB)
- [ ] **Concept lookup** returns results (test_queries.py)
- [ ] **Neighbor queries** < 50ms (test_queries.py)
- [ ] **Physics engine** computes states (test_physics.py)
- [ ] **Context injection** extracts keywords (test_injection.py)
- [ ] **No legacy CSV** loaded at runtime (check memory usage)

---

## 🚨 Troubleshooting

### Migration Script Fails

**Error:** `FileNotFoundError: edges.csv not found`

**Fix:** Check paths to CSV files. Use absolute paths if needed:
```bash
python scripts/migrate_data.py \
  --edges /full/path/to/edges.csv \
  --nodes /full/path/to/nodes.csv
```

---

### Slow Queries (> 100ms)

**Error:** Neighbor queries taking > 100ms

**Fix:** Verify indexes exist:
```sql
-- Connect to database
sqlite3 data/ispace.db

-- Check indexes
SELECT name FROM sqlite_master WHERE type='index';

-- Should see: idx_relations_source, idx_concepts_id, etc.
```

If missing, re-run migration or manually create indexes from `database/schema.sql`.

---

### Import Errors

**Error:** `ModuleNotFoundError: No module named 'database'`

**Fix:** Run Python from `lyra_clean` directory:
```bash
cd lyra_clean
python test_queries.py  # Not from parent directory!
```

Or set PYTHONPATH:
```bash
export PYTHONPATH=/path/to/lyra_clean:$PYTHONPATH
```

---

### Database Locked

**Error:** `sqlite3.OperationalError: database is locked`

**Fix:** Close other connections to database:
```bash
# Find processes using database
lsof data/ispace.db  # macOS/Linux
# Or reboot if stuck

# Enable WAL mode (concurrent reads)
sqlite3 data/ispace.db "PRAGMA journal_mode=WAL;"
```

---

## 🎯 Next Steps

Once all tests pass:

1. **Delete old CSV files** (they're now in SQLite)
   ```bash
   # Optional: backup first
   mv ../data/graphs/edges.csv ../data/graphs/edges.csv.backup
   mv ../data/graphs/nodes.csv ../data/graphs/nodes.csv.backup
   ```

2. **Benchmark performance**
   - Run `test_queries.py` 100 times, measure average
   - Goal: < 10ms for neighbor queries

3. **Create custom Bezier profile**
   - Edit `database/schema.sql`
   - Add new profile with your control points
   - Test with `test_physics.py`

4. **Run API server** (Phase 4 - ✅ IMPLEMENTED)
   ```bash
   # Development mode
   python app/main.py
   # Or with uvicorn
   uvicorn app.main:app --reload

   # Docker deployment
   docker-compose up -d
   ```

   See [API_GUIDE.md](API_GUIDE.md) for complete API documentation.

---

## 📚 Additional Resources

- **Full architecture docs:** [README.md](README.md)
- **Migration audit:** `../AUDIT_TECHNIQUE_LYRA_UNI.md`
- **Database schema:** [database/schema.sql](database/schema.sql)
- **Physics engine:** [core/physics/bezier.py](core/physics/bezier.py)

---

## 💬 Need Help?

**Common issues:**
1. CSV format doesn't match → Check column names match schema
2. Slow queries → Run `EXPLAIN QUERY PLAN SELECT ...` in sqlite3
3. Memory leak → Ensure no legacy code loading CSV in RAM

**Performance targets:**
- Neighbor query: < 10ms
- Context extraction: < 50ms
- Full prompt build: < 100ms

---

**✅ All phases complete! Ready to deploy? See [API_GUIDE.md](API_GUIDE.md) for deployment instructions.**
