import { readFile } from "node:fs/promises"
import path from "node:path"
import { ImageResponse } from "next/og"
import { getArticulo, getArticulos } from "@/lib/blog"

// Imagen al compartir cada artículo (WhatsApp, LinkedIn, X…). 1200×630, generada al compilar.
export const alt = "Artículo del blog de Gobernia"
export const size = { width: 1200, height: 630 }
export const contentType = "image/png"

export function generateStaticParams() {
  return getArticulos().map(a => ({ slug: a.slug }))
}

export default async function Image({ params }: { params: Promise<{ slug: string }> }) {
  const a = getArticulo((await params).slug)
  const titulo = a?.titulo ?? "Blog de Gobernia"
  const foto = a
    ? `data:image/jpeg;base64,${await readFile(path.join(process.cwd(), "public", a.autor.foto), "base64")}`
    : null

  return new ImageResponse(
    (
      <div
        style={{
          width: "100%", height: "100%", display: "flex", flexDirection: "column",
          justifyContent: "space-between", padding: "64px 80px",
          background: "linear-gradient(150deg, #152742 0%, #0E1626 75%)", color: "#FFFFFF",
        }}
      >
        <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center" }}>
          <div style={{ display: "flex", fontSize: 26, letterSpacing: 7, fontWeight: 700, color: "#C2410C" }}>GOBERNIA · BLOG</div>
          {a && <div style={{ display: "flex", fontSize: 24, color: "rgba(255,255,255,0.7)" }}>{a.categoria}</div>}
        </div>
        <div style={{ display: "flex", fontSize: titulo.length > 70 ? 56 : 66, fontWeight: 700, lineHeight: 1.1, maxWidth: 1040 }}>
          {titulo}
        </div>
        <div style={{ display: "flex", alignItems: "center", justifyContent: "space-between" }}>
          {a && (
            <div style={{ display: "flex", alignItems: "center" }}>
              {foto && <img src={foto} width={72} height={72} style={{ borderRadius: 36, marginRight: 20 }} alt="" />}
              <div style={{ display: "flex", flexDirection: "column" }}>
                <span style={{ fontSize: 28, fontWeight: 700 }}>{a.autor.nombre}</span>
                <span style={{ fontSize: 22, color: "rgba(255,255,255,0.65)" }}>{a.autor.cargo}</span>
              </div>
            </div>
          )}
          <span style={{ fontSize: 24, color: "rgba(255,255,255,0.6)" }}>gobernia.ai/blog</span>
        </div>
      </div>
    ),
    size,
  )
}
