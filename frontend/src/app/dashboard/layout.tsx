import TopNav from "@/components/ui/TopNav"

export default function DashboardLayout({ children }: { children: React.ReactNode }) {
  return (
    <>
      <TopNav />
      {children}
    </>
  )
}
