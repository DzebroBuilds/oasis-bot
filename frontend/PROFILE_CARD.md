# ProfileCard integration

The unmodified ProfileCard.jsx and ProfileCard.css come from the React Bits JS-CSS registry:
https://reactbits.dev/r/ProfileCard-JS-CSS.json
Official mirror: https://github.com/DavidHDev/react-bits/blob/main/public/r/ProfileCard-JS-CSS.json

Dependencies added exactly as listed:
- @hugeicons/react@^1.1.10
- @hugeicons/core-free-icons@^4.3.3

The upstream license is in REACT_BITS_LICENSE.md.

App.jsx mounts the requested sample configuration in a labeled profile preview below the workspace. Supplied portrait and pattern paths were placeholders; local SVG artwork is imported through Vite so asset paths also work in subdirectory builds. Replace src/assets/profile-placeholder.svg with the desired portrait and update its import. The name, handle, role and Online status are sample text, not verified account data. The contact callback logs the requested message and shows an accessible preview notice; it does not send anything.

Run npm install and npm run dev from frontend/. CI installs the two dependencies and runs the production build.
