/** @type {import('next').NextConfig} */
const nextConfig = {
  reactStrictMode: true,
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
