#!/usr/bin/env bash
# ==============================================================================
# Script: configure_branch_protection.sh
# Purpose: Configure GitHub branch protection on 'main' and 'dev' branches
#          for repository 'SAGBO4/chatbot'.
#
# Requirements:
#   - GitHub CLI (gh) installed
#   - Authenticated with appropriate permissions (admin/write on repo)
#     via `gh auth login` or GH_TOKEN / GITHUB_TOKEN environment variable.
# ==============================================================================

set -euo pipefail

REPO="SAGBO4/chatbot"
BRANCHES=("main" "dev")
METHOD="classic"
REQUIRE_CODE_OWNER=true
DRY_RUN=false

usage() {
    cat << EOF
Usage: $0 [options]

Options:
  --method [classic|ruleset]  Protection mechanism (default: classic)
  --codeowners [true|false]   Require CODEOWNERS approval (SAGBO4) (default: true)
  --dry-run                   Print payloads and commands without executing API calls
  --help                      Show this help message
EOF
    exit 0
}

while [[ $# -gt 0 ]]; do
    case "$1" in
        --method)
            METHOD="$2"
            shift 2
            ;;
        --codeowners)
            REQUIRE_CODE_OWNER="$2"
            shift 2
            ;;
        --dry-run)
            DRY_RUN=true
            shift
            ;;
        classic|ruleset)
            METHOD="$1"
            shift
            ;;
        --help|-h)
            usage
            ;;
        *)
            echo "Unknown option: $1"
            usage
            ;;
    esac
done

echo "===================================================="
echo " Branch Protection Setup for ${REPO}"
echo " Mode: ${METHOD} | Require SAGBO4 CODEOWNER: ${REQUIRE_CODE_OWNER}"
echo "===================================================="

# 1. Verify GitHub CLI is installed
if ! command -v gh >/dev/null 2>&1; then
    echo "[-] Error: 'gh' CLI tool is not installed."
    echo "    Please install gh: https://cli.github.com/"
    exit 1
fi

# 2. Check GitHub CLI authentication status
echo "[*] Checking GitHub CLI authentication status..."
if ! gh auth status >/dev/null 2>&1; then
    echo "[-] Error: 'gh' is not authenticated."
    echo ""
    echo "    To authenticate, choose one of the following methods:"
    echo "    1) Interactive web / token login:"
    echo "       gh auth login -h github.com -s repo,admin:repo_hook"
    echo ""
    echo "    2) Using a Personal Access Token (classic or fine-grained):"
    echo "       export GH_TOKEN=\"<your_github_personal_access_token>\""
    echo "       Required token scopes: 'repo' (Full control of private repositories)"
    echo "       or fine-grained PAT with: Repository -> Administration (Read & Write)"
    echo ""
    if [ "$DRY_RUN" = false ]; then
        exit 2
    fi
else
    echo "[+] Authenticated user: $(gh api user -q .login 2>/dev/null || echo 'Authenticated')"
fi

# 3. Configure Branch Protection
if [ "$METHOD" == "classic" ]; then
    echo "[*] Configuring Classic Branch Protection rules..."
    for branch in "${BRANCHES[@]}"; do
        echo "  --> Target branch '${branch}'..."

        PAYLOAD=$(cat << EOF
{
  "required_status_checks": null,
  "enforce_admins": true,
  "required_pull_request_reviews": {
    "dismiss_stale_reviews": true,
    "require_code_owner_reviews": ${REQUIRE_CODE_OWNER},
    "required_approving_review_count": 1,
    "require_last_push_approval": true
  },
  "restrictions": null,
  "required_linear_history": false,
  "allow_force_pushes": false,
  "allow_deletions": false,
  "block_creations": false,
  "required_conversation_resolution": true,
  "lock_branch": false,
  "allow_fork_syncing": true
}
EOF
)

        if [ "$DRY_RUN" = true ]; then
            echo "[DRY-RUN] Command: gh api --method PUT /repos/${REPO}/branches/${branch}/protection --input - <<< '...'"
            echo "[DRY-RUN] Payload:"
            echo "$PAYLOAD" | jq .
        else
            echo "$PAYLOAD" | gh api \
                --method PUT \
                -H "Accept: application/vnd.github+json" \
                -H "X-GitHub-Api-Version: 2022-11-28" \
                "/repos/${REPO}/branches/${branch}/protection" \
                --input - >/dev/null
            echo "[+] Protection applied successfully to branch '${branch}'."
        fi
    done

elif [ "$METHOD" == "ruleset" ]; then
    echo "[*] Configuring Repository Ruleset for 'main' and 'dev'..."

    RULESET_PAYLOAD=$(cat << EOF
{
  "name": "Protect main and dev branches",
  "target": "branch",
  "enforcement": "active",
  "conditions": {
    "ref_name": {
      "include": [
        "refs/heads/main",
        "refs/heads/dev"
      ],
      "exclude": []
    }
  },
  "rules": [
    {
      "type": "pull_request",
      "parameters": {
        "required_approving_review_count": 1,
        "dismiss_stale_reviews_on_push": true,
        "require_code_owner_review": ${REQUIRE_CODE_OWNER},
        "require_last_push_approval": true,
        "required_review_thread_resolution": true
      }
    },
    {
      "type": "non_fast_forward"
    },
    {
      "type": "deletion"
    }
  ],
  "bypass_actors": []
}
EOF
)

    if [ "$DRY_RUN" = true ]; then
        echo "[DRY-RUN] Command: gh api --method POST /repos/${REPO}/rulesets --input - <<< '...'"
        echo "[DRY-RUN] Payload:"
        echo "$RULESET_PAYLOAD" | jq .
    else
        echo "$RULESET_PAYLOAD" | gh api \
            --method POST \
            -H "Accept: application/vnd.github+json" \
            -H "X-GitHub-Api-Version: 2022-11-28" \
            "/repos/${REPO}/rulesets" \
            --input - >/dev/null
        echo "[+] Repository Ruleset applied successfully."
    fi
fi

echo ""
echo "===================================================="
if [ "$DRY_RUN" = false ]; then
    echo "[+] Verification:"
    for branch in "${BRANCHES[@]}"; do
        echo "--- Branch Protection Details for ${branch} ---"
        gh api "/repos/${REPO}/branches/${branch}/protection" --jq '{
            enforce_admins: .enforce_admins.enabled,
            required_approving_reviews: .required_pull_request_reviews.required_approving_review_count,
            dismiss_stale_reviews: .required_pull_request_reviews.dismiss_stale_reviews,
            require_code_owner_reviews: .required_pull_request_reviews.require_code_owner_reviews,
            allow_force_pushes: .allow_force_pushes.enabled,
            allow_deletions: .allow_deletions.enabled,
            conversation_resolution: .required_conversation_resolution.enabled
        }' 2>/dev/null || echo "Branch protection query failed or Ruleset used."
    done
    echo "===================================================="
    echo "[✓] Branch protection configuration completed."
else
    echo "[✓] Dry-run completed successfully. All payloads validated."
fi
