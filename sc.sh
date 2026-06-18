#!/bin/bash

echo "🚀 Converting project to PURE JWT mode..."

# 1️⃣ Remove all request.session usage
grep -rl 'request.session.get("user")' modules | while read file; do
    echo "Fixing session usage in $file"

    # Replace session access with current_user dependency
    sed -i 's/u = request.session.get("user")/current_user = current_user/g' "$file"
    sed -i 's/user = request.session.get("user")/current_user = current_user/g' "$file"
    sed -i 's/if not request.session.get("user"):/if not current_user:/g' "$file"
done

# 2️⃣ Remove _get_user helper functions completely
grep -rl 'def _get_user' modules | while read file; do
    echo "Removing _get_user() from $file"
    sed -i '/def _get_user/,/^$/d' "$file"
done

# 3️⃣ Add require_login import if missing
grep -rl 'Depends(require_login)' modules | while read file; do
    if ! grep -q 'from modules.auth_dependency import require_login' "$file"; then
        echo "Adding require_login import to $file"
        sed -i '1i from modules.auth_dependency import require_login' "$file"
    fi
done

# 4️⃣ Remove any leftover session checks
grep -rl 'request.session' modules | while read file; do
    echo "Removing remaining session references in $file"
    sed -i '/request.session/d' "$file"
done

echo "✅ JWT conversion completed."
