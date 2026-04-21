import { useState, useCallback, useEffect } from 'react';
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
} from 'lucide-react';
import { testAPI, clientsAPI } from '../../services/api';
import type { ClientInfo } from '../../types';
import LoadingSpinner from '../common/LoadingSpinner';

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
  const [detectedLabels, setDetectedLabels] = useState<string[]>([]);
  const [extractingLabels, setExtractingLabels] = useState(false);

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

  const extractLabelsFromFile = useCallback(async (file: File) => {
    try {
      setExtractingLabels(true);
      const response = await testAPI.extractJTLLabels(file);
      setDetectedLabels(response.labels || []);
    } catch (err) {
      console.error('Error extracting labels:', err);
      setDetectedLabels([]);
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
        extractLabelsFromFile(validFiles[0]);
      }
      return combined;
    });
  }, [extractLabelsFromFile]);

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
        setDetectedLabels([]);
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

      const acceptanceCriteria = JSON.stringify({
        concurrency: parseInt(concurrency) || 100,
        response_time: parseInt(responseTime) || 2000,
        availability: parseFloat(availability) || 99.5,
        ...(Object.keys(perTransaction).length > 0 ? { per_transaction: perTransaction } : {}),
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
            Criterios de Aceptacion
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

          {/* HF2: Criterios por Transaccion — labels detectados del JTL */}
          {extractingLabels && (
            <p className="mt-4 text-lg text-gray-400 animate-pulse">
              Detectando transacciones del archivo...
            </p>
          )}

          {detectedLabels.length > 0 && (
            <details className="mt-5">
              <summary className="cursor-pointer text-lg font-medium text-gray-600 hover:text-gray-800">
                Criterios por Transaccion ({detectedLabels.length} transacciones detectadas)
              </summary>
              <div className="mt-3 space-y-3 pl-4 border-l-2 border-[#f5a623] max-h-96 overflow-y-auto">
                {detectedLabels.map(label => (
                  <div key={label} className="bg-white rounded-xl p-3 border border-gray-200">
                    <h4 className="text-base font-semibold text-gray-700 mb-2">{label}</h4>
                    <div className="grid grid-cols-3 gap-3">
                      <div>
                        <label className="text-sm text-gray-500 block mb-1">Concurrencia Esperada</label>
                        <input type="number" value={transactionCriteria[label]?.concurrency || ''} placeholder={`ej: ${concurrency}`}
                          onChange={(e) => setTransactionCriteria(prev => ({ ...prev, [label]: { ...prev[label], concurrency: e.target.value } }))}
                          className="w-full border border-gray-300 rounded-lg px-3 py-2 text-base focus:border-[#f5a623]" />
                      </div>
                      <div>
                        <label className="text-sm text-gray-500 block mb-1">Response Time (ms)</label>
                        <input type="number" value={transactionCriteria[label]?.response_time || ''} placeholder={`ej: ${responseTime}`}
                          onChange={(e) => setTransactionCriteria(prev => ({ ...prev, [label]: { ...prev[label], response_time: e.target.value } }))}
                          className="w-full border border-gray-300 rounded-lg px-3 py-2 text-base focus:border-[#f5a623]" />
                      </div>
                      <div>
                        <label className="text-sm text-gray-500 block mb-1">Disponibilidad (%)</label>
                        <input type="number" step="0.1" value={transactionCriteria[label]?.availability || ''} placeholder={`ej: ${availability}`}
                          onChange={(e) => setTransactionCriteria(prev => ({ ...prev, [label]: { ...prev[label], availability: e.target.value } }))}
                          className="w-full border border-gray-300 rounded-lg px-3 py-2 text-base focus:border-[#f5a623]" />
                      </div>
                    </div>
                  </div>
                ))}

                {/* Boton para aplicar mismo criterio a todas */}
                <div className="mt-3 p-3 bg-blue-50 rounded-xl border border-blue-200">
                  <p className="text-sm text-gray-600 mb-2">Aplicar mismo criterio a todas las transacciones:</p>
                  <div className="grid grid-cols-4 gap-3">
                    <input type="number" placeholder="Concurrencia" id="bulk-conc"
                      className="border border-gray-300 rounded-lg px-3 py-2 text-base focus:border-[#f5a623]" />
                    <input type="number" placeholder="RT (ms)" id="bulk-rt"
                      className="border border-gray-300 rounded-lg px-3 py-2 text-base focus:border-[#f5a623]" />
                    <input type="number" step="0.1" placeholder="Disp. %" id="bulk-avail"
                      className="border border-gray-300 rounded-lg px-3 py-2 text-base focus:border-[#f5a623]" />
                    <button
                      type="button"
                      onClick={() => {
                        const concVal = (document.getElementById('bulk-conc') as HTMLInputElement)?.value || '';
                        const rtVal = (document.getElementById('bulk-rt') as HTMLInputElement)?.value || '';
                        const availVal = (document.getElementById('bulk-avail') as HTMLInputElement)?.value || '';
                        const bulk: Record<string, Record<string, string>> = {};
                        detectedLabels.forEach(label => {
                          bulk[label] = {
                            ...(transactionCriteria[label] || {}),
                            ...(concVal ? { concurrency: concVal } : {}),
                            ...(rtVal ? { response_time: rtVal } : {}),
                            ...(availVal ? { availability: availVal } : {}),
                          };
                        });
                        setTransactionCriteria(prev => ({ ...prev, ...bulk }));
                      }}
                      className="px-4 py-2 rounded-lg text-white text-base font-semibold"
                      style={{ backgroundColor: '#f5a623' }}
                    >
                      Aplicar a todas
                    </button>
                  </div>
                </div>
              </div>
            </details>
          )}
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
