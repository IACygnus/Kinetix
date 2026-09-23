/**
 * Crear una sesión de monitoreo — ETAPA O2d (O-D37, O-D45).
 *
 * Tres pasos, y cada uno responde a una pregunta:
 *
 *   1. ¿Qué prueba es y qué servidores miramos?
 *   2. ¿Cómo hacemos que tu JMeter mande sus métricas?  <-- el que faltaba
 *   3. Ver la sesión.
 *
 * El paso 2 es la razón de esta etapa. Antes, la pantalla daba diez parámetros
 * y alguien tenía que copiarlos dentro de JMeter uno a uno. Ahora se sube el
 * `.jmx` y **Kinetix se los pone**. Copiarlos a mano sigue estando, plegado,
 * como lo que es: la salida de emergencia.
 */
import { useEffect, useState } from 'react';
import { useNavigate } from 'react-router-dom';
import {
  AlertTriangle, ArrowLeft, ArrowRight, Check, ChevronDown, ChevronUp, Copy,
  Download, FileUp, Loader2, Server,
} from 'lucide-react';
import { clientsAPI, servidoresAPI, sesionesAPI } from '../services/api';
import type {
  ClientInfo, ConexionJMeter, SesionMonitoreo, ServidorObservado,
} from '../types';

const BOTON = 'min-h-[44px] inline-flex items-center justify-center gap-2 rounded-xl font-semibold transition';
const CAMPO = 'w-full min-h-[44px] px-3 text-lg border border-gray-300 rounded-xl';

const PASOS = [
  'Qué se va a probar',
  'Conecta tu JMeter',
  'Ver la sesión',
];

export default function SesionNuevaPage() {
  const navegar = useNavigate();
  const [paso, setPaso] = useState(1);
  const [error, setError] = useState('');

  // Paso 1
  const [clientes, setClientes] = useState<ClientInfo[]>([]);
  const [servidores, setServidores] = useState<ServidorObservado[]>([]);
  const [nombre, setNombre] = useState('');
  const [clienteId, setClienteId] = useState('');
  const [proyecto, setProyecto] = useState('');
  const [elegidos, setElegidos] = useState<string[]>([]);
  const [creando, setCreando] = useState(false);

  // Paso 2
  const [sesion, setSesion] = useState<SesionMonitoreo | null>(null);
  const [conexion, setConexion] = useState<ConexionJMeter | null>(null);
  const [subiendo, setSubiendo] = useState(false);
  const [resultado, setResultado] = useState<{ mensaje: string; aviso: boolean } | null>(null);
  const [avanzado, setAvanzado] = useState(false);
  const [copiado, setCopiado] = useState('');

  useEffect(() => {
    clientsAPI.list().then(setClientes).catch(() => setClientes([]));
  }, []);

  useEffect(() => {
    if (!clienteId) { setServidores([]); setElegidos([]); return; }
    servidoresAPI.listar(clienteId)
      .then((lista) => {
        const activos = lista.filter((s) => s.activo);
        setServidores(activos);
        // Marcados por defecto: es lo que casi siempre se quiere, y se pueden
        // desmarcar. Mejor que empezar en blanco y que nadie se acuerde.
        setElegidos(activos.map((s) => s.id));
      })
      .catch(() => setServidores([]));
  }, [clienteId]);

  const crear = async () => {
    setCreando(true);
    setError('');
    try {
      const nueva = await sesionesAPI.crear({
        nombre: nombre.trim(), client_id: clienteId,
        proyecto: proyecto.trim(), servidores: elegidos,
      });
      setSesion(nueva);
      setConexion(await sesionesAPI.jmeter(nueva.id));
      setPaso(2);
    } catch (e: unknown) {
      const r = e as { response?: { data?: { detail?: string } } };
      setError(r.response?.data?.detail || 'No se pudo crear la sesión.');
    } finally {
      setCreando(false);
    }
  };

  const subirJmx = async (archivo: File) => {
    if (!sesion) return;
    setSubiendo(true);
    setError('');
    setResultado(null);
    try {
      const r = await sesionesAPI.ponerListener(sesion.id, archivo);
      // Se descarga sola: el usuario ya dijo lo que quería al subir el archivo.
      const url = URL.createObjectURL(r.blob);
      const enlace = document.createElement('a');
      enlace.href = url;
      enlace.download = r.nombre;
      document.body.appendChild(enlace);
      enlace.click();
      document.body.removeChild(enlace);
      URL.revokeObjectURL(url);
      setResultado({ mensaje: r.mensaje, aviso: r.reemplazado });
    } catch (e: unknown) {
      // El backend responde el error como blob porque la petición pedía blob;
      // hay que leerlo para poder enseñarlo.
      const r = e as { response?: { data?: Blob } };
      let detalle = 'No se pudo procesar el archivo.';
      try {
        if (r.response?.data instanceof Blob) {
          const texto = await r.response.data.text();
          detalle = JSON.parse(texto).detail || detalle;
        }
      } catch { /* se queda el mensaje genérico */ }
      setError(detalle);
    } finally {
      setSubiendo(false);
    }
  };

  const copiar = (clave: string, texto: string) => {
    void navigator.clipboard.writeText(texto);
    setCopiado(clave);
    setTimeout(() => setCopiado(''), 1800);
  };

  const listoPaso1 = Boolean(nombre.trim() && clienteId && proyecto.trim());

  return (
    <div className="p-8 max-w-[1100px] mx-auto">
      <button onClick={() => navegar('/observabilidad/sesiones')}
        className={`${BOTON} px-3 mb-4 text-gray-600 hover:bg-gray-100`}>
        <ArrowLeft className="w-5 h-5" /> Volver a las sesiones
      </button>

      <h1 className="text-3xl font-bold text-gray-800 mb-6">Nueva sesión de monitoreo</h1>

      {/* ---------- Los tres pasos ---------- */}
      <ol className="flex gap-3 mb-8 flex-wrap" data-testid="ses-pasos">
        {PASOS.map((texto, i) => {
          const numero = i + 1;
          const hecho = paso > numero;
          const actual = paso === numero;
          return (
            <li key={texto} className={`flex items-center gap-2 px-4 py-2 rounded-xl text-base font-semibold ${
              actual ? 'bg-[#0a1628] text-white'
                : hecho ? 'bg-emerald-100 text-emerald-800'
                  : 'bg-gray-100 text-gray-500'}`}>
              <span className="w-6 h-6 rounded-full bg-white/20 inline-flex items-center justify-center text-sm">
                {hecho ? <Check className="w-4 h-4" /> : numero}
              </span>
              {texto}
            </li>
          );
        })}
      </ol>

      {error && (
        <p className="mb-5 p-4 rounded-xl bg-red-50 border border-red-300 text-base text-red-800"
          data-testid="ses-nueva-error">{error}</p>
      )}

      {/* ================= PASO 1 ================= */}
      {paso === 1 && (
        <div className="bg-white rounded-2xl border border-gray-200 shadow-sm p-6"
          data-testid="ses-paso1">
          <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
            <label className="block md:col-span-2">
              <span className="block text-base font-semibold text-gray-700 mb-1">
                Nombre de la sesión
              </span>
              <input value={nombre} onChange={(e) => setNombre(e.target.value)}
                data-testid="ses-f-nombre" className={CAMPO}
                placeholder="Prueba de carga del catálogo — octubre" />
              <span className="block text-sm text-gray-500 mt-1">
                Para reconocerla dentro de un mes en la lista.
              </span>
            </label>

            <label className="block">
              <span className="block text-base font-semibold text-gray-700 mb-1">Cliente</span>
              <select value={clienteId} onChange={(e) => setClienteId(e.target.value)}
                data-testid="ses-f-cliente" className={CAMPO}>
                <option value="">Elige un cliente…</option>
                {clientes.map((c) => <option key={c.id} value={c.id}>{c.name}</option>)}
              </select>
            </label>

            <label className="block">
              <span className="block text-base font-semibold text-gray-700 mb-1">Proyecto</span>
              <input value={proyecto} onChange={(e) => setProyecto(e.target.value)}
                data-testid="ses-f-proyecto" className={CAMPO} placeholder="Catálogo web" />
            </label>
          </div>

          {/* ---------- Qué servidores se observan ---------- */}
          <div className="mt-6">
            <p className="text-base font-semibold text-gray-700 mb-2">
              Qué servidores se observan
            </p>
            {!clienteId ? (
              <p className="text-base text-gray-500 py-4">
                Elige un cliente y aparecerán sus servidores.
              </p>
            ) : servidores.length === 0 ? (
              <div className="p-4 rounded-xl bg-amber-50 border border-amber-300"
                data-testid="ses-sin-servidores">
                <p className="text-base text-amber-900">
                  Este cliente no tiene servidores dados de alta. La sesión se
                  puede crear igual —verás las métricas de la prueba— pero no
                  habrá nada de infraestructura que enseñar.{' '}
                  <button onClick={() => navegar('/observabilidad/servidores')}
                    className="underline font-semibold min-h-[44px]">
                    Dar de alta un servidor
                  </button>
                </p>
              </div>
            ) : (
              <div className="space-y-2" data-testid="ses-servidores">
                {servidores.map((s) => (
                  <label key={s.id}
                    className="flex items-center gap-3 p-3 rounded-xl border border-gray-200 hover:bg-gray-50 cursor-pointer min-h-[44px]">
                    <input type="checkbox" className="w-6 h-6"
                      data-testid={`ses-srv-${s.name}`}
                      checked={elegidos.includes(s.id)}
                      onChange={(e) => setElegidos((antes) => e.target.checked
                        ? [...antes, s.id]
                        : antes.filter((x) => x !== s.id))} />
                    <Server className="w-5 h-5 text-gray-400" />
                    <span className="text-base text-gray-800">
                      <strong>{s.name}</strong>
                      <span className="text-gray-500">
                        {' '}· {s.tipo} · {s.direccion}:{s.puerto}
                        {' '}· {s.modo === 'agente' ? 'con agente' : 'sin agente'}
                      </span>
                    </span>
                  </label>
                ))}
              </div>
            )}
          </div>

          <div className="flex justify-end mt-6">
            <button onClick={crear} disabled={!listoPaso1 || creando}
              data-testid="ses-crear"
              className={`${BOTON} px-6 text-lg bg-[#f5a623] text-[#0a1628] hover:bg-[#f7b84a] disabled:opacity-40`}>
              {creando ? <Loader2 className="w-5 h-5 animate-spin" />
                : <ArrowRight className="w-5 h-5" />}
              Continuar
            </button>
          </div>
        </div>
      )}

      {/* ================= PASO 2 ================= */}
      {paso === 2 && sesion && (
        <div className="bg-white rounded-2xl border border-gray-200 shadow-sm p-6"
          data-testid="ses-paso2">
          <h2 className="text-2xl font-bold text-gray-800">Conecta tu JMeter</h2>
          <p className="text-lg text-gray-600 mt-2">
            <strong>JMeter no envía sus métricas solo.</strong> Hay que añadirle
            un componente —el Backend Listener— que se las mande a Kinetix. Sube
            aquí tu plan de prueba y te lo devolvemos con él puesto.
          </p>

          <div className="mt-5 p-4 rounded-xl bg-gray-50 border border-gray-200">
            <p className="text-base text-gray-700">
              Esta sesión se identifica como{' '}
              <code className="bg-white px-2 py-1 rounded border border-gray-300 font-mono text-base"
                data-testid="ses-corrida">{sesion.corrida}</code>
            </p>
            <p className="text-sm text-gray-500 mt-1">
              Esa misma etiqueta va en el JMeter y en los servidores. Es lo que
              permite cruzar las dos cosas.
            </p>
          </div>

          {/* ---------- Subir el .jmx ---------- */}
          <div className="mt-6 p-6 rounded-2xl border-2 border-dashed border-gray-300 text-center">
            <FileUp className="w-10 h-10 text-gray-400 mx-auto mb-2" />
            <p className="text-lg font-semibold text-gray-800">
              Sube tu archivo <code>.jmx</code>
            </p>
            <p className="text-base text-gray-500 mt-1 mb-4">
              Se descarga una copia con el listener puesto. Tu archivo original
              no se toca.
            </p>
            <label className={`${BOTON} px-6 text-lg bg-[#f5a623] text-[#0a1628] hover:bg-[#f7b84a] cursor-pointer`}>
              {subiendo ? <Loader2 className="w-5 h-5 animate-spin" />
                : <Download className="w-5 h-5" />}
              Elegir archivo y descargar
              <input type="file" accept=".jmx,application/xml,text/xml"
                data-testid="ses-jmx" className="hidden"
                onChange={(e) => {
                  const archivo = e.target.files?.[0];
                  if (archivo) void subirJmx(archivo);
                  e.target.value = '';
                }} />
            </label>
          </div>

          {resultado && (
            <div data-testid="ses-jmx-resultado"
              className={`mt-4 p-4 rounded-xl border flex items-start gap-3 ${
                resultado.aviso ? 'bg-amber-50 border-amber-300'
                  : 'bg-emerald-50 border-emerald-300'}`}>
              {resultado.aviso ? <AlertTriangle className="w-6 h-6 text-amber-700 shrink-0" />
                : <Check className="w-6 h-6 text-emerald-700 shrink-0" />}
              <p className="text-base text-gray-800">{resultado.mensaje}</p>
            </div>
          )}

          {/* ---------- La opción avanzada, plegada ---------- */}
          <div className="mt-6 border-t border-gray-200 pt-4">
            <button onClick={() => setAvanzado((v) => !v)} data-testid="ses-avanzado"
              className={`${BOTON} text-base text-gray-600 hover:bg-gray-100 px-3`}>
              {avanzado ? <ChevronUp className="w-5 h-5" /> : <ChevronDown className="w-5 h-5" />}
              Prefiero configurarlo a mano en JMeter
            </button>
            {avanzado && conexion && (
              <div className="mt-3 space-y-3" data-testid="ses-parametros">
                <p className="text-base text-gray-600">
                  Añade un <strong>Backend Listener</strong> a tu plan, con la
                  clase <code>InfluxdbBackendListenerClient</code>, y pon estos
                  valores:
                </p>
                {conexion.aviso && (
                  <p className="p-3 rounded-xl bg-amber-50 border border-amber-300 text-base text-amber-900">
                    {conexion.aviso}
                  </p>
                )}
                {conexion.parametros.map((p) => (
                  <div key={p.nombre}
                    className="border border-gray-200 rounded-xl p-3 flex items-start justify-between gap-3 flex-wrap">
                    <div className="min-w-0">
                      <p className="text-base font-bold text-gray-800">{p.nombre}</p>
                      <p className="text-base text-gray-700 font-mono break-all">{p.valor}</p>
                      <p className="text-sm text-gray-500">{p.explicacion}</p>
                    </div>
                    <button onClick={() => copiar(p.nombre, p.valor)}
                      data-testid={`ses-copiar-${p.nombre}`}
                      className={`${BOTON} px-4 border border-gray-300 hover:bg-gray-50`}>
                      {copiado === p.nombre ? <Check className="w-5 h-5" /> : <Copy className="w-5 h-5" />}
                      {copiado === p.nombre ? 'Copiado' : 'Copiar'}
                    </button>
                  </div>
                ))}
              </div>
            )}
          </div>

          <div className="flex justify-end mt-6">
            <button onClick={() => navegar(`/observabilidad/sesiones/${sesion.id}`)}
              data-testid="ses-ir-a-sesion"
              className={`${BOTON} px-6 text-lg bg-[#0a1628] text-white hover:bg-[#16243c]`}>
              Ver la sesión <ArrowRight className="w-5 h-5" />
            </button>
          </div>
        </div>
      )}
    </div>
  );
}
