# Oasis React frontend

Requires Node 22.12+.

```powershell
cd frontend
npm install
npm run dev
```

Build with `npm run build`. This is a frontend preview; it does not connect to trading providers or control the Python bot.

SoftAurora.jsx and SoftAurora.css are the unmodified JS-CSS registry files from React Bits:
- Requested registry: https://reactbits.dev/r/SoftAurora-JS-CSS.json
- Official repository mirror used: https://github.com/DavidHDev/react-bits/blob/main/public/r/SoftAurora-JS-CSS.json

Registry dependency arrays are empty. Only React, React DOM, and the Vite frontend build tool are added. Source license is included in REACT_BITS_LICENSE.md.

App.jsx mounts the component behind the 600px hero using the requested configuration. Animation and interaction are disabled for reduced-motion preferences and the background pause button. A CSS gradient remains visible if WebGL2 is unavailable. The old HTML dashboard remains separate.
