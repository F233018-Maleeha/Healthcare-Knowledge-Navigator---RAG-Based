# Knowledge Navigator — Frontend

A React + TypeScript + Vite frontend for the Healthcare Knowledge Navigator backend. Built deliberately modular so you can change any one piece without needing to understand or touch the others.

## Running it

```bash
cd frontend
npm install
cp .env.example .env      # edit VITE_API_BASE_URL if your backend isn't on localhost:8000
npm run dev                # starts at http://localhost:5173
```

Make sure the backend is running and has `http://localhost:5173` in its `CORS_ALLOWED_ORIGINS` (it does, by default — see `backend/app/core/config.py`).

```bash
npm run build   # type-checks + produces a production build in dist/
npm run preview # serves that production build locally to sanity-check it
```

## Where everything lives, and what to edit for common changes

| I want to... | Edit this file | Why nothing else needs to change |
|---|---|---|
| **Change any color, font, or the overall look** | `src/theme/tokens.css` | Every component references these CSS variables through Tailwind (see `tailwind.config.js`) — never a hardcoded hex value in a component |
| **Change the example question chips** | `src/App.tsx` → `EXAMPLE_QUERIES` array | Just a plain string array, no other file involved |
| **Change the disclaimer banner text** | `src/App.tsx` → `DISCLAIMER_TEXT` | Same — plain string |
| **Point at a different backend URL** | `.env` → `VITE_API_BASE_URL` | The only place any URL is configured — `src/api/client.ts` reads it |
| **Add a new field to a backend response** (e.g. a new confidence sub-score) | 1. `src/api/types.ts` (add the field to the type) 2. Whichever component displays it | TypeScript will flag every place that needs updating once you add the field to the type — you can't forget a spot |
| **Change how a citation looks/behaves** | `src/components/Citation.tsx` | One small file, one job |
| **Change how the confidence badge is calculated/displayed** | `src/components/ConfidenceBadge.tsx` | Display only — the actual score comes from the backend; this file only controls presentation |
| **Add a new API call** (e.g. a history endpoint) | 1. Add the function to `src/api/client.ts` 2. Add any new types to `src/api/types.ts` 3. Call it from a hook or component | The client file is the only place that knows about `fetch`/URLs |
| **Add a whole new panel/section to the page** | New file in `src/components/`, then import + place it in `src/App.tsx` | `App.tsx` is intentionally just composition — no logic to break |

## Architecture, briefly

```
src/
  theme/tokens.css     ← ALL colors/fonts, one file (edit this to reskin)
  api/
    types.ts           ← TypeScript mirror of backend/app/models/schemas.py
    client.ts           ← the only file that calls fetch()
  hooks/
    useClinicalQuery.ts ← all state (loading/error/data/highlighted citation)
  components/           ← one small file per visual piece, purely presentational
  App.tsx               ← wires the hook to the components, no logic of its own
```

**The rule this was built around:** components never call the API directly, and never own state beyond their own props. All state lives in `useClinicalQuery`; all networking lives in `api/client.ts`. This means you can restyle or rearrange any component freely without any risk of breaking the data flow — and if the data flow ever needs to change (new endpoint, caching, retries), there's exactly one file to open.

## Keeping `api/types.ts` in sync with the backend

If you change `backend/app/models/schemas.py`, update the matching type in `frontend/src/api/types.ts` the same way. TypeScript will then show a compile error at every spot in the UI that needs a corresponding change — run `npm run build` after any backend schema change to catch these immediately rather than discovering them at runtime.
