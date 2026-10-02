/**
 * «Analista IA» — la FICHA DEL INFORME (BLOQUE 5).
 *
 * Lo que sale del JTL (cifras, fases, resultados de los criterios) solo se
 * muestra: lo calcula el servidor. Lo que es del analista (casillas, relato,
 * criterios que quita, confirmaciones, pendientes que descarta) se cambia por
 * PATCH con `onCambiar`.
 *
 * Regla 16: todos los hooks antes de cualquier return.
 */
import { useState } from 'react';
import {
  AlertTriangle, CheckCircle2, ClipboardList, FileWarning, FlaskConical, ListChecks, Loader2,
  MessageSquare, Pencil, Target, X, Zap,
} from 'lucide-react';
import type { CambiosFicha, Criterio, EstadoResultado, Sesion } from '../../api/analistaApi';
import MiniGrafico from './MiniGrafico';

const RESULTADO: Record<EstadoResultado, { nombre: string; clase: string }> = {
  cumple: { nombre: 'Cumple', clase: 'bg-green-100 text-green-800 border-green-300' },
  no_cumple: { nombre: 'No cumple', clase: 'bg-red-100 text-red-800 border-red-300' },
  no_evaluado: { nombre: 'No evaluado', clase: 'bg-gray-100 text-gray-700 border-gray-300' },
  lo_confirma_el_analista: { nombre: 'Lo confirma el analista', clase: 'bg-amber-100 text-amber-800 border-amber-300' },
};

const num = (v: number, d = 0) => v.toLocaleString('es-CO', { minimumFractionDigits: d, maximumFractionDigits: d });

function Tarjeta({ titulo, icono, hecho, rojo, ambar, children, testid, extra }: {
  titulo: string; icono: React.ReactNode; hecho?: boolean; rojo?: boolean; ambar?: boolean;
  children: React.ReactNode; testid: string; extra?: React.ReactNode;
}) {
  const borde = rojo ? 'border-red-400 ring-2 ring-red-200' : ambar ? 'border-amber-300' : 'border-gray-200';
  return (
    <section className={`rounded-xl border bg-white p-4 shadow-sm ${borde}`} data-testid={testid}>
      <div className="mb-3 flex items-center justify-between gap-2">
        <h3 className="flex items-center gap-2 text-sm font-semibold text-gray-800">
          {icono}{titulo}
          {hecho && <CheckCircle2 className="h-4 w-4 text-green-600" aria-label="listo" />}
        </h3>
        {extra}
      </div>
      {children}
    </section>
  );
}

function CriterioFila({ c, ocupado, onCambiar }: { c: Criterio; ocupado: boolean; onCambiar: (x: CambiosFicha) => void }) {
  const r = RESULTADO[c.resultado?.estado] || RESULTADO.no_evaluado;
  const donde = c.alcance.tipo === 'transaccion' ? `«${c.alcance.transaccion}»`
    : c.alcance.tipo === 'cada_transaccion' ? 'cada transacción' : 'toda la prueba';
  return (
    <li className="rounded-lg border border-gray-200 p-3" data-testid="criterio">
      <div className="flex items-start justify-between gap-2">
        <p className="text-sm text-gray-900">«{c.texto}» <span className="text-xs text-gray-500">· {donde}</span></p>
        <button type="button" disabled={ocupado} onClick={() => onCambiar({ criterios: { quitar: [c.id] } })}
          className="text-gray-400 hover:text-red-600 disabled:opacity-40" title="Quitar el criterio" data-testid="criterio-quitar">
          <X className="h-4 w-4" />
        </button>
      </div>
      <div className="mt-1.5 flex flex-wrap items-center gap-2">
        <span className={`rounded-full border px-2 py-0.5 text-xs font-semibold ${r.clase}`} data-testid="criterio-resultado">{r.nombre}</span>
        <span className="text-xs text-gray-600">{c.resultado?.texto || c.resultado?.motivo}</span>
      </div>
      {c.resultado?.texto && c.resultado?.motivo && <p className="mt-1 text-xs text-gray-500">{c.resultado.motivo}</p>}
      {c.resultado?.nota && <p className="mt-1 text-xs text-gray-500">{c.resultado.nota}</p>}
      {c.resultado?.estado === 'lo_confirma_el_analista' && (
        <div className="mt-2 flex items-center gap-2 text-xs">
          <span className="text-gray-600">¿Se cumplió?</span>
          {(['cumple', 'no_cumple'] as const).map((v) => (
            <button key={v} type="button" disabled={ocupado}
              onClick={() => onCambiar({ criterios: { editar: [{ id: c.id, confirmacion: c.confirmacion === v ? null : v }] } })}
              className={`rounded-md border px-2 py-0.5 ${c.confirmacion === v ? 'border-indigo-600 bg-indigo-600 text-white' : 'border-gray-300 hover:bg-gray-50'}`}>
              {v === 'cumple' ? 'Sí, cumple' : 'No cumple'}
            </button>
          ))}
        </div>
      )}
    </li>
  );
}

export default function FichaInforme({ sesion, ocupado, generando, resaltarCriterios, onCambiar, onGenerar }: {
  sesion: Sesion;
  ocupado: boolean;
  generando: boolean;
  resaltarCriterios: boolean;
  onCambiar: (cambios: CambiosFicha) => void;
  onGenerar: () => void;
}) {
  const [editando, setEditando] = useState<{ id: string; texto: string } | null>(null);
  const f = sesion.ficha;
  const l = f.listo;
  const crit = f.criterios;
  const sinDeclarar = crit.estado === 'sin_declarar';
  const faltan = l.obligatorios.total - l.obligatorios.listos;
  const opcionalesPendientes = f.pendientes.filter((p) => !p.obligatorio && p.estado === 'pendiente');
  const conInforme = f.transacciones.filter((t) => t.informe).length;
  const fases = f.fases.texto.includes(':') ? f.fases.texto.slice(f.fases.texto.indexOf(':') + 1).trim() : f.fases.texto;
  const abierta = sesion.estado === 'abierta';

  return (
    <div className="space-y-3" data-testid="ficha">
      {/* Cabecera: el contador y generar */}
      <section className="rounded-xl border border-gray-200 bg-white p-4 shadow-sm">
        <div className="flex items-center justify-between gap-3">
          <div>
            <h2 className="text-lg font-bold text-gray-900">Ficha del informe</h2>
            <p className={`text-sm font-semibold ${l.puede_generar ? 'text-green-700' : 'text-red-700'}`} data-testid="ficha-listo">
              {l.puede_generar ? `Listo para generar: ${l.n} de ${l.m}`
                : `Falta${faltan === 1 ? '' : 'n'} ${faltan} dato${faltan === 1 ? '' : 's'} obligatorio${faltan === 1 ? '' : 's'}`}
            </p>
          </div>
          <button type="button" onClick={onGenerar} disabled={!abierta || generando} data-testid="ficha-generar"
            className="inline-flex items-center gap-2 rounded-lg bg-sqa-gold px-5 py-2.5 text-sm font-bold text-sqa-navy shadow hover:bg-sqa-gold-light disabled:cursor-not-allowed disabled:opacity-50">
            {generando ? <Loader2 className="h-4 w-4 animate-spin" /> : <Zap className="h-4 w-4" />}
            Generar informe
          </button>
        </div>
        <div className="mt-3 h-2 w-full overflow-hidden rounded-full bg-gray-200" aria-label="avance">
          <div className={`h-full rounded-full ${l.puede_generar ? 'bg-green-500' : 'bg-red-400'}`}
            style={{ width: `${l.m ? Math.round((100 * l.n) / l.m) : 0}%` }} />
        </div>
        <p className="mt-1 text-xs text-gray-500">
          Obligatorios {l.obligatorios.listos} de {l.obligatorios.total} · opcionales {l.opcionales.listos} de {l.opcionales.total}
        </p>
      </section>

      {/* La prueba */}
      <Tarjeta titulo="La prueba" icono={<FlaskConical className="h-4 w-4 text-indigo-600" />} hecho testid="tarjeta-prueba">
        <div className="grid grid-cols-3 gap-2 text-center text-xs sm:grid-cols-6">
          {[
            ['Peticiones', num(f.cifras.peticiones)],
            ['Errores', `${num(f.cifras.tasa_error, 2)} %`],
            ['P90', `${num(f.cifras.p90_ms)} ms`],
            ['Promedio', `${num(f.cifras.promedio_ms)} ms`],
            ['Duración', `${num(f.cifras.duracion_s / 60, 1)} min`],
            ['Usuarios', f.fases.max_usuarios != null ? num(f.fases.max_usuarios) : '—'],
          ].map(([k, v]) => (
            <div key={k} className="rounded-lg bg-gray-50 px-2 py-1.5">
              <div className="text-gray-500">{k}</div>
              <div className="text-sm font-semibold text-gray-900">{v}</div>
            </div>
          ))}
        </div>
        <div className="mt-3"><MiniGrafico ficha={f} /></div>
        <p className="mt-1 text-xs text-gray-600"><b>Fases:</b> {fases} <span className="text-gray-400">(sombreado: subida y bajada)</span></p>
        {f.fallos.total > 0 && f.fallos.concentracion && (
          <p className="mt-1 text-xs text-gray-600"><b>Fallos:</b> {f.fallos.concentracion}</p>
        )}
      </Tarjeta>

      {/* Criterios */}
      <Tarjeta titulo="Criterios de aceptación" icono={<Target className={`h-4 w-4 ${sinDeclarar ? 'text-red-600' : 'text-indigo-600'}`} />}
        hecho={!sinDeclarar} rojo={sinDeclarar} testid="tarjeta-criterios"
        extra={sinDeclarar ? <span className={`rounded-full bg-red-600 px-2 py-0.5 text-xs font-bold text-white ${resaltarCriterios ? 'animate-pulse' : ''}`}>obligatorio</span> : undefined}>
        {sinDeclarar && (
          <div className="space-y-2">
            <p className="text-sm text-red-800">
              Aún no hay criterios. Cuéntaselos a la IA en el chat con tus palabras (tiempos, errores, usuarios o, si es un
              proceso, cuántos registros en cuánto tiempo).
            </p>
            <button type="button" disabled={ocupado || !abierta} data-testid="criterios-ninguno"
              onClick={() => onCambiar({ criterios: { ninguno_acordado: true } })}
              className="rounded-lg border border-red-300 bg-white px-3 py-1.5 text-xs font-semibold text-red-700 hover:bg-red-50 disabled:opacity-40">
              No se acordó ninguno
            </button>
          </div>
        )}
        {crit.estado === 'no_hay_criterios_acordados' && (
          <div className="flex items-center justify-between gap-2 text-sm text-gray-700">
            <span>No se acordaron criterios: el informe no dirá si cumple o no.</span>
            <button type="button" disabled={ocupado || !abierta} onClick={() => onCambiar({ criterios: { ninguno_acordado: false } })}
              className="text-xs font-semibold text-indigo-700 hover:underline disabled:opacity-40">Deshacer</button>
          </div>
        )}
        {crit.lista.length > 0 && (
          <ul className="space-y-2">
            {crit.lista.map((c) => <CriterioFila key={c.id} c={c} ocupado={ocupado || !abierta} onCambiar={onCambiar} />)}
          </ul>
        )}
      </Tarjeta>

      {/* Lo que contaste */}
      <Tarjeta titulo="Lo que contaste" icono={<MessageSquare className="h-4 w-4 text-indigo-600" />}
        hecho={f.relato.length > 0 || !!f.contexto.ambiente || !!f.contexto.version} testid="tarjeta-relato">
        <p className="text-xs text-gray-600">
          <b>Ambiente:</b> {f.contexto.ambiente || '—'} · <b>Versión:</b> {f.contexto.version || '—'}
        </p>
        {f.relato.length === 0 ? (
          <p className="mt-2 text-xs text-gray-400">Lo que le cuentes a la IA sobre la prueba aparecerá aquí.</p>
        ) : (
          <ul className="mt-2 space-y-1.5">
            {f.relato.map((r) => (
              <li key={r.id} className="flex items-start gap-2 text-sm text-gray-800" data-testid="relato-linea">
                {editando?.id === r.id ? (
                  <form className="flex flex-1 gap-1" onSubmit={(e) => {
                    e.preventDefault();
                    if (editando.texto.trim()) onCambiar({ relato: { editar: [{ id: r.id, texto: editando.texto.trim() }] } });
                    setEditando(null);
                  }}>
                    <input autoFocus value={editando.texto} maxLength={500}
                      onChange={(e) => setEditando({ id: r.id, texto: e.target.value })}
                      className="flex-1 rounded border border-gray-300 px-2 py-0.5 text-sm" />
                    <button type="submit" className="text-xs font-semibold text-indigo-700">Guardar</button>
                  </form>
                ) : (
                  <>
                    <span className="flex-1">• {r.texto}</span>
                    <button type="button" disabled={ocupado || !abierta} onClick={() => setEditando({ id: r.id, texto: r.texto })}
                      className="text-gray-400 hover:text-indigo-600 disabled:opacity-40" title="Editar"><Pencil className="h-3.5 w-3.5" /></button>
                    <button type="button" disabled={ocupado || !abierta} onClick={() => onCambiar({ relato: { quitar: [r.id] } })}
                      className="text-gray-400 hover:text-red-600 disabled:opacity-40" title="Quitar"><X className="h-3.5 w-3.5" /></button>
                  </>
                )}
              </li>
            ))}
          </ul>
        )}
      </Tarjeta>

      {/* Detalle de errores */}
      {sesion.adjuntos.length > 0 && (
        <Tarjeta titulo="Detalle de errores" icono={<FileWarning className="h-4 w-4 text-indigo-600" />} hecho testid="tarjeta-errores">
          <div className="space-y-3">
            {sesion.adjuntos.map((a) => (
              <div key={a.id} className="text-xs" data-testid="adjunto">
                <p className="font-semibold text-gray-800">{a.nombre} · {num(a.resumen.errores)} errores en {num(a.resumen.grupos_total)} grupos</p>
                <p className={`mt-0.5 ${a.resumen.cruce.cuadra ? 'text-green-700' : 'text-amber-700'}`} data-testid="adjunto-cruce">
                  {a.resumen.cruce.texto}
                </p>
                <ul className="mt-1 space-y-0.5 text-gray-600">
                  {a.resumen.grupos.slice(0, 4).map((g, i) => (
                    <li key={i}>«{g.transaccion}» · {g.codigo || 'sin código'} · {num(g.recuento)} ({num(g.porcentaje, 1)} %) · {g.mensaje}</li>
                  ))}
                </ul>
              </div>
            ))}
          </div>
        </Tarjeta>
      )}

      {/* Transacciones con informe propio */}
      <Tarjeta titulo={`Transacciones con informe propio (${conInforme})`} icono={<ListChecks className="h-4 w-4 text-indigo-600" />}
        hecho testid="tarjeta-transacciones">
        <p className="mb-2 text-xs text-gray-500">
          {crit.estado === 'declarados' ? 'Marcadas solas: las críticas según tus criterios.' : 'Marcadas solas: las que tienen errores.'} Puedes cambiarlas.
          {conInforme > f.transacciones_tope && ` Se generan las ${f.transacciones_tope} primeras.`}
        </p>
        <ul className="space-y-1">
          {f.transacciones.map((t) => (
            <li key={t.label}>
              <label className="flex cursor-pointer items-center gap-2 text-sm" title={t.motivo || ''}>
                <input type="checkbox" checked={t.informe} disabled={ocupado || !abierta} data-testid="tx-casilla"
                  onChange={(e) => onCambiar({ transacciones: { [t.label]: e.target.checked } })}
                  className="h-4 w-4 accent-indigo-600" />
                <span className="flex-1 truncate">{t.label}</span>
                {t.errores > 0 && <span className="text-xs text-red-700">{num(t.errores)} err.</span>}
                {t.critica && <span className="rounded bg-red-100 px-1.5 text-xs font-semibold text-red-700">crítica</span>}
              </label>
            </li>
          ))}
        </ul>
      </Tarjeta>

      {/* Pendientes opcionales, en ámbar */}
      {opcionalesPendientes.length > 0 && (
        <Tarjeta titulo="Opcional: si lo sabes, mejora el informe" icono={<AlertTriangle className="h-4 w-4 text-amber-600" />}
          ambar testid="tarjeta-pendientes">
          <ul className="space-y-1.5">
            {opcionalesPendientes.map((p) => (
              <li key={p.id} className="flex items-start justify-between gap-2 rounded-lg bg-amber-50 px-3 py-2 text-sm text-amber-900" data-testid="pendiente">
                <span>{p.pregunta}</span>
                <button type="button" disabled={ocupado || !abierta} onClick={() => onCambiar({ pendientes: { descartar: [p.id] } })}
                  className="flex-shrink-0 text-xs font-semibold text-amber-800 hover:underline disabled:opacity-40">Sigue sin eso</button>
              </li>
            ))}
          </ul>
        </Tarjeta>
      )}

      {sesion.estado === 'generada' && sesion.execution_id && (
        <p className="flex items-center gap-2 text-sm text-green-800"><ClipboardList className="h-4 w-4" />Esta conversación ya generó su informe.</p>
      )}
    </div>
  );
}
