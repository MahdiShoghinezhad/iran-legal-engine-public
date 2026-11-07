# Local admin review panel (fictional demo only)

The review dashboard is available at **http://127.0.0.1:8000/admin** after explicitly enabling it. It is not a production-ready authentication system. It is disabled by default, has no user accounts, and should **never** be exposed via a public hostname or reverse proxy.

## Windows PowerShell (run from cloned project)

1. Pull the latest repository and install the demo:

    git pull
    python -m pip install -e ".[test]"
    python -m pytest -q

2. Start the application with a random **local-only** admin token, not a fixed shared password:

    $env:LEGAL_DB="storage/demo.sqlite3"
    $env:LEGAL_ADMIN_ENABLED="1"
    $tokenBytes = New-Object byte[] 32
    [System.Security.Cryptography.RandomNumberGenerator]::Fill($tokenBytes)
    $env:LEGAL_ADMIN_TOKEN=[Convert]::ToHexString($tokenBytes)
    $env:LEGAL_ADMIN_TOKEN
    python -m uvicorn legalcore.api:app --host 127.0.0.1 --port 8000 --reload

3. Copy the printed token into the password input at http://127.0.0.1:8000/admin, add a reviewer name, and click connect.
   The admin UI does not use cookies, browser storage, third-party JavaScript, or external scripts. Your token remains in the current page's memory only.

4. Click **بارگذاری نمونه دو ماده‌ای** or choose your own explicit FICTIONAL_DEMO_ONLY JSON. Review the pending text and its earlier approved version. Approve or reject fictional changes only.

5. Stop the local server with Ctrl+C. Start a new PowerShell session to clear the admin environment variables, or explicitly run:
    Remove-Item Env:LEGAL_ADMIN_ENABLED,Env:LEGAL_ADMIN_TOKEN -ErrorAction SilentlyContinue

## Security and scope

- Every administrative read/write API requires both LEGAL_ADMIN_ENABLED=1 and a secret of at least 32 characters.
- Browser transmits the credential in the X-Admin-Token request header (not query strings or cookies).
- Admin import is strictly limited to fictional demo documents and example.invalid source URLs.
- **Research Civil Code snapshots are not accepted.** There is no path for the panel to certify or publish the 1,335 unverified articles.
- Rejecting an update does not change approved versions. New proposed text remains private until an explicit reviewer decision.
- The compare UI displays previous approved text, proposed text and a simple unified diff.
- The prototype intentionally does not provide RBAC, reverse-proxy authentication, legal evidence verification, signed reviews, rate limiting or multi-user concurrency safety.
- Never use the demo admin on a public interface. For later VPS deployment, develop proper authentication, CSRF-safe sessions as applicable, audit access controls, and separation of duties.

## Suggested test

    python -m pytest -q

Also review the dedicated tests in tests/test_admin.py, especially forbidden publication of unverified legislation.
