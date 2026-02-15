#!/bin/bash
echo "=== CWD ==="
pwd

echo ""
echo "=== 2. SINGLETONS (C2) ==="
grep -rn "global _" --include="*.py" database/ services/ app/ | grep -v __pycache__ | grep -v test_

echo ""
echo "=== 3. EXCEPT SILENCIEUX (C3) ==="
grep -rn "except" --include="*.py" -A2 database/ services/ app/ cli/ | grep -B1 "pass$" | grep -v "logger\." | grep -v "logging\." | grep -v "raise" | grep -v "AUDIT" | grep -v "# OK:" | grep -v __pycache__ | grep -v test_

echo ""
echo "=== 4. ASSERTIONS FAIBLES (C6) ==="
grep -rn "assert.*is not None$" --include="*.py" tests/
grep -rn "assert True$" --include="*.py" tests/
grep -rn "assert.*is True$" --include="*.py" tests/

echo ""
echo "=== FIN ==="