import React from 'react';
import { Copy, Check, X } from 'lucide-react';
import { Button } from './ui/Button';

interface InoculationViewerProps {
  html: string;
  onClose: () => void;
}

export function InoculationViewer({ html, onClose }: InoculationViewerProps) {
  const [copied, setCopied] = React.useState(false);

  const handleCopy = () => {
    navigator.clipboard.writeText(html);
    setCopied(true);
    setTimeout(() => setCopied(false), 2000);
  };

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center bg-background/80 backdrop-blur-sm animate-in fade-in duration-200">
      <div className="bg-surface border border-border p-6 rounded-2xl w-full max-w-lg shadow-2xl relative animate-in zoom-in-95 duration-200">
        <button 
          onClick={onClose}
          className="absolute top-4 right-4 text-slate-400 hover:text-white transition-colors"
        >
          <X size={20} />
        </button>
        
        <h3 className="text-xl font-bold mb-4">Inoculation Card</h3>
        <p className="text-sm text-slate-400 mb-6">
          This card is ready to be shared on campus channels to pre-bunk the rumor.
        </p>
        
        <div 
          className="bg-white rounded-lg overflow-hidden mb-6"
          dangerouslySetInnerHTML={{ __html: html }}
        />

        <div className="flex justify-end">
          <Button variant="primary" onClick={handleCopy} className="flex items-center space-x-2">
            {copied ? <Check size={18} /> : <Copy size={18} />}
            <span>{copied ? 'Copied HTML!' : 'Copy HTML'}</span>
          </Button>
        </div>
      </div>
    </div>
  );
}
