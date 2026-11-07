# Publish the portfolio demo as a new PUBLIC GitHub repository

1. Sign in as `MahdiShoghinezhad` and open https://github.com/new.
2. Repository name: `iran-legal-engine-public`. Visibility: **Public**.
3. Leave GitHub's "Add README", ".gitignore", and "Choose a license" options unchecked — these files are already in the download.
4. Unzip `iran-legal-engine-public.zip`. In PowerShell, open the unzipped project folder.
5. Run:

```powershell
git init -b main
git add .
git commit -m "Initial legal versioning portfolio demo"
git remote add origin https://github.com/MahdiShoghinezhad/iran-legal-engine-public.git
git push -u origin main
```

If your GitHub authentication prompts, authenticate using a supported credential manager or GitHub CLI. Do not paste or commit access tokens. Open the repository's **Actions** tab to inspect CI results. Add a screenshot only after a real UI exists. GitHub Pages is optional and not configured in this backend-only starter.

For the **commercial/private** workspace, create a separate repository named `iran-legal-platform-private` and select **Private** before adding any files. Never switch that repository to public without a full data/security audit.
