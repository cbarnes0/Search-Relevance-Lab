import type { NextConfig } from "next";

const nextConfig: NextConfig = {
  // Emit a self-contained production server (.next/standalone) with a minimal
  // node_modules, so the runtime Docker image stays small. See Dockerfile.prod.
  output: "standalone",
};

export default nextConfig;
