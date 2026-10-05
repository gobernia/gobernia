import type { MetadataRoute } from "next"
import { SITE_URL } from "@/lib/seo"

// Las áreas privadas (dashboard, onboarding y enlaces por token) no se rastrean. Los
// buscadores y las IAs (GPTBot, ClaudeBot, PerplexityBot…) sí pueden leer lo público.
const PRIVADO = ["/dashboard", "/onboarding", "/auth", "/c/", "/t/", "/p/", "/v2", "/landing-2"]

export default function robots(): MetadataRoute.Robots {
  return {
    rules: [
      { userAgent: "*", allow: "/", disallow: PRIVADO },
      {
        userAgent: [
          "GPTBot", "OAI-SearchBot", "ChatGPT-User", "ClaudeBot", "Claude-SearchBot",
          "PerplexityBot", "Google-Extended", "Applebot-Extended", "Bingbot",
        ],
        allow: "/",
        disallow: PRIVADO,
      },
    ],
    sitemap: `${SITE_URL}/sitemap.xml`,
    host: SITE_URL,
  }
}
