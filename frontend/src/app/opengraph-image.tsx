import { ImageResponse } from "next/og"

// Imagen al compartir el enlace (WhatsApp, LinkedIn, X, Slack…). 1200×630.
export const alt = "Gobernia — Consejo de Administración con Inteligencia Artificial"
export const size = { width: 1200, height: 630 }
export const contentType = "image/png"

export default function Image() {
  return new ImageResponse(
    (
      <div
        style={{
          width: "100%", height: "100%", display: "flex", flexDirection: "column",
          justifyContent: "space-between", padding: "72px 80px",
          background: "linear-gradient(150deg, #152742 0%, #0E1626 75%)", color: "#FFFFFF",
        }}
      >
        <div style={{ display: "flex", fontSize: 30, letterSpacing: 8, fontWeight: 700, color: "#C2410C" }}>
          GOBERNIA
        </div>
        <div style={{ display: "flex", flexDirection: "column" }}>
          <div style={{ display: "flex", fontSize: 72, fontWeight: 700, lineHeight: 1.08, maxWidth: 980 }}>
            Tu Consejo de Administración con IA
          </div>
          <div style={{ display: "flex", marginTop: 28, fontSize: 32, color: "rgba(255,255,255,0.78)", maxWidth: 940, lineHeight: 1.35 }}>
            Cinco consejeros con IA y un Secretario analizan tu empresa, preparan cada sesión y proponen decisiones.
          </div>
        </div>
        <div style={{ display: "flex", justifyContent: "space-between", fontSize: 26, color: "rgba(255,255,255,0.6)" }}>
          <span>Gobierno corporativo con inteligencia artificial</span>
          <span>gobernia.ai</span>
        </div>
      </div>
    ),
    size,
  )
}
