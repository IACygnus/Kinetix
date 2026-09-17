/**
 * Catálogo de actividades del MÓDULO DE HORAS (ETAPA H1.4).
 *
 * Especificación de horas v1.0 §1.2 y §8: listar, crear, renombrar,
 * activar/desactivar y borrar cuando corresponde.
 *
 * La regla que la pantalla tiene que dejar clara: **una actividad con horas
 * registradas no se borra, se desactiva**. Por eso el botón de borrar se
 * deshabilita con un motivo visible en vez de dejar que el usuario pulse y se
 * lleve un error.
 *
 * Regla 16: todos los hooks antes de cualquier return.
 */
import { useCallback, useEffect, useState } from 'react';
import { Plus, Pencil, Trash2, Check, X, Loader2, AlertTriangle } from 'lucide-react';
import { Actividad, horasApi } from '../../api/horasApi';
import { useAuth } from '../../context/AuthContext';

export default function ActividadesPage() {
  const { user } = useAuth();
  const esAdmin = user?.role === 'admin';

  const [actividades, setActividades] = useState<Actividad[]>([]);
  const [cargando, setCargando] = useState(true);
  const [error, setError] = useState('');
  const [aviso, setAviso] = useState('');
  const [nueva, setNueva] = useState('');
  const [creando, setCreando] = useState(false);
  const [editando, setEditando] = useState<string | null>(null);
  const [borrador, setBorrador] = useState('');

  const cargar = useCallback(async () => {
    try {
      setActividades(await horasApi.listarActividades());
      setError('');
    } catch {
      setError('No se pudieron cargar las actividades.');
    }
    setCargando(false);
  }, []);

  useEffect(() => { cargar(); }, [cargar]);

  const fallo = (e: any, porDefecto: string) =>
    setError(e?.response?.data?.detail || porDefecto);

  const crear = async () => {
    const nombre = nueva.trim();
    if (!nombre) return;
    setCreando(true);
    try {
      await horasApi.crearActividad(nombre);
      setNueva('');
      setAviso(`Actividad «${nombre}» creada.`);
      setError('');
      await cargar();
    } catch (e) { fallo(e, 'No se pudo crear la actividad.'); }
    setCreando(false);
  };

  const renombrar = async (a: Actividad) => {
    const nombre = borrador.trim();
    if (!nombre || nombre === a.name) { setEditando(null); return; }
    try {
      await horasApi.editarActividad(a.id, { name: nombre });
      setEditando(null);
      setError('');
      await cargar();
    } catch (e) { fallo(e, 'No se pudo renombrar.'); }
  };

  const alternar = async (a: Actividad) => {
    try {
      await horasApi.editarActividad(a.id, { is_active: !a.is_active });
      setAviso(a.is_active
        ? `«${a.name}» desactivada: deja de ofrecerse en los proyectos nuevos.`
        : `«${a.name}» activada.`);
      setError('');
      await cargar();
    } catch (e) { fallo(e, 'No se pudo cambiar el estado.'); }
  };

  const borrar = async (a: Actividad) => {
    if (!window.confirm(`¿Borrar la actividad «${a.name}»? No se puede deshacer.`)) return;
    try {
      await horasApi.borrarActividad(a.id);
      setAviso(`Actividad «${a.name}» borrada.`);
      setError('');
      await cargar();
    } catch (e) { fallo(e, 'No se pudo borrar la actividad.'); }
  };

  /** Por qué NO se puede borrar esta actividad, en palabras. */
  const motivoNoBorrable = (a: Actividad): string => {
    if (a.has_entries) return 'Tiene horas registradas: desactívala en vez de borrarla.';
    if (a.projects_count > 0) {
      return `Está en ${a.projects_count} proyecto${a.projects_count === 1 ? '' : 's'}.`;
    }
    if (!esAdmin) return 'Borrar es exclusivo del administrador.';
    return '';
  };

  return (
    <div className="p-8 max-w-5xl mx-auto">
      <div className="mb-6">
        <h1 className="text-4xl font-bold text-gray-800">Actividades</h1>
        <p className="text-lg text-gray-500 mt-1">
          El catálogo que alimenta a todos los proyectos. Una actividad con horas registradas
          no se borra: se desactiva y deja de ofrecerse en los proyectos nuevos.
        </p>
      </div>

      {error && (
        <div className="mb-4 flex items-start gap-2 p-4 rounded-xl bg-red-50 border border-red-200 text-red-800">
          <AlertTriangle className="w-5 h-5 mt-0.5 flex-shrink-0" />
          <span className="text-base">{error}</span>
        </div>
      )}
      {aviso && !error && (
        <div className="mb-4 p-4 rounded-xl bg-emerald-50 border border-emerald-200 text-emerald-800 text-base">
          {aviso}
        </div>
      )}

      {/* Crear */}
      <div className="mb-6 flex gap-3">
        <input
          value={nueva}
          onChange={(e) => setNueva(e.target.value)}
          onKeyDown={(e) => { if (e.key === 'Enter') crear(); }}
          placeholder="Nombre de la actividad nueva"
          data-testid="nueva-actividad"
          className="flex-1 px-4 py-3 border-2 border-gray-300 rounded-xl text-lg focus:border-[#f5a623] focus:ring-2 focus:ring-[#f5a623]/30"
        />
        <button
          onClick={crear}
          disabled={creando || !nueva.trim()}
          data-testid="crear-actividad"
          className="flex items-center gap-2 px-6 py-3 bg-[#f5a623] text-[#0a1628] text-lg font-bold rounded-xl hover:bg-[#f7b84a] disabled:opacity-40 disabled:cursor-not-allowed"
        >
          {creando ? <Loader2 className="w-5 h-5 animate-spin" /> : <Plus className="w-5 h-5" />}
          Crear
        </button>
      </div>

      {cargando ? (
        <div className="py-12 text-center text-gray-400 text-lg">Cargando actividades…</div>
      ) : (
        <div className="bg-white rounded-2xl border border-gray-200 shadow-sm overflow-hidden">
          <table className="w-full">
            <thead className="bg-gray-50 border-b border-gray-200">
              <tr className="text-sm uppercase text-gray-500">
                <th className="py-3 px-4 text-left">Actividad</th>
                <th className="py-3 px-4 text-center w-32">Proyectos</th>
                <th className="py-3 px-4 text-center w-32">Estado</th>
                <th className="py-3 px-4 text-right w-56">Acciones</th>
              </tr>
            </thead>
            <tbody data-testid="tabla-actividades">
              {actividades.map((a) => {
                const motivo = motivoNoBorrable(a);
                return (
                  <tr key={a.id} className="border-b border-gray-100 last:border-0" data-actividad={a.name}>
                    <td className="py-3 px-4">
                      {editando === a.id ? (
                        <div className="flex items-center gap-2">
                          <input
                            value={borrador}
                            onChange={(e) => setBorrador(e.target.value)}
                            onKeyDown={(e) => {
                              if (e.key === 'Enter') renombrar(a);
                              if (e.key === 'Escape') setEditando(null);
                            }}
                            autoFocus
                            className="flex-1 px-3 py-1.5 border-2 border-[#f5a623] rounded-lg text-lg"
                          />
                          <button onClick={() => renombrar(a)} aria-label="Guardar"
                            className="p-1.5 text-emerald-600 hover:bg-emerald-50 rounded-lg">
                            <Check className="w-5 h-5" />
                          </button>
                          <button onClick={() => setEditando(null)} aria-label="Cancelar"
                            className="p-1.5 text-gray-400 hover:bg-gray-100 rounded-lg">
                            <X className="w-5 h-5" />
                          </button>
                        </div>
                      ) : (
                        <span className={`text-lg ${a.is_active ? 'text-gray-800' : 'text-gray-400 line-through'}`}>
                          {a.name}
                        </span>
                      )}
                    </td>
                    <td className="py-3 px-4 text-center text-gray-600 tabular-nums">
                      {a.projects_count}
                    </td>
                    <td className="py-3 px-4 text-center">
                      <span
                        data-estado={a.is_active ? 'activa' : 'inactiva'}
                        className={`px-3 py-1 text-sm font-semibold rounded-full ${
                          a.is_active ? 'bg-emerald-100 text-emerald-800' : 'bg-gray-200 text-gray-600'
                        }`}>
                        {a.is_active ? 'Activa' : 'Inactiva'}
                      </span>
                    </td>
                    <td className="py-3 px-4">
                      <div className="flex items-center justify-end gap-2">
                        <button
                          onClick={() => { setEditando(a.id); setBorrador(a.name); }}
                          title="Renombrar" aria-label={`Renombrar ${a.name}`}
                          className="p-2 text-gray-500 hover:text-gray-800 hover:bg-gray-100 rounded-lg">
                          <Pencil className="w-5 h-5" />
                        </button>
                        <button
                          onClick={() => alternar(a)}
                          data-testid="alternar-actividad"
                          className="px-3 py-1.5 text-sm font-semibold rounded-lg border border-gray-300 text-gray-600 hover:bg-gray-50">
                          {a.is_active ? 'Desactivar' : 'Activar'}
                        </button>
                        <button
                          onClick={() => borrar(a)}
                          disabled={!!motivo}
                          title={motivo || 'Borrar'}
                          data-testid="borrar-actividad"
                          aria-label={`Borrar ${a.name}`}
                          className="p-2 text-red-600 hover:bg-red-50 rounded-lg disabled:opacity-30 disabled:cursor-not-allowed disabled:hover:bg-transparent">
                          <Trash2 className="w-5 h-5" />
                        </button>
                      </div>
                      {motivo && (
                        <div className="text-xs text-gray-400 text-right mt-1">{motivo}</div>
                      )}
                    </td>
                  </tr>
                );
              })}
              {actividades.length === 0 && (
                <tr><td colSpan={4} className="py-10 text-center text-gray-400 text-lg">
                  Todavía no hay actividades.
                </td></tr>
              )}
            </tbody>
          </table>
        </div>
      )}
    </div>
  );
}
