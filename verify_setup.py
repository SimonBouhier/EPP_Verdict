#!/usr/bin/env python3
"""
LYRA CLEAN - SETUP VERIFICATION SCRIPT
======================================

Quick verification that all components are working correctly.

Usage:
    python verify_setup.py
"""
import sys
import asyncio
from pathlib import Path


def print_header(text: str):
    """Print formatted section header."""
    print("\n" + "="*70)
    print(f" {text}")
    print("="*70)


def print_success(text: str):
    """Print success message."""
    print(f"✅ {text}")


def print_error(text: str):
    """Print error message."""
    print(f"❌ {text}")


def print_warning(text: str):
    """Print warning message."""
    print(f"⚠️  {text}")


def print_info(text: str):
    """Print info message."""
    print(f"ℹ️  {text}")


async def verify_imports():
    """Verify all required imports work."""
    print_header("STEP 1: Verifying Dependencies")

    required_packages = [
        ("fastapi", "FastAPI web framework"),
        ("uvicorn", "ASGI server"),
        ("pydantic", "Data validation"),
        ("aiosqlite", "Async SQLite"),
        ("httpx", "Async HTTP client"),
        ("yaml", "YAML config parser"),
    ]

    all_ok = True
    for package, description in required_packages:
        try:
            __import__(package)
            print_success(f"{package:15s} - {description}")
        except ImportError:
            print_error(f"{package:15s} - NOT FOUND")
            all_ok = False

    if not all_ok:
        print_error("\nMissing dependencies! Run: pip install -r requirements.txt")
        return False

    return True


async def verify_file_structure():
    """Verify all required files exist."""
    print_header("STEP 2: Verifying File Structure")

    required_files = [
        "database/schema.sql",
        "database/engine.py",
        "core/physics/bezier.py",
        "services/injector.py",
        "app/main.py",
        "app/models.py",
        "app/llm_client.py",
        "app/api/chat.py",
        "app/api/sessions.py",
        "scripts/migrate_data.py",
        "config.yaml",
        "requirements.txt",
        "Dockerfile",
        "docker-compose.yml",
        "README.md",
        "API_GUIDE.md",
    ]

    all_ok = True
    for file_path in required_files:
        path = Path(file_path)
        if path.exists():
            size_kb = path.stat().st_size / 1024
            print_success(f"{file_path:30s} ({size_kb:.1f} KB)")
        else:
            print_error(f"{file_path:30s} MISSING")
            all_ok = False

    # Check directories
    required_dirs = ["data", "logs"]
    for dir_path in required_dirs:
        path = Path(dir_path)
        if path.exists() and path.is_dir():
            print_success(f"{dir_path}/ directory exists")
        else:
            print_warning(f"{dir_path}/ directory missing (will be created)")

    return all_ok


async def verify_database():
    """Verify database exists and has correct schema."""
    print_header("STEP 3: Verifying Database")

    db_path = Path("data/ispace.db")

    if not db_path.exists():
        print_warning("Database not found at data/ispace.db")
        print_info("Run migration script first:")
        print_info("  python scripts/migrate_data.py --edges <edges.csv> --nodes <nodes.csv>")
        return False

    try:
        import aiosqlite
        async with aiosqlite.connect(str(db_path)) as conn:
            # Check tables
            cursor = await conn.execute(
                "SELECT name FROM sqlite_master WHERE type='table' ORDER BY name"
            )
            tables = [row[0] for row in await cursor.fetchall()]

            required_tables = ["concepts", "relations", "sessions", "events", "trajectories", "profiles"]
            missing_tables = set(required_tables) - set(tables)

            if missing_tables:
                print_error(f"Missing tables: {', '.join(missing_tables)}")
                return False

            print_success(f"Found all required tables: {', '.join(tables)}")

            # Check row counts
            for table in required_tables:
                cursor = await conn.execute(f"SELECT COUNT(*) FROM {table}")
                count = (await cursor.fetchone())[0]
                print_info(f"  {table:15s}: {count:6d} rows")

            # Check indexes
            cursor = await conn.execute(
                "SELECT name FROM sqlite_master WHERE type='index' AND name LIKE 'idx_%'"
            )
            indexes = [row[0] for row in await cursor.fetchall()]
            if indexes:
                print_success(f"Indexes: {', '.join(indexes)}")
            else:
                print_warning("No custom indexes found (query performance may be slow)")

            return True

    except Exception as e:
        print_error(f"Database error: {e}")
        return False


async def verify_python_imports():
    """Verify Python modules can be imported."""
    print_header("STEP 4: Verifying Python Modules")

    modules_to_test = [
        ("database", "Database engine"),
        ("core.physics.bezier", "Bezier physics engine"),
        ("services.injector", "Context injection service"),
        ("app.models", "API models"),
        ("app.llm_client", "LLM client"),
    ]

    all_ok = True
    for module_name, description in modules_to_test:
        try:
            __import__(module_name)
            print_success(f"{module_name:30s} - {description}")
        except Exception as e:
            print_error(f"{module_name:30s} - FAILED: {e}")
            all_ok = False

    return all_ok


async def verify_config():
    """Verify configuration file."""
    print_header("STEP 5: Verifying Configuration")

    config_path = Path("config.yaml")

    if not config_path.exists():
        print_error("config.yaml not found")
        return False

    try:
        import yaml
        with open(config_path) as f:
            config = yaml.safe_load(f)

        required_sections = ["server", "database", "llm", "physics", "context"]
        missing_sections = [s for s in required_sections if s not in config]

        if missing_sections:
            print_error(f"Missing config sections: {', '.join(missing_sections)}")
            return False

        print_success("All config sections present")

        # Show key settings
        print_info(f"  Server: {config['server']['host']}:{config['server']['port']}")
        print_info(f"  Database: {config['database']['path']}")
        print_info(f"  LLM: {config['llm']['model']} @ {config['llm']['base_url']}")
        print_info(f"  Default profile: {config['physics']['default_profile']}")

        return True

    except Exception as e:
        print_error(f"Config error: {e}")
        return False


async def main():
    """Run all verification checks."""
    print("\n")
    print("╔" + "="*68 + "╗")
    print("║" + " "*20 + "LYRA CLEAN - SETUP VERIFICATION" + " "*17 + "║")
    print("╚" + "="*68 + "╝")

    results = []

    # Run all checks
    results.append(("Dependencies", await verify_imports()))
    results.append(("File Structure", await verify_file_structure()))
    results.append(("Database", await verify_database()))
    results.append(("Python Modules", await verify_python_imports()))
    results.append(("Configuration", await verify_config()))

    # Summary
    print_header("VERIFICATION SUMMARY")

    all_passed = all(result for _, result in results)

    for check_name, passed in results:
        status = "✅ PASS" if passed else "❌ FAIL"
        print(f"  {check_name:20s} {status}")

    print("\n" + "-"*70)

    if all_passed:
        print_success("All checks passed! ✨")
        print("\nNext steps:")
        print("  1. Ensure database is migrated: python scripts/migrate_data.py")
        print("  2. Start server: python app/main.py")
        print("  3. Check health: curl http://localhost:8000/health")
        print("  4. Read API docs: http://localhost:8000/docs")
        print("\nDocumentation:")
        print("  • Quick Start:  GETTING_STARTED.md")
        print("  • API Guide:    API_GUIDE.md")
        print("  • Architecture: README.md")
        return 0
    else:
        print_error("Some checks failed!")
        print("\nTroubleshooting:")
        print("  • Missing dependencies: pip install -r requirements.txt")
        print("  • Missing database: python scripts/migrate_data.py --help")
        print("  • Import errors: Ensure you're running from lyra_clean/ directory")
        print("\nSee GETTING_STARTED.md for detailed setup instructions.")
        return 1


if __name__ == "__main__":
    try:
        exit_code = asyncio.run(main())
        sys.exit(exit_code)
    except KeyboardInterrupt:
        print("\n\nVerification interrupted.")
        sys.exit(1)
    except Exception as e:
        print_error(f"Unexpected error: {e}")
        sys.exit(1)
