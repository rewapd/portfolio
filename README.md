# Rewa Prasad — Portfolio

React portfolio built with Vite, Tailwind CSS, Framer Motion, and React Three Fiber. The profile is served as a static JSON file so the site can run on GitHub Pages without a Node server. The Express API remains available for local development.

## Run locally

```sh
npm install
npm --prefix client install
npm run dev
```

Open `http://localhost:4173`.

## Deploy to GitHub Pages

1. Push this project to a GitHub repository on the `main` branch.
2. In the repository, open **Settings → Pages** and select **GitHub Actions** as the build and deployment source.
3. The workflow in `.github/workflows/deploy.yml` builds the Vite app and publishes `client/dist`. It runs on pushes to `main` and can also be started from the **Actions** tab.
4. Find the published URL in the completed **Deploy portfolio to GitHub Pages** workflow run.

The Vite config automatically uses the repository subpath for project sites and the root path for `*.github.io` user sites.

## Update portfolio content

The portfolio polls the private Google Doc hourly. When the document changes, it updates the downloadable PDF and rebuilds the project cards from its `PROJECTS` section. Existing portfolio links and descriptions are retained for matching project names.

To enable the private sync, create a Google service account with the Docs API and Drive API enabled, share the document with its service-account email as a Viewer, then add the full service-account JSON key as the `GOOGLE_SERVICE_ACCOUNT_JSON` Actions secret. Add the document ID as the `GOOGLE_DOC_ID` Actions variable. Never commit or share the service-account key. The `Sync portfolio from Google Doc` workflow can also be run manually from GitHub Actions.

Other profile details are in `client/public/profile.json`; automatic extraction currently updates project cards and the downloadable resume PDF.
