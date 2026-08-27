import type { NextConfig } from "next";

const nextConfig: NextConfig = {
  // CloudBase static hosting uses the exported `out` directory. The default
  // remains Docker-friendly so the macmini deployment is unaffected.
  output: process.env.CLOUDBASE_STATIC_EXPORT === "true" ? "export" : "standalone",
};

export default nextConfig;
