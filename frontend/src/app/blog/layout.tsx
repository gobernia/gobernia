import BlogShell from "@/components/blog/BlogShell"

export default function BlogLayout({ children }: { children: React.ReactNode }) {
  return <BlogShell>{children}</BlogShell>
}
