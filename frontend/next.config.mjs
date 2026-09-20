/** @type {import('next').NextConfig} */
const nextConfig = {
  reactStrictMode: true,
  // The browser never talks to the LLM provider or holds its credentials -
  // it only ever calls our own FastAPI backend, whose base URL is public
  // (not secret) and injected at build time via NEXT_PUBLIC_API_BASE_URL.
};

export default nextConfig;
