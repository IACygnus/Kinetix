import { Loader2 } from 'lucide-react';

interface LoadingSpinnerProps {
  message?: string;
}

export default function LoadingSpinner({ message = "Procesando..." }: LoadingSpinnerProps) {
  return (
    <div className="fixed inset-0 bg-black bg-opacity-50 flex items-center justify-center z-50">
      <div className="bg-white rounded-lg p-8 flex flex-col items-center space-y-4 shadow-2xl">
        <Loader2 className="w-16 h-16 text-blue-600 animate-spin" />
        <div className="text-center">
          <h3 className="text-xl font-semibold text-gray-900 mb-2">{message}</h3>
          <p className="text-gray-600 text-sm">
            Analizando resultados de JMeter...
          </p>
        </div>
        <div className="flex space-x-2">
          <div className="w-2 h-2 bg-blue-600 rounded-full animate-bounce"></div>
          <div className="w-2 h-2 bg-blue-600 rounded-full animate-bounce delay-100"></div>
          <div className="w-2 h-2 bg-blue-600 rounded-full animate-bounce delay-200"></div>
        </div>
      </div>
    </div>
  );
}
