import type { NextConfig } from "next";

// Cabeceras de seguridad para todo el sitio. (Una Content-Security-Policy queda pendiente:
// requiere listar con cuidado Supabase, el API y las fuentes para no romper la app.)
const SECURITY_HEADERS = [
  { key: "X-Content-Type-Options", value: "nosniff" },
  { key: "Referrer-Policy", value: "strict-origin-when-cross-origin" },
  { key: "X-Frame-Options", value: "SAMEORIGIN" },
  { key: "Permissions-Policy", value: "camera=(), microphone=(), geolocation=(), payment=()" },
];

const nextConfig: NextConfig = {
  // Landings anteriores (eliminadas): sus enlaces viejos llevan a la página principal.
  async redirects() {
    return [
      { source: "/v2", destination: "/", permanent: true },
      { source: "/landing-2", destination: "/", permanent: true },
    ];
  },
  async headers() {
    return [{ source: "/:path*", headers: SECURITY_HEADERS }];
  },
};

export default nextConfig;
