# Security Setup Checklist

Use this checklist to harden the GitHub repository settings without changing
runtime behavior.

## GitHub Settings

1. **Branch protection (main)**
   - Require pull request reviews (at least 1).
   - Require status checks to pass before merging:
     - `CI` (from `.github/workflows/ci.yml`)
   - Require linear history (optional).

2. **Secret scanning**
   - Enable GitHub Secret Scanning for the repository.
   - Enable push protection for secrets (recommended).

3. **Code scanning**
   - Enable CodeQL code scanning on default branch.
   - Add scheduled runs (weekly is enough for this repo).

4. **Secret scanning**
   - Gitleaks workflow runs on push/PR (`.github/workflows/gitleaks.yml`).
   - Keep GitHub Secret Scanning enabled for server-side checks.

5. **Issue labels**
   - Run the `Sync Labels` workflow to apply `.github/labels.yml`.

6. **Dependabot**
   - `.github/dependabot.yml` is already configured for pip updates.

## Runtime Safety Notes

- Keep `LIBRARY_PORTAL_API_KEY` configured in production environments.
- Avoid adding new public endpoints to `PUBLIC_PATHS` in `APIKeyMiddleware`.
