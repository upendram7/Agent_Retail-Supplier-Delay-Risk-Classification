/** @type {import('next').NextConfig} */
const nextConfig = {
  reactStrictMode: true,
  async rewrites() {
    const configuredBackend =
      process.env.BACKEND_API_URL ||
      (process.env.NODE_ENV === 'development' ? 'http://localhost:8000' : undefined);

    if (!configuredBackend) {
      return [];
    }

    let backend;
    try {
      backend = new URL(configuredBackend);
    } catch {
      throw new Error('BACKEND_API_URL must be a valid HTTP or HTTPS origin.');
    }

    if (!['http:', 'https:'].includes(backend.protocol) || backend.pathname !== '/' || backend.search || backend.hash) {
      throw new Error('BACKEND_API_URL must be an HTTP or HTTPS origin without a path, query, or fragment.');
    }

    return [
      {
        source: '/api/:path*',
        destination: `${backend.origin}/api/:path*`,
      },
    ];
  },
};

export default nextConfig;
