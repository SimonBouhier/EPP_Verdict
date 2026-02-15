Set-Content -Path "find_orphans.sh" -Value @'
#!/bin/bash
echo "=== FICHIERS PYTHON JAMAIS IMPORTES ==="
for f in $(find . -name "*.py" -not -path "./.venv/*" -not -path "*__pycache__*" -not -path "*__init__*" -not -path "*/tests/*" -not -path "*/demos/*" | sort); do
    module=$(echo "$f" | sed 's|^\./||' | sed 's|\.py$||' | sed 's|/|.|g')
    base=$(basename "$f" .py)
    count=$(grep -rl "$base" --include="*.py" . | grep -v __pycache__ | grep -v .venv | grep -v "$f" | wc -l)
    if [ "$count" -eq 0 ]; then
        echo "ORPHELIN: $f"
    fi
done
'@ -Encoding ASCII