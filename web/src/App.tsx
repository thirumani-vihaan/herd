import { IngestPortal } from './components/IngestPortal'
import { ShieldCheck } from 'lucide-react'

function App() {
  return (
    <div className="min-h-screen bg-background text-white p-4 md:p-8 flex flex-col items-center justify-center relative overflow-hidden">
      
      {/* Background decoration */}
      <div className="absolute top-[-20%] left-[-10%] w-[50%] h-[50%] rounded-full bg-primary/10 blur-[120px] pointer-events-none" />
      <div className="absolute bottom-[-20%] right-[-10%] w-[50%] h-[50%] rounded-full bg-danger/10 blur-[120px] pointer-events-none" />

      <div className="z-10 w-full max-w-6xl mx-auto flex flex-col md:flex-row gap-8 items-start justify-center">
        
        {/* Left side: Branding */}
        <div className="flex-1 max-w-md pt-12">
          <div className="w-16 h-16 bg-primary/20 rounded-xl flex items-center justify-center text-primary mb-6 shadow-[0_0_20px_rgba(59,130,246,0.3)] border border-primary/30">
            <ShieldCheck size={32} />
          </div>
          <h1 className="text-5xl font-bold tracking-tight mb-6 bg-clip-text text-transparent bg-gradient-to-r from-white to-slate-400">
            HERD Immune System
          </h1>
          <p className="text-lg text-slate-400 mb-8 leading-relaxed">
            Upload suspicious campus claims or screenshots. Our autonomous cascade will evaluate the threat level across 4 independent tiers in seconds.
          </p>
        </div>

        {/* Right side: Portal */}
        <div className="flex-1 w-full">
          <IngestPortal />
        </div>

      </div>
    </div>
  )
}

export default App
