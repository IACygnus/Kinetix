import { Fragment, useState, useCallback, useEffect } from 'react';
import {
  Upload,
  FileText,
  AlertCircle,
  Settings,
  FolderOpen,
  Zap,
  X,
  AlertTriangle,
  CheckCircle,
  File as FileIcon,
  ChevronRight,
  ChevronDown,
} from 'lucide-react';
import { testAPI, clientsAPI } from '../../services/api';
import type { TransactionMetrics } from '../../services/api';   // N3.3
import type { ClientInfo } from '../../types';
import LoadingSpinner from '../common/LoadingSpinner';
import { evaluarCriticidad } from '../../utils/criticidad';   // ETAPA 5 (D42)

interface UploadJTLProps {
  onUploadSuccess: (id: string) => void;
}

type TestType = 'load' | 'stress' | 'endurance' | 'scalability' | 'spike' | 'smoke';

interface TestTypeOption {
  value: TestType;
  label: string;
  description: string;
  color: string;
  bgColor: string;
}

const TEST_TYPE_OPTIONS: TestTypeOption[] = [
  { value: 'load', label: 'Load Test', description: 'Carga esperada', color: 'text-blue-700', bgColor: 'bg-blue-50 border-blue-300' },
  { value: 'stress', label: 'Stress Test', description: 'Punto de quiebre', color: 'text-red-700', bgColor: 'bg-red-50 border-red-300' },
  { value: 'endurance', label: 'Endurance Test', description: 'Estabilidad prolongada', color: 'text-emerald-700', bgColor: 'bg-emerald-50 border-emerald-300' },
  { value: 'scalability', label: 'Scalability Test', description: 'Escalamiento gradual', color: 'text-purple-700', bgColor: 'bg-purple-50 border-purple-300' },
  { value: 'spike', label: 'Spike Test', description: 'Picos subitos', color: 'text-orange-700', bgColor: 'bg-orange-50 border-orange-300' },
  { value: 'smoke', label: 'Smoke Test', description: 'Validacion basica', color: 'text-gray-700', bgColor: 'bg-gray-50 border-gray-300' },
];

interface ValidationWarning {
  warnings: string[];
  errors: string[];
  compatible: boolean;
  summary: Record<string, unknown> | null;
}

export default function UploadJTL({ onUploadSuccess }: UploadJTLProps) {
  const [files, setFiles] = useState<File[]>([]);
  const [clientId, setClientId] = useState('');
  const [clientName, setClientName] = useState('');
  const [clients, setClients] = useState<ClientInfo[]>([]);
  const [project, setProject] = useState('');
  const [testType, setTestType] = useState<TestType>('load');

  // Criterios de aceptacion
  const [concurrency, setConcurrency] = useState('100');
  const [responseTime, setResponseTime] = useState('2000');
  const [availability, setAvailability] = useState('99.5');

  // KNX-08: Unidad de medida para análisis AI
  const [metricUnit, setMetricUnit] = useState<'TPS' | 'UVC'>('TPS');

  // HF2: Criterios por transaccion (labels detectados del JTL)
  const [transactionCriteria, setTransactionCriteria] = useState<Record<string, Record<string, string>>>({});
  const [extractingLabels, setExtractingLabels] = useState(false);

  // N3.3: metricas por transaccion + seleccion para analisis individual.
  // `manualSel` guarda SOLO lo que Fredy toca; la seleccion efectiva se deriva
  // de la sugerencia del backend con su override encima. Asi, al re-evaluar la
  // criticidad (porque cambiaron los criterios) no se pierde lo que ya marco.
  const [transactions, setTransactions] = useState<TransactionMetrics[]>([]);
  const [manualSel, setManualSel] = useState<Record<string, boolean>>({});
  // ETAPA 5 (D40): que filas estan desplegadas. Varias a la vez.
  const [filasAbiertas, setFilasAbiertas] = useState<Record<string, boolean>>({});

  const [dragActive, setDragActive] = useState(false);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState('');

  // Validation modal
  const [validationResult, setValidationResult] = useState<ValidationWarning | null>(null);
  const [showValidationModal, setShowValidationModal] = useState(false);
  const [validating, setValidating] = useState(false);

  // Fetch available clients on mount
  useEffect(() => {
    clientsAPI.getMyClients().then(setClients).catch(() => {});
  }, []);

  const handleDrag = useCallback((e: React.DragEvent) => {
    e.preventDefault();
    e.stopPropagation();
    if (e.type === 'dragenter' || e.type === 'dragover') {
      setDragActive(true);
    } else if (e.type === 'dragleave') {
      setDragActive(false);
    }
  }, []);

  // N3.3: primero el endpoint nuevo (metricas + criticidad, soporta XML y no
  // trunca a 10.000 lineas). Si falla por lo que sea, se cae al viejo y el
  // panel queda como estaba antes: sin metricas pero sin pantalla rota.
  const extractLabelsFromFile = useCallback(async (file: File, rt?: string, av?: string) => {
    try {
      setExtractingLabels(true);
      const data = await testAPI.extractJTLTransactions(file, rt, av);
      setTransactions(data.transactions || []);
    } catch (err) {
      // ETAPA 5 (D40/D43): los criterios por transaccion viven DENTRO de la fila
      // de cada transaccion, y una fila necesita sus metricas. Si este endpoint
      // falla no hay metricas, asi que no hay panel: quedan los criterios
      // generales, que se aplican a todo. Antes el respaldo pintaba la lista de
      // nombres para el bloque desplegable, que ya no existe.
      console.error('extract-jtl-transactions fallo; el panel queda sin transacciones:', err);
      setTransactions([]);
    } finally {
      setExtractingLabels(false);
    }
  }, []);

  const addFiles = useCallback((newFiles: FileList | File[]) => {
    const validFiles: File[] = [];
    for (let i = 0; i < newFiles.length; i++) {
      const f = newFiles[i];
      if (f.name.endsWith('.jtl') || f.name.endsWith('.csv') || f.name.endsWith('.xml')) {
        validFiles.push(f);
      }
    }

    if (validFiles.length === 0) {
      setError('Solo se permiten archivos .jtl, .csv o .xml');
      return;
    }

    setFiles((prev) => {
      const combined = [...prev, ...validFiles];
      if (combined.length > 5) {
        setError('Maximo 5 archivos JTL permitidos');
        return prev;
      }
      setError('');
      // Extraer labels del primer archivo
      if (prev.length === 0 && validFiles.length > 0) {
        extractLabelsFromFile(validFiles[0], responseTime, availability);
      }
      return combined;
    });
  }, [extractLabelsFromFile, responseTime, availability]);

  // ETAPA 5 (D42): aqui vivia un `useEffect` con 800 ms de debounce que RESUBIA
  // el JTL entero cada vez que cambiaba un criterio global, para que el backend
  // recalculara la criticidad. Con criterios por fila (D40) eso seria una
  // resubida por tecla. La regla se recalcula ahora en el cliente con
  // `criticidad.ts`, que es el puerto literal de la del backend y tiene pruebas
  // de paridad sobre los mismos casos. Las metricas siguen viniendo del
  // endpoint: lo unico que se movio es la decision de "critica o no".

  // ETAPA 5 (D42): la criticidad se recalcula AQUI, al instante, con el puerto
  // en TS de la misma regla del backend (`criticidad.ts`, con pruebas de
  // paridad). Antes venia solo del backend y editar un criterio obligaba a
  // resubir el JTL entero.
  const criteriosEfectivos = useCallback((label: string) => {
    const propios = transactionCriteria[label] || {};
    return {
      response_time: propios.response_time || responseTime,
      availability: propios.availability || availability,
    };
  }, [transactionCriteria, responseTime, availability]);

  // D41: una fila "tiene criterios propios" si escribio alguno de los tres.
  const tieneCriteriosPropios = useCallback((label: string) => {
    const c = transactionCriteria[label] || {};
    return Boolean(c.concurrency || c.response_time || c.availability);
  }, [transactionCriteria]);

  const criticidadDe = useCallback(
    (t: TransactionMetrics) => evaluarCriticidad(t, criteriosEfectivos(t.label)),
    [criteriosEfectivos],
  );

  // Seleccion efectiva = sugerencia (ahora recalculada aqui) + lo que Fredy toque.
  const isSelected = (t: TransactionMetrics) => manualSel[t.label] ?? criticidadDe(t).esCritica;
  const selectedLabels = transactions.filter(isSelected).map(t => t.label);
  const setAll = (value: boolean | null) => {
    if (value === null) { setManualSel({}); return; }   // volver a la sugerencia
    setManualSel(Object.fromEntries(transactions.map(t => [t.label, value])));
  };
  const fmt = (n: number) => Math.round(n).toLocaleString('es-CO');
  const fmt2 = (n: number) => n.toLocaleString('es-CO', { minimumFractionDigits: 2, maximumFractionDigits: 2 });

  const handleDrop = useCallback(
    (e: React.DragEvent) => {
      e.preventDefault();
      e.stopPropagation();
      setDragActive(false);
      if (e.dataTransfer.files && e.dataTransfer.files.length > 0) {
        addFiles(e.dataTransfer.files);
      }
    },
    [addFiles]
  );

  const handleFileChange = (e: React.ChangeEvent<HTMLInputElement>) => {
    if (e.target.files && e.target.files.length > 0) {
      addFiles(e.target.files);
    }
    // Reset input
    e.target.value = '';
  };

  const removeFile = (index: number) => {
    setFiles((prev) => {
      const updated = prev.filter((_, i) => i !== index);
      if (updated.length === 0) {
        setFilasAbiertas({});
        setTransactionCriteria({});
      }
      return updated;
    });
    setError('');
  };

  const formatFileSize = (bytes: number): string => {
    if (bytes < 1024) return `${bytes} B`;
    if (bytes < 1024 * 1024) return `${(bytes / 1024).toFixed(1)} KB`;
    return `${(bytes / (1024 * 1024)).toFixed(1)} MB`;
  };

  const handleSubmit = async () => {
    if (files.length === 0) {
      setError('Selecciona al menos un archivo JTL');
      return;
    }

    if (!project) {
      setError('El nombre del proyecto es obligatorio');
      return;
    }

    // Si hay multiples archivos, validar primero
    if (files.length > 1 && !validationResult) {
      await validateFiles();
      return;
    }

    // Si la validacion tiene errores, no continuar
    if (validationResult && !validationResult.compatible) {
      setError('Los archivos no son compatibles. Corrige los errores antes de continuar.');
      return;
    }

    await uploadFiles();
  };

  const validateFiles = async () => {
    setValidating(true);
    setError('');
    try {
      const result = await testAPI.validateJTL(files);
      setValidationResult(result);

      if (!result.compatible) {
        setShowValidationModal(true);
      } else if (result.warnings && result.warnings.length > 0) {
        setShowValidationModal(true);
      } else {
        // Todo ok, subir directamente
        await uploadFiles();
      }
    } catch (err: unknown) {
      const axiosErr = err as { response?: { data?: { detail?: string } } };
      setError(axiosErr.response?.data?.detail || 'Error validando archivos');
    } finally {
      setValidating(false);
    }
  };

  const uploadFiles = async () => {
    setLoading(true);
    setError('');
    setShowValidationModal(false);

    try {
      // Build per_transaction from detected labels criteria (error_rate fijo 0.5%)
      const perTransaction: Record<string, Record<string, number>> = {};
      Object.entries(transactionCriteria).forEach(([label, vals]) => {
        const hasValues = vals.concurrency || vals.response_time || vals.availability;
        if (hasValues) {
          perTransaction[label] = {
            concurrency: Number(vals.concurrency) || parseInt(concurrency) || 100,
            response_time: Number(vals.response_time) || parseInt(responseTime) || 2000,
            availability: Number(vals.availability) || parseFloat(availability) || 99.5,
            error_rate: 0.5,
          };
        }
      });

      // N3.3: las marcadas viajan como una clave nueva del mismo JSON de
      // criterios. Es aditivo: si no hay ninguna la clave no se emite y el
      // payload queda byte a byte como antes. En N3.3 el backend la ignora;
      // N3.4 la leera para saber que transacciones analizar.
      const acceptanceCriteria = JSON.stringify({
        concurrency: parseInt(concurrency) || 100,
        response_time: parseInt(responseTime) || 2000,
        availability: parseFloat(availability) || 99.5,
        ...(Object.keys(perTransaction).length > 0 ? { per_transaction: perTransaction } : {}),
        ...(selectedLabels.length > 0 ? { critical_transactions: selectedLabels } : {}),
      });

      const result = await testAPI.uploadJTL(
        files,
        project,
        clientName ? `Cliente: ${clientName}` : '',
        testType,
        clientName,
        project,
        acceptanceCriteria,
        clientId,
        metricUnit,
      );
      // Store AI status for toast notification on Dashboard
      if (result.ai_status) {
        sessionStorage.setItem('ai_status', JSON.stringify(result.ai_status));
      }
      onUploadSuccess(result.id);
    } catch (err: unknown) {
      const axiosErr = err as { response?: { data?: { detail?: string } } };
      setError(axiosErr.response?.data?.detail || 'Error al subir los archivos');
      setLoading(false);
    }
  };

  if (loading) {
    return (
      <LoadingSpinner
        message={`Procesando ${files.length} archivo(s) JTL y generando analisis...`}
      />
    );
  }

  return (
    <div className="w-full space-y-6">
      {/* Header */}
      <div className="bg-white rounded-2xl shadow-lg p-8 border border-gray-200">
        <div className="flex items-center justify-center">
          <Settings className="w-10 h-10 mr-4 text-sqa-gold" />
          <div className="text-center">
            <h2 className="text-4xl font-bold text-gray-800 mb-1">
              Configuracion del Reporte de Performance
            </h2>
            <p className="text-xl text-gray-500">
              Configure los parametros y seleccione los archivos JTL para analizar
            </p>
          </div>
        </div>
      </div>

      <div className="bg-white rounded-2xl shadow-lg p-8 space-y-8 border border-gray-200">
        {/* Tipo de Prueba */}
        <div>
          <h3 className="text-xl font-semibold text-gray-700 mb-3 uppercase tracking-wider">
            Tipo de Prueba
          </h3>
          <div className="grid grid-cols-2 md:grid-cols-3 gap-4">
            {TEST_TYPE_OPTIONS.map((opt) => (
              <button
                key={opt.value}
                onClick={() => setTestType(opt.value)}
                className={`p-5 rounded-xl border text-left transition-all ${
                  testType === opt.value
                    ? `${opt.bgColor} border-2 ring-1 ring-offset-0 ring-offset-transparent`
                    : 'bg-gray-50 border-gray-200 hover:border-gray-400'
                }`}
              >
                <p className={`font-semibold text-xl ${testType === opt.value ? opt.color : 'text-gray-700'}`}>
                  {opt.label}
                </p>
                <p className="text-lg text-gray-500 mt-1">{opt.description}</p>
              </button>
            ))}
          </div>
        </div>

        {/* Cliente y Proyecto */}
        <div className="grid grid-cols-1 md:grid-cols-2 gap-6">
          <div>
            <label className="flex items-center text-xl font-semibold text-gray-700 mb-2">
              <FolderOpen className="w-7 h-7 mr-2 text-sqa-gold" />
              Cliente
            </label>
            <select
              value={clientId}
              onChange={(e) => {
                setClientId(e.target.value);
                const selected = clients.find((c) => c.id === e.target.value);
                setClientName(selected ? selected.name : '');
              }}
              className="w-full px-5 h-14 bg-gray-50 border border-gray-300 rounded-xl text-xl text-gray-800 focus:outline-none focus:border-sqa-gold focus:ring-2 focus:ring-sqa-gold/20 transition-colors appearance-none"
            >
              <option value="">Seleccionar cliente...</option>
              {clients.map((c) => (
                <option key={c.id} value={c.id}>
                  {c.name}
                </option>
              ))}
            </select>
          </div>

          <div>
            <label className="flex items-center text-xl font-semibold text-gray-700 mb-2">
              <FileText className="w-7 h-7 mr-2 text-sqa-gold" />
              Proyecto *
            </label>
            <input
              type="text"
              value={project}
              onChange={(e) => setProject(e.target.value)}
              className="w-full px-5 h-14 bg-gray-50 border border-gray-300 rounded-xl text-xl text-gray-800 placeholder:text-gray-400 focus:outline-none focus:border-sqa-gold focus:ring-2 focus:ring-sqa-gold/20 transition-colors"
              placeholder="Nombre del proyecto"
              required
            />
          </div>
        </div>

        {/* Archivos JTL */}
        <div>
          <h3 className="text-xl font-semibold text-gray-700 mb-3 uppercase tracking-wider">
            Archivos JTL (1-5 archivos)
          </h3>

          <div
            className={`border-2 border-dashed rounded-2xl p-10 text-center transition-all ${
              dragActive
                ? 'border-sqa-gold bg-sqa-gold/5'
                : 'border-gray-300 bg-gray-50 hover:border-gray-400'
            }`}
            onDragEnter={handleDrag}
            onDragLeave={handleDrag}
            onDragOver={handleDrag}
            onDrop={handleDrop}
          >
            <Upload
              className={`mx-auto h-14 w-14 mb-4 ${
                dragActive ? 'text-sqa-gold' : 'text-gray-400'
              }`}
            />

            <label className="cursor-pointer">
              <span className="inline-block bg-sqa-gold text-sqa-navy px-8 py-3 rounded-xl font-bold hover:bg-sqa-gold-light transition-colors text-xl">
                Seleccionar Archivos
              </span>
              <input
                type="file"
                className="hidden"
                accept=".jtl,.csv,.xml"
                multiple
                onChange={handleFileChange}
              />
            </label>

            <p className="text-xl text-gray-500 mt-4">
              Arrastra archivos o haz clic para seleccionar. Formatos: .jtl, .csv (Locust), .xml (WAPT)
            </p>
          </div>

          {/* File list */}
          {files.length > 0 && (
            <div className="mt-4 space-y-2">
              {files.map((f, i) => (
                <div
                  key={`${f.name}-${i}`}
                  className="flex items-center justify-between bg-gray-50 border border-gray-200 rounded-xl px-5 py-4"
                >
                  <div className="flex items-center gap-3 min-w-0">
                    <FileIcon className="w-7 h-7 text-sqa-gold flex-shrink-0" />
                    <span className="text-xl text-gray-800 truncate">{f.name}</span>
                    <span className="text-lg text-gray-500 flex-shrink-0">
                      {formatFileSize(f.size)}
                    </span>
                  </div>
                  <button
                    onClick={() => removeFile(i)}
                    className="p-1 text-gray-400 hover:text-red-500 transition-colors flex-shrink-0"
                  >
                    <X className="w-7 h-7" />
                  </button>
                </div>
              ))}
              <p className="text-lg text-gray-500">
                {files.length} de 5 archivos seleccionados
                {files.length > 1 && ' (se consolidaran en un solo analisis)'}
              </p>
            </div>
          )}
        </div>

        {/* Criterios de Aceptacion */}
        <div className="p-6 bg-gray-50 rounded-2xl border border-gray-200">
          <h3 className="text-xl font-semibold text-gray-700 mb-4 uppercase tracking-wider">
            Criterios de aceptación
          </h3>

          <div className="grid grid-cols-1 md:grid-cols-3 gap-5">
            <div>
              <label className="text-xl font-medium text-gray-600 mb-2 block">
                Concurrencia Esperada
              </label>
              <input
                type="number"
                value={concurrency}
                onChange={(e) => setConcurrency(e.target.value)}
                className="w-full px-5 h-14 bg-white border border-gray-300 rounded-xl text-xl text-gray-800 placeholder:text-gray-400 focus:outline-none focus:border-sqa-gold focus:ring-2 focus:ring-sqa-gold/20 transition-colors"
                placeholder="100"
              />
            </div>

            <div>
              <label className="text-xl font-medium text-gray-600 mb-2 block">
                Tiempo de Respuesta (ms)
              </label>
              <input
                type="number"
                value={responseTime}
                onChange={(e) => setResponseTime(e.target.value)}
                className="w-full px-5 h-14 bg-white border border-gray-300 rounded-xl text-xl text-gray-800 placeholder:text-gray-400 focus:outline-none focus:border-sqa-gold focus:ring-2 focus:ring-sqa-gold/20 transition-colors"
                placeholder="2000"
              />
            </div>

            <div>
              <label className="text-xl font-medium text-gray-600 mb-2 block">
                Disponibilidad (%)
              </label>
              <input
                type="number"
                step="0.1"
                value={availability}
                onChange={(e) => setAvailability(e.target.value)}
                className="w-full px-5 h-14 bg-white border border-gray-300 rounded-xl text-xl text-gray-800 placeholder:text-gray-400 focus:outline-none focus:border-sqa-gold focus:ring-2 focus:ring-sqa-gold/20 transition-colors"
                placeholder="99.5"
              />
            </div>
          </div>

          {/* KNX-08: Selector de unidad de medida para análisis AI */}
          <div className="mt-5">
            <label className="text-xl font-medium text-gray-600 mb-2 block">
              Unidad de medida en el analisis AI
            </label>
            <div className="flex gap-6">
              <label className="flex items-center gap-2 cursor-pointer">
                <input
                  type="radio"
                  name="metric_unit"
                  value="TPS"
                  checked={metricUnit === 'TPS'}
                  onChange={() => setMetricUnit('TPS')}
                  className="w-5 h-5 text-[#f5a623] focus:ring-[#f5a623]"
                />
                <span className="text-lg text-gray-700">TPS (Transacciones por segundo)</span>
              </label>
              <label className="flex items-center gap-2 cursor-pointer">
                <input
                  type="radio"
                  name="metric_unit"
                  value="UVC"
                  checked={metricUnit === 'UVC'}
                  onChange={() => setMetricUnit('UVC')}
                  className="w-5 h-5 text-[#f5a623] focus:ring-[#f5a623]"
                />
                <span className="text-lg text-gray-700">UVC (Usuarios virtuales concurrentes)</span>
              </label>
            </div>
          </div>

          {/* ETAPA 5 (D40): las transacciones del JTL, con sus criterios dentro. */}
          {extractingLabels && (
            <p className="mt-4 text-lg text-gray-400 animate-pulse">
              Detectando transacciones del archivo...
            </p>
          )}

          {/* N3.3: transacciones con metricas reales y seleccion para analisis
              individual. Solo aparece si el endpoint nuevo respondio; en
              el panel no se pinta (ver el comentario de extractLabelsFromFile). */}
          {transactions.length > 0 && (
            <div className="mt-5 bg-white rounded-xl border border-gray-200 p-4">
              <div className="flex flex-wrap items-center justify-between gap-3 mb-3">
                <div>
                  <h3 className="text-lg font-semibold text-gray-700">Transacciones del JTL</h3>
                  <p className="text-sm text-gray-500">
                    {selectedLabels.length} de {transactions.length} transacciones marcadas para análisis individual
                  </p>
                </div>
                <div className="flex gap-2">
                  <button type="button" onClick={() => setAll(true)}
                    className="px-3 py-1.5 text-sm rounded-lg border border-gray-300 hover:bg-gray-50">Marcar todas</button>
                  <button type="button" onClick={() => setAll(null)}
                    className="px-3 py-1.5 text-sm rounded-lg border border-gray-300 hover:bg-gray-50">Solo críticas</button>
                  <button type="button" onClick={() => setAll(false)}
                    className="px-3 py-1.5 text-sm rounded-lg border border-gray-300 hover:bg-gray-50">Ninguna</button>
                </div>
              </div>

              {selectedLabels.length > 10 && (
                <div className="mb-3 p-3 rounded-lg bg-amber-50 border border-amber-300 text-sm text-amber-800">
                  {selectedLabels.length} transacciones marcadas: el análisis añadirá ~{selectedLabels.length} llamadas
                  de IA y varios minutos al procesamiento.
                </div>
              )}

              <div className="max-h-96 overflow-y-auto">
                {/* ETAPA 5 (D39): las columnas de v1.2 §2.1 — sin p90 ni Max, con TPS. */}
                <table className="w-full text-sm">
                  <thead className="text-xs uppercase text-gray-500 border-b border-gray-200">
                    {/* ETAPA 5b (D54): sale la flecha de la izquierda y entra una
                        ultima columna "Criterios" con un boton por fila. */}
                    <tr>
                      <th className="py-2 pr-2 text-left w-8"></th>
                      <th className="py-2 pr-2 text-left">Transacción</th>
                      <th className="py-2 px-2 text-right">Muestras</th>
                      <th className="py-2 px-2 text-right">Promedio</th>
                      <th className="py-2 px-2 text-right">TPS</th>
                      <th className="py-2 px-2 text-right">Errores</th>
                      <th className="py-2 pl-2 text-center">Criterios</th>
                    </tr>
                  </thead>
                  <tbody>
                    {transactions.map(t => {
                      const { esCritica, motivos } = criticidadDe(t);
                      const abierta = Boolean(filasAbiertas[t.label]);
                      const propios = transactionCriteria[t.label] || {};
                      const conPropios = tieneCriteriosPropios(t.label);
                      const motivo = motivos.join(' · ');
                      return (
                        <Fragment key={t.label}>
                          <tr className={`border-b border-gray-100 ${esCritica ? 'bg-amber-50/60' : ''}`}>
                            <td className="py-2 pr-2 align-top">
                              <input type="checkbox" checked={isSelected(t)}
                                onChange={e => setManualSel(prev => ({ ...prev, [t.label]: e.target.checked }))}
                                className="w-4 h-4 accent-[#f5a623] cursor-pointer" />
                            </td>
                            <td className="py-2 pr-2">
                              <span className="font-medium text-gray-700">{t.label}</span>
                              {esCritica && (
                                <span className="ml-2 px-1.5 py-0.5 text-xs rounded bg-amber-200 text-amber-900">crítica</span>
                              )}
                              {conPropios && (
                                <span className="ml-2 px-1.5 py-0.5 text-xs rounded bg-indigo-100 text-indigo-800">criterios propios</span>
                              )}
                              {motivo && (
                                <div className="text-xs text-gray-500 mt-0.5" title={motivo}>{motivo}</div>
                              )}
                            </td>
                            <td className="py-2 px-2 text-right tabular-nums text-gray-600">{fmt(t.muestras)}</td>
                            <td className="py-2 px-2 text-right tabular-nums text-gray-600">{fmt(t.promedio)} ms</td>
                            <td className="py-2 px-2 text-right tabular-nums text-gray-600">{fmt2(t.tps)}</td>
                            <td className="py-2 px-2 text-right tabular-nums text-gray-600">
                              {fmt(t.errores)} <span className="text-gray-400">({fmt2(t.tasa_error)}%)</span>
                            </td>
                            {/* ETAPA 5b (D54): el boton dice de un vistazo con que se
                                evalua la fila, y es lo que abre sus criterios. D40 sigue
                                en pie: pueden estar varias filas abiertas a la vez. */}
                            <td className="py-2 pl-2 text-center">
                              <button type="button"
                                data-testid="boton-criterios"
                                data-tx={t.label}
                                data-estado={conPropios ? 'propios' : 'globales'}
                                aria-label={`Criterios de ${t.label}`}
                                aria-expanded={abierta}
                                onClick={() => setFilasAbiertas(p => ({ ...p, [t.label]: !p[t.label] }))}
                                className={`inline-flex items-center gap-1 px-2.5 py-1 text-xs font-semibold rounded-lg border transition-colors ${
                                  conPropios
                                    ? 'border-indigo-300 bg-indigo-100 text-indigo-800 hover:bg-indigo-200'
                                    : 'border-gray-300 bg-gray-100 text-gray-600 hover:bg-gray-200'
                                }`}>
                                {conPropios ? 'Propios' : 'Globales'}
                                {abierta ? <ChevronDown className="w-3.5 h-3.5" /> : <ChevronRight className="w-3.5 h-3.5" />}
                              </button>
                            </td>
                          </tr>
                          {abierta && (
                            <tr className="border-b border-gray-100 bg-gray-50/70">
                              <td colSpan={7} className="px-4 py-3">
                                <div className="flex flex-wrap items-end justify-between gap-3">
                                  <p className="text-sm text-gray-500">
                                    Criterios de aceptación de esta transacción.{' '}
                                    {conPropios
                                      ? 'Se evalúa con estos valores.'
                                      : 'Sin valores propios se evalúa con los criterios generales de arriba.'}
                                  </p>
                                  {/* D41: volver a los globales limpia los propios. */}
                                  <button type="button" disabled={!conPropios}
                                    onClick={() => setTransactionCriteria(prev => {
                                      const copia = { ...prev };
                                      delete copia[t.label];
                                      return copia;
                                    })}
                                    className="px-3 py-1.5 text-sm rounded-lg border border-gray-300 hover:bg-white disabled:opacity-40 disabled:cursor-not-allowed">
                                    Usar globales
                                  </button>
                                </div>
                                <div className="grid grid-cols-1 sm:grid-cols-3 gap-3 mt-3">
                                  {([
                                    ['concurrency', 'Concurrencia esperada', concurrency, '1'],
                                    ['response_time', 'Tiempo de respuesta (ms)', responseTime, '1'],
                                    ['availability', 'Disponibilidad (%)', availability, '0.1'],
                                  ] as const).map(([campo, etiqueta, global, paso]) => (
                                    <div key={campo}>
                                      <label className="text-sm text-gray-500 block mb-1">{etiqueta}</label>
                                      <input type="number" step={paso}
                                        value={propios[campo] || ''}
                                        placeholder={global}
                                        onChange={e => setTransactionCriteria(prev => ({
                                          ...prev, [t.label]: { ...prev[t.label], [campo]: e.target.value },
                                        }))}
                                        className="w-full border border-gray-300 rounded-lg px-3 py-2 text-base focus:border-[#f5a623]" />
                                    </div>
                                  ))}
                                </div>
                                <p className="text-xs text-gray-400 mt-2">
                                  La marca de crítica se recalcula con el tiempo de respuesta y la
                                  disponibilidad. La concurrencia se guarda con el informe pero no
                                  interviene en ese cálculo.
                                </p>
                              </td>
                            </tr>
                          )}
                        </Fragment>
                      );
                    })}
                  </tbody>
                </table>
              </div>
            </div>
          )}

          {/* ETAPA 5 (D43): aqui vivia el bloque desplegable "Criterios por
              Transaccion". Sus tres campos se mudaron dentro de la fila de cada
              transaccion (D40), que es donde se ven junto a sus metricas. */}
        </div>

        {/* Error */}
        {error && (
          <div className="bg-red-50 border border-red-200 rounded-xl p-5 flex items-start gap-3">
            <AlertCircle className="w-7 h-7 text-red-500 flex-shrink-0 mt-0.5" />
            <span className="text-red-700 text-xl">{error}</span>
          </div>
        )}

        {/* Submit */}
        <div className="flex justify-end">
          <button
            onClick={handleSubmit}
            disabled={files.length === 0 || !project || validating}
            className="bg-sqa-gold text-sqa-navy font-bold h-16 px-14 rounded-xl text-xl hover:bg-sqa-gold-light disabled:bg-gray-300 disabled:text-gray-500 disabled:cursor-not-allowed transition-all shadow-lg hover:shadow-xl flex items-center gap-3"
          >
            {validating ? (
              <>
                <div className="w-7 h-7 border-2 border-sqa-navy/30 border-t-sqa-navy rounded-full animate-spin" />
                <span>Validando...</span>
              </>
            ) : (
              <>
                <Zap className="w-8 h-8" />
                <span>Generar Reporte</span>
              </>
            )}
          </button>
        </div>
      </div>

      {/* Validation Modal */}
      {showValidationModal && validationResult && (
        <div className="fixed inset-0 bg-black/60 backdrop-blur-sm flex items-center justify-center z-50 p-4">
          <div className="bg-white border border-gray-200 rounded-2xl w-full max-w-lg shadow-2xl">
            <div className="p-6">
              <div className="flex items-center gap-3 mb-4">
                {validationResult.compatible ? (
                  <AlertTriangle className="w-8 h-8 text-amber-500" />
                ) : (
                  <AlertCircle className="w-8 h-8 text-red-500" />
                )}
                <h3 className="text-3xl font-semibold text-gray-800">
                  {validationResult.compatible
                    ? 'Advertencias de Compatibilidad'
                    : 'Archivos Incompatibles'}
                </h3>
              </div>

              {validationResult.errors.length > 0 && (
                <div className="mb-4 space-y-2">
                  {validationResult.errors.map((err, i) => (
                    <div
                      key={i}
                      className="flex items-start gap-2 bg-red-50 border border-red-200 rounded-xl p-4"
                    >
                      <AlertCircle className="w-6 h-6 text-red-500 mt-0.5 flex-shrink-0" />
                      <span className="text-xl text-red-700">{err}</span>
                    </div>
                  ))}
                </div>
              )}

              {validationResult.warnings.length > 0 && (
                <div className="mb-4 space-y-2">
                  {validationResult.warnings.map((warn, i) => (
                    <div
                      key={i}
                      className="flex items-start gap-2 bg-amber-50 border border-amber-200 rounded-xl p-4"
                    >
                      <AlertTriangle className="w-6 h-6 text-amber-500 mt-0.5 flex-shrink-0" />
                      <span className="text-xl text-amber-700">{warn}</span>
                    </div>
                  ))}
                </div>
              )}

              {validationResult.summary && (
                <div className="bg-gray-50 border border-gray-200 rounded-xl p-4 mb-4">
                  <p className="text-lg text-gray-500 mb-1">Resumen:</p>
                  <div className="text-xl text-gray-700 space-y-1">
                    {Object.entries(validationResult.summary).map(([key, val]) => (
                      <p key={key}>
                        <span className="text-gray-500">{key}:</span>{' '}
                        {String(val)}
                      </p>
                    ))}
                  </div>
                </div>
              )}
            </div>

            <div className="border-t border-gray-200 p-5 flex justify-end gap-3">
              <button
                onClick={() => setShowValidationModal(false)}
                className="px-6 py-3 text-xl text-gray-500 hover:text-gray-700 transition-colors"
              >
                Cancelar
              </button>
              {validationResult.compatible && (
                <button
                  onClick={uploadFiles}
                  className="px-6 py-3 bg-sqa-gold text-sqa-navy rounded-xl hover:bg-sqa-gold-light text-xl font-bold transition-colors flex items-center gap-2"
                >
                  <CheckCircle className="w-6 h-6" />
                  Continuar de todas formas
                </button>
              )}
            </div>
          </div>
        </div>
      )}
    </div>
  );
}
