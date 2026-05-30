# KITTAYYYYYYY Web Hub (GitHub Pages)

This folder is a static site intended for GitHub Pages.

## What it includes

- Wiki sections:
  - Commands
  - Cats
  - Features
- Inventory Viewer section:
  - Opens from the bot's signed "Use Web UI" inventory button
  - Auto-loads the matching guild/user inventory from the URL token
  - Lets you search cats, rename them, play with them, toggle favorites, and use supported items
  - Does not allow self-grants or direct inventory editing

## Publish on GitHub Pages

1. Push this repo to GitHub.
2. In repository settings, open Pages.
3. Set source to "Deploy from a branch".
4. Choose your branch and folder "docs".
5. Save.

## Required bot env vars

- INVENTORY_WEB_TOKEN_SECRET=<strong secret>
- INVENTORY_WEB_UI_URL=https://<your-username>.github.io or your custom Pages URL
- INVENTORY_API_BASE_URL=https://<your-bot-public-url>
- WEB_UI_ORIGIN=https://<your-username>.github.io (or your custom domain)
- TOPGG_WEBHOOK_SECRET or WEBHOOK_VERIFY (if vote webhook is enabled)
- VOTE_WEBHOOK_PORT (optional, defaults to 3001)

## Security notes

- Do not hardcode the inventory token secret in this frontend.
- The website should only be opened from the bot's signed link.
- Rotate INVENTORY_WEB_TOKEN_SECRET if it is ever exposed.
