# StudySmart deployment

## GitHub

The repository is prepared to keep secrets, the local database, virtual environments and build output out of source control. The trained OULAD Random Forest model is intentionally included because prediction must work after deployment.

After signing in to GitHub, create an empty repository named `smart-study-planner`. From the project folder, connect and push the local repository:

```powershell
git remote add origin https://github.com/YOUR-USERNAME/smart-study-planner.git
git push -u origin main
```

Choose **Private** if the university code should only be shared with invited lecturers, or **Public** if a public demonstration repository is required.

## Vercel

1. Provision a persistent MySQL database and copy its connection URL. The hosted application must not use the local SQLite development database.
2. In Vercel, import the GitHub repository and keep the framework preset as **Other**. The included `app.py`, `requirements.txt`, `.python-version` and `vercel.json` configure the Flask application.
3. Add these environment variables to Production and Preview:
   - `DATABASE_URL`: `mysql+pymysql://USER:PASSWORD@HOST:3306/DATABASE`
   - `SECRET_KEY`: a long random value
   - `JWT_SECRET_KEY`: a different long random value
   - `CORS_ORIGINS`: the final `https://...vercel.app` address
   - `SESSION_HOURS`: `8`
4. Deploy. On first connection, StudySmart creates missing tables without deleting existing records.
5. Check `https://YOUR-DOMAIN/api/v1/health`, then register a fresh account through the web interface.

The web application and API are deployed together, so no frontend API address needs changing. The Flutter release uses the same HTTPS API address with `--dart-define=API_URL=https://YOUR-DOMAIN/api/v1`.

## Mobile web installation

The web client includes a StudySmart favicon and installable-app manifest. On Android Chrome, open the hosted site and choose **Install app** or **Add to Home screen**. This provides immediate phone access while the native Flutter package is being built.
