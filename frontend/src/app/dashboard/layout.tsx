import Sidebar from "@/components/ui/Sidebar"
import Notices from "@/components/dashboard/Notices"
import WelcomeTour from "@/components/dashboard/WelcomeTour"
import ToddFlotante from "@/components/consejo/ToddFlotante"

export default function DashboardLayout({ children }: { children: React.ReactNode }) {
  return (
    <div className="min-h-dvh" style={{ background: "#F2F2F0" }}>
      <Sidebar />
      <Notices />
      <div className="md:ml-56">{children}</div>
      {/* Todd siempre disponible, en cualquier página del dashboard */}
      <ToddFlotante />
      <WelcomeTour />
    </div>
  )
}
