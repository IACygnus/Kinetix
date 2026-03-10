/**
 * Login - Pagina de inicio de sesion - SQA Corporate Branding
 */
import { useState } from 'react';
import { useNavigate } from 'react-router-dom';
import { LogIn } from 'lucide-react';
import { useAuth } from '../../context/AuthContext';

export default function Login() {
  const navigate = useNavigate();
  const { login, isAuthenticated, sessionExpiredMessage, clearSessionMessage } = useAuth();
  const [username, setUsername] = useState('');
  const [password, setPassword] = useState('');
  const [error, setError] = useState('');
  const [loading, setLoading] = useState(false);

  // Si ya esta autenticado, redirigir
  if (isAuthenticated) {
    navigate('/dashboard', { replace: true });
    return null;
  }

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    setLoading(true);
    setError('');

    try {
      await login(username, password);
      navigate('/dashboard');
    } catch (err: unknown) {
      const status = (err as { response?: { status?: number } })?.response?.status;
      const detail = (err as { response?: { data?: { detail?: string } } })?.response?.data?.detail;
      if (status === 429) {
        setError(detail || 'Demasiados intentos. Intenta en 15 minutos.');
      } else {
        setError(detail || 'Credenciales invalidas. Verifica tu usuario y contrasena.');
      }
    } finally {
      setLoading(false);
    }
  };

  return (
    <div className="min-h-screen bg-sqa-navy flex items-center justify-center p-4 relative overflow-hidden">
      {/* Particle Effects */}
      <div className="absolute inset-0 pointer-events-none">
        <div className="particle" style={{ top: '20%', left: '10%' }} />
        <div className="particle" style={{ top: '60%', left: '25%' }} />
        <div className="particle" style={{ top: '30%', left: '70%' }} />
        <div className="particle" style={{ top: '80%', left: '85%' }} />
        <div className="particle" style={{ top: '10%', left: '50%' }} />
        <div className="particle" style={{ top: '50%', left: '40%' }} />
        <div className="particle" style={{ top: '70%', left: '60%' }} />
        <div className="particle" style={{ top: '40%', left: '90%' }} />
      </div>

      {/* Subtle gradient overlay */}
      <div className="absolute inset-0 bg-gradient-to-br from-sqa-navy via-sqa-navy-light/50 to-sqa-navy opacity-80" />

      <div className="w-full relative z-10" style={{ maxWidth: '550px' }}>
        {/* Logo and Header */}
        <div className="text-center mb-12">
          <h1 className="text-7xl font-bold text-white tracking-tight">
            sqa<span className="text-sqa-gold">_</span>
          </h1>
          <h2 className="text-3xl font-semibold text-slate-300 mt-4">
            Software Quality Assurance
          </h2>
          <p className="text-xl text-slate-400/70 italic mt-3">
            Del pasado aprendimos, En el presente construimos,
            <br />
            Para el futuro nos preparamos
          </p>
        </div>

        {/* Login Card - Glassmorphism */}
        <div className="bg-white/5 backdrop-blur-xl rounded-2xl shadow-2xl p-12 border border-white/10">
          <h3 className="text-4xl font-bold text-white mb-10 text-center">
            Iniciar Sesion
          </h3>

          <form onSubmit={handleSubmit} className="space-y-8">
            <div>
              <label className="block text-xl font-medium text-slate-300 mb-3">
                Usuario o Email
              </label>
              <input
                type="text"
                value={username}
                onChange={(e) => setUsername(e.target.value)}
                className="w-full px-6 h-16 bg-sqa-navy/60 border border-sqa-border rounded-xl text-2xl text-slate-200 placeholder:text-slate-500 focus:outline-none focus:ring-2 focus:ring-sqa-gold/50 focus:border-sqa-gold transition-all"
                placeholder="admin"
                required
              />
            </div>

            <div>
              <label className="block text-xl font-medium text-slate-300 mb-3">
                Contrasena
              </label>
              <input
                type="password"
                value={password}
                onChange={(e) => setPassword(e.target.value)}
                className="w-full px-6 h-16 bg-sqa-navy/60 border border-sqa-border rounded-xl text-2xl text-slate-200 placeholder:text-slate-500 focus:outline-none focus:ring-2 focus:ring-sqa-gold/50 focus:border-sqa-gold transition-all"
                placeholder="••••••••"
                required
              />
            </div>

            {sessionExpiredMessage && (
              <div className="bg-amber-900/20 border border-amber-600/50 text-amber-300 px-6 py-4 rounded-xl text-xl">
                {sessionExpiredMessage}
                <button
                  type="button"
                  onClick={clearSessionMessage}
                  className="ml-3 text-amber-400 hover:text-amber-200 font-bold"
                >&times;</button>
              </div>
            )}

            {error && (
              <div className="bg-red-900/20 border border-red-700/50 text-red-300 px-6 py-4 rounded-xl text-xl">
                {error}
              </div>
            )}

            <button
              type="submit"
              disabled={loading}
              className="w-full bg-sqa-gold text-sqa-navy font-bold h-16 px-6 rounded-xl text-2xl hover:bg-sqa-gold-light disabled:bg-slate-600 disabled:text-slate-400 transition-all shadow-lg hover:shadow-sqa-gold/25 hover:shadow-xl transform hover:-translate-y-0.5 flex items-center justify-center space-x-3"
            >
              <LogIn className="w-8 h-8" />
              <span>{loading ? 'Ingresando...' : 'Ingresar'}</span>
            </button>
          </form>

          <div className="mt-8 pt-6 border-t border-white/10 text-center">
            <p className="text-xl text-slate-500">Contacta al administrador si no tienes cuenta</p>
          </div>
        </div>

        <div className="text-center mt-8">
          <p className="text-2xl text-slate-500">
            JMeter Analyzer Pro v2.0
          </p>
        </div>
      </div>
    </div>
  );
}
