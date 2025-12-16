import { useState, useCallback } from 'react';
import { Upload, FileText, AlertCircle, Settings, FolderOpen, Zap } from 'lucide-react';
import { testAPI } from '../../services/api';
import LoadingSpinner from '../common/LoadingSpinner';

interface UploadJTLProps {
  onUploadSuccess: (id: string) => void;
}

export default function UploadJTL({ onUploadSuccess }: UploadJTLProps) {
  const [file, setFile] = useState<File | null>(null);
  const [cliente, setCliente] = useState('');
  const [proyecto, setProyecto] = useState('');
  
  // Criterios estructurados
  const [concurrenciaEsperada, setConcurrenciaEsperada] = useState('100');
  const [tiempoRespuesta, setTiempoRespuesta] = useState('2000');
  const [disponibilidad, setDisponibilidad] = useState('99.5');
  
  const [dragActive, setDragActive] = useState(false);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState('');

  const handleDrag = useCallback((e: React.DragEvent) => {
    e.preventDefault();
    e.stopPropagation();
    if (e.type === "dragenter" || e.type === "dragover") {
      setDragActive(true);
    } else if (e.type === "dragleave") {
      setDragActive(false);
    }
  }, []);

  const handleDrop = useCallback((e: React.DragEvent) => {
    e.preventDefault();
    e.stopPropagation();
    setDragActive(false);
    
    if (e.dataTransfer.files && e.dataTransfer.files[0]) {
      const droppedFile = e.dataTransfer.files[0];
      if (droppedFile.name.endsWith('.jtl') || droppedFile.name.endsWith('.csv')) {
        setFile(droppedFile);
        setError('');
      } else {
        setError('Solo se permiten archivos .jtl o .csv');
      }
    }
  }, []);

  const handleChange = (e: React.ChangeEvent<HTMLInputElement>) => {
    if (e.target.files && e.target.files[0]) {
      const selectedFile = e.target.files[0];
      setFile(selectedFile);
      setError('');
    }
  };

  const handleSubmit = async () => {
    if (!file) {
      setError('Por favor selecciona un archivo JTL');
      return;
    }

    if (!proyecto) {
      setError('Por favor ingresa el nombre del proyecto');
      return;
    }

    setLoading(true);
    setError('');

    try {
      // Construir criterios en formato texto
      const criteriosTexto = `• Tiempo de respuesta promedio < ${tiempoRespuesta}ms
• Tasa de error < ${(100 - parseFloat(disponibilidad))}%
• Throughput > ${parseFloat(concurrenciaEsperada) / 2} req/s`;

      const name = proyecto;
      const description = cliente ? `Cliente: ${cliente}` : '';

      const result = await testAPI.uploadJTL(file, name, description, criteriosTexto);
      onUploadSuccess(result.id);
    } catch (err: any) {
      setError(err.response?.data?.detail || 'Error al subir el archivo');
      setLoading(false);
    }
  };

  if (loading) {
    return <LoadingSpinner message="Procesando archivo JTL y generando análisis..." />;
  }

  return (
    <div className="max-w-5xl mx-auto">
      {/* Header Card Estilo SQA */}
      <div className="bg-gradient-to-r from-blue-700 via-blue-600 to-purple-600 rounded-2xl shadow-2xl p-8 mb-8 text-white border-4 border-blue-800">
        <div className="flex items-center justify-center mb-4">
          <Settings className="w-12 h-12 mr-4" />
          <div className="text-center">
            <h2 className="text-3xl font-bold mb-2">
              ⚙️ Configuración del Reporte de Performance
            </h2>
            <p className="text-blue-100">
              Configure los parámetros del proyecto y seleccione los archivos JTL
            </p>
          </div>
        </div>
      </div>

      <div className="bg-white rounded-2xl shadow-2xl p-8 border-2 border-blue-100">
        {/* Sección: Cliente y Proyecto */}
        <div className="grid grid-cols-1 md:grid-cols-2 gap-6 mb-8">
          <div>
            <label className="flex items-center text-sm font-semibold text-gray-700 mb-3">
              <FolderOpen className="w-4 h-4 mr-2 text-blue-600" />
              👤 Cliente
            </label>
            <input
              type="text"
              value={cliente}
              onChange={(e) => setCliente(e.target.value)}
              className="w-full px-4 py-3 border-2 border-blue-200 rounded-lg focus:ring-2 focus:ring-blue-500 focus:border-blue-500 transition-all"
              placeholder="Booking"
            />
          </div>

          <div>
            <label className="flex items-center text-sm font-semibold text-gray-700 mb-3">
              <FileText className="w-4 h-4 mr-2 text-blue-600" />
              📁 Proyecto
            </label>
            <input
              type="text"
              value={proyecto}
              onChange={(e) => setProyecto(e.target.value)}
              className="w-full px-4 py-3 border-2 border-blue-200 rounded-lg focus:ring-2 focus:ring-blue-500 focus:border-blue-500 transition-all"
              placeholder="Proyecto de Performance"
              required
            />
          </div>
        </div>

        {/* Sección: Seleccionar Archivos JTL */}
        <div className="mb-8 p-6 bg-blue-50 rounded-xl border-2 border-dashed border-blue-300">
          <h3 className="flex items-center text-lg font-bold text-gray-900 mb-4">
            📎 Seleccionar Archivos JTL
          </h3>
          
          <div
            className={`border-2 border-dashed rounded-xl p-8 text-center transition-all ${
              dragActive
                ? 'border-blue-500 bg-blue-100'
                : 'border-blue-300 bg-white hover:border-blue-400'
            }`}
            onDragEnter={handleDrag}
            onDragLeave={handleDrag}
            onDragOver={handleDrag}
            onDrop={handleDrop}
          >
            <Upload className={`mx-auto h-12 w-12 mb-3 ${dragActive ? 'text-blue-600' : 'text-gray-400'}`} />
            
            <label className="cursor-pointer">
              <span className="inline-block bg-blue-600 text-white px-6 py-3 rounded-lg font-semibold hover:bg-blue-700 transition-colors mb-3">
                📁 Seleccionar Archivo
              </span>
              <input
                type="file"
                className="hidden"
                accept=".jtl,.csv"
                onChange={handleChange}
              />
            </label>
            
            <p className="text-sm text-gray-500 mt-2">
              {file ? (
                <span className="text-blue-600 font-semibold">{file.name}</span>
              ) : (
                'No se ha seleccionado ningún archivo'
              )}
            </p>
          </div>
        </div>

        {/* Sección: Criterios de Aceptación */}
        <div className="mb-8 p-6 bg-purple-50 rounded-xl border-2 border-purple-200">
          <h3 className="flex items-center text-lg font-bold text-gray-900 mb-6">
            📋 Criterios de Aceptación
          </h3>
          
          <div className="grid grid-cols-1 md:grid-cols-3 gap-6">
            <div>
              <label className="flex items-center text-sm font-semibold text-gray-700 mb-2">
                ⚙️ Concurrencia Esperada
              </label>
              <input
                type="number"
                value={concurrenciaEsperada}
                onChange={(e) => setConcurrenciaEsperada(e.target.value)}
                className="w-full px-4 py-3 border-2 border-purple-200 rounded-lg focus:ring-2 focus:ring-purple-500 focus:border-purple-500 transition-all"
                placeholder="100"
              />
            </div>

            <div>
              <label className="flex items-center text-sm font-semibold text-gray-700 mb-2">
                ⏱️ Tiempo de Respuesta (ms)
              </label>
              <input
                type="number"
                value={tiempoRespuesta}
                onChange={(e) => setTiempoRespuesta(e.target.value)}
                className="w-full px-4 py-3 border-2 border-purple-200 rounded-lg focus:ring-2 focus:ring-purple-500 focus:border-purple-500 transition-all"
                placeholder="2000"
              />
            </div>

            <div>
              <label className="flex items-center text-sm font-semibold text-gray-700 mb-2">
                ✅ Disponibilidad (%)
              </label>
              <input
                type="number"
                step="0.1"
                value={disponibilidad}
                onChange={(e) => setDisponibilidad(e.target.value)}
                className="w-full px-4 py-3 border-2 border-purple-200 rounded-lg focus:ring-2 focus:ring-purple-500 focus:border-purple-500 transition-all"
                placeholder="99.5"
              />
            </div>
          </div>
        </div>

        {/* Error Message */}
        {error && (
          <div className="mb-6 bg-red-50 border-2 border-red-200 rounded-lg p-4 flex items-start">
            <AlertCircle className="w-5 h-5 text-red-600 mr-3 flex-shrink-0 mt-0.5" />
            <span className="text-red-700 font-medium">{error}</span>
          </div>
        )}

        {/* Action Button */}
        <div className="flex justify-end">
          <button
            onClick={handleSubmit}
            disabled={!file || !proyecto}
            className="bg-gradient-to-r from-orange-500 to-orange-600 text-white font-bold py-4 px-8 rounded-lg hover:from-orange-600 hover:to-orange-700 disabled:from-gray-400 disabled:to-gray-400 disabled:cursor-not-allowed transition-all shadow-lg hover:shadow-xl flex items-center space-x-2"
          >
            <Zap className="w-5 h-5" />
            <span>🗑️ Generar Reporte</span>
          </button>
        </div>
      </div>
    </div>
  );
}
