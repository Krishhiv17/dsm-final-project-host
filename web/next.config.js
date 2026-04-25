/** @type {import('next').NextConfig} */
const nextConfig = {
  // deck.gl / luma.gl maintain a process-global registry that re-registers
  // on every mount. Strict-mode's intentional double-mount in dev triggers
  // "luma.gl: This version of luma.gl has already been initialized" and
  // breaks the WebGL pipeline. Disable strict mode to keep the map healthy.
  reactStrictMode: false,
  transpilePackages: ["plotly.js", "react-plotly.js"],
  webpack: (config) => {
    config.externals.push({
      "node:fs":   "fs",
      "node:path": "path",
    });
    return config;
  },
};
module.exports = nextConfig;
