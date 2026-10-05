import { createServerClient } from "@supabase/ssr"
import { NextResponse, type NextRequest } from "next/server"

// /t = escritorio público del responsable (enlace mágico, sin login).
const PUBLIC_PATHS = ["/", "/sign-in", "/sign-up", "/auth/callback", "/legal", "/c", "/t"]

// Archivos para buscadores e IAs: deben responder siempre, sin pasar por el login.
const SEO_FILES = ["/robots.txt", "/sitemap.xml", "/llms.txt", "/opengraph-image", "/twitter-image"]

// Dominio de despliegue de Vercel: sus páginas PÚBLICAS se redirigen al dominio oficial para
// que buscadores e IAs no vean contenido duplicado (la app privada sigue funcionando ahí).
const HOST_DESPLIEGUE = "gobernia-liard.vercel.app"
const DOMINIO_OFICIAL = "https://www.gobernia.ai"
const PUBLICAS_SEO = ["/", "/sign-up", "/legal", ...SEO_FILES]

const coincide = (lista: string[], pathname: string) =>
  lista.some(p => pathname === p || pathname.startsWith(p + "/") || (p !== "/" && pathname.startsWith(p)))

export async function middleware(request: NextRequest) {
  const { pathname, search } = request.nextUrl

  if (request.headers.get("host") === HOST_DESPLIEGUE && coincide(PUBLICAS_SEO, pathname)
      && !pathname.startsWith("/sign-in")) {
    return NextResponse.redirect(`${DOMINIO_OFICIAL}${pathname}${search}`, 308)
  }

  if (SEO_FILES.some(p => pathname === p || pathname.startsWith(p))) {
    return NextResponse.next()
  }

  if (PUBLIC_PATHS.some(p => pathname === p || pathname.startsWith(p + "/"))) {
    return NextResponse.next()
  }

  const response = NextResponse.next()

  const supabase = createServerClient(
    process.env.NEXT_PUBLIC_SUPABASE_URL!,
    process.env.NEXT_PUBLIC_SUPABASE_ANON_KEY!,
    {
      cookies: {
        getAll: () => request.cookies.getAll(),
        setAll: cookies => cookies.forEach(({ name, value, options }) =>
          response.cookies.set(name, value, options)
        ),
      },
    }
  )

  const { data: { user } } = await supabase.auth.getUser()

  if (!user) {
    return NextResponse.redirect(new URL("/sign-in", request.url))
  }

  return response
}

export const config = {
  matcher: [
    "/((?!_next/static|_next/image|favicon.ico|fonts/|.*\\.(?:svg|png|jpg|jpeg|gif|webp|woff2|woff|otf|ttf|mp4|webm)$).*)",
  ],
}
