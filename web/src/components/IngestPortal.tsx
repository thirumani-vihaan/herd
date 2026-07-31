import React, { useState, useRef } from 'react';
import { UploadCloud, FileText, Send, CheckCircle2, AlertCircle, Loader2 } from 'lucide-react';
import { Button } from './ui/Button';

export function IngestPortal() {
  const [text, setText] = useState('');
  const [file, setFile] = useState<File | null>(null);
  const [isDragging, setIsDragging] = useState(false);
  const [status, setStatus] = useState<'idle' | 'loading' | 'success' | 'error'>('idle');
  const [result, setResult] = useState<any>(null);
  const fileInputRef = useRef<HTMLInputElement>(null);

  const handleDragOver = (e: React.DragEvent) => {
    e.preventDefault();
    setIsDragging(true);
  };

  const handleDragLeave = () => {
    setIsDragging(false);
  };

  const handleDrop = (e: React.DragEvent) => {
    e.preventDefault();
    setIsDragging(false);
    if (e.dataTransfer.files && e.dataTransfer.files[0]) {
      setFile(e.dataTransfer.files[0]);
    }
  };

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!text && !file) return;

    setStatus('loading');
    
    const formData = new FormData();
    formData.append('text', text);
    formData.append('reporter_hash', 'frontend_user_123');
    if (file) {
      formData.append('image', file);
    }

    try {
      const response = await fetch('http://localhost:8000/ingest', {
        method: 'POST',
        body: formData,
      });
      
      const data = await response.json();
      setResult(data);
      setStatus('success');
      
      // Reset form after a delay
      setTimeout(() => {
        setText('');
        setFile(null);
        setStatus('idle');
        setResult(null);
      }, 5000);
      
    } catch (error) {
      console.error('Ingest error:', error);
      setStatus('error');
    }
  };

  return (
    <div className="glass-card p-6 md:p-8 w-full max-w-2xl mx-auto relative overflow-hidden transition-all duration-300">
      
      <div className="flex items-center space-x-3 mb-6">
        <div className="w-10 h-10 bg-primary/20 rounded-lg flex items-center justify-center text-primary shadow-[0_0_10px_rgba(59,130,246,0.5)]">
          <UploadCloud size={24} />
        </div>
        <div>
          <h2 className="text-xl font-bold tracking-tight">Report a Rumor</h2>
          <p className="text-sm text-slate-400">Upload a screenshot or paste text</p>
        </div>
      </div>

      <form onSubmit={handleSubmit} className="space-y-6">
        {/* Text Input */}
        <div className="relative group">
          <div className="absolute inset-y-0 left-0 pl-3 flex items-start pt-3 pointer-events-none text-slate-400 group-focus-within:text-primary transition-colors">
            <FileText size={18} />
          </div>
          <textarea
            value={text}
            onChange={(e) => setText(e.target.value)}
            className="w-full bg-surface/50 border border-border focus:border-primary/50 focus:ring-1 focus:ring-primary/50 rounded-xl pl-10 pr-4 py-3 text-white placeholder-slate-500 transition-all outline-none min-h-[120px] resize-none"
            placeholder="What is the claim?"
            disabled={status === 'loading'}
          />
        </div>

        {/* Drag and Drop Zone */}
        <div 
          className={`relative border-2 border-dashed rounded-xl p-8 flex flex-col items-center justify-center transition-all duration-200 cursor-pointer ${
            isDragging 
              ? 'border-primary bg-primary/10 shadow-[0_0_20px_rgba(59,130,246,0.2)]' 
              : 'border-border bg-surface/30 hover:bg-surface/50 hover:border-slate-500'
          }`}
          onDragOver={handleDragOver}
          onDragLeave={handleDragLeave}
          onDrop={handleDrop}
          onClick={() => fileInputRef.current?.click()}
        >
          <input 
            type="file" 
            className="hidden" 
            ref={fileInputRef} 
            onChange={(e) => e.target.files && setFile(e.target.files[0])}
            accept="image/*"
          />
          <UploadCloud size={32} className={`mb-3 ${isDragging ? 'text-primary' : 'text-slate-400'}`} />
          {file ? (
            <div className="text-center">
              <p className="font-medium text-white">{file.name}</p>
              <p className="text-xs text-slate-400 mt-1">{(file.size / 1024 / 1024).toFixed(2)} MB</p>
            </div>
          ) : (
            <div className="text-center">
              <p className="font-medium text-slate-300">Drag & drop a screenshot</p>
              <p className="text-xs text-slate-500 mt-1">or click to browse</p>
            </div>
          )}
        </div>

        <div className="flex justify-end pt-2">
          <Button 
            variant="primary" 
            className={`flex items-center space-x-2 ${(!text && !file) ? 'opacity-50 cursor-not-allowed' : ''}`}
            disabled={(!text && !file) || status === 'loading'}
          >
            {status === 'loading' ? (
              <>
                <Loader2 size={18} className="animate-spin" />
                <span>Investigating...</span>
              </>
            ) : status === 'success' ? (
              <>
                <CheckCircle2 size={18} />
                <span>Submitted</span>
              </>
            ) : status === 'error' ? (
              <>
                <AlertCircle size={18} />
                <span>Failed</span>
              </>
            ) : (
              <>
                <Send size={18} />
                <span>Submit Report</span>
              </>
            )}
          </Button>
        </div>
      </form>

      {/* Loading Overlay */}
      {status === 'loading' && (
        <div className="absolute inset-0 bg-background/80 backdrop-blur-sm flex flex-col items-center justify-center z-10 animate-in fade-in duration-300">
          <div className="w-16 h-16 relative">
            <div className="absolute inset-0 border-4 border-primary/20 rounded-full"></div>
            <div className="absolute inset-0 border-4 border-primary border-t-transparent rounded-full animate-spin"></div>
          </div>
          <h3 className="mt-6 text-lg font-medium text-white animate-pulse">Running Investigation Cascade...</h3>
          <p className="text-sm text-slate-400 mt-2">Checking Tier 0 Heuristics</p>
        </div>
      )}
      
      {/* Success State */}
      {status === 'success' && result && (
        <div className="absolute inset-0 bg-surface border border-success/30 rounded-xl flex flex-col items-center justify-center z-10 p-6 animate-in zoom-in-95 duration-300">
          <div className="w-16 h-16 bg-success/20 text-success rounded-full flex items-center justify-center mb-4 shadow-[0_0_20px_rgba(34,197,94,0.4)]">
            <CheckCircle2 size={32} />
          </div>
          <h3 className="text-xl font-bold text-white mb-2">Ingestion Accepted</h3>
          <p className="text-slate-400 text-center text-sm mb-4">
            Tracking ID: <span className="font-mono text-primary">{result.tracking_id}</span>
          </p>
          <div className="text-xs text-slate-500 bg-background/50 p-3 rounded-lg w-full max-w-sm font-mono border border-border">
            Status: {result.status}
          </div>
        </div>
      )}
    </div>
  );
}
