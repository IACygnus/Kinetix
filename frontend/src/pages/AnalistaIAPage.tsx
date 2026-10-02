/**
 * «Analista IA» — BLOQUE 5 (reporte 148). Contrato del backend: reporte 147.
 *
 *   /performance/analista            la ventana inicial «Nueva prueba»
 *   /performance/analista/:sesionId  la pantalla única: chat a la izquierda y
 *                                    «Ficha del informe» a la derecha
 *
 * La sesión vive en la URL: recargar la página la recupera tal cual.
 * Regla 16: todos los hooks antes de cualquier return.
 */
import { useCallback, useEffect, useState } from 'react';
import { useNavigate, useParams } from 'react-router-dom';
import { AlertOctagon, Pencil, RefreshCcw, ShieldAlert, Sparkles, X } from 'lucide-react';
import { aiConfigAPI, clientsAPI } from '../services/api';
import type { ClientInfo } from '../types';
import LoadingSpinner from '../components/common/LoadingSpinner';
import { AvisoTrasGenerar, PanelIANoDisponible } from '../components/common/AvisoRespaldo';
import type { EstadoIA } from '../components/common/AvisoRespaldo';
import NuevaPrueba, { TIPOS_PRUEBA } from '../components/analista/NuevaPrueba';
import ChatAnalista from '../components/analista/ChatAnalista';
import FichaInforme from '../components/analista/FichaInforme';
import { analistaAPI, codigoError, detalleError } from '../api/analistaApi';
import type { CambiosFicha, ResultadoGenerar, Sesion } from '../api/analistaApi';

const nombreTipo = (t: string) => TIPOS_PRUEBA.find((x) => x.id === t)?.nombre || t;

function CambiarDatos({ sesion, onCerrar, onGuardado }: {
  sesion: Sesion; onCerrar: () => void; onGuardado: (s: Sesion) => void;
}) {
  const [clientes, setClientes] = useState<ClientInfo[]>([]);
  const [clientId, setClientId] = useState(sesion.cliente_id || '');
  const [proyecto, setProyecto] = useState(sesion.proyecto);
  const [tipo, setTipo] = useState(sesion.tipo);
  const [unidad, setUnidad] = useState(sesion.unidad);
  const [guardando, setGuardando] = useState(false);
  const [error, setError] = useState('');
  useEffect(() => { clientsAPI.getMyClients().then(setClientes).catch(() => {}); }, []);
  const guardar = async () => {
    setGuardando(true);
    setError('');
    try {
      onGuardado(await analistaAPI.cambiarPrueba(sesion.id, { proyecto: proyecto.trim(), tipo, client_id: clientId, unidad }));
    } catch (err) {
      setError(detalleError(err, 'No se pudieron guardar los datos.'));
      setGuardando(false);
    }
  };
  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/50 p-4" data-testid="modal-datos">
      <div className="w-full max-w-lg rounded-2xl bg-white p-6 shadow-2xl">
        <div className="mb-4 flex items-center justify-between">
          <h2 className="text-lg font-bold text-gray-900">Cambiar datos de la prueba</h2>
          <button type="button" onClick={onCerrar} className="text-gray-400 hover:text-gray-700"><X className="h-5 w-5" /></button>
        </div>
        <div className="space-y-3 text-sm">
          <label className="block"><span className="font-semibold text-gray-700">Cliente</span>
            <select value={clientId} onChange={(e) => setClientId(e.target.value)} className="mt-1 w-full rounded-lg border border-gray-300 px-3 py-2">
              <option value="">Sin cliente</option>
              {clientes.map((c) => <option key={c.id} value={c.id}>{c.name}</option>)}
              {sesion.cliente_id && !clientes.some((c) => c.id === sesion.cliente_id) && <option value={sesion.cliente_id}>{sesion.cliente}</option>}
            </select>
          </label>
          <label className="block"><span className="font-semibold text-gray-700">Proyecto</span>
            <input value={proyecto} onChange={(e) => setProyecto(e.target.value)} maxLength={255} data-testid="datos-proyecto"
              className="mt-1 w-full rounded-lg border border-gray-300 px-3 py-2" />
          </label>
          <div className="grid grid-cols-2 gap-3">
            <label className="block"><span className="font-semibold text-gray-700">Tipo de prueba</span>
              <select value={tipo} onChange={(e) => setTipo(e.target.value)} className="mt-1 w-full rounded-lg border border-gray-300 px-3 py-2">
                {TIPOS_PRUEBA.map((t) => <option key={t.id} value={t.id}>{t.nombre}</option>)}
              </select>
            </label>
            <label className="block"><span className="font-semibold text-gray-700">Unidad</span>
              <select value={unidad} onChange={(e) => setUnidad(e.target.value)} className="mt-1 w-full rounded-lg border border-gray-300 px-3 py-2">
                <option value="TPS">TPS</option><option value="UVC">UVC</option>
              </select>
            </label>
          </div>
          <p className="text-xs text-gray-500">Los JTL no se cambian aquí: otra prueba es otra conversación («Nueva conversación»).</p>
          {error && <p className="rounded-lg bg-red-50 p-2 text-red-800" role="alert">{error}</p>}
        </div>
        <div className="mt-5 flex justify-end gap-2">
          <button type="button" onClick={onCerrar} className="rounded-lg border border-gray-300 px-4 py-2 text-sm">Cancelar</button>
          <button type="button" onClick={guardar} disabled={guardando || !proyecto.trim()} data-testid="datos-guardar"
            className="rounded-lg bg-indigo-600 px-4 py-2 text-sm font-semibold text-white hover:bg-indigo-700 disabled:opacity-40">Guardar</button>
        </div>
      </div>
    </div>
  );
}

function Conversacion({ sesionId }: { sesionId: string }) {
  const navigate = useNavigate();
  const [sesion, setSesion] = useState<Sesion | null>(null);
  const [noEsTuya, setNoEsTuya] = useState(false);
  const [errorCarga, setErrorCarga] = useState('');
  const [estadoIA, setEstadoIA] = useState<EstadoIA | null>(null);
  const [comprobando, setComprobando] = useState(false);
  const [enviando, setEnviando] = useState(false);
  const [adjuntando, setAdjuntando] = useState(false);
  const [cambiando, setCambiando] = useState(false);
  const [generando, setGenerando] = useState(false);
  const [resaltar, setResaltar] = useState(false);
  const [aviso, setAviso] = useState<{ tipo: 'error' | 'ok'; texto: string } | null>(null);
  const [datos, setDatos] = useState(false);
  const [confirmarSinIA, setConfirmarSinIA] = useState(false);
  const [aceptaSinIA, setAceptaSinIA] = useState(false);
  const [trasGenerar, setTrasGenerar] = useState<ResultadoGenerar | null>(null);

  const comprobarIA = useCallback(async (forzar: boolean) => {
    setComprobando(true);
    try {
      const e: EstadoIA = await aiConfigAPI.estado(forzar);
      setEstadoIA(e);
      return e;
    } catch {
      return null;
    } finally {
      setComprobando(false);
    }
  }, []);

  useEffect(() => {
    setSesion(null);
    setNoEsTuya(false);
    setErrorCarga('');
    analistaAPI.leer(sesionId).then(setSesion).catch((err) => {
      if (codigoError(err) === 404) setNoEsTuya(true);
      else setErrorCarga(detalleError(err, 'No se pudo abrir la conversación.'));
    });
    comprobarIA(false);
  }, [sesionId, comprobarIA]);

  const enviar = async (texto: string): Promise<boolean> => {
    if (!sesion) return false;
    setEnviando(true);
    setAviso(null);
    // El mensaje se ve enseguida; el servidor lo guarda antes de llamar a la IA.
    const provisional = { id: `tmp-${Date.now()}`, rol: 'analista' as const, texto, momento: '', origen: null, pregunta: false, cambios: null, avisos: [] };
    setSesion({ ...sesion, mensajes: [...sesion.mensajes, provisional] });
    try {
      const s = await analistaAPI.mensaje(sesion.id, texto);
      setSesion(s);
      if (s.turno && !s.turno.ok) {
        setAviso({ tipo: 'error', texto: 'La IA no pudo responder. Tu mensaje quedó guardado y la ficha no cambió: vuelve a intentarlo o completa la ficha a mano.' });
      }
      return true;
    } catch (err) {
      setSesion(sesion);
      setAviso({ tipo: 'error', texto: detalleError(err, 'No se pudo enviar el mensaje.') });
      return false;
    } finally {
      setEnviando(false);
    }
  };

  const adjuntar = async (f: File) => {
    if (!sesion) return;
    setAdjuntando(true);
    setAviso(null);
    try {
      const s = await analistaAPI.adjuntar(sesion.id, f);
      setSesion(s);
      const a = s.adjuntos[s.adjuntos.length - 1];
      setAviso({ tipo: 'ok', texto: `Leí «${a.nombre}»: ${a.resumen.errores.toLocaleString('es-CO')} errores. ${a.resumen.cruce.texto}` });
    } catch (err) {
      setAviso({ tipo: 'error', texto: `Adjunto rechazado: ${detalleError(err, 'no se pudo leer el archivo.')}` });
    } finally {
      setAdjuntando(false);
    }
  };

  const cambiar = async (cambios: CambiosFicha) => {
    if (!sesion) return;
    setCambiando(true);
    try {
      setSesion(await analistaAPI.cambiar(sesion.id, cambios));
      setResaltar(false);
    } catch (err) {
      setAviso({ tipo: 'error', texto: detalleError(err, 'No se pudo cambiar la ficha.') });
    } finally {
      setCambiando(false);
    }
  };

  const generarYa = async () => {
    if (!sesion) return;
    setConfirmarSinIA(false);
    setAviso(null);
    setGenerando(true);
    try {
      const r = await analistaAPI.generar(sesion.id);
      setSesion(r.sesion);
      if (r.resultado === 'faltan_criterios') {
        setResaltar(true);
        setGenerando(false);
        return;
      }
      if (r.ai_status) sessionStorage.setItem('ai_status', JSON.stringify(r.ai_status));
      if ((r.ai_status?.respaldo || 0) > 0) {
        setGenerando(false);
        setTrasGenerar(r);
        return;
      }
      navigate(`/performance/report/${r.execution_id}`);
    } catch (err) {
      setAviso({ tipo: 'error', texto: detalleError(err, 'No se pudo generar el informe.') });
      setGenerando(false);
    }
  };

  const generar = async () => {
    if (!sesion) return;
    // Sin criterios no hace falta mirar la IA: el servidor no genera y la pide en el chat.
    if (sesion.ficha.criterios.estado !== 'sin_declarar') {
      const e = await comprobarIA(true);   // F2: sin caché, justo antes de generar
      if (e && !e.ok && !aceptaSinIA) {
        setConfirmarSinIA(true);
        return;
      }
    }
    generarYa();
  };

  if (noEsTuya) {
    return (
      <div className="flex min-h-[calc(100vh-8rem)] items-center justify-center bg-gray-100 p-6">
        <div className="max-w-lg rounded-2xl border-2 border-red-300 bg-white p-8 text-center shadow-lg" role="alert" data-testid="sesion-no-tuya">
          <AlertOctagon className="mx-auto mb-3 h-10 w-10 text-red-600" />
          <h2 className="text-xl font-bold text-gray-900">Esta conversación no existe o no es tuya</h2>
          <p className="mt-2 text-sm text-gray-600">Cada analista ve solo sus propias conversaciones.</p>
          <button type="button" onClick={() => navigate('/performance/analista')}
            className="mt-5 rounded-lg bg-indigo-600 px-5 py-2 text-sm font-semibold text-white hover:bg-indigo-700">Empezar una nueva</button>
        </div>
      </div>
    );
  }
  if (errorCarga) {
    return <div className="p-6"><p className="rounded-lg bg-red-50 p-4 text-red-800" role="alert">{errorCarga}</p></div>;
  }
  if (!sesion) {
    return <div className="flex min-h-[50vh] items-center justify-center text-gray-500">Abriendo la conversación…</div>;
  }

  const n = sesion.jtl.length;
  return (
    <div className="flex h-[calc(100vh-8rem)] flex-col bg-gray-100" data-testid="analista-conversacion">
      {generando && sesion.ficha.criterios.estado !== 'sin_declarar' && (
        <LoadingSpinner message={`Procesando ${n} archivo(s) JTL y generando análisis...`} />
      )}
      {trasGenerar && (
        <AvisoTrasGenerar aiStatus={trasGenerar.ai_status || {}} onVer={() => navigate(`/performance/report/${trasGenerar.execution_id}`)} />
      )}
      {datos && <CambiarDatos sesion={sesion} onCerrar={() => setDatos(false)} onGuardado={(s) => { setSesion(s); setDatos(false); }} />}
      {confirmarSinIA && estadoIA && (
        <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/50 p-4">
          <div className="w-full max-w-3xl">
            <PanelIANoDisponible estado={estadoIA} aceptado={aceptaSinIA} onAceptar={setAceptaSinIA}
              onRecomprobar={async () => { const e = await comprobarIA(true); if (e?.ok) { setConfirmarSinIA(false); } }}
              comprobando={comprobando} onSubirSinIA={generarYa} />
            <button type="button" onClick={() => setConfirmarSinIA(false)} className="mt-2 text-sm text-white underline">Volver a la conversación</button>
          </div>
        </div>
      )}

      {/* Cabecera */}
      <div className="flex items-center justify-between border-b border-gray-200 bg-white px-6 py-3">
        <div className="flex min-w-0 items-center gap-3">
          <div className="flex h-10 w-10 flex-shrink-0 items-center justify-center rounded-xl bg-indigo-600 text-white"><Sparkles className="h-5 w-5" /></div>
          <div className="min-w-0">
            <h1 className="truncate text-xl font-bold text-gray-900" data-testid="cabecera-titulo">
              {sesion.cliente ? `${sesion.cliente} · ` : ''}{sesion.proyecto}
            </h1>
            <p className="truncate text-sm text-gray-500">
              Analista IA · {nombreTipo(sesion.tipo)} · {sesion.unidad} · {sesion.jtl.join(', ')}
            </p>
          </div>
        </div>
        <div className="flex flex-shrink-0 items-center gap-2">
          <button type="button" onClick={() => setDatos(true)} disabled={sesion.estado !== 'abierta'} data-testid="cabecera-cambiar"
            className="inline-flex items-center gap-2 rounded-lg border border-indigo-300 bg-white px-3 py-2 text-sm font-medium text-indigo-700 hover:bg-indigo-50 disabled:opacity-40">
            <Pencil className="h-4 w-4" /> Cambiar datos de la prueba
          </button>
          <button type="button" onClick={() => navigate('/performance/analista')} data-testid="cabecera-nueva"
            className="inline-flex items-center gap-2 rounded-lg border border-gray-300 px-3 py-2 text-sm font-medium text-gray-700 hover:bg-gray-50">
            <RefreshCcw className="h-4 w-4" /> Nueva conversación
          </button>
        </div>
      </div>

      {estadoIA && !estadoIA.ok && (
        <div className="flex items-start gap-2 border-b border-red-300 bg-red-50 px-6 py-2 text-sm text-red-800" role="alert" data-testid="ia-caida">
          <ShieldAlert className="mt-0.5 h-4 w-4 flex-shrink-0" />
          <span>
            <b>La IA no está disponible</b>{estadoIA.motivo_frase ? `: ${estadoIA.motivo_frase}` : ''}. Puedes seguir llenando la
            ficha a mano; el chat no podrá responder hasta que vuelva.
          </span>
        </div>
      )}

      <div className="grid min-h-0 flex-1 grid-cols-1 lg:grid-cols-[2fr_3fr]">
        <div className="min-h-0 border-r border-gray-200">
          <ChatAnalista mensajes={sesion.mensajes} enviando={enviando} adjuntando={adjuntando}
            deshabilitado={sesion.estado !== 'abierta'} aviso={aviso} onCerrarAviso={() => setAviso(null)}
            onEnviar={enviar} onAdjuntar={adjuntar} />
        </div>
        <div className="min-h-0 overflow-y-auto p-4">
          <FichaInforme sesion={sesion} ocupado={cambiando || enviando} generando={generando}
            resaltarCriterios={resaltar} onCambiar={cambiar} onGenerar={generar} />
        </div>
      </div>
    </div>
  );
}

export default function AnalistaIAPage() {
  const { sesionId } = useParams();
  const navigate = useNavigate();
  if (sesionId) return <Conversacion sesionId={sesionId} />;
  return (
    <NuevaPrueba
      onCreada={(s) => navigate(`/performance/analista/${s.id}`)}
      onAbrir={(id) => navigate(`/performance/analista/${id}`)}
    />
  );
}
