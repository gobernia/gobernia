import type { MetadataRoute } from "next"
import { AUTORES, categoriasConArticulos, getArticulos } from "@/lib/blog"
import { SITE_URL } from "@/lib/seo"

export default function sitemap(): MetadataRoute.Sitemap {
  const articulos = getArticulos()
  return [
    { url: `${SITE_URL}/`, changeFrequency: "weekly", priority: 1 },
    { url: `${SITE_URL}/blog`, changeFrequency: "weekly", priority: 0.8 },
    ...articulos.map(a => ({
      url: `${SITE_URL}/blog/${a.slug}`, lastModified: a.fecha,
      changeFrequency: "monthly" as const, priority: 0.7,
    })),
    ...categoriasConArticulos().map(c => ({
      url: `${SITE_URL}/blog/categoria/${c.slug}`, changeFrequency: "weekly" as const, priority: 0.5,
    })),
    ...Object.keys(AUTORES).map(slug => ({
      url: `${SITE_URL}/blog/autor/${slug}`, changeFrequency: "monthly" as const, priority: 0.5,
    })),
    { url: `${SITE_URL}/sign-up`, changeFrequency: "monthly", priority: 0.6 },
    { url: `${SITE_URL}/legal/privacidad`, changeFrequency: "yearly", priority: 0.3 },
    { url: `${SITE_URL}/legal/terminos`, changeFrequency: "yearly", priority: 0.3 },
    { url: `${SITE_URL}/legal/cookies`, changeFrequency: "yearly", priority: 0.3 },
  ]
}
