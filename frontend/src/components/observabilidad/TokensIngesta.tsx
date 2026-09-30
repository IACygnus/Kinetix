/**
 * Los tokens de ingesta del agente y la conexión con InfluxDB — ETAPA O2e.4a.
 *
 * Dos piezas, porque son de dueños distintos:
 *
 *   - `TokensIngesta`: los tokens de UN cliente. Con ellos escriben sus
 *     agentes en `POST /api/v1/ingesta` (O-D49).
 *   - `ConexionInflux`: si Kinetix tiene cargado el token con el que escribe
 *     en el cubo `infra`. Es de Kinetix, no de un cliente.
 *
 * **El token de ingesta se ve UNA vez**, en el modal del alta, y solo vive en
 * el estado de este componente mientras el modal está abierto. Al pulsar «Ya
 * lo copié» se pone a `null`: no pasa por ningún store, caché, localStorage ni
 * consola, y no queda ningún elemento en la página que lo contenga. El modal
 * no se cierra con Escape ni pinchando fuera: perder el token por un gesto sin
 * querer obligaría a revocarlo y crear otro.
 *
 * Los revocados se ven, no se esconden: son la constancia de que existieron.
 */
import { useCallback, useEffect, useState } from 'react';
import { Check, Copy, KeyRound, Loader2, Plus, ShieldOff } from 'lucide-react';
import { ingestaAPI } from '../../services/api';
import type { EstadoTokenEscritura, TokenIngesta } from '../../services/api';

const BOTON = 'min-h-[44px] inline-flex items-center justify-center gap-2 rounded-xl font-semibold transition';
const CAMPO = 'w-full min-h-[44px] px-3 text-lg border border-gray-300 rounded-xl';

const AVISO_REVOCAR =
  'Los servidores que usan este token dejan de enviar en el acto. No se puede deshacer.';

/** El backend guarda en UTC y sin zona: se le añade para mostrarla en local. */
function fecha(valor: string): string {
  const d = new Date(/[zZ]|[+-]\d\d:\d\d$/.test(valor) ? valor : `${valor}Z`);
  return d.toLocaleString('es-CO', { dateStyle: 'medium', timeStyle: 'short' });
}

/** Activos primero; dentro de cada grupo, el más reciente arriba. */
function ordenar(tokens: TokenIngesta[]): TokenIngesta[] {
  return [...tokens].sort((a, b) => {
    const activoA = a.revocado_en ? 1 : 0;
    const activoB = b.revocado_en ? 1 : 0;
    if (activoA !== activoB) return activoA - activoB;
    return b.creado_en.localeCompare(a.creado_en);
  });
}

function mensajeDeError(e: unknown, porDefecto: string): string {
  const r = e as { response?: { data?: { detail?: string } } };
  return r.response?.data?.detail || porDefecto;
}

// ===========================================================================
// Los tokens de un cliente
// ===========================================================================
interface Props {
  clienteId: string;
  clienteNombre: string;
  esAdmin: boolean;
}

export function TokensIngesta({ clienteId, clienteNombre, esAdmin }: Props) {
  const [tokens, setTokens] = useState<TokenIngesta[]>([]);
  const [cargando, setCargando] = useState(true);
  const [error, setError] = useState('');
  const [creando, setCreando] = useState(false);
  const [revocando, setRevocando] = useState('');
  // Solo mientras el modal está abierto. Ver la cabecera.
  const [nuevo, setNuevo] = useState<{ token: string; aviso: string } | null>(null);
  const [copiado, setCopiado] = useState(false);

  const cargar = useCallback(async () => {
    setCargando(true);
    try {
      setTokens(ordenar(await ingestaAPI.listar(clienteId)));
      setError('');
    } catch {
      setError('No se pudo cargar la lista de tokens.');
    } finally {
      setCargando(false);
    }
  }, [clienteId]);

  useEffect(() => { void cargar(); }, [cargar]);

  const crear = async () => {
    setCreando(true);
    setError('');
    try {
      const r = await ingestaAPI.crear(clienteId);
      setCopiado(false);
      setNuevo({ token: r.token, aviso: r.aviso });
      await cargar();
    } catch (e) {
      setError(mensajeDeError(e, 'No se pudo crear el token.'));
    } finally {
      setCreando(false);
    }
  };

  const copiar = () => {
    if (!nuevo) return;
    void navigator.clipboard.writeText(nuevo.token);
    setCopiado(true);
  };

  const cerrarModal = () => {
    setNuevo(null);
    setCopiado(false);
  };

  const revocar = async (t: TokenIngesta) => {
    if (!window.confirm(`¿Revocar el token ${t.prefijo}…?\n\n${AVISO_REVOCAR}`)) return;
    setRevocando(t.id);
    setError('');
    try {
      await ingestaAPI.revocar(t.id);
      await cargar();
    } catch (e) {
      setError(mensajeDeError(e, 'No se pudo revocar el token.'));
    } finally {
      setRevocando('');
    }
  };

  return (
    <div className="bg-white rounded-2xl border border-gray-200 shadow-sm p-5 mb-6"
      data-testid="ing-bloque">
      <div className="flex items-start justify-between gap-4 flex-wrap mb-3">
        <div>
          <h2 className="text-xl font-bold text-gray-800 flex items-center gap-2">
            <KeyRound className="w-6 h-6 text-[#f5a623]" /> Token de ingesta
          </h2>
          <p className="text-base text-gray-500 mt-1">
            Con él escriben sus métricas los agentes de <strong>{clienteNombre}</strong>.
            Solo acepta métricas de este cliente.
          </p>
        </div>
        {esAdmin && (
          <button onClick={crear} disabled={creando} data-testid="ing-crear"
            className={`${BOTON} px-5 bg-[#f5a623] text-[#0a1628] hover:bg-[#f7b84a] disabled:opacity-40`}>
            {creando ? <Loader2 className="w-5 h-5 animate-spin" /> : <Plus className="w-5 h-5" />}
            Crear token
          </button>
        )}
      </div>

      {error && (
        <p className="mb-3 p-3 rounded-xl bg-red-50 border border-red-300 text-base text-red-800"
          data-testid="ing-error">{error}</p>
      )}

      {cargando ? (
        <div className="py-6 text-center text-gray-400">
          <Loader2 className="w-6 h-6 animate-spin mx-auto" />
        </div>
      ) : tokens.length === 0 ? (
        <p className="py-4 text-base text-gray-500" data-testid="ing-vacio">
          Este cliente no tiene tokens de ingesta todavía.
        </p>
      ) : (
        <div className="overflow-x-auto">
          <table className="w-full text-base" data-testid="ing-lista">
            <thead>
              <tr className="text-left text-gray-500 border-b border-gray-200">
                <th className="py-2 pr-4 font-semibold">Token</th>
                <th className="py-2 pr-4 font-semibold">Creado</th>
                <th className="py-2 pr-4 font-semibold">Último uso</th>
                <th className="py-2 pr-4 font-semibold">Estado</th>
                {esAdmin && <th className="py-2" />}
              </tr>
            </thead>
            <tbody>
              {tokens.map((t) => (
                <tr key={t.id} data-testid={`ing-fila-${t.prefijo}`}
                  className="border-b border-gray-100 last:border-0">
                  <td className="py-2 pr-4 font-mono text-gray-500" data-testid="ing-prefijo">
                    {t.prefijo}…
                  </td>
                  <td className="py-2 pr-4 tabular-nums">{fecha(t.creado_en)}</td>
                  <td className="py-2 pr-4 tabular-nums">
                    {t.ultimo_uso ? fecha(t.ultimo_uso) : <span className="text-gray-400">nunca</span>}
                  </td>
                  <td className="py-2 pr-4" data-testid="ing-estado">
                    {t.revocado_en ? (
                      <span className="text-gray-500">revocado el {fecha(t.revocado_en)}</span>
                    ) : (
                      <span className="text-emerald-700 font-semibold">activo</span>
                    )}
                  </td>
                  {esAdmin && (
                    <td className="py-2 text-right">
                      {!t.revocado_en && (
                        <button onClick={() => revocar(t)} disabled={revocando === t.id}
                          data-testid={`ing-revocar-${t.prefijo}`}
                          className={`${BOTON} px-4 border border-red-300 text-red-700 hover:bg-red-50 disabled:opacity-40`}>
                          {revocando === t.id
                            ? <Loader2 className="w-5 h-5 animate-spin" />
                            : <ShieldOff className="w-5 h-5" />}
                          Revocar
                        </button>
                      )}
                    </td>
                  )}
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}

      {/* ========== El token, UNA vez. Sin cierre por Escape ni por fuera ========== */}
      {nuevo && (
        <div className="fixed inset-0 bg-black/40 flex items-start justify-center p-4 overflow-auto z-50">
          <div className="bg-white rounded-2xl shadow-xl max-w-2xl w-full my-8 p-6"
            role="dialog" aria-modal="true" aria-labelledby="ing-modal-titulo"
            data-testid="ing-modal">
            <h2 id="ing-modal-titulo" className="text-2xl font-bold text-gray-800 mb-4">
              Token de ingesta de {clienteNombre}
            </h2>
            <p className="mb-4 p-4 rounded-xl bg-amber-50 border border-amber-300 text-base text-amber-900"
              data-testid="ing-aviso">
              {nuevo.aviso}
            </p>
            <pre className="p-4 rounded-xl bg-[#0a1628] text-gray-100 text-base font-mono break-all whitespace-pre-wrap"
              data-testid="ing-token">{nuevo.token}</pre>
            <div className="flex justify-end gap-3 mt-5 flex-wrap">
              <button onClick={copiar} data-testid="ing-copiar"
                className={`${BOTON} px-5 bg-[#0a1628] text-white hover:bg-[#16243c]`}>
                {copiado ? <Check className="w-5 h-5" /> : <Copy className="w-5 h-5" />}
                {copiado ? 'Copiado' : 'Copiar'}
              </button>
              <button onClick={cerrarModal} data-testid="ing-ya-copie"
                className={`${BOTON} px-5 bg-[#f5a623] text-[#0a1628] hover:bg-[#f7b84a]`}>
                Ya lo copié
              </button>
            </div>
          </div>
        </div>
      )}
    </div>
  );
}

// ===========================================================================
// La conexión de Kinetix con InfluxDB (cubo infra)
// ===========================================================================
export function ConexionInflux({ esAdmin }: { esAdmin: boolean }) {
  const [estado, setEstado] = useState<EstadoTokenEscritura | null>(null);
  const [fallo, setFallo] = useState(false);
  const [editando, setEditando] = useState(false);
  const [valor, setValor] = useState('');
  const [guardando, setGuardando] = useState(false);
  const [error, setError] = useState('');

  const cargar = useCallback(async () => {
    try {
      setEstado(await ingestaAPI.estadoEscritura());
      setFallo(false);
    } catch {
      setFallo(true);
    }
  }, []);

  useEffect(() => { void cargar(); }, [cargar]);

  const cancelar = () => {
    setValor('');
    setEditando(false);
    setError('');
  };

  const guardar = async () => {
    setGuardando(true);
    setError('');
    try {
      await ingestaAPI.cargarEscritura(valor.trim());
      cancelar();
      await cargar();
    } catch (e) {
      // El campo se vacía también si falla: el token no se queda en pantalla.
      setValor('');
      setError(mensajeDeError(e, 'No se pudo guardar el token.'));
    } finally {
      setGuardando(false);
    }
  };

  return (
    <div className="bg-white rounded-2xl border border-gray-200 shadow-sm p-5 mb-6"
      data-testid="inf-linea">
      <div className="flex items-center justify-between gap-4 flex-wrap">
        <p className="text-base text-gray-700">
          <span className="font-semibold">Conexión con InfluxDB (cubo infra)</span>
          {' · '}Token de escritura cargado:{' '}
          <span data-testid="inf-estado" className={
            estado?.hay_token ? 'font-semibold text-emerald-700' : 'font-semibold text-amber-700'}>
            {fallo ? 'no se pudo consultar' : estado === null ? '…' : estado.hay_token ? 'sí' : 'no'}
          </span>
          {estado && !estado.columna_aplicada && (
            <span className="text-gray-500"> (falta aplicar {estado.sql})</span>
          )}
        </p>
        {esAdmin && !editando && (
          <button onClick={() => setEditando(true)} data-testid="inf-cargar"
            className={`${BOTON} px-4 border border-gray-300 hover:bg-gray-50`}>
            Cargar
          </button>
        )}
      </div>

      {esAdmin && editando && (
        <div className="flex gap-3 mt-3 flex-wrap items-center">
          <input type="password" value={valor} autoComplete="off" data-testid="inf-campo"
            onChange={(e) => setValor(e.target.value)}
            placeholder="Token de escritura del cubo infra"
            className={`${CAMPO} max-w-md`} />
          <button onClick={guardar} disabled={guardando || !valor.trim()} data-testid="inf-guardar"
            className={`${BOTON} px-5 bg-[#f5a623] text-[#0a1628] hover:bg-[#f7b84a] disabled:opacity-40`}>
            {guardando ? <Loader2 className="w-5 h-5 animate-spin" /> : <Check className="w-5 h-5" />}
            Guardar
          </button>
          <button onClick={cancelar} data-testid="inf-cancelar"
            className={`${BOTON} px-5 border border-gray-300 hover:bg-gray-50`}>
            Cancelar
          </button>
        </div>
      )}
      {error && (
        <p className="mt-3 p-3 rounded-xl bg-red-50 border border-red-300 text-base text-red-800"
          data-testid="inf-error">{error}</p>
      )}
    </div>
  );
}
