# KITTAYYYYYYY Web Hub (GitHub Pages)

This folder is a static site intended for GitHub Pages.

## What it includes

- Wiki section:
  - Command list from docs/data/commands.json
  - Cat type rarity list
- Inventory Manager section:
  - Loads inventory via GET /api/inventory
  - Updates kibble, packs, and items via POST /api/inventory

## Publish on GitHub Pages

1. Push this repo to GitHub.
2. In repository settings, open Pages.
3. Set source to "Deploy from a branch".
4. Choose your branch and folder "docs".
5. Save.

## Required bot env vars

- INVENTORY_API_KEY=<strong secret>
- WEB_UI_ORIGIN=https://<your-username>.github.io (or your custom domain)
- TOPGG_WEBHOOK_SECRET or WEBHOOK_VERIFY (if vote webhook is enabled)
- VOTE_WEBHOOK_PORT (optional, defaults to 3001)

## Security notes

- Do not hardcode INVENTORY_API_KEY in this frontend.
- Enter the key manually in the UI when you need to manage inventory.
- Rotate the API key if it is ever exposed.
