import "./globals.css";
import type { Metadata } from "next";
import { Sidebar } from "@/components/sidebar";

export const metadata: Metadata = {
  title: "AirHealth · Air Quality & Public Health Analytics",
  description: "Interactive analytics platform for pollution & disease propagation across Indian districts.",
};

export default function RootLayout({ children }: { children: React.ReactNode }) {
  return (
    <html lang="en" className="dark">
      <body className="min-h-screen bg-background text-foreground antialiased">
        <div className="relative">
          {/* Ambient gradient background */}
          <div className="pointer-events-none fixed inset-0 -z-10">
            <div className="absolute top-0 left-1/3 w-[600px] h-[600px] bg-sky-500/10 rounded-full blur-[120px]" />
            <div className="absolute bottom-0 right-1/3 w-[500px] h-[500px] bg-emerald-500/10 rounded-full blur-[120px]" />
          </div>

          <div className="flex">
            <Sidebar />
            <main className="flex-1 min-h-screen">
              <div className="container max-w-7xl py-10 px-6 lg:px-10">
                {children}
              </div>
            </main>
          </div>
        </div>
      </body>
    </html>
  );
}
