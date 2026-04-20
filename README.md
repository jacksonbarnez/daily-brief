# Daily Brief

A free daily business and technology digest built with:
- GitHub Pages for the installable web app
- GitHub Actions for the daily automation
- Google Apps Script for automatic email sending
- ntfy for free phone and desktop notifications

## Local preview (optional)

If Python is installed on your Windows PC:

```powershell
cd news-digest-pwa
py -m http.server 5500
```

Then open:

```text
http://localhost:5500/public/
```

## Main files

- `public/` - the installable web app
- `scripts/build_digest.py` - fetches RSS feeds and creates the digest
- `.github/workflows/daily-digest.yml` - runs the digest every day and deploys the site
- `apps-script/Code.gs` - the Google Apps Script email webhook
