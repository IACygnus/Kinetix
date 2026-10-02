/**
 * «Analista IA» — la ventana inicial «Nueva prueba» (BLOQUE 5).
 *
 * Cliente, proyecto, tipo y los JTL. SIN criterios: esos se le cuentan a la IA
 * en la conversación. Los JTL se pueden soltar en CUALQUIER parte de la ventana.
 *
 * Regla 16: todos los hooks antes de cualquier return.
 */
import { useCallback, useEffect, useRef, useState } from 'react';
import { AlertCircle, FileUp, MessageSquare, Sparkles, X } from 'lucide-react';
import { clientsAPI } from '../../services/api';
import type { ClientInfo } from '../../types';
import LoadingSpinner from '../common/LoadingSpinner';
import { analistaAPI, detalleError } from '../../api/analistaApi';
import type { Sesion, SesionResumen } from '../../api/analistaApi';

export const TIPOS_PRUEBA: { id: string; nombre: string }[] = [
  { id: 'load', nombre: 'Carga (Load)' },
  { id: 'stress', nombre: 'Estrés (Stress)' },
  { id: 'endurance', nombre: 'Resistencia (Endurance)' },
  { id: 'scalability', nombre: 'Escalabilidad' },
  { id: 'spike', nombre: 'Picos (Spike)' },
  { id: 'smoke', nombre: 'Humo (Smoke)' },
];
const EXTENSIONES = ['.jtl', '.csv', '.xml'];
const MAX_JTL = 5;

export default function NuevaPrueba({ onCreada, onAbrir }: {
  onCreada: (s: Sesion) => void;
  onAbrir: (id: string) => void;
}) {
  const [clientes, setClientes] = useState<ClientInfo[]>([]);
  const [clientId, setClientId] = useState('');
  const [proyecto, setProyecto] = useState('');
  const [tipo, setTipo] = useState('load');
  const [files, setFiles] = useState<File[]>([]);
  const [arrastrando, setArrastrando] = useState(false);
  const [leyendo, setLeyendo] = useState(false);
  const [error, setError] = useState('');
  const [recientes, setRecientes] = useState<SesionResumen[]>([]);
  const entrada = useRef<HTMLInputElement>(null);
  const profundidad = useRef(0);

  useEffect(() => {
    clientsAPI.getMyClients().then(setClientes).catch(() => {});
    analistaAPI.listar().then((l) => setRecientes(l.filter((s) => s.estado === 'abierta').slice(0, 5))).catch(() => {});
  }, []);

  const agregar = useCallback((lista: FileList | File[]) => {
    const nuevos = Array.from(lista);
    const malos = nuevos.filter((f) => !EXTENSIONES.some((e) => f.name.toLowerCase().endsWith(e)));
    if (malos.length) {
      setError(`Solo archivos .jtl, .csv o .xml de JMeter: ${malos.map((f) => f.name).join(', ')}`);
    } else {
      setError('');
    }
    setFiles((prev) => {
      const juntos = [...prev, ...nuevos.filter((f) => !malos.includes(f) && !prev.some((p) => p.name === f.name))];
      if (juntos.length > MAX_JTL) setError(`Como máximo ${MAX_JTL} archivos JTL.`);
      return juntos.slice(0, MAX_JTL);
    });
  }, []);

  // Soltar en CUALQUIER parte de la ventana: el contador evita el parpadeo de
  // dragenter/dragleave al pasar por encima de los elementos hijos.
  const alEntrar = (e: React.DragEvent) => { e.preventDefault(); profundidad.current += 1; setArrastrando(true); };
  const alSalir = (e: React.DragEvent) => {
    e.preventDefault();
    profundidad.current = Math.max(0, profundidad.current - 1);
    if (profundidad.current === 0) setArrastrando(false);
  };
  const alSoltar = (e: React.DragEvent) => {
    e.preventDefault();
    profundidad.current = 0;
    setArrastrando(false);
    if (e.dataTransfer.files?.length) agregar(e.dataTransfer.files);
  };

  const leer = async () => {
    setError('');
    setLeyendo(true);
    try {
      const s = await analistaAPI.crear({ files, proyecto: proyecto.trim(), tipo, clientId, unidad: 'TPS' });
      onCreada(s);
    } catch (err) {
      setError(detalleError(err, 'No se pudo leer la prueba.'));
      setLeyendo(false);
    }
  };

  const puede = files.length > 0 && proyecto.trim().length > 0 && !leyendo;

  return (
    <div
      className="relative min-h-[calc(100vh-8rem)] bg-gray-100 p-6"
      onDragEnter={alEntrar} onDragOver={(e) => e.preventDefault()} onDragLeave={alSalir} onDrop={alSoltar}
      data-testid="analista-nueva"
    >
      {leyendo && <LoadingSpinner message="Leyendo la prueba…" />}
      {arrastrando && (
        <div className="pointer-events-none absolute inset-3 z-40 flex items-center justify-center rounded-2xl border-4 border-dashed border-indigo-500 bg-indigo-50/80">
          <p className="text-2xl font-semibold text-indigo-700">Suelta aquí los JTL</p>
        </div>
      )}

      <div className="mx-auto max-w-3xl space-y-5">
        <div className="rounded-2xl border border-gray-200 bg-white p-8 shadow-lg">
          <div className="mb-6 flex items-center gap-3">
            <div className="flex h-11 w-11 items-center justify-center rounded-xl bg-indigo-600 text-white">
              <Sparkles className="h-6 w-6" />
            </div>
            <div>
              <h1 className="text-2xl font-bold text-gray-900">Nueva prueba</h1>
              <p className="text-sm text-gray-500">Analista IA: carga la prueba y conversa para completar la ficha del informe.</p>
            </div>
          </div>

          <div className="grid grid-cols-1 gap-4 md:grid-cols-2">
            <label className="block">
              <span className="text-sm font-semibold text-gray-700">Cliente</span>
              <select value={clientId} onChange={(e) => setClientId(e.target.value)} data-testid="nueva-cliente"
                className="mt-1 w-full rounded-lg border border-gray-300 px-3 py-2 text-sm focus:border-indigo-500 focus:outline-none">
                <option value="">Sin cliente</option>
                {clientes.map((c) => <option key={c.id} value={c.id}>{c.name}</option>)}
              </select>
            </label>
            <label className="block">
              <span className="text-sm font-semibold text-gray-700">Proyecto *</span>
              <input value={proyecto} onChange={(e) => setProyecto(e.target.value)} maxLength={255}
                data-testid="nueva-proyecto" placeholder="Nombre de la prueba o del proyecto"
                className="mt-1 w-full rounded-lg border border-gray-300 px-3 py-2 text-sm focus:border-indigo-500 focus:outline-none" />
            </label>
          </div>

          <div className="mt-4">
            <span className="text-sm font-semibold text-gray-700">Tipo de prueba</span>
            <div className="mt-1 grid grid-cols-2 gap-2 md:grid-cols-3">
              {TIPOS_PRUEBA.map((t) => (
                <button key={t.id} type="button" onClick={() => setTipo(t.id)} data-testid={`nueva-tipo-${t.id}`}
                  className={`rounded-lg border px-3 py-2 text-sm font-medium transition ${tipo === t.id
                    ? 'border-indigo-600 bg-indigo-600 text-white' : 'border-gray-300 bg-white text-gray-700 hover:bg-gray-50'}`}>
                  {t.nombre}
                </button>
              ))}
            </div>
          </div>

          <div
            className={`mt-5 flex cursor-pointer flex-col items-center justify-center rounded-xl border-2 border-dashed p-8 text-center transition ${arrastrando ? 'border-indigo-500 bg-indigo-50' : 'border-gray-300 hover:border-indigo-400 hover:bg-gray-50'}`}
            onClick={() => entrada.current?.click()} data-testid="nueva-zona"
          >
            <FileUp className="mb-2 h-10 w-10 text-indigo-500" />
            <p className="text-base font-semibold text-gray-800">Arrastra aquí los JTL (o suéltalos en cualquier parte)</p>
            <p className="text-sm text-gray-500">o haz clic para elegirlos · de 1 a {MAX_JTL} archivos .jtl, .csv o .xml</p>
            <input ref={entrada} type="file" multiple accept=".jtl,.csv,.xml" className="hidden" data-testid="nueva-archivos"
              onChange={(e) => { if (e.target.files) agregar(e.target.files); e.target.value = ''; }} />
          </div>
          {files.length > 0 && (
            <ul className="mt-3 space-y-1" data-testid="nueva-lista">
              {files.map((f) => (
                <li key={f.name} className="flex items-center justify-between rounded-lg bg-gray-50 px-3 py-1.5 text-sm">
                  <span className="truncate">{f.name} <span className="text-gray-400">· {(f.size / 1024 / 1024).toFixed(1)} MB</span></span>
                  <button type="button" onClick={() => setFiles(files.filter((x) => x !== f))} className="text-gray-400 hover:text-red-600" title="Quitar">
                    <X className="h-4 w-4" />
                  </button>
                </li>
              ))}
            </ul>
          )}

          <div className="mt-5 flex items-start gap-3 rounded-xl border border-indigo-200 bg-indigo-50 p-4 text-sm text-indigo-900">
            <MessageSquare className="mt-0.5 h-5 w-5 flex-shrink-0" />
            <p>
              Los <b>criterios de aceptación no se escriben aquí</b>: se los cuentas a la IA en la conversación, con tus
              palabras («el 90 % en menos de 2 segundos», «procesar 20.000 registros en 30 minutos»…). Kinetix calcula
              con el JTL si se cumplen.
            </p>
          </div>

          {error && (
            <div className="mt-4 flex items-start gap-2 rounded-lg border border-red-300 bg-red-50 p-3 text-sm text-red-800" role="alert" data-testid="nueva-error">
              <AlertCircle className="mt-0.5 h-4 w-4 flex-shrink-0" />{error}
            </div>
          )}

          <div className="mt-6 flex justify-end">
            <button type="button" onClick={leer} disabled={!puede} data-testid="nueva-leer"
              className="inline-flex items-center gap-2 rounded-xl bg-indigo-600 px-6 py-3 text-base font-semibold text-white shadow hover:bg-indigo-700 disabled:cursor-not-allowed disabled:opacity-40">
              <Sparkles className="h-5 w-5" />
              Leer la prueba y conversar
            </button>
          </div>
        </div>

        {recientes.length > 0 && (
          <div className="rounded-2xl border border-gray-200 bg-white p-5 shadow" data-testid="nueva-recientes">
            <h2 className="mb-2 text-sm font-semibold text-gray-700">Retomar una conversación</h2>
            <ul className="divide-y divide-gray-100">
              {recientes.map((s) => (
                <li key={s.id}>
                  <button type="button" onClick={() => onAbrir(s.id)}
                    className="flex w-full items-center justify-between py-2 text-left text-sm hover:text-indigo-700">
                    <span className="truncate">{s.proyecto}{s.cliente ? ` · ${s.cliente}` : ''}</span>
                    <span className="ml-3 flex-shrink-0 text-xs text-gray-500">
                      {s.listo ? `listo ${s.listo.n} de ${s.listo.m}` : ''}
                    </span>
                  </button>
                </li>
              ))}
            </ul>
          </div>
        )}
      </div>
    </div>
  );
}
