import { useState, useEffect } from 'react';
import Login from './components/auth/Login';
import UploadJTL from './components/dashboard/UploadJTL';
import Dashboard from './components/dashboard/Dashboard';
import { BookOpen, LogOut } from 'lucide-react';

type View = 'login' | 'upload' | 'dashboard';

function App() {
  const [view, setView] = useState<View>('login');
  const [executionId, setExecutionId] = useState<string | null>(null);

  useEffect(() => {
    // Verificar si hay token al cargar
    const token = localStorage.getItem('token');
    if (token) {
      setView('upload');
    }
  }, []);

  const handleLoginSuccess = () => {
    setView('upload');
  };

  const handleUploadSuccess = (id: string) => {
    setExecutionId(id);
    setView('dashboard');
  };

  const handleLogout = () => {
    localStorage.removeItem('token');
    localStorage.removeItem('email');
    setView('login');
    setExecutionId(null);
  };

  const handleBack = () => {
    setView('upload');
    setExecutionId(null);
  };

  return (
    <>
      {view === 'login' && <Login onLoginSuccess={handleLoginSuccess} />}
      
      {view === 'upload' && (
        <div className="min-h-screen bg-gradient-to-br from-blue-50 via-white to-blue-50">
          {/* Header con estilo SQA */}
          <header className="bg-gradient-to-r from-blue-900 via-blue-800 to-blue-900 shadow-xl border-b-4 border-blue-700">
            <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8 py-6">
              <div className="flex items-center justify-between">
                <div className="flex items-center space-x-4">
                  <div className="flex items-center justify-center w-16 h-16 bg-white/10 backdrop-blur-sm rounded-xl shadow-lg border border-white/20">
                    <BookOpen className="w-8 h-8 text-white" />
                  </div>
                  <div>
                    <h1 className="text-3xl font-bold text-white mb-1">
                      sqa — Software Quality Assurance
                    </h1>
                    <p className="text-sm text-blue-200 italic">
                      Del pasado aprendimos, En el presente construimos, Para el futuro nos preparamos
                    </p>
                  </div>
                </div>
                <div className="flex items-center space-x-4">
                  <div className="text-right">
                    <p className="text-sm font-semibold text-white">Realizado por:</p>
                    <p className="text-xs text-blue-200">Célula de performance SQA</p>
                    <p className="text-xs text-blue-300 mt-1">📊 Generado: --</p>
                  </div>
                  <button
                    onClick={handleLogout}
                    className="flex items-center space-x-2 px-4 py-2 bg-white/10 hover:bg-white/20 text-white rounded-lg transition-all backdrop-blur-sm border border-white/20"
                  >
                    <LogOut className="w-5 h-5" />
                    <span className="text-sm">Salir</span>
                  </button>
                </div>
              </div>
            </div>
          </header>

          <main className="max-w-7xl mx-auto px-4 py-12 sm:px-6 lg:px-8">
            <UploadJTL onUploadSuccess={handleUploadSuccess} />
            
            {/* Features Section */}
            <div className="mt-16 grid grid-cols-1 md:grid-cols-3 gap-8">
              <div className="bg-white rounded-xl shadow-lg p-6 border-l-4 border-blue-600 hover:shadow-xl transition-shadow">
                <div className="flex items-center mb-4">
                  <div className="w-12 h-12 bg-blue-100 rounded-lg flex items-center justify-center mr-4 text-2xl">
                    📊
                  </div>
                  <h3 className="text-lg font-bold text-gray-900">
                    Análisis Automatizado
                  </h3>
                </div>
                <p className="text-gray-600 text-sm">
                  Sistema inteligente que procesa automáticamente tus archivos JTL de JMeter y genera análisis profesionales con recomendaciones basadas en criterios de aceptación.
                </p>
              </div>

              <div className="bg-white rounded-xl shadow-lg p-6 border-l-4 border-purple-600 hover:shadow-xl transition-shadow">
                <div className="flex items-center mb-4">
                  <div className="w-12 h-12 bg-purple-100 rounded-lg flex items-center justify-center mr-4 text-2xl">
                    📈
                  </div>
                  <h3 className="text-lg font-bold text-gray-900">
                    Visualizaciones Avanzadas
                  </h3>
                </div>
                <p className="text-gray-600 text-sm">
                  Gráficos interactivos de línea de tiempo, distribución por endpoint, códigos HTTP y percentiles para identificar rápidamente problemas de performance.
                </p>
              </div>

              <div className="bg-white rounded-xl shadow-lg p-6 border-l-4 border-green-600 hover:shadow-xl transition-shadow">
                <div className="flex items-center mb-4">
                  <div className="w-12 h-12 bg-green-100 rounded-lg flex items-center justify-center mr-4 text-2xl">
                    ✅
                  </div>
                  <h3 className="text-lg font-bold text-gray-900">
                    Evaluación vs SLAs
                  </h3>
                </div>
                <p className="text-gray-600 text-sm">
                  Define tus criterios de aceptación (tiempo de respuesta, tasa de error, throughput) y el sistema evaluará automáticamente el cumplimiento de cada métrica.
                </p>
              </div>
            </div>

            {/* Tech Stack Footer */}
            <div className="mt-16 bg-gradient-to-r from-blue-900 to-blue-800 rounded-xl shadow-lg p-6 text-center border border-blue-700">
              <p className="text-sm text-blue-200 mb-2">
                Arquitectura de la Solución
              </p>
              <p className="text-xs text-white font-mono">
                FastAPI + React + TypeScript + PostgreSQL + Google Gemini AI + Docker
              </p>
            </div>
          </main>
        </div>
      )}
      
      {view === 'dashboard' && executionId && (
        <Dashboard
          executionId={executionId}
          onLogout={handleLogout}
          onBack={handleBack}
        />
      )}
    </>
  );
}

export default App;
