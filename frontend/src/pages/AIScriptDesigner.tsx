/**
 * AI Script Designer — conversational JMX generation.
 * Left panel: chat with the AI.
 * Right panel: live JMX preview + validation + download.
 */
import { useEffect, useRef, useState } from 'react';
import axios from 'axios';
import {
  Sparkles,
  Send,
  Loader2,
  Download,
  CheckCircle2,
  XCircle,
  RefreshCcw,
  FileCode,
  Bot,
  User as UserIcon,
  Paperclip,
  FileText,
  X,
} from 'lucide-react';

const API_BASE_URL = import.meta.env.VITE_API_BASE_URL || 'http://localhost:8001/api/v1';

const aiApi = axios.create({
  baseURL: `${API_BASE_URL}/script-designer/ai`,
  timeout: 180000,
  withCredentials: true,
  headers: { 'Content-Type': 'application/json' },
});

aiApi.interceptors.request.use((config) => {
  if (config.method && config.method !== 'get') {
    const csrfToken = document.cookie
      .split('; ')
      .find((row) => row.startsWith('csrf_token='))
      ?.split('=')[1];
    if (csrfToken) {
      config.headers['X-CSRF-Token'] = csrfToken;
    }
  }
  return config;
});

interface ChatMessage {
  role: 'user' | 'assistant';
  content: string;
}

interface ComponentInfo {
  type: string;
  name: string;
  props: Record<string, string>;
}

interface AIResponse {
  jmx_content: string;
  explanation: string;
  is_valid: boolean;
  error: string | null;
  components: ComponentInfo[] | null;
  file_kind?: string | null;
  file_content?: string | null;
  file_name?: string | null;
}

const MAX_UPLOAD_BYTES = 500 * 1024; // matches backend MAX_FILE_BYTES
const ACCEPT_UPLOAD = '.json,.yaml,.yml,.txt,.postman_collection,application/json,text/yaml,text/plain';

const EXAMPLE_PROMPT =
  'Genera un script de prueba de carga para un API REST de login con 100 usuarios concurrentes, ramp-up de 30 segundos, contra https://api.example.com/auth con metodo POST y body JSON {username, password}.';

export default function AIScriptDesigner() {
  const [messages, setMessages] = useState<ChatMessage[]>([]);
  const [input, setInput] = useState('');
  const [currentJmx, setCurrentJmx] = useState('');
  const [isLoading, setIsLoading] = useState(false);
  const [isValid, setIsValid] = useState(false);
  const [components, setComponents] = useState<ComponentInfo[]>([]);
  const [error, setError] = useState<string | null>(null);

  // Pending file (selected but not yet sent)
  const [pendingFile, setPendingFile] = useState<File | null>(null);
  // Persisted file context — sent on /refine so the AI keeps the reference
  const [refFileName, setRefFileName] = useState<string | null>(null);
  const [refFileContent, setRefFileContent] = useState<string | null>(null);

  const chatEndRef = useRef<HTMLDivElement | null>(null);
  const fileInputRef = useRef<HTMLInputElement | null>(null);

  useEffect(() => {
    chatEndRef.current?.scrollIntoView({ behavior: 'smooth' });
  }, [messages, isLoading]);

  const applyAIResponse = (data: AIResponse) => {
    if (data.jmx_content) setCurrentJmx(data.jmx_content);
    setIsValid(data.is_valid);
    setComponents(data.components || []);
    setError(data.error);
    if (data.file_content) setRefFileContent(data.file_content);
    if (data.file_name) setRefFileName(data.file_name);
  };

  const handlePickFile = () => {
    if (isLoading) return;
    fileInputRef.current?.click();
  };

  const handleFileChange = (e: React.ChangeEvent<HTMLInputElement>) => {
    const file = e.target.files?.[0];
    e.target.value = ''; // allow re-selecting the same file later
    if (!file) return;
    if (file.size > MAX_UPLOAD_BYTES) {
      setError(
        `El archivo "${file.name}" supera el limite de ${Math.round(MAX_UPLOAD_BYTES / 1024)} KB. ` +
          `Se truncara para el analisis con IA.`
      );
    }
    setPendingFile(file);
  };

  const removePendingFile = () => {
    setPendingFile(null);
  };

  const removeReferenceFile = () => {
    setRefFileName(null);
    setRefFileContent(null);
  };

  const sendPrompt = async () => {
    const prompt = input.trim();
    if (!prompt && !pendingFile) return;
    if (isLoading) return;

    const fileTag = pendingFile ? `[📎 ${pendingFile.name}] ` : '';
    const userMessage = `${fileTag}${prompt || '(generar JMX a partir del archivo adjunto)'}`;
    const nextHistory: ChatMessage[] = [...messages, { role: 'user', content: userMessage }];
    setMessages(nextHistory);
    setInput('');
    setIsLoading(true);
    setError(null);

    try {
      let data: AIResponse;

      if (pendingFile) {
        // multipart upload — backend parses Postman / Swagger / text
        const form = new FormData();
        form.append('file', pendingFile);
        form.append('prompt', prompt);
        form.append('conversation_history', JSON.stringify(messages));
        const response = await aiApi.post<AIResponse>('/generate-from-file', form, {
          headers: { 'Content-Type': 'multipart/form-data' },
        });
        data = response.data;
        setPendingFile(null);
      } else {
        const endpoint = currentJmx ? '/refine' : '/generate';
        const payload: Record<string, unknown> = {
          prompt,
          conversation_history: messages,
        };
        if (currentJmx) payload.current_jmx = currentJmx;
        // Persist reference file across refinements
        if (currentJmx && refFileContent) {
          payload.file_content = refFileContent;
          payload.file_name = refFileName;
        }
        const response = await aiApi.post<AIResponse>(endpoint, payload);
        data = response.data;
      }

      applyAIResponse(data);
      setMessages([
        ...nextHistory,
        {
          role: 'assistant',
          content:
            data.explanation ||
            (data.jmx_content ? 'JMX generado correctamente.' : 'Sin respuesta del modelo.'),
        },
      ]);
    } catch (err) {
      const detail =
        (axios.isAxiosError(err) && (err.response?.data?.detail || err.message)) ||
        (err instanceof Error ? err.message : 'Error desconocido');
      setError(String(detail));
      setMessages([
        ...nextHistory,
        { role: 'assistant', content: `Error: ${detail}` },
      ]);
    } finally {
      setIsLoading(false);
    }
  };

  const handleNewConversation = () => {
    if (isLoading) return;
    setMessages([]);
    setInput('');
    setCurrentJmx('');
    setComponents([]);
    setIsValid(false);
    setError(null);
    setPendingFile(null);
    setRefFileName(null);
    setRefFileContent(null);
  };

  const handleDownload = async () => {
    if (!currentJmx || !isValid) return;
    try {
      const response = await aiApi.post(
        '/download',
        { jmx_content: currentJmx, filename: 'ai_generated_test.jmx' },
        { responseType: 'blob' }
      );
      const blob = new Blob([response.data], { type: 'application/xml' });
      const url = URL.createObjectURL(blob);
      const link = document.createElement('a');
      link.href = url;
      link.download = 'ai_generated_test.jmx';
      document.body.appendChild(link);
      link.click();
      document.body.removeChild(link);
      URL.revokeObjectURL(url);
    } catch (err) {
      const detail =
        (axios.isAxiosError(err) && (err.response?.data?.detail || err.message)) ||
        (err instanceof Error ? err.message : 'Error de descarga');
      setError(String(detail));
    }
  };

  const handleUseExample = () => {
    if (isLoading) return;
    setInput(EXAMPLE_PROMPT);
  };

  const handleKeyDown = (e: React.KeyboardEvent<HTMLTextAreaElement>) => {
    if (e.key === 'Enter' && (e.ctrlKey || e.metaKey)) {
      e.preventDefault();
      sendPrompt();
    }
  };

  const actionLabel = pendingFile ? 'Generar desde archivo' : currentJmx ? 'Refinar' : 'Generar';

  return (
    <div className="h-[calc(100vh-8rem)] flex flex-col bg-gray-100">
      {/* Header */}
      <div className="bg-white border-b border-gray-200 px-6 py-4 flex items-center justify-between">
        <div className="flex items-center gap-3">
          <div className="w-10 h-10 rounded-xl bg-indigo-600 flex items-center justify-center text-white">
            <Sparkles className="w-5 h-5" />
          </div>
          <div>
            <h1 className="text-xl font-bold text-gray-900">Diseñador IA — Generador de JMX</h1>
            <p className="text-sm text-gray-500">
              Describe tu prueba en lenguaje natural. La IA genera un JMX listo para JMeter.
            </p>
          </div>
        </div>
        <button
          type="button"
          onClick={handleNewConversation}
          disabled={isLoading || (messages.length === 0 && !currentJmx)}
          className="inline-flex items-center gap-2 px-3 py-2 rounded-lg border border-gray-300 text-sm font-medium text-gray-700 hover:bg-gray-50 disabled:opacity-50 disabled:cursor-not-allowed"
        >
          <RefreshCcw className="w-4 h-4" />
          Nueva conversación
        </button>
      </div>

      {/* Two-pane layout */}
      <div className="flex-1 flex overflow-hidden">
        {/* Left — Chat (40%) */}
        <div className="w-2/5 flex flex-col border-r border-gray-200 bg-white">
          <div className="flex-1 overflow-y-auto p-4 space-y-3">
            {messages.length === 0 && (
              <div className="rounded-xl border border-dashed border-gray-300 p-6 text-center text-gray-500">
                <Bot className="w-10 h-10 mx-auto mb-2 text-indigo-500" />
                <p className="font-medium mb-1">Empieza la conversación</p>
                <p className="text-sm mb-3">
                  Describe el endpoint, el numero de usuarios, ramp-up, tipo de carga, headers,
                  etc.
                </p>
                <button
                  type="button"
                  onClick={handleUseExample}
                  className="text-sm text-indigo-600 hover:text-indigo-700 underline"
                >
                  Usar prompt de ejemplo
                </button>
              </div>
            )}

            {messages.map((msg, idx) => (
              <div
                key={idx}
                className={`flex gap-2 ${msg.role === 'user' ? 'justify-end' : 'justify-start'}`}
              >
                {msg.role === 'assistant' && (
                  <div className="w-8 h-8 rounded-full bg-indigo-100 flex items-center justify-center flex-shrink-0 text-indigo-600">
                    <Bot className="w-4 h-4" />
                  </div>
                )}
                <div
                  className={`max-w-[80%] rounded-2xl px-4 py-2.5 text-sm whitespace-pre-wrap ${
                    msg.role === 'user'
                      ? 'bg-indigo-600 text-white rounded-br-sm'
                      : 'bg-gray-100 text-gray-800 rounded-bl-sm'
                  }`}
                >
                  {msg.content}
                </div>
                {msg.role === 'user' && (
                  <div className="w-8 h-8 rounded-full bg-indigo-600 flex items-center justify-center flex-shrink-0 text-white">
                    <UserIcon className="w-4 h-4" />
                  </div>
                )}
              </div>
            ))}

            {isLoading && (
              <div className="flex gap-2 justify-start">
                <div className="w-8 h-8 rounded-full bg-indigo-100 flex items-center justify-center text-indigo-600">
                  <Bot className="w-4 h-4" />
                </div>
                <div className="bg-gray-100 text-gray-700 rounded-2xl rounded-bl-sm px-4 py-2.5 text-sm inline-flex items-center gap-2">
                  <Loader2 className="w-4 h-4 animate-spin" />
                  Generando script...
                </div>
              </div>
            )}

            <div ref={chatEndRef} />
          </div>

          {/* Input area */}
          <div className="border-t border-gray-200 p-3 bg-gray-50">
            <textarea
              value={input}
              onChange={(e) => setInput(e.target.value)}
              onKeyDown={handleKeyDown}
              rows={3}
              placeholder={
                pendingFile
                  ? 'Instrucciones adicionales (opcional)...'
                  : currentJmx
                  ? 'Describe el ajuste a aplicar al JMX actual...'
                  : 'Describe la prueba de carga que necesitas...'
              }
              className="w-full px-3 py-2 border border-gray-300 rounded-lg focus:ring-2 focus:ring-indigo-500 focus:border-indigo-500 text-sm resize-none"
              disabled={isLoading}
            />

            {/* Hidden file input */}
            <input
              ref={fileInputRef}
              type="file"
              accept={ACCEPT_UPLOAD}
              className="hidden"
              onChange={handleFileChange}
            />

            {/* Pending file chip (selected but not yet sent) */}
            {pendingFile && (
              <div className="mt-2 inline-flex items-center gap-2 px-2.5 py-1.5 rounded-lg bg-indigo-100 border border-indigo-200 text-indigo-800 text-xs">
                <FileText className="w-4 h-4" />
                <span className="font-medium">{pendingFile.name}</span>
                <span className="text-indigo-500">
                  · {(pendingFile.size / 1024).toFixed(1)} KB
                </span>
                <button
                  type="button"
                  onClick={removePendingFile}
                  className="ml-1 p-0.5 rounded hover:bg-indigo-200"
                  aria-label="Quitar archivo"
                >
                  <X className="w-3.5 h-3.5" />
                </button>
              </div>
            )}

            {/* Persistent reference file chip (used during refinements) */}
            {!pendingFile && refFileName && (
              <div className="mt-2 inline-flex items-center gap-2 px-2.5 py-1.5 rounded-lg bg-indigo-50 border border-indigo-200 text-indigo-700 text-xs">
                <FileText className="w-4 h-4" />
                <span className="font-medium">Referencia: {refFileName}</span>
                <span className="text-indigo-400">· se reusa en refinamientos</span>
                <button
                  type="button"
                  onClick={removeReferenceFile}
                  className="ml-1 p-0.5 rounded hover:bg-indigo-100"
                  aria-label="Quitar referencia"
                >
                  <X className="w-3.5 h-3.5" />
                </button>
              </div>
            )}

            <div className="flex items-center justify-between mt-2">
              <div className="flex items-center gap-2">
                <button
                  type="button"
                  onClick={handlePickFile}
                  disabled={isLoading}
                  className="inline-flex items-center gap-1.5 px-2.5 py-1.5 rounded-lg border border-gray-300 text-gray-600 text-xs hover:bg-gray-100 disabled:opacity-50 disabled:cursor-not-allowed"
                  title="Adjuntar Postman / Swagger / archivo"
                >
                  <Paperclip className="w-4 h-4" />
                  Adjuntar archivo
                </button>
                <span className="text-xs text-gray-400">Ctrl+Enter para enviar</span>
              </div>
              <button
                type="button"
                onClick={sendPrompt}
                disabled={isLoading || (!input.trim() && !pendingFile)}
                className="inline-flex items-center gap-2 px-4 py-2 rounded-lg bg-indigo-600 text-white text-sm font-medium hover:bg-indigo-700 disabled:opacity-50 disabled:cursor-not-allowed"
              >
                {isLoading ? (
                  <Loader2 className="w-4 h-4 animate-spin" />
                ) : (
                  <Send className="w-4 h-4" />
                )}
                {actionLabel}
              </button>
            </div>
          </div>
        </div>

        {/* Right — Preview (60%) */}
        <div className="w-3/5 flex flex-col bg-gray-50">
          {/* Status bar */}
          <div className="bg-white border-b border-gray-200 px-4 py-3 flex items-center justify-between">
            <div className="flex items-center gap-3">
              <FileCode className="w-5 h-5 text-gray-500" />
              <span className="font-medium text-gray-800">Preview JMX</span>
              {currentJmx ? (
                isValid ? (
                  <span className="inline-flex items-center gap-1 px-2.5 py-1 rounded-full bg-green-100 text-green-800 text-xs font-medium">
                    <CheckCircle2 className="w-3.5 h-3.5" />
                    JMX Válido
                  </span>
                ) : (
                  <span className="inline-flex items-center gap-1 px-2.5 py-1 rounded-full bg-red-100 text-red-800 text-xs font-medium">
                    <XCircle className="w-3.5 h-3.5" />
                    JMX Inválido
                  </span>
                )
              ) : (
                <span className="text-xs text-gray-400">Esperando generación...</span>
              )}
            </div>
            <button
              type="button"
              onClick={handleDownload}
              disabled={!currentJmx || !isValid || isLoading}
              className="inline-flex items-center gap-2 px-3 py-2 rounded-lg bg-green-600 text-white text-sm font-medium hover:bg-green-700 disabled:opacity-50 disabled:cursor-not-allowed"
            >
              <Download className="w-4 h-4" />
              Descargar JMX
            </button>
          </div>

          {/* Error banner */}
          {error && (
            <div className="bg-red-50 border-b border-red-200 px-4 py-2 text-sm text-red-800">
              {error}
            </div>
          )}

          {/* Components summary */}
          {components.length > 0 && (
            <div className="bg-white border-b border-gray-200 px-4 py-3">
              <p className="text-xs font-semibold text-gray-500 uppercase mb-2">
                Componentes detectados ({components.length})
              </p>
              <div className="flex flex-wrap gap-2">
                {components.slice(0, 24).map((c, i) => (
                  <span
                    key={i}
                    className="inline-flex items-center gap-1.5 px-2.5 py-1 rounded-md bg-indigo-50 border border-indigo-200 text-xs"
                    title={Object.entries(c.props)
                      .map(([k, v]) => `${k}=${v}`)
                      .join('\n')}
                  >
                    <span className="font-semibold text-indigo-700">{c.type}</span>
                    <span className="text-gray-600">{c.name}</span>
                    {c.props['ThreadGroup.num_threads'] && (
                      <span className="text-indigo-600">
                        · {c.props['ThreadGroup.num_threads']} usuarios
                      </span>
                    )}
                    {c.props['HTTPSampler.method'] && (
                      <span className="text-indigo-600">
                        · {c.props['HTTPSampler.method']}
                      </span>
                    )}
                  </span>
                ))}
                {components.length > 24 && (
                  <span className="text-xs text-gray-400">
                    +{components.length - 24} mas...
                  </span>
                )}
              </div>
            </div>
          )}

          {/* JMX code */}
          <div className="flex-1 overflow-auto p-4">
            {currentJmx ? (
              <pre className="font-mono text-xs bg-gray-900 text-gray-100 rounded-lg p-4 overflow-auto whitespace-pre">
                {currentJmx}
              </pre>
            ) : (
              <div className="h-full flex flex-col items-center justify-center text-gray-400">
                <FileCode className="w-16 h-16 mb-3" />
                <p className="text-sm">El JMX generado aparecera aqui</p>
              </div>
            )}
          </div>
        </div>
      </div>
    </div>
  );
}
