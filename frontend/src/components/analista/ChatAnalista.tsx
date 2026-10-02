/**
 * «Analista IA» — el chat (BLOQUE 5). Mensajes, botones rápidos, caja de texto
 * (Ctrl+Enter envía) y «Adjuntar archivo» para el CSV o XML de errores.
 *
 * Regla 16: todos los hooks antes de cualquier return.
 */
import { useEffect, useRef, useState } from 'react';
import { AlertCircle, Bot, Loader2, Paperclip, Send, User } from 'lucide-react';
import type { Mensaje } from '../../api/analistaApi';

const RAPIDOS: { nombre: string; texto: string; enviar?: boolean }[] = [
  { nombre: 'Ambiente y versión', texto: 'Ambiente: \nVersión desplegada: ' },
  { nombre: 'Objetivo de la prueba', texto: 'El objetivo de la prueba era ' },
  { nombre: 'Incidentes', texto: 'Durante la prueba pasó lo siguiente: ' },
  { nombre: 'No sé, sigue sin eso', texto: 'No lo sé, sigue sin eso.', enviar: true },
];

export default function ChatAnalista({ mensajes, enviando, adjuntando, deshabilitado, aviso, onCerrarAviso, onEnviar, onAdjuntar }: {
  mensajes: Mensaje[];
  enviando: boolean;
  adjuntando: boolean;
  deshabilitado: boolean;
  aviso: { tipo: 'error' | 'ok'; texto: string } | null;
  onCerrarAviso: () => void;
  onEnviar: (texto: string) => Promise<boolean>;
  onAdjuntar: (f: File) => void;
}) {
  const [texto, setTexto] = useState('');
  const fondo = useRef<HTMLDivElement>(null);
  const caja = useRef<HTMLTextAreaElement>(null);
  const archivo = useRef<HTMLInputElement>(null);

  useEffect(() => {
    fondo.current?.scrollIntoView({ block: 'end' });
  }, [mensajes.length, enviando]);

  const enviar = async (t: string) => {
    const limpio = t.trim();
    if (!limpio || enviando || deshabilitado) return;
    const ok = await onEnviar(limpio);
    if (ok) setTexto('');
  };

  const bloqueado = enviando || deshabilitado;

  return (
    <div className="flex h-full flex-col bg-white" data-testid="chat">
      <div className="flex-1 space-y-3 overflow-y-auto p-4" data-testid="chat-mensajes">
        {mensajes.map((m) => {
          const ia = m.rol === 'ia';
          const fallo = m.origen === 'error';
          return (
            <div key={m.id} className={`flex gap-2 ${ia ? '' : 'flex-row-reverse'}`} data-testid={`mensaje-${m.rol}`} data-origen={m.origen || ''}>
              <div className={`flex h-8 w-8 flex-shrink-0 items-center justify-center rounded-full ${ia ? (fallo ? 'bg-red-100 text-red-700' : 'bg-indigo-100 text-indigo-700') : 'bg-gray-200 text-gray-700'}`}>
                {ia ? (fallo ? <AlertCircle className="h-4 w-4" /> : <Bot className="h-4 w-4" />) : <User className="h-4 w-4" />}
              </div>
              <div className={`max-w-[85%] rounded-2xl px-4 py-2.5 text-sm ${ia
                ? (fallo ? 'border border-red-300 bg-red-50 text-red-900' : 'bg-indigo-50 text-gray-900')
                : 'bg-gray-100 text-gray-900'}`}>
                <p className="whitespace-pre-wrap">{m.texto}</p>
                {m.origen === 'fijo' && <p className="mt-1 text-[11px] text-gray-500">Mensaje de Kinetix (sin IA)</p>}
                {m.avisos?.length > 0 && (
                  <ul className="mt-1 space-y-0.5 text-[11px] text-amber-700">{m.avisos.map((a, i) => <li key={i}>{a}</li>)}</ul>
                )}
              </div>
            </div>
          );
        })}
        {enviando && (
          <div className="flex items-center gap-2 text-sm text-gray-500" data-testid="chat-pensando">
            <Loader2 className="h-4 w-4 animate-spin" /> La IA está leyendo tu mensaje…
          </div>
        )}
        <div ref={fondo} />
      </div>

      {aviso && (
        <div role="alert" data-testid={`chat-aviso-${aviso.tipo}`}
          className={`mx-4 mb-2 flex items-start justify-between gap-2 rounded-lg border px-3 py-2 text-sm ${aviso.tipo === 'error'
            ? 'border-red-300 bg-red-50 text-red-800' : 'border-green-300 bg-green-50 text-green-800'}`}>
          <span>{aviso.texto}</span>
          <button type="button" onClick={onCerrarAviso} className="text-xs font-semibold">Cerrar</button>
        </div>
      )}

      <div className="border-t border-gray-200 p-3">
        <div className="mb-2 flex flex-wrap gap-1.5">
          {RAPIDOS.map((r) => (
            <button key={r.nombre} type="button" disabled={bloqueado} data-testid={`rapido-${r.nombre}`}
              onClick={() => {
                if (r.enviar) { enviar(r.texto); return; }
                setTexto((t) => (t ? `${t}\n${r.texto}` : r.texto));
                caja.current?.focus();
              }}
              className="rounded-full border border-indigo-200 bg-indigo-50 px-3 py-1 text-xs font-medium text-indigo-700 hover:bg-indigo-100 disabled:opacity-40">
              {r.nombre}
            </button>
          ))}
        </div>
        <textarea
          ref={caja} value={texto} onChange={(e) => setTexto(e.target.value)} maxLength={2000} rows={3}
          disabled={deshabilitado} data-testid="chat-caja"
          placeholder={deshabilitado ? 'Esta conversación ya generó su informe.' : 'Cuéntale a la IA los criterios, el ambiente, lo que pasó… (Ctrl+Enter para enviar)'}
          onKeyDown={(e) => { if (e.key === 'Enter' && (e.ctrlKey || e.metaKey)) { e.preventDefault(); enviar(texto); } }}
          className="w-full resize-none rounded-lg border border-gray-300 px-3 py-2 text-sm focus:border-indigo-500 focus:outline-none disabled:bg-gray-50"
        />
        <div className="mt-2 flex items-center justify-between">
          <div className="flex items-center gap-2">
            <button type="button" disabled={bloqueado || adjuntando} onClick={() => archivo.current?.click()} data-testid="chat-adjuntar"
              className="inline-flex items-center gap-1.5 rounded-lg border border-gray-300 px-3 py-1.5 text-xs font-medium text-gray-700 hover:bg-gray-50 disabled:opacity-40"
              title="El CSV o XML de JMeter con el detalle de los errores">
              {adjuntando ? <Loader2 className="h-4 w-4 animate-spin" /> : <Paperclip className="h-4 w-4" />}
              Adjuntar archivo
            </button>
            <input ref={archivo} type="file" accept=".csv,.xml" className="hidden" data-testid="chat-archivo"
              onChange={(e) => { const f = e.target.files?.[0]; if (f) onAdjuntar(f); e.target.value = ''; }} />
            <span className="text-[11px] text-gray-400">{texto.length}/2000 · Ctrl+Enter</span>
          </div>
          <button type="button" onClick={() => enviar(texto)} disabled={bloqueado || !texto.trim()} data-testid="chat-enviar"
            className="inline-flex items-center gap-1.5 rounded-lg bg-indigo-600 px-4 py-1.5 text-sm font-semibold text-white hover:bg-indigo-700 disabled:opacity-40">
            <Send className="h-4 w-4" /> Enviar
          </button>
        </div>
      </div>
    </div>
  );
}
