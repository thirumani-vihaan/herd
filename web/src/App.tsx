import { IngestPortal } from './components/IngestPortal'
import { Dashboard } from './components/Dashboard'
import { ShieldCheck } from 'lucide-react'

function App() {
  return (
    <div className="min-h-screen bg-background text-white p-4 md:p-8 flex flex-col relative overflow-hidden">
      
      {/* Background decoration */}
      <div className="absolute top-[-20%] left-[-10%] w-[50%] h-[50%] rounded-full bg-primary/10 blur-[120px] pointer-events-none" />
      <div className="absolute bottom-[-20%] right-[-10%] w-[50%] h-[50%] rounded-full bg-danger/10 blur-[120px] pointer-events-none" />

      {/* Header */}
      <header className="z-10 flex items-center space-x-4 mb-12 max-w-7xl mx-auto w-full">
        <div className="w-12 h-12 bg-primary/20 rounded-xl flex items-center justify-center text-primary shadow-[0_0_20px_rgba(59,130,246,0.3)] border border-primary/30">
          <ShieldCheck size={28} />
        </div>
        <h1 className="text-3xl font-bold tracking-tight bg-clip-text text-transparent bg-gradient-to-r from-white to-slate-400">
          HERD Immune System
        </h1>
      </header>

      {/* Content */}
      <div className="z-10 w-full max-w-7xl mx-auto flex flex-col lg:flex-row gap-8 items-stretch justify-center">
        
        {/* Left side: Portal */}
        <div className="flex-1 w-full flex flex-col justify-center">
          <div className="mb-6 pl-2">
            <h2 className="text-2xl font-bold mb-2">Incoming Reports</h2>
            <p className="text-slate-400">Upload suspicious claims to run the autonomous cascade.</p>
          </div>
          <IngestPortal />
        </div>

        {/* Right side: Dashboard */}
        <div className="flex-1 w-full">
          <Dashboard />
        </div>

      </div>
    </div>
  )
}

export default App
