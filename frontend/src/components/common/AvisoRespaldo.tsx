/**
 * F2 (aviso de respaldo) — que Kinetix diga con todas las letras cuándo un
 * texto del informe NO lo escribió la IA, y por qué.
 *
 * Nace del 26-28 de septiembre de 2026: la clave de OpenAI dejó de valer y se
 * generaron informes con el analizador de respaldo durante dos días. El único
 * aviso era un toast de 5 s que no se guardaba en ningún sitio.
 *
 * Todo lo que se pinta aquí sale del registro de F1 (`/executions/{id}/origen-ia`,
 * `/ai-config/estado`). Son textos, no colores: el color acompaña, no informa.
 *
 * Piezas:
 *   useOrigenIA            lee el origen de una ejecución.
 *   FranjaRespaldo         la franja del informe (arriba, en la tabla resumen).
 *   RotuloSeccion          el rótulo de UNA sección (informe por transacción).
 *   PanelIANoDisponible    el bloqueo de ANTES de subir (UploadJTL).
 *   AvisoTrasGenerar       el aviso de DESPUÉS de subir, que no se cierra solo.
 *   AvisoExportar          el aviso del diálogo de exportación.
 *
 * Nada de esto sale en el PDF ni en el HTML exportados: allí va la marca
 * invisible del backend (decisión de Fredy, 29/09/2026).
 *
 * Regla 16: todos los hooks antes de cualquier return.
 */
import { useEffect, useState } from 'react';
import { AlertOctagon, RefreshCw, ShieldAlert } from 'lucide-react';
import api from '../../services/api';

export interface SeccionOrigen {
  section: string;
  label: string | null;
  nombre: string;
  origen: 'ia' | 'respaldo' | 'sin_texto' | 'fijo' | 'desconocido';
  provider: string | null;
  model: string | null;
  motivo_tipo: string | null;
  motivo_frase: string | null;
  motivo: string | null;
  generated_at: string | null;
  edited_at: string | null;
}

export interface OrigenIA {
  fuente: 'registro' | 'texto' | 'ninguna';
  total: number;
  ia: number;
  respaldo: number;
  sin_texto: number;
  afectadas: number;
  afectadas_sin_editar: number;
  general: { total: number; afectadas: number };
  transacciones: Record<string, { total: number; afectadas: number }>;
  motivo_tipo: string | null;
  motivo_frase: string | null;
  motivo: string | null;
  provider: string | null;
  model: string | null;
  fecha: string | null;
  secciones: SeccionOrigen[];
}

export interface EstadoIA {
  ok: boolean;
  provider: string | null;
  model: string | null;
  motivo_tipo: string | null;
  motivo_frase: string | null;
  detalle: string | null;
  comprobado_en: string;
  limite: string;
}

export const AFECTADAS = ['respaldo', 'sin_texto'];

const mayuscula = (t?: string | null) => (t ? t.charAt(0).toUpperCase() + t.slice(1) : '');

function fecha(iso: string | null): string {
  if (!iso) return '';
  const d = new Date(iso.endsWith('Z') ? iso : `${iso}Z`);   // el backend guarda UTC sin zona
  return d.toLocaleString('es-CO', { day: '2-digit', month: '2-digit', year: 'numeric', hour: '2-digit', minute: '2-digit' });
}

/** El origen de una ejecución: `undefined` mientras carga, `null` si no se pudo leer. */
export function useOrigenIA(executionId?: string | null, recargar = 0): OrigenIA | null | undefined {
  const [origen, setOrigen] = useState<OrigenIA | null | undefined>(undefined);
  useEffect(() => {
    if (!executionId) return;
    let vivo = true;
    api.get(`/executions/${executionId}/origen-ia`)
      .then((r) => { if (vivo) setOrigen(r.data); })
      .catch(() => { if (vivo) setOrigen(null); });   // sin dato no se inventa un aviso
    return () => { vivo = false; };
  }, [executionId, recargar]);
  return origen;
}

// ====================================================================
// La franja del informe
// ====================================================================

export function FranjaRespaldo({ executionId }: { executionId?: string | null }) {
  const origen = useOrigenIA(executionId);
  const [verDetalle, setVerDetalle] = useState(false);
  if (!origen || origen.afectadas === 0) return null;

  const general = origen.secciones.filter((s) => AFECTADAS.includes(s.origen));
  const tx = Object.entries(origen.transacciones).filter(([, v]) => v.afectadas > 0);
  const corregidas = origen.afectadas - origen.afectadas_sin_editar;
  const todo = origen.afectadas === origen.total;

  return (
    <div className="mb-6 rounded-2xl border-2 border-red-400 bg-red-50 p-5 text-red-900" data-testid="franja-respaldo" role="alert">
      <div className="flex items-start gap-3">
        <AlertOctagon className="mt-1 h-8 w-8 flex-shrink-0 text-red-600" />
        <div className="min-w-0 space-y-2">
          <p className="text-2xl font-bold">
            {todo
              ? 'Este análisis no lo escribió la IA.'
              : `${origen.afectadas} de ${origen.total} secciones de este informe no las escribió la IA.`}
          </p>
          <p className="text-lg">
            <span className="font-semibold">Por qué: </span>
            {origen.motivo_frase || 'no consta el motivo'}
            {origen.fecha ? ` · generado el ${fecha(origen.fecha)}` : ''}
          </p>
          <p className="text-lg">
            {origen.respaldo > 0 && 'Los textos afectados son de plantilla del analizador de respaldo: las cifras son correctas, la redacción es genérica. '}
            {origen.sin_texto > 0 && 'Las secciones sin texto quedaron vacías. '}
            Lo que corresponde es regenerarlo cuando la IA vuelva a funcionar, no enviarlo así.
          </p>
          {general.length > 0 && (
            <p className="text-base">
              <span className="font-semibold">Informe general: </span>
              {general.map((s) => s.nombre + (s.edited_at ? ' (corregida a mano)' : '')).join(', ')}.
            </p>
          )}
          {tx.length > 0 && (
            <p className="text-base">
              <span className="font-semibold">Transacciones: </span>
              {tx.map(([l, v]) => `${l} (${v.afectadas} de ${v.total})`).join(', ')}.
            </p>
          )}
          {corregidas > 0 && (
            <p className="text-base">{corregidas} de ellas ya se corrigieron a mano después.</p>
          )}
          {origen.fuente === 'texto' && (
            <p className="text-base italic">
              Informe anterior al registro del origen: se reconoce por el texto de plantilla, sin motivo guardado.
            </p>
          )}
          {origen.motivo && (
            <button type="button" onClick={() => setVerDetalle(!verDetalle)}
              className="text-sm font-semibold text-red-700 underline">
              {verDetalle ? 'Ocultar el error del proveedor' : 'Ver el error del proveedor'}
            </button>
          )}
          {verDetalle && origen.motivo && (
            <pre className="whitespace-pre-wrap break-all rounded-lg bg-white/70 p-3 text-xs text-red-800">{origen.motivo}</pre>
          )}
          <p className="text-xs text-red-700/80">Este aviso no sale en el PDF ni en el HTML exportados.</p>
        </div>
      </div>
    </div>
  );
}

// ====================================================================
// El rótulo de una sección
// ====================================================================

export function RotuloSeccion({ origen }: { origen?: SeccionOrigen | null }) {
  if (!origen || !AFECTADAS.includes(origen.origen)) return null;
  return (
    <div className="mb-2 rounded-lg border border-red-300 bg-red-50 px-3 py-1.5 text-sm text-red-800" data-testid="rotulo-respaldo">
      <span className="font-semibold">
        {origen.origen === 'sin_texto' ? 'Sin texto: la IA no lo generó. ' : 'Este texto no lo escribió la IA. '}
      </span>
      {mayuscula(origen.motivo_frase)}
      {origen.edited_at ? ' · corregido a mano después' : ''}
    </div>
  );
}

// ====================================================================
// Antes de subir: la IA no sirve
// ====================================================================

export function PanelIANoDisponible({ estado, aceptado, onAceptar, onRecomprobar, comprobando, onSubirSinIA }: {
  estado: EstadoIA;
  aceptado: boolean;
  onAceptar: (v: boolean) => void;
  onRecomprobar: () => void;
  comprobando: boolean;
  onSubirSinIA: () => void;
}) {
  return (
    <div className="rounded-2xl border-2 border-red-400 bg-red-50 p-6 text-red-900" data-testid="panel-ia-no-disponible" role="alert">
      <div className="flex items-start gap-3">
        <ShieldAlert className="mt-1 h-9 w-9 flex-shrink-0 text-red-600" />
        <div className="min-w-0 space-y-3">
          <p className="text-2xl font-bold">La IA no está disponible: si generas ahora, el análisis no lo escribirá la IA.</p>
          <p className="text-lg">
            <span className="font-semibold">Por qué: </span>{estado.motivo_frase || 'no consta el motivo'}
            {estado.provider ? ` (${estado.provider}${estado.model ? ` ${estado.model}` : ''})` : ''}.
          </p>
          {estado.detalle && (
            <pre className="whitespace-pre-wrap break-all rounded-lg bg-white/70 p-3 text-xs text-red-800">{estado.detalle}</pre>
          )}
          <p className="text-lg">
            El informe saldría con texto de plantilla del analizador de respaldo (o vacío). Lo recomendable es
            no generarlo todavía: arreglar la configuración de la IA y volver aquí.
          </p>
          <div className="flex flex-wrap items-center gap-3 pt-1">
            <button type="button" onClick={onRecomprobar} disabled={comprobando}
              data-testid="ia-recomprobar"
              className="flex items-center gap-2 rounded-xl bg-red-600 px-6 py-3 text-lg font-bold text-white hover:bg-red-700 disabled:opacity-60">
              <RefreshCw className={`h-5 w-5 ${comprobando ? 'animate-spin' : ''}`} />
              No generar todavía · volver a comprobar la IA
            </button>
          </div>
          <div className="mt-2 border-t border-red-200 pt-3">
            <label className="flex cursor-pointer items-start gap-3 text-base">
              <input type="checkbox" className="mt-1 h-5 w-5 accent-red-600" checked={aceptado}
                data-testid="ia-aceptar-sin-ia"
                onChange={(e) => onAceptar(e.target.checked)} />
              <span>Entiendo que el análisis no lo escribirá la IA y quiero generar el informe igualmente.</span>
            </label>
            <button type="button" onClick={onSubirSinIA} disabled={!aceptado}
              data-testid="ia-subir-sin-ia"
              className="mt-3 rounded-xl border-2 border-red-400 bg-white px-5 py-2.5 text-base font-semibold text-red-700 hover:bg-red-100 disabled:cursor-not-allowed disabled:opacity-40">
              Generar sin IA: el informe saldrá con texto de plantilla
            </button>
          </div>
          <p className="text-xs text-red-700/80">{estado.limite}</p>
        </div>
      </div>
    </div>
  );
}

// ====================================================================
// Después de subir: no se cierra solo
// ====================================================================

export function AvisoTrasGenerar({ aiStatus, onVer }: {
  aiStatus: { respaldo?: number; secciones?: number; motivo_frase?: string; motivo?: string | null; error?: string | null };
  onVer: () => void;
}) {
  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/60 p-4" data-testid="aviso-tras-generar">
      <div className="w-full max-w-2xl rounded-2xl border-2 border-red-400 bg-white p-7 shadow-2xl" role="alertdialog">
        <div className="flex items-start gap-3">
          <AlertOctagon className="mt-1 h-9 w-9 flex-shrink-0 text-red-600" />
          <div className="space-y-3 text-red-900">
            <p className="text-2xl font-bold">
              El informe se generó, pero {aiStatus.respaldo} de {aiStatus.secciones} secciones no las escribió la IA.
            </p>
            <p className="text-lg"><span className="font-semibold">Por qué: </span>{aiStatus.motivo_frase || aiStatus.error || 'no consta el motivo'}.</p>
            {aiStatus.motivo && (
              <pre className="whitespace-pre-wrap break-all rounded-lg bg-red-50 p-3 text-xs text-red-800">{aiStatus.motivo}</pre>
            )}
            <p className="text-lg">
              Queda guardado en el informe y en el historial. Lo recomendable es no enviarlo así y
              regenerarlo cuando la IA vuelva a funcionar.
            </p>
            <div className="flex justify-end pt-2">
              <button type="button" onClick={onVer} data-testid="aviso-tras-generar-ver"
                className="rounded-xl bg-red-600 px-6 py-3 text-lg font-bold text-white hover:bg-red-700">
                Entendido, ver el informe
              </button>
            </div>
          </div>
        </div>
      </div>
    </div>
  );
}

// ====================================================================
// Al exportar
// ====================================================================

export function AvisoExportar({ origen }: { origen: OrigenIA | null | undefined }) {
  if (!origen || origen.afectadas === 0) return null;
  return (
    <div className="mt-4 rounded-xl border-2 border-red-400 bg-red-50 p-4 text-red-900" data-testid="aviso-exportar" role="alert">
      <p className="text-lg font-bold">
        {origen.afectadas} de {origen.total} secciones de este informe no las escribió la IA.
      </p>
      <p className="text-base">
        Motivo: {origen.motivo_frase || 'no consta'}{origen.fecha ? ` (generado el ${fecha(origen.fecha)})` : ''}.
        El documento no lo dice en la página: quien lo reciba no lo sabrá. Lo recomendable es
        regenerarlo con IA antes de enviarlo.
      </p>
    </div>
  );
}
