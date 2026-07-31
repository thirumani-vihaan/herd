import React, { useEffect, useState } from 'react';
import { Activity, AlertTriangle, ShieldAlert, CheckCircle, FileText } from 'lucide-react';
import { InoculationViewer } from './InoculationViewer';

interface Alert {
  verdict: string;
  summary: string;
  velocity?: string;
  inoculation_html?: string;
  timestamp: number;
}

export function Dashboard() {
  const [alerts, setAlerts] = useState<Alert[]>([]);
  const [connected, setConnected] = useState(false);
  const [selectedHtml, setSelectedHtml] = useState<string | null>(null);

  useEffect(() => {
    const ws = new WebSocket('ws://localhost:8000/ws');

    ws.onopen = () => {
      setConnected(true);
    };

    ws.onmessage = (event) => {
      try {
        const data = JSON.parse(event.data);
        setAlerts((prev) => [{ ...data, timestamp: Date.now() }, ...prev].slice(0, 10));
      } catch (e) {
        console.error("WebSocket message parse error:", e);
      }
    };

    ws.onclose = () => {
      setConnected(false);
    };

    return () => {
      ws.close();
    };
  }, []);

  return (
    <div className="glass-card p-6 md:p-8 w-full max-w-2xl mx-auto h-[600px] flex flex-col">
      <div className="flex items-center justify-between mb-6 border-b border-border pb-4">
        <div className="flex items-center space-x-3">
          <div className="w-10 h-10 bg-surface rounded-lg flex items-center justify-center text-white">
            <Activity size={24} />
          </div>
          <div>
            <h2 className="text-xl font-bold tracking-tight">Live Dashboard</h2>
            <p className="text-sm text-slate-400">Autonomous Cascade Monitoring</p>
          </div>
        </div>
        <div className="flex items-center space-x-2">
          <div className={`w-2 h-2 rounded-full ${connected ? 'bg-success animate-pulse' : 'bg-danger'}`}></div>
          <span className="text-sm font-medium text-slate-300">
            {connected ? 'Connected' : 'Disconnected'}
          </span>
        </div>
      </div>

      <div className="flex-1 overflow-y-auto space-y-4 pr-2">
        {alerts.length === 0 ? (
          <div className="h-full flex flex-col items-center justify-center text-slate-500 space-y-4">
            <ShieldAlert size={48} className="opacity-20" />
            <p>No active threats detected.</p>
          </div>
        ) : (
          alerts.map((alert, i) => {
            const isFalse = alert.verdict === 'FALSE';
            const isMisleading = alert.verdict === 'MISLEADING';
            const isTrue = alert.verdict === 'TRUE';
            
            return (
              <div 
                key={alert.timestamp + i} 
                className={`p-4 rounded-xl border flex items-start space-x-4 animate-in slide-in-from-right duration-300 ${
                  isFalse ? 'bg-danger/10 border-danger/30' : 
                  isMisleading ? 'bg-warning/10 border-warning/30' : 
                  isTrue ? 'bg-success/10 border-success/30' : 
                  'bg-surface border-border'
                }`}
              >
                <div className={`mt-1 p-2 rounded-full ${
                  isFalse ? 'bg-danger/20 text-danger' : 
                  isMisleading ? 'bg-warning/20 text-warning' : 
                  isTrue ? 'bg-success/20 text-success' : 
                  'bg-slate-700 text-slate-300'
                }`}>
                  {isFalse ? <AlertTriangle size={20} /> : <CheckCircle size={20} />}
                </div>
                <div>
                  <div className="flex items-center space-x-2 mb-1">
                    <span className={`font-bold ${
                      isFalse ? 'text-danger' : 
                      isMisleading ? 'text-warning' : 
                      isTrue ? 'text-success' : 
                      'text-slate-300'
                    }`}>
                      {alert.verdict}
                    </span>
                    <span className="text-xs text-slate-500">
                      {new Date(alert.timestamp).toLocaleTimeString()}
                    </span>
                    {alert.velocity === 'high' && (
                      <span className="ml-2 px-2 py-0.5 rounded-full bg-danger/20 text-danger text-xs font-bold animate-pulse flex items-center">
                        <Activity size={12} className="mr-1" /> Viral
                      </span>
                    )}
                    {alert.velocity === 'medium' && (
                      <span className="ml-2 px-2 py-0.5 rounded-full bg-warning/20 text-warning text-xs font-bold flex items-center">
                        <Activity size={12} className="mr-1" /> Rising
                      </span>
                    )}
                  </div>
                  <p className="text-slate-300 text-sm leading-relaxed">
                    {alert.summary}
                  </p>
                  {alert.inoculation_html && (
                    <button 
                      onClick={() => setSelectedHtml(alert.inoculation_html!)}
                      className="mt-3 text-xs flex items-center text-primary hover:text-blue-400 transition-colors bg-primary/10 px-3 py-1.5 rounded-lg border border-primary/20 hover:bg-primary/20"
                    >
                      <FileText size={14} className="mr-1.5" />
                      View Inoculation Card
                    </button>
                  )}
                </div>
              </div>
            );
          })
        )}
      </div>

      {selectedHtml && (
        <InoculationViewer 
          html={selectedHtml} 
          onClose={() => setSelectedHtml(null)} 
        />
      )}
    </div>
  );
}
