import { Loader2 } from 'lucide-react';

interface LoadingSpinnerProps {
  message?: string;
}

export default function LoadingSpinner({ message = "Procesando..." }: LoadingSpinnerProps) {
  return (
    <div className="fixed inset-0 bg-sqa-navy/80 backdrop-blur-sm flex items-center justify-center z-50">
      <div className="bg-sqa-card border border-sqa-border rounded-2xl p-8 flex flex-col items-center space-y-4 shadow-2xl">
        <Loader2 className="w-14 h-14 text-sqa-gold animate-spin" />
        <div className="text-center">
          <h3 className="text-2xl font-semibold text-white mb-1">{message}</h3>
          <p className="text-slate-400 text-xl">
            Analizando resultados de JMeter...
          </p>
        </div>
        <div className="flex space-x-2">
          <div className="w-2.5 h-2.5 bg-sqa-gold rounded-full animate-bounce"></div>
          <div className="w-2.5 h-2.5 bg-sqa-gold rounded-full animate-bounce" style={{ animationDelay: '0.1s' }}></div>
          <div className="w-2.5 h-2.5 bg-sqa-gold rounded-full animate-bounce" style={{ animationDelay: '0.2s' }}></div>
        </div>
      </div>
    </div>
  );
}
