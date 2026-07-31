import { Button } from './components/ui/Button'
import { ShieldCheck } from 'lucide-react'

function App() {
  return (
    <div className="min-h-screen p-8 flex flex-col items-center justify-center">
      <div className="glass-card p-8 max-w-md w-full space-y-6 text-center">
        <div className="mx-auto w-16 h-16 bg-primary/20 rounded-full flex items-center justify-center text-primary mb-4 shadow-[0_0_15px_rgba(59,130,246,0.5)]">
          <ShieldCheck size={32} />
        </div>
        <h1 className="text-3xl font-bold tracking-tight">HERD Immune System</h1>
        <p className="text-slate-400">Design System Foundation Loaded.</p>
        
        <div className="flex gap-4 justify-center pt-4">
          <Button variant="outline">Secondary</Button>
          <Button variant="primary">Primary Action</Button>
        </div>
      </div>
    </div>
  )
}

export default App
