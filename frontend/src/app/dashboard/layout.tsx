import Sidebar from "@/components/ui/Sidebar"
import Notices from "@/components/dashboard/Notices"

export default function DashboardLayout({ children }: { children: React.ReactNode }) {
  return (
    <div className="min-h-dvh">
      <Sidebar />
      <Notices />
      <div className="md:ml-60">{children}</div>
    </div>
  )
}
