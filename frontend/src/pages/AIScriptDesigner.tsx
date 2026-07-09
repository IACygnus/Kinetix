/**
 * AI Script Designer — conversational JMX generation.
 * Left panel: chat with the AI.
 * Right panel: live JMX preview + validation + download.
 */
import { useEffect, useRef, useState } from 'react';
import { useNavigate, useSearchParams } from 'react-router-dom';
import { v4 as uuidv4 } from 'uuid';
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
  Save,
  Users,
  AlertCircle,
  MessageSquare,
  Code,
} from 'lucide-react';
import {
  aiScriptDesignsAPI,
  clientsAPI,
  refineSurgicalAPI,
  AIConversationMessage,
  AIDesignReferenceFileType,
  AIScriptDesignDetail,
} from '../services/api';

const API_BASE_URL = import.meta.env.VITE_API_BASE_URL || 'http://localhost:8001/api/v1';

const aiApi = axios.create({
  baseURL: `${API_BASE_URL}/script-designer/ai`,
  // HF5: refine con JMX grande puede tardar más de 3 min — subido a 5 min.
  // HF6: subido a 10 min para upload + compresión + análisis IA de HARs ≤ 50 MB.
  timeout: 600000,
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

interface CompressionStats {
  original_size: number;
  compressed_size: number;
  reduction_ratio: number;
  entries_original: number;
  entries_unique: number;
  entries_static_filtered: number;
  entries_tracking_filtered: number;
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
  compression_stats?: CompressionStats | null;
  // Sprint 2.7a — backend flags a response the model cut off mid-XML.
  truncated?: boolean | null;
  partial_samplers?: number | null;
}

const MAX_UPLOAD_BYTES = 50 * 1024 * 1024; // 50 MB — matches backend MAX_FILE_BYTES (Sprint 2.4-HF6)
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
  // Sprint 2.9 — multi-HAR: lista de archivos pendientes (antes era 1 solo).
  const [pendingFiles, setPendingFiles] = useState<File[]>([]);
  const MAX_FILES = 5;
  // Persisted file context — sent on /refine so the AI keeps the reference
  const [refFileName, setRefFileName] = useState<string | null>(null);
  const [refFileContent, setRefFileContent] = useState<string | null>(null);
  const [refFileType, setRefFileType] = useState<AIDesignReferenceFileType | null>(null);

  // === Persistencia de diseño ===
  const [searchParams] = useSearchParams();
  const navigate = useNavigate();
  const designIdFromUrl = searchParams.get('designId');
  const fromEditor = searchParams.get('fromEditor') === 'true';

  // session_id estable durante toda la vida del componente
  const sessionIdRef = useRef<string>(uuidv4());

  const [designId, setDesignId] = useState<string | null>(designIdFromUrl);
  const [designName, setDesignName] = useState<string | null>(null);
  const [isDraft, setIsDraft] = useState<boolean>(true);

  // Cliente seleccionado (obligatorio para entrar al diseñador)
  const [selectedClientId, setSelectedClientId] = useState<string | null>(null);
  const [clientsList, setClientsList] = useState<Array<{ id: string; name: string }>>([]);
  const [showClientModal, setShowClientModal] = useState<boolean>(false);

  // Sprint 1.5 — Modal "Continuar?" + cambio de cliente
  const [showContinueModal, setShowContinueModal] = useState<boolean>(false);
  const [pendingDraft, setPendingDraft] = useState<AIScriptDesignDetail | null>(null);
  const [, setCheckingLastDraft] = useState<boolean>(false);
  const [showChangeClientModal, setShowChangeClientModal] = useState<boolean>(false);

  // Auto-save state
  const [lastSavedAt, setLastSavedAt] = useState<Date | null>(null);
  const [isSaving, setIsSaving] = useState<boolean>(false);
  const [saveError, setSaveError] = useState<string | null>(null);

  // Save-as modal
  const [showSaveAsModal, setShowSaveAsModal] = useState<boolean>(false);
  const [saveAsName, setSaveAsName] = useState<string>('');
  const [isSavingAs, setIsSavingAs] = useState<boolean>(false);

  // Indicador "hace X segundos"
  const [savedAgoLabel, setSavedAgoLabel] = useState<string>('');

  const chatEndRef = useRef<HTMLDivElement | null>(null);
  const fileInputRef = useRef<HTMLInputElement | null>(null);

  useEffect(() => {
    chatEndRef.current?.scrollIntoView({ behavior: 'smooth' });
  }, [messages, isLoading]);

  // Cargar lista de clientes asignados al usuario actual
  useEffect(() => {
    const loadClients = async () => {
      try {
        const data = await clientsAPI.getMyClients();
        setClientsList(data.map((c) => ({ id: c.id, name: c.name })));
      } catch (e) {
        console.error('Error cargando clientes', e);
      }
    };
    loadClients();
  }, []);

  // Sprint 1.5 — Al entrar sin designId, chequear si hay borrador previo.
  // Si sí → modal "Continuar?". Si no → modal Cliente.
  useEffect(() => {
    if (designIdFromUrl) return;       // hidratación toma el control
    if (selectedClientId) return;      // ya seleccionado en runtime
    let cancelled = false;

    const checkDraft = async () => {
      setCheckingLastDraft(true);
      try {
        const draft = await aiScriptDesignsAPI.getLastDraft();
        if (cancelled) return;
        if (draft && draft.id) {
          setPendingDraft(draft);
          setShowContinueModal(true);
        } else {
          setShowClientModal(true);
        }
      } catch (e) {
        if (cancelled) return;
        console.error('Error chequeando último borrador', e);
        setShowClientModal(true);
      } finally {
        if (!cancelled) setCheckingLastDraft(false);
      }
    };
    checkDraft();
    return () => {
      cancelled = true;
    };
  }, [designIdFromUrl, selectedClientId]);

  // Hidratar desde ?designId=xxx si viene en la URL
  useEffect(() => {
    if (!designIdFromUrl) return;
    let cancelled = false;

    const hydrate = async () => {
      try {
        const detail = await aiScriptDesignsAPI.getById(designIdFromUrl);
        if (cancelled) return;

        sessionIdRef.current = detail.session_id;
        setDesignId(detail.id);
        setDesignName(detail.name);
        setIsDraft(detail.is_draft);
        setSelectedClientId(detail.client_id);

        if (detail.conversation && Array.isArray(detail.conversation)) {
          // Filtrar a la forma esperada por ChatMessage local
          const restored: ChatMessage[] = detail.conversation
            .filter((m) => m && (m.role === 'user' || m.role === 'assistant'))
            .map((m) => ({ role: m.role as 'user' | 'assistant', content: m.content }));
          setMessages(restored);
        }

        if (detail.current_jmx) {
          setCurrentJmx(detail.current_jmx);
          // Validar el JMX hidratado en background
          try {
            const v = await aiApi.post<{
              is_valid: boolean;
              components: ComponentInfo[];
              errors: string[];
            }>('/validate', { jmx_content: detail.current_jmx });
            if (!cancelled) {
              setIsValid(v.data.is_valid);
              setComponents(v.data.components || []);
            }
          } catch {
            /* validación silenciosa */
          }
        }

        if (detail.reference_file_name) {
          setRefFileName(detail.reference_file_name);
          setRefFileContent(detail.reference_file_content);
          setRefFileType(detail.reference_file_type);
        }

        setLastSavedAt(new Date(detail.updated_at));

        // Sprint 2.4-HF4: si viene del Editor IA, pre-poblar el input.
        if (fromEditor && !cancelled) {
          setInput('Vengo del Editor IA. Quiero que ajustes lo siguiente del JMX: ');
        }
      } catch (e) {
        const detailMsg =
          (axios.isAxiosError(e) && (e.response?.data?.detail || e.message)) ||
          (e instanceof Error ? e.message : 'Error desconocido');
        console.error('Error hidratando diseño', e);
        setSaveError('No se pudo cargar el diseño: ' + String(detailMsg));
      }
    };
    hydrate();
    return () => {
      cancelled = true;
    };
  }, [designIdFromUrl]);

  // Indicador "Guardado hace Xs" — refresca cada 10s
  useEffect(() => {
    const update = () => {
      if (!lastSavedAt) {
        setSavedAgoLabel('');
        return;
      }
      const diff = Math.floor((Date.now() - lastSavedAt.getTime()) / 1000);
      if (diff < 5) setSavedAgoLabel('Guardado hace un momento');
      else if (diff < 60) setSavedAgoLabel(`Guardado hace ${diff}s`);
      else if (diff < 3600) setSavedAgoLabel(`Guardado hace ${Math.floor(diff / 60)}min`);
      else setSavedAgoLabel(`Guardado hace ${Math.floor(diff / 3600)}h`);
    };
    update();
    const interval = setInterval(update, 10000);
    return () => clearInterval(interval);
  }, [lastSavedAt]);

  const applyAIResponse = (data: AIResponse) => {
    if (data.jmx_content) setCurrentJmx(data.jmx_content);
    setIsValid(data.is_valid);
    setComponents(data.components || []);
    setError(data.error);
    if (data.file_content) setRefFileContent(data.file_content);
    if (data.file_name) setRefFileName(data.file_name);
    if (data.file_kind) setRefFileType(data.file_kind as AIDesignReferenceFileType);
  };

  // === Auto-save / Save As ===

  const performAutoSave = async (overrides?: {
    conversation?: AIConversationMessage[];
    current_jmx?: string | null;
    reference_file_name?: string | null;
    reference_file_content?: string | null;
    reference_file_type?: AIDesignReferenceFileType | null;
  }) => {
    if (!selectedClientId) return; // sin cliente no hay auto-save
    setIsSaving(true);
    setSaveError(null);
    try {
      const convPayload: AIConversationMessage[] =
        overrides?.conversation ??
        messages.map((m) => ({ role: m.role, content: m.content }));

      // Sprint 2.7a — never overwrite a valid JMX with an empty/truncated one.
      // A failed generation returns jmx_content="" (no closing tag); if we
      // already hold a complete JMX in state, keep it instead of wiping it.
      const isClosedJmx = (s: string | null | undefined): boolean =>
        !!s && s.includes('</jmeterTestPlan>');
      const incomingJmx = overrides?.current_jmx ?? (currentJmx || null);
      const jmxToSave = isClosedJmx(incomingJmx)
        ? incomingJmx
        : isClosedJmx(currentJmx)
          ? currentJmx
          : incomingJmx;

      const payload = {
        session_id: sessionIdRef.current,
        client_id: selectedClientId,
        conversation: convPayload,
        current_jmx: jmxToSave,
        reference_file_name: overrides?.reference_file_name ?? refFileName,
        reference_file_content: overrides?.reference_file_content ?? refFileContent,
        reference_file_type: overrides?.reference_file_type ?? refFileType,
      };

      const saved = await aiScriptDesignsAPI.upsert(payload);
      setDesignId(saved.id);
      setIsDraft(saved.is_draft);
      if (saved.name) setDesignName(saved.name);
      setLastSavedAt(new Date());
    } catch (e) {
      const detailMsg =
        (axios.isAxiosError(e) && (e.response?.data?.detail || e.message)) ||
        (e instanceof Error ? e.message : 'Error al auto-guardar');
      setSaveError(String(detailMsg));
    } finally {
      setIsSaving(false);
    }
  };

  const handleSaveAs = async () => {
    if (!designId) {
      setSaveError('Debes generar al menos un mensaje antes de guardar.');
      return;
    }
    const trimmed = saveAsName.trim();
    if (!trimmed) {
      setSaveError('El nombre no puede estar vacío.');
      return;
    }
    setIsSavingAs(true);
    setSaveError(null);
    try {
      const saved = await aiScriptDesignsAPI.saveAs(designId, { name: trimmed });
      setDesignName(saved.name);
      setIsDraft(saved.is_draft);
      setLastSavedAt(new Date());
      setShowSaveAsModal(false);
      setSaveAsName('');
    } catch (e) {
      const detailMsg =
        (axios.isAxiosError(e) && (e.response?.data?.detail || e.message)) ||
        (e instanceof Error ? e.message : 'Error al guardar el diseño');
      setSaveError(String(detailMsg));
    } finally {
      setIsSavingAs(false);
    }
  };

  // Sprint 1.5 — Continuar borrador previo / Empezar nuevo

  const handleContinueDraft = () => {
    if (!pendingDraft) return;

    // Hidratar el state como si viniera de ?designId=
    sessionIdRef.current = pendingDraft.session_id;
    setDesignId(pendingDraft.id);
    setDesignName(pendingDraft.name);
    setIsDraft(pendingDraft.is_draft);
    setSelectedClientId(pendingDraft.client_id);

    if (Array.isArray(pendingDraft.conversation)) {
      const restored: ChatMessage[] = pendingDraft.conversation
        .filter((m) => m && (m.role === 'user' || m.role === 'assistant'))
        .map((m) => ({ role: m.role as 'user' | 'assistant', content: m.content }));
      setMessages(restored);
    }

    if (pendingDraft.current_jmx) {
      setCurrentJmx(pendingDraft.current_jmx);
      // Validar en background para reconstruir is_valid + components
      void (async () => {
        try {
          const v = await aiApi.post<{
            is_valid: boolean;
            components: ComponentInfo[];
            errors: string[];
          }>('/validate', { jmx_content: pendingDraft.current_jmx });
          setIsValid(v.data.is_valid);
          setComponents(v.data.components || []);
        } catch {
          /* validación silenciosa */
        }
      })();
    }

    if (pendingDraft.reference_file_name) {
      setRefFileName(pendingDraft.reference_file_name);
      setRefFileContent(pendingDraft.reference_file_content);
      setRefFileType(pendingDraft.reference_file_type);
    }

    setLastSavedAt(new Date(pendingDraft.updated_at));
    setShowContinueModal(false);
    setPendingDraft(null);
  };

  const handleStartNew = () => {
    setShowContinueModal(false);
    setPendingDraft(null);
    setShowClientModal(true);
  };

  const handleChangeClient = (newClientId: string) => {
    if (!newClientId || newClientId === selectedClientId) {
      setShowChangeClientModal(false);
      return;
    }
    setSelectedClientId(newClientId);
    setShowChangeClientModal(false);
    // Si ya hay un diseño en curso, forzar guardado con el nuevo cliente
    if (designId) {
      void performAutoSave();
    }
  };

  const handlePickFile = () => {
    if (isLoading) return;
    fileInputRef.current?.click();
  };

  const handleFileChange = (e: React.ChangeEvent<HTMLInputElement>) => {
    const selected = e.target.files ? Array.from(e.target.files) : [];
    e.target.value = ''; // allow re-selecting the same file later
    if (selected.length === 0) return;
    const oversize = selected.find((f) => f.size > MAX_UPLOAD_BYTES);
    if (oversize) {
      setError(
        `El archivo "${oversize.name}" supera el limite de ${Math.round(MAX_UPLOAD_BYTES / 1024 / 1024)} MB. ` +
          `Se truncara para el analisis con IA.`
      );
    }
    // Sprint 2.9 — acumular con los ya pendientes, respetando el tope.
    setPendingFiles((current) => {
      const combined = [...current, ...selected];
      if (combined.length > MAX_FILES) {
        setError(`Maximo ${MAX_FILES} archivos por conversacion. Se mantienen los primeros ${MAX_FILES}.`);
        return combined.slice(0, MAX_FILES);
      }
      return combined;
    });
  };

  const removePendingFile = (index: number) => {
    setPendingFiles((current) => current.filter((_, i) => i !== index));
  };

  const removeReferenceFile = () => {
    setRefFileName(null);
    setRefFileContent(null);
    setRefFileType(null);
  };

  const sendPrompt = async () => {
    const prompt = input.trim();
    if (!prompt && pendingFiles.length === 0) return;
    if (isLoading) return;

    const fileTag =
      pendingFiles.length > 0
        ? `[📎 ${pendingFiles.length === 1 ? pendingFiles[0].name : `${pendingFiles.length} archivos`}] `
        : '';
    const userMessage = `${fileTag}${prompt || '(generar JMX a partir del archivo adjunto)'}`;
    const nextHistory: ChatMessage[] = [...messages, { role: 'user', content: userMessage }];
    setMessages(nextHistory);
    setInput('');
    setIsLoading(true);
    setError(null);

    try {
      let data: AIResponse = {
        jmx_content: '',
        explanation: '',
        is_valid: false,
        error: null,
        components: null,
      };

      if (pendingFiles.length > 0) {
        // multipart upload — backend parses HAR / Postman / Swagger / text.
        // Sprint 2.9 — varios archivos van en el campo 'files' (FastAPI los
        // recibe como lista); 1 archivo sigue funcionando igual.
        const form = new FormData();
        pendingFiles.forEach((f) => form.append('files', f));
        form.append('prompt', prompt);
        form.append('conversation_history', JSON.stringify(messages));
        const response = await aiApi.post<AIResponse>('/generate-from-file', form, {
          headers: { 'Content-Type': 'multipart/form-data' },
        });
        data = response.data;
        setPendingFiles([]);
      } else if (currentJmx) {
        // Sprint 2.4-HF5.1 — refine híbrido: primero intenta el quirúrgico,
        // si la IA pide fallback (o falla) cae al refine clásico del HF5.
        let surgicalSucceeded = false;
        try {
          const surgical = await refineSurgicalAPI.refine(
            currentJmx,
            prompt,
            messages.map((m) => ({ role: m.role, content: m.content })),
            refFileContent || undefined,
          );

          if (!surgical.fallback_used && !surgical.error) {
            data = {
              jmx_content: surgical.jmx_content,
              explanation:
                surgical.explanation ||
                (surgical.operations_applied > 0
                  ? `Cambio aplicado quirúrgicamente (${surgical.operations_applied} op).`
                  : 'Sin cambios.'),
              is_valid: surgical.is_valid,
              error: null,
              components: null,
            };
            surgicalSucceeded = true;
          } else {
            console.log(
              '[refine] quirúrgico solicitó fallback al clásico:',
              surgical.fallback_reason || surgical.error,
            );
          }
        } catch (e) {
          console.warn('[refine] error en quirúrgico, cae al clásico:', e);
        }

        if (!surgicalSucceeded) {
          const payload: Record<string, unknown> = {
            prompt,
            conversation_history: messages,
            current_jmx: currentJmx,
          };
          if (refFileContent) {
            payload.file_content = refFileContent;
            payload.file_name = refFileName;
          }
          const response = await aiApi.post<AIResponse>('/refine', payload);
          data = response.data;
        }
      } else {
        // Primera generación
        const response = await aiApi.post<AIResponse>('/generate', {
          prompt,
          conversation_history: messages,
        });
        data = response.data;
      }

      applyAIResponse(data);

      // HF6: si el backend comprimió un HAR, anteponer un resumen al mensaje
      // del assistant para que el usuario vea cuánto se redujo.
      let assistantContent =
        data.explanation ||
        (data.jmx_content ? 'JMX generado correctamente.' : 'Sin respuesta del modelo.');
      if (data.compression_stats) {
        const s = data.compression_stats;
        const origMB = (s.original_size / 1024 / 1024).toFixed(1);
        const compMB = (s.compressed_size / 1024 / 1024).toFixed(2);
        const banner =
          `📊 HAR comprimido: ${origMB} MB → ${compMB} MB (${s.reduction_ratio}% reducción)\n` +
          `${s.entries_original} requests → ${s.entries_unique} únicos · ` +
          `filtrados ${s.entries_static_filtered} assets, ${s.entries_tracking_filtered} tracking\n\n`;
        assistantContent = banner + assistantContent;
      }

      const finalMessages: ChatMessage[] = [
        ...nextHistory,
        { role: 'assistant', content: assistantContent },
      ];
      setMessages(finalMessages);

      // Auto-save tras turno exitoso (incluye estado fresco del JMX y archivo)
      void performAutoSave({
        conversation: finalMessages.map((m) => ({ role: m.role, content: m.content })),
        current_jmx: data.jmx_content || currentJmx || null,
        reference_file_name: data.file_name ?? refFileName,
        reference_file_content: data.file_content ?? refFileContent,
        reference_file_type: (data.file_kind as AIDesignReferenceFileType | null | undefined) ?? refFileType,
      });
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
    setPendingFiles([]);
    setRefFileName(null);
    setRefFileContent(null);
    setRefFileType(null);

    // Resetear estado de persistencia: nuevo session_id, sin designId
    sessionIdRef.current = uuidv4();
    setDesignId(null);
    setDesignName(null);
    setIsDraft(true);
    setLastSavedAt(null);
    setSavedAgoLabel('');
    setSaveError(null);
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

  const actionLabel =
    pendingFiles.length > 0
      ? pendingFiles.length > 1
        ? 'Generar desde archivos'
        : 'Generar desde archivo'
      : currentJmx
      ? 'Refinar'
      : 'Generar';

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
        <div className="flex items-center gap-3">
          {/* Badge de cliente clickeable */}
          {selectedClientId && (
            <button
              type="button"
              onClick={() => setShowChangeClientModal(true)}
              className="flex items-center gap-2 px-3 py-1.5 bg-indigo-50 text-indigo-700 text-sm font-medium rounded-md hover:bg-indigo-100 border border-indigo-200 transition"
              title="Cambiar cliente"
            >
              <Users className="w-4 h-4" />
              {clientsList.find((c) => c.id === selectedClientId)?.name || 'Cliente'}
            </button>
          )}

          {/* Indicador de auto-save */}
          <div className="flex items-center gap-2 text-sm">
            {isSaving ? (
              <span className="flex items-center gap-1 text-gray-500">
                <Loader2 className="w-4 h-4 animate-spin" />
                Guardando...
              </span>
            ) : saveError ? (
              <span className="flex items-center gap-1 text-red-600" title={saveError}>
                <AlertCircle className="w-4 h-4" />
                Error al guardar
              </span>
            ) : savedAgoLabel ? (
              <span className="flex items-center gap-1 text-green-600">
                <CheckCircle2 className="w-4 h-4" />
                {savedAgoLabel}
              </span>
            ) : null}
          </div>

          {/* Badge "Borrador" o nombre del diseño */}
          {designName ? (
            <span className="px-3 py-1 bg-indigo-50 text-indigo-700 text-sm rounded-md font-medium">
              {designName}
            </span>
          ) : isDraft && designId ? (
            <span className="px-3 py-1 bg-gray-100 text-gray-600 text-sm rounded-md">
              Borrador
            </span>
          ) : null}

          {/* Botón Abrir en Editor IA */}
          <button
            type="button"
            onClick={() => designId && navigate(`/ai-script-designer/editor/${designId}`)}
            disabled={!designId || !currentJmx}
            className="inline-flex items-center gap-2 px-4 py-2 bg-white border border-indigo-300 text-indigo-700 text-sm font-medium rounded-lg hover:bg-indigo-50 disabled:opacity-40 disabled:cursor-not-allowed"
            title={!designId ? 'Guarda el diseño primero' : !currentJmx ? 'Genera un JMX primero' : 'Abrir en Editor IA'}
          >
            <Code className="w-4 h-4" />
            Abrir en Editor IA
          </button>

          {/* Botón Guardar como */}
          <button
            type="button"
            onClick={() => setShowSaveAsModal(true)}
            disabled={!designId}
            className="inline-flex items-center gap-2 px-4 py-2 bg-indigo-600 text-white text-sm font-medium rounded-lg hover:bg-indigo-700 disabled:opacity-40 disabled:cursor-not-allowed"
            title={!designId ? 'Genera al menos un mensaje antes de guardar' : 'Guardar diseño con nombre'}
          >
            <Save className="w-4 h-4" />
            Guardar como…
          </button>

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
      </div>

      {/* Two-pane layout */}
      <div className="flex-1 flex overflow-hidden">
        {/* Left — Chat (40%) */}
        <div className="w-2/5 flex flex-col border-r border-gray-200 bg-white">
          <div className="flex-1 overflow-y-auto p-4 space-y-3">
            {fromEditor && (
              <div className="p-2 bg-indigo-50 border border-indigo-200 rounded text-xs text-indigo-700">
                <strong>Desde Editor IA:</strong> el chat ya tiene cargado el JMX actual. Describe qué ajuste necesitas.
              </div>
            )}
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
                pendingFiles.length > 0
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
              multiple
              className="hidden"
              onChange={handleFileChange}
            />

            {/* Sprint 2.9 — lista de archivos pendientes (selected, not yet sent) */}
            {pendingFiles.length > 0 && (
              <div className="mt-2 space-y-1">
                {pendingFiles.map((file, idx) => (
                  <div
                    key={`${file.name}-${idx}`}
                    className="inline-flex items-center gap-2 px-2.5 py-1.5 rounded-lg bg-indigo-100 border border-indigo-200 text-indigo-800 text-xs mr-1"
                  >
                    <FileText className="w-4 h-4" />
                    <span className="font-medium">{file.name}</span>
                    <span className="text-indigo-500">· {(file.size / 1024).toFixed(1)} KB</span>
                    <button
                      type="button"
                      onClick={() => removePendingFile(idx)}
                      className="ml-1 p-0.5 rounded hover:bg-indigo-200"
                      aria-label="Quitar archivo"
                    >
                      <X className="w-3.5 h-3.5" />
                    </button>
                  </div>
                ))}
                {pendingFiles.length >= 2 && (
                  <p className="text-xs text-gray-500 italic">
                    💡 La IA procesará los {pendingFiles.length} archivos como un solo flujo continuo.
                  </p>
                )}
              </div>
            )}

            {/* Persistent reference file chip (used during refinements) */}
            {pendingFiles.length === 0 && refFileName && (
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
                <span className="text-xs text-gray-400">Máx. 50 MB · HAR comprimido automáticamente</span>
                <span className="text-xs text-gray-400">·</span>
                <span className="text-xs text-gray-400">Ctrl+Enter para enviar</span>
              </div>
              <button
                type="button"
                onClick={sendPrompt}
                disabled={isLoading || (!input.trim() && pendingFiles.length === 0)}
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
            <div className="bg-red-50 border-b border-red-200 px-4 py-2 text-sm text-red-800 whitespace-pre-line">
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

      {/* Modal de selección de cliente (bloqueante) */}
      {showClientModal && (
        <div className="fixed inset-0 bg-black/60 flex items-center justify-center z-50 p-4">
          <div className="bg-white rounded-lg shadow-xl max-w-md w-full p-6">
            <div className="flex items-center gap-3 mb-4">
              <div className="w-10 h-10 bg-indigo-100 rounded-full flex items-center justify-center">
                <Users className="w-5 h-5 text-indigo-600" />
              </div>
              <div>
                <h3 className="text-lg font-semibold text-gray-900">Selecciona un cliente</h3>
                <p className="text-sm text-gray-600">
                  Todo diseño debe asociarse a un cliente antes de comenzar.
                </p>
              </div>
            </div>

            <select
              value={selectedClientId || ''}
              onChange={(e) => setSelectedClientId(e.target.value || null)}
              className="w-full px-3 py-2 border border-gray-300 rounded-md text-sm mb-4 focus:ring-2 focus:ring-indigo-500"
            >
              <option value="">-- Selecciona un cliente --</option>
              {clientsList.map((c) => (
                <option key={c.id} value={c.id}>{c.name}</option>
              ))}
            </select>

            <div className="flex justify-end gap-2">
              <button
                type="button"
                onClick={() => {
                  if (selectedClientId) setShowClientModal(false);
                }}
                disabled={!selectedClientId}
                className="px-4 py-2 bg-indigo-600 text-white text-sm rounded-md hover:bg-indigo-700 disabled:opacity-40 disabled:cursor-not-allowed"
              >
                Continuar
              </button>
            </div>
          </div>
        </div>
      )}

      {/* Modal "Guardar como..." */}
      {showSaveAsModal && (
        <div className="fixed inset-0 bg-black/60 flex items-center justify-center z-50 p-4">
          <div className="bg-white rounded-lg shadow-xl max-w-md w-full p-6">
            <div className="flex items-center gap-3 mb-4">
              <Save className="w-6 h-6 text-indigo-600" />
              <h3 className="text-lg font-semibold text-gray-900">Guardar diseño</h3>
            </div>

            <label className="block text-sm font-medium text-gray-700 mb-1">
              Nombre del diseño
            </label>
            <input
              type="text"
              value={saveAsName}
              onChange={(e) => setSaveAsName(e.target.value)}
              onKeyDown={(e) => {
                if (e.key === 'Enter') handleSaveAs();
              }}
              autoFocus
              placeholder="Ej. Login API – carga 50 usuarios"
              className="w-full px-3 py-2 border border-gray-300 rounded-md text-sm mb-4 focus:ring-2 focus:ring-indigo-500"
            />

            {saveError && (
              <p className="text-sm text-red-600 mb-3">{saveError}</p>
            )}

            <div className="flex justify-end gap-2">
              <button
                type="button"
                onClick={() => {
                  setShowSaveAsModal(false);
                  setSaveAsName('');
                  setSaveError(null);
                }}
                disabled={isSavingAs}
                className="px-4 py-2 text-sm text-gray-700 border border-gray-300 rounded-md hover:bg-gray-50 disabled:opacity-50"
              >
                Cancelar
              </button>
              <button
                type="button"
                onClick={handleSaveAs}
                disabled={isSavingAs || !saveAsName.trim()}
                className="px-4 py-2 bg-indigo-600 text-white text-sm rounded-md hover:bg-indigo-700 disabled:opacity-50 flex items-center gap-2"
              >
                {isSavingAs && <Loader2 className="w-4 h-4 animate-spin" />}
                Guardar
              </button>
            </div>
          </div>
        </div>
      )}

      {/* Sprint 1.5 — Modal "¿Continuar diseño anterior?" */}
      {showContinueModal && pendingDraft && (
        <div className="fixed inset-0 bg-black/60 flex items-center justify-center z-50 p-4">
          <div className="bg-white rounded-lg shadow-xl max-w-md w-full p-6">
            <div className="flex items-center gap-3 mb-4">
              <div className="w-10 h-10 bg-indigo-100 rounded-full flex items-center justify-center">
                <Sparkles className="w-5 h-5 text-indigo-600" />
              </div>
              <div>
                <h3 className="text-lg font-semibold text-gray-900">¿Continuar diseño anterior?</h3>
                <p className="text-sm text-gray-600 mt-1">
                  Tienes un borrador en curso. ¿Quieres retomarlo o empezar uno nuevo?
                </p>
              </div>
            </div>

            <div className="bg-gray-50 border border-gray-200 rounded-md p-3 mb-4 text-sm">
              <div className="flex items-center gap-2 text-gray-700 mb-1">
                <MessageSquare className="w-4 h-4 text-gray-500" />
                <span>
                  {Array.isArray(pendingDraft.conversation) ? pendingDraft.conversation.length : 0} mensaje(s)
                </span>
              </div>
              {pendingDraft.current_jmx && (
                <div className="flex items-center gap-2 text-gray-700 mb-1">
                  <FileCode className="w-4 h-4 text-gray-500" />
                  <span>JMX en curso</span>
                </div>
              )}
              {pendingDraft.reference_file_name && (
                <div className="flex items-center gap-2 text-gray-700">
                  <FileText className="w-4 h-4 text-gray-500" />
                  <span className="truncate">{pendingDraft.reference_file_name}</span>
                </div>
              )}
              <div className="text-xs text-gray-500 mt-2">
                Última actividad: {new Date(pendingDraft.updated_at).toLocaleString('es-CO')}
              </div>
            </div>

            <div className="flex justify-end gap-2">
              <button
                type="button"
                onClick={handleStartNew}
                className="px-4 py-2 text-sm text-gray-700 border border-gray-300 rounded-md hover:bg-gray-50"
              >
                Empezar nuevo
              </button>
              <button
                type="button"
                onClick={handleContinueDraft}
                className="px-4 py-2 bg-indigo-600 text-white text-sm rounded-md hover:bg-indigo-700"
              >
                Continuar
              </button>
            </div>
          </div>
        </div>
      )}

      {/* Sprint 1.5 — Modal de cambio de cliente */}
      {showChangeClientModal && (
        <div className="fixed inset-0 bg-black/60 flex items-center justify-center z-50 p-4">
          <div className="bg-white rounded-lg shadow-xl max-w-md w-full p-6">
            <div className="flex items-center gap-3 mb-4">
              <Users className="w-6 h-6 text-indigo-600" />
              <h3 className="text-lg font-semibold text-gray-900">Cambiar cliente</h3>
            </div>

            <p className="text-sm text-gray-600 mb-3">
              Cambiar el cliente NO descarta tu conversación. El diseño actual queda asociado al
              nuevo cliente en el próximo guardado.
            </p>

            <select
              value={selectedClientId || ''}
              onChange={(e) => handleChangeClient(e.target.value)}
              className="w-full px-3 py-2 border border-gray-300 rounded-md text-sm mb-4 focus:ring-2 focus:ring-indigo-500"
            >
              {clientsList.map((c) => (
                <option key={c.id} value={c.id}>{c.name}</option>
              ))}
            </select>

            <div className="flex justify-end">
              <button
                type="button"
                onClick={() => setShowChangeClientModal(false)}
                className="px-4 py-2 text-sm text-gray-700 border border-gray-300 rounded-md hover:bg-gray-50"
              >
                Cancelar
              </button>
            </div>
          </div>
        </div>
      )}
    </div>
  );
}
