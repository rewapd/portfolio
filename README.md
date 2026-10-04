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

Replace `client/public/Rewa-Prasad-Resume.pdf` with the updated resume and push it to `main`. The GitHub Pages workflow extracts the `PROJECTS` section, regenerates the portfolio project cards, and deploys the updated site automatically. Keep project entries under a `PROJECTS` heading in the PDF; numbered entries such as `#1: Project Name — https://...` are recognized as separate projects.

Existing profile details are in `client/public/profile.json`. Run `npm run sync:resume` after replacing the PDF to regenerate project cards locally; Python 3 and the packages in `requirements.txt` must be installed first.
