// Blog de Gobernia: los artículos viven como Markdown en `content/blog/*.md` (con frontmatter
// YAML) y se leen al compilar. Todas las páginas del blog son estáticas: Google y las IAs
// reciben el HTML completo, sin depender de JavaScript.
import fs from "node:fs"
import path from "node:path"
import matter from "gray-matter"
import { Marked, type Tokens } from "marked"

const DIR = path.join(process.cwd(), "content", "blog")

// Fecha en que los artículos se publicaron en este blog (los textos vienen de ebooks
// anteriores; su año original se conserva en `anioOriginal`).
const FECHA_PUBLICACION = "2026-10-16"

export const CATEGORIAS = [
  "Gobierno corporativo",
  "Consejo de administración",
  "Sucesión",
  "Protocolo familiar",
  "Familia empresaria",
  "Finanzas",
  "Patrimonio",
  "Innovación y tecnología",
  "Sostenibilidad y ESG",
  "Entorno económico",
] as const
export type Categoria = (typeof CATEGORIAS)[number]

export interface Autor {
  slug: string
  nombre: string
  cargo: string
  organizacion: { nombre: string; url: string }
  bio: string
  foto: string
  sameAs: string[]
}

export const AUTORES: Record<string, Autor> = {
  "fernando-todd": {
    slug: "fernando-todd",
    nombre: "Fernando Todd",
    cargo: "CEO y Socio Director de TODD Empresas de Familia",
    organizacion: { nombre: "TODD Empresas de Familia", url: "https://empresasdefamilia.mx" },
    bio:
      "Fernando Todd es CEO y Socio Director de TODD Empresas de Familia, firma especializada en " +
      "gobierno corporativo, sucesión y protocolo familiar para familias empresarias. Escribe sobre " +
      "gobernanza en la revista Players of Life (Monterrey, Guadalajara, La Laguna y Saltillo) y en su " +
      "newsletter de LinkedIn, y colabora con Gobernia en la metodología de su Consejo de Administración con IA.",
    foto: "/images/autores/fernando-todd.jpg",
    sameAs: ["https://empresasdefamilia.mx"],
  },
}

export interface Pregunta { pregunta: string; respuesta: string }
export interface Encabezado { id: string; texto: string; nivel: 2 | 3 }

export interface ArticuloResumen {
  slug: string
  titulo: string
  seoTitulo: string
  descripcion: string
  respuestaCorta: string
  categoria: Categoria
  etiquetas: string[]
  fuente: string
  anioOriginal: number
  orden: number
  autor: Autor
  fecha: string
  minutos: number
}

export interface Articulo extends ArticuloResumen {
  puntosClave: string[]
  faq: Pregunta[]
  html: string
  indice: Encabezado[]
  palabras: number
}

export function slugify(texto: string): string {
  return texto
    .normalize("NFD").replace(/[̀-ͯ]/g, "")
    .toLowerCase().replace(/[^a-z0-9]+/g, "-").replace(/^-+|-+$/g, "")
}

export const slugCategoria = (c: string) => slugify(c)

function renderizar(md: string): { html: string; indice: Encabezado[] } {
  const indice: Encabezado[] = []
  const usados = new Set<string>()
  const marked = new Marked({ gfm: true })
  marked.use({
    renderer: {
      // h2/h3 con id estable: índice del artículo, enlaces directos y citas de las IAs.
      heading(this: { parser: { parseInline: (t: Tokens.Generic[]) => string } }, token: Tokens.Heading) {
        const texto = this.parser.parseInline(token.tokens)
        const nivel = Math.min(Math.max(token.depth, 2), 4)
        if (nivel > 3) return `<h4>${texto}</h4>\n`
        let id = slugify(token.text) || "seccion"
        while (usados.has(id)) id += "-2"
        usados.add(id)
        indice.push({ id, texto: token.text.replace(/\*\*/g, ""), nivel: nivel as 2 | 3 })
        return `<h${nivel} id="${id}">${texto}</h${nivel}>\n`
      },
      // Tablas con contenedor desplazable para que no rompan el ancho en celular.
      table(this: { parser: unknown }, token: Tokens.Table) {
        const original = new Marked({ gfm: true })
        return `<div class="tabla">${original.parser([token])}</div>\n`
      },
    },
  })
  return { html: marked.parse(md, { async: false }) as string, indice }
}

const contarPalabras = (md: string) => md.split(/\s+/).filter(Boolean).length

function leer(archivo: string): Articulo {
  const { data, content } = matter(fs.readFileSync(path.join(DIR, archivo), "utf8"))
  const autor = AUTORES[String(data.autor ?? "fernando-todd")] ?? AUTORES["fernando-todd"]
  const categoria = (CATEGORIAS as readonly string[]).includes(data.categoria)
    ? (data.categoria as Categoria) : "Gobierno corporativo"
  const { html, indice } = renderizar(content)
  const palabras = contarPalabras(content)
  return {
    slug: String(data.slug ?? archivo.replace(/\.md$/, "")),
    titulo: String(data.titulo),
    seoTitulo: String(data.seo_titulo ?? data.titulo),
    descripcion: String(data.descripcion ?? ""),
    respuestaCorta: String(data.respuesta_corta ?? ""),
    puntosClave: Array.isArray(data.puntos_clave) ? data.puntos_clave.map(String) : [],
    categoria,
    etiquetas: Array.isArray(data.etiquetas) ? data.etiquetas.map(String) : [],
    faq: Array.isArray(data.faq)
      ? data.faq.filter((f: Pregunta) => f?.pregunta && f?.respuesta)
          .map((f: Pregunta) => ({ pregunta: String(f.pregunta), respuesta: String(f.respuesta) }))
      : [],
    fuente: String(data.fuente ?? ""),
    anioOriginal: Number(data.anio_original ?? 0),
    orden: Number(data.orden ?? 0),
    autor,
    fecha: String(data.fecha ?? FECHA_PUBLICACION),
    html,
    indice,
    palabras,
    minutos: Math.max(1, Math.round(palabras / 220)),
  }
}

let cache: Articulo[] | null = null

/** Todos los artículos: los ebooks más recientes primero, y dentro de cada uno, su orden. */
export function getArticulos(): Articulo[] {
  // En desarrollo se releen los archivos para ver al instante los artículos nuevos o editados.
  if (cache && process.env.NODE_ENV === "production") return cache
  const archivos = fs.existsSync(DIR) ? fs.readdirSync(DIR).filter(f => f.endsWith(".md")) : []
  cache = archivos.map(leer).sort((a, b) =>
    b.anioOriginal - a.anioOriginal || a.fuente.localeCompare(b.fuente) || a.orden - b.orden)
  return cache
}

export const getArticulo = (slug: string) => getArticulos().find(a => a.slug === slug)

export function resumen(a: Articulo): ArticuloResumen {
  const { slug, titulo, seoTitulo, descripcion, respuestaCorta, categoria, etiquetas, fuente,
    anioOriginal, orden, autor, fecha, minutos } = a
  return { slug, titulo, seoTitulo, descripcion, respuestaCorta, categoria, etiquetas, fuente,
    anioOriginal, orden, autor, fecha, minutos }
}

/** Categorías que tienen al menos un artículo, en el orden de CATEGORIAS. */
export function categoriasConArticulos(): { nombre: Categoria; slug: string; total: number }[] {
  const arts = getArticulos()
  return CATEGORIAS
    .map(nombre => ({ nombre, slug: slugCategoria(nombre), total: arts.filter(a => a.categoria === nombre).length }))
    .filter(c => c.total > 0)
}

export const categoriaPorSlug = (slug: string) =>
  categoriasConArticulos().find(c => c.slug === slug)

/** Selección para el carrusel de la home: se alterna entre categorías para mostrar variedad. */
export function destacadosHome(n = 10): ArticuloResumen[] {
  const porCategoria = categoriasConArticulos()
    .map(c => getArticulos().filter(a => a.categoria === c.nombre))
  const elegidos: Articulo[] = []
  for (let ronda = 0; elegidos.length < n && porCategoria.some(l => l[ronda]); ronda++) {
    for (const lista of porCategoria) {
      if (lista[ronda] && elegidos.length < n) elegidos.push(lista[ronda])
    }
  }
  return elegidos.map(resumen)
}

/** Hasta 3 artículos relacionados: misma categoría y luego etiquetas en común. */
export function relacionados(a: Articulo, n = 3): ArticuloResumen[] {
  const puntaje = (b: Articulo) =>
    (b.categoria === a.categoria ? 10 : 0) + b.etiquetas.filter(e => a.etiquetas.includes(e)).length
  return getArticulos()
    .filter(b => b.slug !== a.slug)
    .sort((x, y) => puntaje(y) - puntaje(x))
    .slice(0, n)
    .map(resumen)
}
