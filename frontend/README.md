# Oasis React frontend

Live: https://dzebrobuilds.github.io/oasis-bot/

Requires Node 22.12+.

```powershell
cd frontend
npm install --ignore-scripts
npm run dev
```

Build with `npm run build`. Dashboard.jsx reads the public paper feed produced by Python in the `oasis-data` branch. Run and pause controls link to authenticated GitHub Actions. No tokens are stored in the browser. See ../docs/CONNECTED_DASHBOARD.md.

SoftAurora.jsx and SoftAurora.css are the unmodified JS-CSS registry files from React Bits: https://reactbits.dev/r/SoftAurora-JS-CSS.json (retrieved from the official DavidHDev/react-bits repository mirror). The registry lists no additional dependencies. It is mounted behind a 600px hero using the requested settings, with pause/reduced-motion controls and a CSS fallback.

ProfileCard uses its exact registry source and both listed Hugeicons dependencies. See PROFILE_CARD.md. Upstream license: REACT_BITS_LICENSE.md.
