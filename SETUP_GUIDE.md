# Setup Guide

## 1) Create a public GitHub repo
Create a repo named `daily-brief` and upload everything from this folder.

## 2) Create the Apps Script mailer
- Go to https://script.google.com
- Create a new project
- Paste `apps-script/Code.gs`
- Replace `EXPECTED_TOKEN`
- Deploy as a Web app
- Copy the Web app URL

## 3) Add GitHub secrets
Repository → Settings → Secrets and variables → Actions → New repository secret
- `MAILER_WEBHOOK_URL`
- `MAILER_TOKEN`
- `NTFY_TOPIC`

## 4) Enable GitHub Pages
Repository → Settings → Pages → Source = GitHub Actions

## 5) Subscribe to ntfy
- Open https://ntfy.sh/app
- Subscribe to the exact topic from `NTFY_TOPIC`
- Allow notifications
- Install the PWA if you want it to behave like an app

## 6) Run the workflow once
GitHub repo → Actions → Daily Brief → Run workflow

## 7) Open the site
Your site URL will be:
`https://YOUR-GITHUB-USERNAME.github.io/YOUR-REPO-NAME/`
