import { useCallback, useEffect, useMemo, useRef, useState } from 'react';
import { useNavigate, useParams } from 'react-router-dom';
import {
  ChevronRight,
  ChevronDown,
  ArrowLeft,
  Code,
  AlertCircle,
  Loader2,
  FileCode,
  Layers,
  Network,
  Database,
  ListChecks,
  Search as SearchIcon,
  Eye,
  X,
  Info,
  AlertTriangle,
  CheckCircle2,
  Users as UsersIcon,
  Sliders,
  Settings,
  Headphones,
  Clock,
  Sparkles,
  Plus,
  Trash2,
  Play,
  XCircle,
  Zap,
  History,
  ExternalLink,
  Download,
} from 'lucide-react';
import {
  LineChart, Line, AreaChart, Area, XAxis, YAxis, Tooltip,
  ResponsiveContainer, Legend, CartesianGrid,
} from 'recharts';
import { aiScriptDesignsAPI, aiScriptStructureAPI, aiDesignDataFilesAPI, smokeTestAPI, executionAPI } from '../services/api';
import type {
  AIConversationMessage,
  AIDesignReferenceFileType,
  AIDesignDataFile,
  AIDesignDataFilePreview,
  SmokeTestResult,
  ExecutionLiveMetrics,
  DesignExecutionHistoryItem,
  ListenersState,
  SamplerStats,
  TimeBucket,
} from '../services/api';
import type {
  AIScriptStructure,
  ThreadGroupModel,
  SteppingConfig,
  HTTPSamplerModel,
  SamplerBody,
  FormArgument,
  TGChild,
  SamplerChild,
  HeaderManagerModel,
  HeaderModel,
  ResponseAssertionModel,
  RegexExtractorModel,
  JsonExtractorModel,
  XPathExtractorModel,
  BoundaryExtractorModel,
  ConstantTimerModel,
  UniformRandomTimerModel,
  GaussianRandomTimerModel,
  TestPlanModel,
  UserDefinedVariable,
  CSVDataSetModel,
  CSVShareMode,
  HttpDefaultsModel,
  CookieManagerModel,
  CacheManagerModel,
} from '../types/aiScriptStructure';

// ============================================================================
// Tipos auxiliares para selección en el árbol
// ============================================================================

type SelectedNode =
  | { kind: 'overview' }
  | { kind: 'test_plan' }
  | { kind: 'udvs' }
  | { kind: 'http_defaults' }
  | { kind: 'cookie_manager' }
  | { kind: 'cache_manager' }
  | { kind: 'csv_data_set'; id: string }
  | { kind: 'thread_group'; id: string }
  | { kind: 'sampler'; tg_id: string; sampler_id: string }
  | { kind: 'sampler_child'; tg_id: string; sampler_id: string; child_id: string }
  | { kind: 'controller'; tg_id: string; controller_id: string }
  | { kind: 'listener'; id: string }
  | { kind: 'unmapped'; id: string }
  | { kind: 'data_files_root' }
  | { kind: 'data_file'; id: string };

interface ExpandedState {
  [nodeId: string]: boolean;
}

// ============================================================================
// HF7.A — Acciones estructurales para el árbol (add/delete/toggle)
// ============================================================================

type AddElementType = 'sampler' | 'sampler_child' | 'udv' | 'csv_dataset' | 'listener';

type DeletableKind =
  | 'thread_group'
  | 'sampler'
  | 'sampler_child'
  | 'csv_data_set'
  | 'listener'
  | 'udv';

type ToggleableKind =
  | 'thread_group'
  | 'sampler'
  | 'sampler_child'
  | 'csv_data_set'
  | 'listener'
  | 'cookie_manager'
  | 'cache_manager';

interface TreeActions {
  openAdd: (type: AddElementType, contextId?: string) => void;
  onDelete: (
    kind: DeletableKind,
    id: string,
    opts?: { sampler_id?: string; udv_name?: string },
  ) => void;
  onToggle: (
    kind: ToggleableKind,
    id: string,
    nextEnabled: boolean,
    opts?: { sampler_id?: string },
  ) => void;
}

// ============================================================================
// Componente principal
// ============================================================================

export default function AIScriptEditor() {
  const { designId } = useParams<{ designId: string }>();
  const navigate = useNavigate();

  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [designName, setDesignName] = useState<string | null>(null);
  const [originalJmx, setOriginalJmx] = useState<string>('');
  const [structure, setStructure] = useState<AIScriptStructure | null>(null);

  const [selected, setSelected] = useState<SelectedNode>({ kind: 'overview' });
  const [expanded, setExpanded] = useState<ExpandedState>({});
  const [searchFilter, setSearchFilter] = useState('');
  const [showXmlModal, setShowXmlModal] = useState(false);
  const [downloadingJmx, setDownloadingJmx] = useState(false);

  // ==========================================================================
  // Auto-save state (Sprint 2.4b)
  // ==========================================================================
  const [saving, setSaving] = useState(false);
  const [lastSaved, setLastSaved] = useState<Date | null>(null);
  const [saveError, setSaveError] = useState<string | null>(null);
  const [, setTick] = useState(0); // forzar re-render del indicador "hace Xs"
  const saveTimerRef = useRef<ReturnType<typeof setTimeout> | null>(null);
  const isDirtyRef = useRef(false);

  // ==========================================================================
  // HF7.A — Modal de agregar elemento + handlers de mutación estructural
  // ==========================================================================
  const [addModalOpen, setAddModalOpen] = useState(false);
  const [addModalType, setAddModalType] = useState<AddElementType>('sampler');
  const [addModalContext, setAddModalContext] = useState<string | undefined>(undefined);

  // ==========================================================================
  // Sprint 2.5c — Smoke Test modal + runner
  // ==========================================================================
  const [smokeModalOpen, setSmokeModalOpen] = useState(false);
  const [smokeRunning, setSmokeRunning] = useState(false);
  const [smokeResult, setSmokeResult] = useState<SmokeTestResult | null>(null);
  const [smokeError, setSmokeError] = useState<string | null>(null);
  const [smokeShowLog, setSmokeShowLog] = useState(false);
  // Sprint 2.5c.1 — smoke configurable (1-20 usuarios, 1-5 loops)
  const [smokeConfig, setSmokeConfig] = useState({ numThreads: 1, loops: 1 });

  // ==========================================================================
  // Sprint 2.5e.1 — Ejecución FULL (modal + drawer live + polling)
  // ==========================================================================
  const [executeModalOpen, setExecuteModalOpen] = useState(false);
  const [executionLiveOpen, setExecutionLiveOpen] = useState(false);
  const [currentExecution, setCurrentExecution] = useState<ExecutionLiveMetrics | null>(null);
  // Sprint 2.6b: estado en vivo de los listeners (polling cada 2s mientras se ve un listener).
  const [listenersState, setListenersState] = useState<ListenersState | null>(null);
  const [listenersPollLoading, setListenersPollLoading] = useState(false);
  const listenersPollIntervalRef = useRef<number | null>(null);
  const [executionStarting, setExecutionStarting] = useState(false);
  const [stopRequesting, setStopRequesting] = useState(false);
  const pollIntervalRef = useRef<number | null>(null);
  // HF13: historial de métricas para el mini-chart (response time avg vs tiempo)
  const [metricsHistory, setMetricsHistory] = useState<Array<{ time: number; avg_response_ms: number }>>([]);

  // ==========================================================================
  // Sprint 2.5e.2 — Análisis IA + Historial
  // ==========================================================================
  const [analyzingAI, setAnalyzingAI] = useState(false);
  const [analysisResult, setAnalysisResult] = useState<{ test_execution_id: string; dashboard_url: string } | null>(null);
  const [analysisError, setAnalysisError] = useState<string | null>(null);
  const [historyOpen, setHistoryOpen] = useState(false);
  const [historyLoading, setHistoryLoading] = useState(false);
  const [executionHistory, setExecutionHistory] = useState<DesignExecutionHistoryItem[]>([]);

  // Snapshot del design para reusar en upsert (campos no editables desde el editor)
  const [designSessionId, setDesignSessionId] = useState<string>('');
  const [designClientId, setDesignClientId] = useState<string>('');
  const [designNameSnapshot, setDesignNameSnapshot] = useState<string | null>(null);
  const [designConversation, setDesignConversation] = useState<AIConversationMessage[]>([]);
  const [designRefFile, setDesignRefFile] = useState<{
    name: string | null;
    content: string | null;
    type: AIDesignReferenceFileType | null;
  }>({ name: null, content: null, type: null });

  // Data Files (Sprint 2.4-HF2)
  const [dataFiles, setDataFiles] = useState<AIDesignDataFile[]>([]);
  const [dataFilesLoading, setDataFilesLoading] = useState(false);

  const reloadDataFiles = useCallback(async () => {
    if (!designId) return;
    setDataFilesLoading(true);
    try {
      const files = await aiDesignDataFilesAPI.list(designId);
      setDataFiles(files);
    } catch (e) {
      console.error('Error cargando data files:', e);
    } finally {
      setDataFilesLoading(false);
    }
  }, [designId]);

  // Sprint 2.5c.1 (HF2.1): re-parsea el JMX del diseño para refrescar el árbol
  // tras autocrearse un CSV Data Set al subir un Data File con variables.
  const reloadStructure = useCallback(async () => {
    if (!designId) return;
    try {
      const design = await aiScriptDesignsAPI.getById(designId);
      if (design.current_jmx) {
        const parsed = await aiScriptStructureAPI.parseJmx(design.current_jmx);
        setOriginalJmx(design.current_jmx);
        setStructure(parsed);
      }
    } catch (e) {
      console.error('Error recargando estructura:', e);
    }
  }, [designId]);

  // ==========================================================================
  // Carga inicial: traer design + parsear JMX
  // ==========================================================================

  useEffect(() => {
    if (!designId) {
      setError('Falta designId en la URL');
      setLoading(false);
      return;
    }

    let cancelled = false;
    const load = async () => {
      setLoading(true);
      setError(null);
      try {
        const design = await aiScriptDesignsAPI.getById(designId);
        if (cancelled) return;

        if (!design.current_jmx) {
          setError('Este diseño no tiene JMX para editar. Genera uno primero desde el chat.');
          setLoading(false);
          return;
        }

        setDesignName(design.name || 'Sin nombre');
        setOriginalJmx(design.current_jmx);

        // Snapshot para auto-save: campos del design que el upsert necesita
        setDesignSessionId(design.session_id || '');
        setDesignClientId(design.client_id || '');
        setDesignNameSnapshot(design.name);
        setDesignConversation(design.conversation || []);
        setDesignRefFile({
          name: design.reference_file_name,
          content: design.reference_file_content,
          type: design.reference_file_type,
        });

        const parsed = await aiScriptStructureAPI.parseJmx(design.current_jmx);
        if (cancelled) return;

        setStructure(parsed);

        // Auto-expand primer nivel
        const initialExpanded: ExpandedState = { root: true, threadGroups: true, configElements: true };
        for (const tg of parsed.thread_groups) {
          initialExpanded[`tg-${tg.id}`] = true;
        }
        setExpanded(initialExpanded);
      } catch (e: any) {
        if (!cancelled) {
          setError(e?.response?.data?.detail || e.message || 'Error al cargar el editor');
        }
      } finally {
        if (!cancelled) setLoading(false);
      }
    };
    load();
    return () => { cancelled = true; };
  }, [designId]);

  // ==========================================================================
  // Data Files (Sprint 2.4-HF2): cargar tras parse exitoso
  // ==========================================================================
  useEffect(() => {
    if (designId && !loading && structure) {
      reloadDataFiles();
    }
  }, [designId, loading, structure, reloadDataFiles]);

  // ==========================================================================
  // Auto-save: refresh del indicador "hace Xs" + cleanup del timer
  // ==========================================================================
  useEffect(() => {
    if (!lastSaved) return;
    const interval = setInterval(() => setTick((t) => t + 1), 5000);
    return () => clearInterval(interval);
  }, [lastSaved]);

  useEffect(() => {
    return () => {
      if (saveTimerRef.current) clearTimeout(saveTimerRef.current);
    };
  }, []);

  // ==========================================================================
  // Auto-save: persistJmx (regenerate + upsert) y updateStructure (debounce 800ms)
  // ==========================================================================
  const persistJmx = useCallback(
    async (jmxText: string) => {
      if (!designSessionId || !designClientId) {
        throw new Error('Falta session_id o client_id del design');
      }
      await aiScriptDesignsAPI.upsert({
        session_id: designSessionId,
        client_id: designClientId,
        current_jmx: jmxText,
        conversation: designConversation,
        reference_file_name: designRefFile.name,
        reference_file_content: designRefFile.content,
        reference_file_type: designRefFile.type,
      });
    },
    [designSessionId, designClientId, designConversation, designRefFile],
  );

  const updateStructure = useCallback(
    (newStructure: AIScriptStructure) => {
      setStructure(newStructure);
      isDirtyRef.current = true;
      setSaveError(null);

      if (saveTimerRef.current) clearTimeout(saveTimerRef.current);

      saveTimerRef.current = setTimeout(async () => {
        if (!designId || !isDirtyRef.current) return;
        setSaving(true);
        setSaveError(null);
        try {
          const regen = await aiScriptStructureAPI.regenerateJmx(newStructure);
          await persistJmx(regen.jmx_text);
          setOriginalJmx(regen.jmx_text);
          setLastSaved(new Date());
          isDirtyRef.current = false;
        } catch (e: any) {
          setSaveError(e?.response?.data?.detail || e?.message || 'Error guardando');
        } finally {
          setSaving(false);
        }
      }, 800);
    },
    [designId, persistJmx],
  );

  // Suppress unused-var warning for snapshot (será usado cuando upsert acepte 'name')
  void designNameSnapshot;

  // Descarga el JMX actual del diseño (originalJmx se mantiene en sync con cada edición).
  const handleDownloadJmx = useCallback(async () => {
    if (!designId) return;
    setDownloadingJmx(true);
    try {
      // HF14b: export-bundle — el backend decide JMX puro vs ZIP (con CSVs) y el naming.
      await aiScriptDesignsAPI.exportBundle(designId);
    } catch (e: any) {
      const detail = e?.response?.data?.detail;
      const msg =
        detail && typeof detail === 'object'
          ? detail.message || JSON.stringify(detail)
          : detail || e?.message || 'Error al descargar';
      alert(String(msg));
    } finally {
      setDownloadingJmx(false);
    }
  }, [designId]);

  // ==========================================================================
  // Helpers de árbol
  // ==========================================================================

  const toggleExpand = (key: string) => {
    setExpanded((prev) => ({ ...prev, [key]: !prev[key] }));
  };

  const matchesFilter = (text: string): boolean => {
    if (!searchFilter.trim()) return true;
    return text.toLowerCase().includes(searchFilter.toLowerCase());
  };

  // ==========================================================================
  // HF7.A — Handlers de mutación estructural del árbol
  // ==========================================================================

  const openAddModal = useCallback(
    (type: AddElementType, contextId?: string) => {
      setAddModalType(type);
      setAddModalContext(contextId);
      setAddModalOpen(true);
    },
    [],
  );

  const newLocalId = (): string => {
    if (typeof crypto !== 'undefined' && typeof crypto.randomUUID === 'function') {
      return crypto.randomUUID();
    }
    return 'id-' + Math.random().toString(36).slice(2, 14);
  };

  const handleAddElement = useCallback(
    (data: any) => {
      if (!structure) return;
      const next: AIScriptStructure = JSON.parse(JSON.stringify(structure));

      if (addModalType === 'sampler' && addModalContext) {
        const tg = next.thread_groups.find((t) => t.id === addModalContext);
        if (!tg) return;
        const newSampler: any = {
          id: newLocalId(),
          type: 'sampler',
          name: data.name || 'Nuevo Sampler',
          enabled: true,
          method: data.method || 'GET',
          domain: data.domain || null,
          port: null,
          protocol: null,
          path: data.path || '/',
          follow_redirects: true,
          auto_redirects: false,
          use_keepalive: true,
          content_encoding: 'UTF-8',
          body: { mode: 'none', raw_text: null, form_args: [], body_type: 'auto' },
          children: [],
          raw_xml: '',
          is_dirty: true,
        };
        tg.children.push({
          type: 'sampler',
          order: tg.children.length,
          sampler: newSampler,
          controller: null,
          unsupported: null,
        } as any);
        tg.is_dirty = true;
      } else if (addModalType === 'sampler_child' && addModalContext) {
        const childKind: string = data.child_kind;
        const childData = data.data || {};

        let sampler: any = null;
        for (const tg of next.thread_groups) {
          const found = tg.children.find(
            (ch) => ch.type === 'sampler' && ch.sampler?.id === addModalContext,
          );
          if (found && found.sampler) {
            sampler = found.sampler;
            tg.is_dirty = true;
            break;
          }
        }
        if (!sampler) return;

        let newChildData: any = null;
        if (childKind === 'header_manager') {
          newChildData = {
            id: newLocalId(),
            enabled: true,
            headers: [],
            is_dirty: true,
          };
        } else if (childKind === 'response_assertion') {
          newChildData = {
            id: newLocalId(),
            enabled: true,
            name: childData.name || 'Response Assertion',
            test_field: 'Assertion.response_code',
            test_type: 2,
            test_strings: ['200'],
            custom_message: null,
            assume_success: false,
            negate: false,
            pattern_match: 'contains',
            is_dirty: true,
          };
        } else if (childKind === 'regex_extractor') {
          newChildData = {
            id: newLocalId(),
            enabled: true,
            name: childData.name || 'Regex Extractor',
            refname: childData.refname || 'var',
            regex: childData.regex || '',
            template: '$1$',
            match_number: '1',
            default: 'NOT_FOUND',
            default_empty_value: false,
            use_headers: 'false',
            scope: null,
            extract_from: 'body',
            is_dirty: true,
          };
        } else if (childKind === 'json_extractor') {
          newChildData = {
            id: newLocalId(),
            enabled: true,
            name: childData.name || 'JSON Extractor',
            refname: childData.refname || 'var',
            json_path: childData.json_path || '$.id',
            match_number: '1',
            default: 'NOT_FOUND',
            is_dirty: true,
          };
        } else if (childKind === 'constant_timer') {
          newChildData = {
            id: newLocalId(),
            enabled: true,
            name: childData.name || 'Constant Timer',
            delay_ms: 1000,
            is_dirty: true,
          };
        }
        if (!newChildData) return;

        sampler.children.push({
          type: childKind,
          order: sampler.children.length,
          data: newChildData,
        });
        sampler.is_dirty = true;
      } else if (addModalType === 'udv') {
        if (!data.name) return;
        if (next.user_defined_variables.some((u) => u.name === data.name)) {
          alert(`Ya existe una variable con nombre '${data.name}'`);
          return;
        }
        next.user_defined_variables.push({
          name: data.name,
          value: data.value || '',
          metadata: '=',
          description: null,
          is_dirty: true,
        } as any);
      } else if (addModalType === 'csv_dataset') {
        next.csv_data_sets.push({
          id: newLocalId(),
          testname: data.testname || 'CSV Data Set',
          enabled: true,
          filename: data.filename || '',
          file_encoding: null,
          variable_names: Array.isArray(data.variable_names) ? data.variable_names : [],
          delimiter: ',',
          quoted_data: false,
          recycle: true,
          stop_thread: false,
          share_mode: 'shareMode.all',
          ignore_first_line: false,
          is_dirty: true,
        } as any);
      } else if (addModalType === 'listener') {
        // HF7.B — los listeners van con raw_xml inicial para que el regenerator
        // del backend (passthrough total) los respete tal cual. Replica el
        // mismo esquema del applier Python en backend/.../refine_operations_applier.py.
        const listenerKind: string = data.listener_kind || 'view_results_tree';
        // HF7.B.1 — 11 tipos (replica LISTENER_KIND_DEFAULTS del applier Python).
        type ListenerDef = {
          guiclass: string;
          testclass: string;
          nameDefault: string;
          schemaKind: string;
          interval?: number;          // solo jpgc → interval_grouping
          filenamePattern?: string;   // solo *_with_csv → filename default
        };
        const defaults: Record<string, ListenerDef> = {
          view_results_tree:           { guiclass: 'ViewResultsFullVisualizer', testclass: 'ResultCollector',  nameDefault: 'View Results Tree',    schemaKind: 'view_results_tree' },
          view_results_tree_with_csv:  { guiclass: 'ViewResultsFullVisualizer', testclass: 'ResultCollector',  nameDefault: 'View Results Tree (errors + CSV)', schemaKind: 'view_results_tree', filenamePattern: 'resultados_log_${__time(d-MMM-yyyy)}-${__time(HHmmss)}.csv' },
          summary_report:              { guiclass: 'SummaryReport',             testclass: 'ResultCollector',  nameDefault: 'Summary Report',       schemaKind: 'summary_report' },
          aggregate_report:            { guiclass: 'StatVisualizer',            testclass: 'ResultCollector',  nameDefault: 'Informe Agregado',     schemaKind: 'aggregate_report' },
          aggregate_report_with_csv:   { guiclass: 'StatVisualizer',            testclass: 'ResultCollector',  nameDefault: 'Informe Agregado (con CSV)', schemaKind: 'aggregate_report', filenamePattern: 'resultados_general_${__time(d-MMM-yyyy)}-${__time(HHmmss)}.jtl' },
          response_time_graph:         { guiclass: 'RespTimeGraphVisualizer',   testclass: 'ResultCollector',  nameDefault: 'Response Time Graph',  schemaKind: 'other' },
          jpgc_response_times_over_time:  { guiclass: 'kg.apc.jmeter.vizualizers.ResponseTimesOverTimeGui',  testclass: 'kg.apc.jmeter.vizualizers.CorrectedResultCollector', nameDefault: 'jp@gc - Response Times Over Time',  schemaKind: 'kg_apc_response_times_over_time',  interval: 500 },
          jpgc_response_codes_per_second: { guiclass: 'kg.apc.jmeter.vizualizers.ResponseCodesPerSecondGui', testclass: 'kg.apc.jmeter.vizualizers.CorrectedResultCollector', nameDefault: 'jp@gc - Response Codes per Second', schemaKind: 'kg_apc_response_codes_per_second', interval: 1000 },
          jpgc_transactions_per_second:   { guiclass: 'kg.apc.jmeter.vizualizers.TransactionsPerSecondGui',  testclass: 'kg.apc.jmeter.vizualizers.CorrectedResultCollector', nameDefault: 'jp@gc - Transactions per Second',  schemaKind: 'kg_apc_transactions_per_second',  interval: 1000 },
          jpgc_active_threads_over_time:  { guiclass: 'kg.apc.jmeter.vizualizers.ThreadsStateOverTimeGui',   testclass: 'kg.apc.jmeter.vizualizers.CorrectedResultCollector', nameDefault: 'jp@gc - Active Threads Over Time',  schemaKind: 'kg_apc_active_threads_over_time',  interval: 1000 },
          backend_listener:            { guiclass: 'BackendListenerGui',        testclass: 'BackendListener',  nameDefault: 'Backend Listener (InfluxDB)', schemaKind: 'other' },
        };
        const def = defaults[listenerKind] || defaults.view_results_tree;
        const listenerName = (data.name || def.nameDefault).trim() || def.nameDefault;
        const xmlEscape = (s: string) =>
          String(s).replace(/&/g, '&amp;').replace(/</g, '&lt;').replace(/>/g, '&gt;').replace(/"/g, '&quot;');

        let rawXml = '';
        if (listenerKind === 'backend_listener') {
          const influxArgs = [
            { name: 'influxdbMetricsSender', value: 'org.apache.jmeter.visualizers.backend.influxdb.HttpMetricsSender' },
            { name: 'influxdbUrl', value: 'http://influxdb:8086/api/v2/write?org=performance&bucket=jmeter&precision=ms' },
            { name: 'application', value: '${__P(application,Kinetix Test)}' },
            { name: 'measurement', value: 'jmeter' },
            { name: 'summaryOnly', value: 'false' },
            { name: 'samplersRegex', value: '.*' },
            { name: 'percentiles', value: '90;95;99' },
            { name: 'testTitle', value: 'Test name' },
            { name: 'eventTags', value: '' },
            { name: 'TOKEN', value: 'jmeter-token-2024-super-secret' },
          ];
          const argsXml = influxArgs
            .map(
              (a) =>
                `          <elementProp name="${xmlEscape(a.name)}" elementType="Argument">\n` +
                `            <stringProp name="Argument.name">${xmlEscape(a.name)}</stringProp>\n` +
                `            <stringProp name="Argument.value">${xmlEscape(a.value)}</stringProp>\n` +
                `            <stringProp name="Argument.metadata">=</stringProp>\n` +
                `          </elementProp>`,
            )
            .join('\n');
          rawXml =
            `<BackendListener guiclass="BackendListenerGui" testclass="BackendListener" testname="${xmlEscape(listenerName)}" enabled="true">\n` +
            `  <elementProp name="arguments" elementType="Arguments" guiclass="ArgumentsPanel" testclass="Arguments" testname="User Defined Variables" enabled="true">\n` +
            `    <collectionProp name="Arguments.arguments">\n` +
            `${argsXml}\n` +
            `    </collectionProp>\n` +
            `  </elementProp>\n` +
            `  <stringProp name="classname">org.apache.jmeter.visualizers.backend.influxdb.InfluxdbBackendListenerClient</stringProp>\n` +
            `</BackendListener>`;
        } else {
          // saveConfig estándar compartido por ResultCollector y CorrectedResultCollector
          const saveConfig =
            `  <objProp>\n` +
            `    <name>saveConfig</name>\n` +
            `    <value class="SampleSaveConfiguration">\n` +
            `      <time>true</time>\n      <latency>true</latency>\n      <timestamp>true</timestamp>\n      <success>true</success>\n      <label>true</label>\n      <code>true</code>\n      <message>true</message>\n      <threadName>true</threadName>\n      <dataType>true</dataType>\n      <encoding>false</encoding>\n      <assertions>true</assertions>\n      <subresults>true</subresults>\n      <responseData>false</responseData>\n      <samplerData>false</samplerData>\n      <xml>false</xml>\n      <fieldNames>true</fieldNames>\n      <responseHeaders>false</responseHeaders>\n      <requestHeaders>false</requestHeaders>\n      <responseDataOnError>false</responseDataOnError>\n      <saveAssertionResultsFailureMessage>true</saveAssertionResultsFailureMessage>\n      <assertionsResultsToSave>0</assertionsResultsToSave>\n      <bytes>true</bytes>\n      <sentBytes>true</sentBytes>\n      <url>true</url>\n      <threadCounts>true</threadCounts>\n      <idleTime>true</idleTime>\n      <connectTime>true</connectTime>\n` +
            `    </value>\n` +
            `  </objProp>\n`;
          const fileName = def.filenamePattern || '';

          if (listenerKind.startsWith('jpgc_')) {
            // Gráficas jp@gc → CorrectedResultCollector
            const tag = 'kg.apc.jmeter.vizualizers.CorrectedResultCollector';
            rawXml =
              `<${tag} guiclass="${def.guiclass}" testclass="${tag}" testname="${xmlEscape(listenerName)}" enabled="true">\n` +
              `  <boolProp name="ResultCollector.error_logging">false</boolProp>\n` +
              saveConfig +
              `  <stringProp name="filename">${xmlEscape(fileName)}</stringProp>\n` +
              `  <longProp name="interval_grouping">${def.interval ?? 1000}</longProp>\n` +
              `  <boolProp name="graph_aggregated">false</boolProp>\n` +
              `  <stringProp name="include_sample_labels"></stringProp>\n` +
              `  <stringProp name="exclude_sample_labels"></stringProp>\n` +
              `  <stringProp name="start_offset"></stringProp>\n` +
              `  <stringProp name="end_offset"></stringProp>\n` +
              `  <boolProp name="include_checkbox_state">false</boolProp>\n` +
              `  <boolProp name="exclude_checkbox_state">false</boolProp>\n` +
              `</${tag}>`;
          } else {
            rawXml =
              `<ResultCollector guiclass="${def.guiclass}" testclass="ResultCollector" testname="${xmlEscape(listenerName)}" enabled="true">\n` +
              `  <boolProp name="ResultCollector.error_logging">false</boolProp>\n` +
              saveConfig +
              `  <stringProp name="filename">${xmlEscape(fileName)}</stringProp>\n` +
              `</ResultCollector>`;
          }
        }

        next.listeners.push({
          id: newLocalId(),
          kind: def.schemaKind,
          guiclass: def.guiclass,
          name: listenerName,
          enabled: true,
          filename: def.filenamePattern || null,
          raw_xml: rawXml,
          is_dirty: false, // raw_xml válido — el regenerator lo respeta tal cual
        } as any);
      }

      updateStructure(next); // HF20b: persiste (marca dirty + auto-save), antes setStructure directo no persistía
    },
    [addModalType, addModalContext, structure, updateStructure],
  );

  const handleDeleteElement = useCallback(
    (
      kind: DeletableKind,
      id: string,
      opts: { sampler_id?: string; udv_name?: string } = {},
    ) => {
      if (!structure) return;
      if (!window.confirm('¿Eliminar este elemento?')) return;
      const next: AIScriptStructure = JSON.parse(JSON.stringify(structure));

      if (kind === 'thread_group') {
        next.thread_groups = next.thread_groups.filter((t) => t.id !== id);
      } else if (kind === 'sampler') {
        for (const tg of next.thread_groups) {
          const idx = tg.children.findIndex(
            (ch) => ch.type === 'sampler' && ch.sampler?.id === id,
          );
          if (idx !== -1) {
            tg.children.splice(idx, 1);
            tg.is_dirty = true;
            break;
          }
        }
      } else if (kind === 'sampler_child' && opts.sampler_id) {
        for (const tg of next.thread_groups) {
          for (const ch of tg.children) {
            if (ch.type === 'sampler' && ch.sampler?.id === opts.sampler_id) {
              const idx = ch.sampler.children.findIndex(
                (sc) => (sc.data as any).id === id,
              );
              if (idx !== -1) {
                ch.sampler.children.splice(idx, 1);
                ch.sampler.is_dirty = true;
                tg.is_dirty = true;
                break;
              }
            }
          }
        }
      } else if (kind === 'csv_data_set') {
        next.csv_data_sets = next.csv_data_sets.filter((d) => d.id !== id);
      } else if (kind === 'listener') {
        next.listeners = next.listeners.filter((l) => l.id !== id);
      } else if (kind === 'udv' && opts.udv_name) {
        next.user_defined_variables = next.user_defined_variables.filter(
          (u) => u.name !== opts.udv_name,
        );
      }

      // Si el elemento borrado era el seleccionado, limpiar selección
      setSelected({ kind: 'overview' });
      updateStructure(next); // HF20b: persiste el borrado (antes setStructure no disparaba auto-save)
    },
    [structure, updateStructure],
  );

  const handleToggleEnabled = useCallback(
    (
      kind: ToggleableKind,
      id: string,
      nextEnabled: boolean,
      opts: { sampler_id?: string } = {},
    ) => {
      if (!structure) return;
      const next: AIScriptStructure = JSON.parse(JSON.stringify(structure));

      if (kind === 'thread_group') {
        const tg = next.thread_groups.find((t) => t.id === id);
        if (tg) {
          tg.enabled = nextEnabled;
          tg.is_dirty = true;
        }
      } else if (kind === 'sampler') {
        for (const tg of next.thread_groups) {
          const ch = tg.children.find(
            (c) => c.type === 'sampler' && c.sampler?.id === id,
          );
          if (ch?.sampler) {
            ch.sampler.enabled = nextEnabled;
            ch.sampler.is_dirty = true;
            break;
          }
        }
      } else if (kind === 'sampler_child' && opts.sampler_id) {
        for (const tg of next.thread_groups) {
          for (const ch of tg.children) {
            if (ch.type === 'sampler' && ch.sampler?.id === opts.sampler_id) {
              const sc = ch.sampler.children.find(
                (s) => (s.data as any).id === id,
              );
              if (sc) {
                (sc.data as any).enabled = nextEnabled;
                (sc.data as any).is_dirty = true;
                ch.sampler.is_dirty = true;
              }
            }
          }
        }
      } else if (kind === 'csv_data_set') {
        const ds = next.csv_data_sets.find((d) => d.id === id);
        if (ds) {
          ds.enabled = nextEnabled;
          ds.is_dirty = true;
        }
      } else if (kind === 'listener') {
        const l = next.listeners.find((x) => x.id === id);
        if (l) {
          l.enabled = nextEnabled;
          l.is_dirty = true;
        }
      } else if (kind === 'cookie_manager' && next.cookie_manager) {
        next.cookie_manager.enabled = nextEnabled;
        next.cookie_manager.is_dirty = true;
      } else if (kind === 'cache_manager' && next.cache_manager) {
        next.cache_manager.enabled = nextEnabled;
        next.cache_manager.is_dirty = true;
      }

      updateStructure(next); // HF20b: persiste el toggle (antes setStructure no disparaba auto-save)
    },
    [structure, updateStructure],
  );

  const treeActions: TreeActions = useMemo(
    () => ({
      openAdd: openAddModal,
      onDelete: handleDeleteElement,
      onToggle: handleToggleEnabled,
    }),
    [openAddModal, handleDeleteElement, handleToggleEnabled],
  );

  // ==========================================================================
  // Sprint 2.5c — Runner del smoke test
  // ==========================================================================
  const runSmokeTest = useCallback(
    async (config: { numThreads: number; loops: number } = { numThreads: 1, loops: 1 }) => {
      if (!designId) return;
      setSmokeRunning(true);
      setSmokeResult(null);
      setSmokeError(null);
      setSmokeShowLog(false);
      try {
        const r = await smokeTestAPI.run(designId, {
          numThreads: config.numThreads,
          loops: config.loops,
          timeoutSec: 60,
        });
        setSmokeResult(r);
      } catch (e: any) {
        // HF14a: detail puede ser objeto {error_type, message, ...} (csv_missing).
        const detail = e?.response?.data?.detail;
        const msg =
          detail && typeof detail === 'object'
            ? detail.message || JSON.stringify(detail)
            : detail || e?.message || 'Error desconocido';
        setSmokeError(String(msg));
      } finally {
        setSmokeRunning(false);
      }
    },
    [designId],
  );

  // ==========================================================================
  // Sprint 2.5e.1 — Handlers de ejecución FULL
  // ==========================================================================
  const handleStartExecution = useCallback(async () => {
    if (!designId) return;
    setExecutionStarting(true);
    setMetricsHistory([]); // HF13: reset del mini-chart
    try {
      const resp = await executionAPI.start(designId);
      setExecuteModalOpen(false);
      setExecutionLiveOpen(true);
      setCurrentExecution({
        execution_id: resp.execution_id,
        status: 'starting',
        elapsed_sec: 0,
        metrics: {},
      });
      // Polling cada 2s al endpoint /live-metrics
      if (pollIntervalRef.current) clearInterval(pollIntervalRef.current);
      pollIntervalRef.current = window.setInterval(async () => {
        try {
          const metrics = await executionAPI.getLiveMetrics(resp.execution_id);
          setCurrentExecution(metrics);
          // HF13: acumular punto para el mini-chart (máximo 60 puntos = ~2 min)
          setMetricsHistory((prev) => {
            const newPoint = {
              time: Math.round(metrics.elapsed_sec),
              avg_response_ms: metrics.metrics.avg_response_ms ?? 0,
            };
            return [...prev, newPoint].slice(-60);
          });
          if (['completed', 'cancelled', 'error'].includes(metrics.status)) {
            if (pollIntervalRef.current) {
              clearInterval(pollIntervalRef.current);
              pollIntervalRef.current = null;
            }
          }
        } catch (e) {
          // Errores transitorios de polling, ignorar
          console.warn('Poll error:', e);
        }
      }, 2000);
    } catch (e: any) {
      // HF14a: detail puede ser objeto {error_type, message, ...} (csv_missing).
      const detail = e?.response?.data?.detail;
      const msg =
        detail && typeof detail === 'object'
          ? detail.message || JSON.stringify(detail)
          : detail || e?.message || 'Error iniciando ejecución';
      alert(msg);
    } finally {
      setExecutionStarting(false);
    }
  }, [designId]);

  const handleStopExecution = useCallback(async () => {
    if (!currentExecution) return;
    if (!confirm('¿Detener la ejecución en curso? La ejecución quedará en estado cancelled.')) return;
    setStopRequesting(true);
    try {
      await executionAPI.stop(currentExecution.execution_id);
      // El polling actualizará el estado automáticamente
    } catch (e: any) {
      alert(e?.response?.data?.detail || e?.message || 'Error deteniendo');
    } finally {
      setStopRequesting(false);
    }
  }, [currentExecution]);

  const handleCloseExecutionPanel = useCallback(() => {
    // Sprint 2.6b: cleanup del cache backend de listeners (Opción R híbrida).
    if (currentExecution) {
      executionAPI.clearListenersCache(currentExecution.execution_id).catch((e) => {
        console.warn('Error clearing listeners cache:', e);
      });
    }

    setExecutionLiveOpen(false);

    // Si terminó, limpiar para la próxima ejecución
    if (currentExecution && ['completed', 'cancelled', 'error'].includes(currentExecution.status)) {
      setCurrentExecution(null);
      // Sprint 2.5e.2: limpiar también el resultado de análisis IA
      setAnalysisResult(null);
      setAnalysisError(null);
    }

    // Sprint 2.6b: salir del modo viewer de listeners siempre al cerrar el drawer.
    setListenersState(null);
  }, [currentExecution]);

  // ==========================================================================
  // Sprint 2.6b — Modo ejecución: routing del panel central a ListenerLiveViewer
  // ==========================================================================
  // Modo ejecución: drawer derecho abierto Y hay una ejecución activa/reciente.
  const isInExecutionMode = useMemo(
    () => executionLiveOpen && currentExecution !== null,
    [executionLiveOpen, currentExecution],
  );

  // Listener actualmente seleccionado en el árbol (derivado de `selected`).
  const activeListener = useMemo(() => {
    if (selected.kind !== 'listener') return null;
    return structure?.listeners.find((l) => l.id === selected.id) || null;
  }, [selected, structure]);

  // ¿El panel central debe mostrar el viewer en vivo en vez del editor estructural?
  const isViewingLiveListener = isInExecutionMode && activeListener !== null;

  // Polling de /listeners-state cada 2s mientras se está viendo un listener en vivo.
  const currentExecutionId = currentExecution?.execution_id;
  const currentExecutionStatus = currentExecution?.status;
  useEffect(() => {
    if (!isViewingLiveListener || !currentExecutionId) {
      if (listenersPollIntervalRef.current) {
        clearInterval(listenersPollIntervalRef.current);
        listenersPollIntervalRef.current = null;
      }
      return;
    }

    let cancelled = false;
    const fetchState = async () => {
      setListenersPollLoading(true);
      try {
        const state = await executionAPI.getListenersState(currentExecutionId);
        if (!cancelled) setListenersState(state);
      } catch (e) {
        console.warn('Error fetching listeners state:', e);
      } finally {
        if (!cancelled) setListenersPollLoading(false);
      }
    };

    // Fetch inicial inmediato.
    void fetchState();

    // Si la ejecución sigue corriendo → poll cada 2s. Si ya terminó, un solo fetch basta.
    if (currentExecutionStatus === 'running' || currentExecutionStatus === 'starting') {
      listenersPollIntervalRef.current = window.setInterval(() => {
        void fetchState();
      }, 2000);
    }

    return () => {
      cancelled = true;
      if (listenersPollIntervalRef.current) {
        clearInterval(listenersPollIntervalRef.current);
        listenersPollIntervalRef.current = null;
      }
    };
  }, [isViewingLiveListener, currentExecutionId, currentExecutionStatus]);

  // ==========================================================================
  // Sprint 2.5e.2 — Handlers de análisis IA + historial
  // ==========================================================================
  const handleAnalyzeAI = useCallback(async () => {
    if (!currentExecution) return;
    setAnalyzingAI(true);
    setAnalysisError(null);
    setAnalysisResult(null);
    try {
      const resp = await executionAPI.analyzeWithAI(currentExecution.execution_id);
      setAnalysisResult({
        test_execution_id: resp.test_execution_id,
        dashboard_url: resp.dashboard_url,
      });
    } catch (e: any) {
      const msg = e?.response?.data?.detail || e?.message || 'Error en pipeline IA';
      setAnalysisError(String(msg));
    } finally {
      setAnalyzingAI(false);
    }
  }, [currentExecution]);

  const handleOpenDashboard = useCallback(() => {
    if (!analysisResult) return;
    window.open(analysisResult.dashboard_url, '_blank', 'noopener,noreferrer');
  }, [analysisResult]);

  const handleOpenHistory = useCallback(async () => {
    if (!designId) return;
    setHistoryOpen(true);
    setHistoryLoading(true);
    try {
      const items = await executionAPI.history(designId, 20);
      setExecutionHistory(items);
    } catch (e: any) {
      console.error('Error cargando historial:', e);
      setExecutionHistory([]);
    } finally {
      setHistoryLoading(false);
    }
  }, [designId]);

  // Cleanup del polling al desmontar el componente
  useEffect(() => {
    return () => {
      if (pollIntervalRef.current) {
        clearInterval(pollIntervalRef.current);
        pollIntervalRef.current = null;
      }
    };
  }, []);
  // Sprint 2.5c.1: ya NO se auto-ejecuta al abrir; el usuario configura
  // usuarios/iteraciones y pulsa "Ejecutar smoke test" dentro del modal.

  // ==========================================================================
  // Render
  // ==========================================================================

  if (loading) {
    return (
      <div className="flex items-center justify-center h-screen">
        <Loader2 className="w-8 h-8 text-indigo-600 animate-spin" />
        <span className="ml-3 text-gray-600">Cargando editor...</span>
      </div>
    );
  }

  if (error || !structure) {
    return (
      <div className="p-6 max-w-3xl mx-auto">
        <div className="bg-red-50 border border-red-200 rounded-lg p-6">
          <div className="flex items-start gap-3">
            <AlertCircle className="w-6 h-6 text-red-600 flex-shrink-0 mt-0.5" />
            <div className="flex-1">
              <h2 className="text-lg font-semibold text-red-900">No se pudo abrir el editor</h2>
              <p className="text-sm text-red-700 mt-1">{error}</p>
              <button
                onClick={() => navigate('/ai-script-designer/history')}
                className="mt-4 px-4 py-2 bg-white border border-red-300 text-red-700 text-sm rounded-md hover:bg-red-50"
              >
                ← Volver al Workspace
              </button>
            </div>
          </div>
        </div>
      </div>
    );
  }

  return (
    <div className="h-screen flex flex-col bg-gray-50">
      {/* Header */}
      <div className="bg-white border-b border-gray-200 px-6 py-3 flex items-center justify-between flex-shrink-0">
        <div className="flex items-center gap-4">
          <button
            onClick={() => navigate('/ai-script-editor')}
            className="p-2 text-gray-600 hover:bg-gray-100 rounded-md"
            title="Volver a Editor IA"
          >
            <ArrowLeft className="w-5 h-5" />
          </button>
          <div className="flex items-center gap-2">
            <Code className="w-6 h-6 text-indigo-600" />
            <div>
              <h1 className="text-lg font-semibold text-gray-900">Editor IA</h1>
              <p className="text-xs text-gray-500">{designName}</p>
            </div>
          </div>
        </div>

        <div className="flex items-center gap-2">
          <button
            onClick={() => setExecuteModalOpen(true)}
            disabled={!designId || executionStarting || currentExecution?.status === 'running'}
            className="flex items-center gap-2 px-3 py-1.5 text-sm text-purple-700 bg-purple-50 border border-purple-200 rounded-md hover:bg-purple-100 disabled:opacity-50 disabled:cursor-not-allowed"
            title="Ejecución completa con la configuración del Thread Group"
          >
            <Zap className="w-4 h-4" />
            Ejecutar
          </button>
          <button
            onClick={() => setSmokeModalOpen(true)}
            disabled={!designId || smokeRunning}
            className="flex items-center gap-2 px-3 py-1.5 text-sm text-emerald-700 bg-emerald-50 border border-emerald-200 rounded-md hover:bg-emerald-100 disabled:opacity-50 disabled:cursor-not-allowed"
            title="Ejecutar smoke test (1 usuario, 1 iteración) con JMeter real"
          >
            <Play className="w-4 h-4" />
            Probar (Smoke)
          </button>
          <button
            onClick={() => {
              if (!designId) return;
              navigate(`/ai-script-designer?designId=${designId}&fromEditor=true`);
            }}
            disabled={!designId}
            className="flex items-center gap-2 px-3 py-1.5 text-sm text-indigo-700 bg-indigo-50 border border-indigo-200 rounded-md hover:bg-indigo-100 disabled:opacity-50 disabled:cursor-not-allowed"
            title="Pedir ayuda a la IA en el chat"
          >
            <Sparkles className="w-4 h-4" />
            Pedir a IA
          </button>
          <button
            onClick={handleOpenHistory}
            disabled={!designId}
            className="flex items-center gap-2 px-3 py-1.5 text-sm text-gray-700 bg-gray-50 border border-gray-200 rounded-md hover:bg-gray-100 disabled:opacity-50 disabled:cursor-not-allowed"
            title="Historial de ejecuciones de este diseño"
          >
            <History className="w-4 h-4" />
            Historial
          </button>
          <button
            onClick={handleDownloadJmx}
            disabled={!designId || downloadingJmx}
            className="flex items-center gap-2 px-3 py-1.5 text-sm text-slate-700 bg-slate-50 border border-slate-200 rounded-md hover:bg-slate-100 disabled:opacity-50 disabled:cursor-not-allowed"
            title="Descargar el diseño para JMeter desktop (ZIP con CSVs si los hay)"
          >
            {downloadingJmx ? (
              <>
                <Loader2 className="w-4 h-4 animate-spin" />
                Descargando…
              </>
            ) : (
              <>
                <Download className="w-4 h-4" />
                Descargar
              </>
            )}
          </button>
          <button
            onClick={() => setShowXmlModal(true)}
            className="flex items-center gap-2 px-3 py-1.5 text-sm text-gray-700 border border-gray-300 rounded-md hover:bg-gray-50"
          >
            <FileCode className="w-4 h-4" />
            Ver XML raw
          </button>
          {saving && (
            <div className="flex items-center gap-1.5 text-xs text-gray-600">
              <Loader2 className="w-3 h-3 animate-spin" />
              Guardando...
            </div>
          )}
          {!saving && lastSaved && !saveError && (
            <div className="flex items-center gap-1.5 text-xs text-green-600">
              <CheckCircle2 className="w-3 h-3" />
              Guardado {formatRelativeTime(lastSaved)}
            </div>
          )}
          {!saving && !lastSaved && !saveError && (
            <span className="text-xs text-gray-400">Sin cambios</span>
          )}
          {saveError && (
            <div className="flex items-center gap-1.5 text-xs text-red-600" title={saveError}>
              <AlertCircle className="w-3 h-3" />
              Error al guardar
            </div>
          )}
        </div>
      </div>

      {/* Cuerpo: 2 paneles */}
      <div className="flex-1 flex overflow-hidden">
        {/* Panel izquierdo: árbol */}
        <div className="w-[30%] bg-white border-r border-gray-200 flex flex-col">
          {/* Búsqueda */}
          <div className="p-3 border-b border-gray-200">
            <div className="relative">
              <SearchIcon className="absolute left-3 top-1/2 -translate-y-1/2 w-4 h-4 text-gray-400" />
              <input
                type="text"
                placeholder="Buscar en el árbol..."
                value={searchFilter}
                onChange={(e) => setSearchFilter(e.target.value)}
                className="w-full pl-9 pr-3 py-1.5 text-sm border border-gray-300 rounded-md focus:ring-2 focus:ring-indigo-500"
              />
            </div>
          </div>

          {/* Árbol */}
          <div className="flex-1 overflow-y-auto p-2">
            <TreeView
              structure={structure}
              selected={selected}
              expanded={expanded}
              onSelect={setSelected}
              onToggleExpand={toggleExpand}
              matchesFilter={matchesFilter}
              dataFiles={dataFiles}
              treeActions={treeActions}
            />
          </div>
        </div>

        {/* Panel derecho: detalle */}
        <div className="flex-1 overflow-y-auto">
          {/* Sprint 2.6b: en modo ejecución, un listener seleccionado muestra el
              viewer en vivo en vez del editor estructural. */}
          {isViewingLiveListener && activeListener ? (
            <ListenerLiveViewer
              listenerKind={activeListener.kind}
              listenerName={activeListener.name}
              state={listenersState}
              loading={listenersPollLoading}
              executionStatus={currentExecution?.status || 'unknown'}
            />
          ) : (
            <DetailPanel
              structure={structure}
              selected={selected}
              onUpdateStructure={updateStructure}
              designId={designId || ''}
              dataFiles={dataFiles}
              dataFilesLoading={dataFilesLoading}
              reloadDataFiles={reloadDataFiles}
              reloadStructure={reloadStructure}
              onDataFileSelect={setSelected}
            />
          )}
        </div>
      </div>

      {/* Modal XML raw */}
      {showXmlModal && (
        <XmlRawModal jmx={originalJmx} onClose={() => setShowXmlModal(false)} />
      )}

      {/* HF7.A — Modal de agregar elemento */}
      <AddElementModal
        open={addModalOpen}
        elementType={addModalType}
        onClose={() => setAddModalOpen(false)}
        onConfirm={handleAddElement}
      />

      {/* Sprint 2.5c — Modal de Smoke Test */}
      <SmokeTestModal
        open={smokeModalOpen}
        running={smokeRunning}
        result={smokeResult}
        error={smokeError}
        showLog={smokeShowLog}
        config={smokeConfig}
        onConfigChange={setSmokeConfig}
        onRun={() => void runSmokeTest(smokeConfig)}
        onClose={() => {
          setSmokeModalOpen(false);
          // Limpiar estado tras cerrar para que la próxima vez vuelva a la config
          setTimeout(() => {
            setSmokeResult(null);
            setSmokeError(null);
            setSmokeShowLog(false);
          }, 200);
        }}
        onRetry={() => {
          setSmokeResult(null);
          setSmokeError(null);
          void runSmokeTest(smokeConfig);
        }}
        onToggleLog={() => setSmokeShowLog((v) => !v)}
      />

      {/* Sprint 2.5e.1: Modal pre-ejecución FULL */}
      {executeModalOpen && (
        <div className="fixed inset-0 bg-black/40 z-50 flex items-center justify-center p-4">
          <div className="bg-white rounded-lg shadow-xl w-[500px] max-w-full">
            <div className="px-5 py-4 border-b border-gray-200 flex items-center gap-2">
              <Zap className="w-5 h-5 text-purple-600" />
              <h3 className="text-lg font-semibold">Ejecución completa</h3>
            </div>

            <div className="px-5 py-4">
              <div className="bg-amber-50 border border-amber-200 rounded-lg p-3 mb-3">
                <div className="flex items-start gap-2">
                  <AlertTriangle className="w-5 h-5 text-amber-600 flex-shrink-0 mt-0.5" />
                  <div className="text-sm space-y-2">
                    <p className="font-medium text-amber-900">Esto NO es un smoke test.</p>
                    <p className="text-amber-800">
                      JMeter ejecutará el JMX con la configuración del Thread Group
                      (usuarios, ramp-up, duración) tal como está definida en el diseño.
                    </p>
                    <p className="text-amber-800">
                      Las métricas se enviarán a <strong>InfluxDB</strong> y se podrán visualizar
                      en Grafana en tiempo real.
                    </p>
                    <p className="text-amber-800">
                      Duración estimada: <strong>varios minutos</strong> según tu Thread Group.
                    </p>
                  </div>
                </div>
              </div>

              <p className="text-sm text-gray-700">
                ¿Iniciar ejecución del diseño?
              </p>
            </div>

            <div className="flex justify-end gap-2 px-5 py-3 border-t border-gray-200 bg-gray-50">
              <button
                onClick={() => setExecuteModalOpen(false)}
                disabled={executionStarting}
                className="px-3 py-1.5 text-sm border border-gray-300 rounded hover:bg-white disabled:opacity-50"
              >
                Cancelar
              </button>
              <button
                onClick={handleStartExecution}
                disabled={executionStarting}
                className="px-3 py-1.5 text-sm bg-purple-600 text-white rounded hover:bg-purple-700 disabled:opacity-50 flex items-center gap-2"
              >
                {executionStarting ? (
                  <>
                    <Loader2 className="w-4 h-4 animate-spin" />
                    Iniciando…
                  </>
                ) : (
                  <>
                    <Zap className="w-4 h-4" />
                    Ejecutar ahora
                  </>
                )}
              </button>
            </div>
          </div>
        </div>
      )}

      {/* Sprint 2.5e.1: Drawer de ejecución live */}
      {executionLiveOpen && currentExecution && (
        <div className="fixed inset-y-0 right-0 w-[400px] bg-white shadow-2xl z-40 flex flex-col border-l border-gray-200">
          <div className="px-4 py-3 border-b border-gray-200 flex items-center justify-between bg-gradient-to-r from-purple-50 to-indigo-50">
            <div className="flex items-center gap-2">
              <Zap className={`w-5 h-5 ${currentExecution.status === 'running' ? 'text-purple-600 animate-pulse' : 'text-gray-500'}`} />
              <h3 className="font-semibold">Ejecución #{currentExecution.execution_id}</h3>
            </div>
            <button onClick={handleCloseExecutionPanel} className="text-gray-400 hover:text-gray-600">
              <X className="w-5 h-5" />
            </button>
          </div>

          <div className="flex-1 overflow-y-auto px-4 py-3 space-y-3">
            {/* Status badge */}
            <div className={`rounded-lg p-3 ${
              currentExecution.status === 'running' ? 'bg-purple-50 border border-purple-200' :
              currentExecution.status === 'starting' ? 'bg-blue-50 border border-blue-200' :
              currentExecution.status === 'completed' ? 'bg-emerald-50 border border-emerald-200' :
              currentExecution.status === 'error' ? 'bg-red-50 border border-red-200' :
              currentExecution.status === 'cancelled' ? 'bg-gray-100 border border-gray-300' :
              'bg-gray-50 border border-gray-200'
            }`}>
              <div className="text-xs text-gray-600 mb-1">Estado</div>
              <div className="text-lg font-semibold capitalize flex items-center gap-2">
                {currentExecution.status === 'running' && <Loader2 className="w-4 h-4 animate-spin" />}
                {currentExecution.status === 'completed' && <CheckCircle2 className="w-4 h-4 text-emerald-600" />}
                {currentExecution.status === 'error' && <XCircle className="w-4 h-4 text-red-600" />}
                {currentExecution.status === 'cancelled' && <X className="w-4 h-4 text-gray-500" />}
                {currentExecution.status}
              </div>
              <div className="text-xs text-gray-500 mt-1">
                Tiempo transcurrido: {Math.floor(currentExecution.elapsed_sec / 60)}m {Math.floor(currentExecution.elapsed_sec % 60)}s
              </div>
            </div>

            {/* Métricas tiempo real */}
            <div className="grid grid-cols-2 gap-2">
              <div className="bg-gray-50 rounded p-3">
                <div className="text-xs text-gray-600">Samples totales</div>
                <div className="text-2xl font-semibold">{currentExecution.metrics.total_samples ?? 0}</div>
              </div>
              <div className="bg-gray-50 rounded p-3">
                <div className="text-xs text-gray-600">Throughput</div>
                <div className="text-2xl font-semibold">
                  {currentExecution.metrics.throughput_per_sec?.toFixed(1) ?? '0.0'}
                  <span className="text-sm text-gray-500"> /s</span>
                </div>
              </div>
              <div className="bg-emerald-50 rounded p-3">
                <div className="text-xs text-emerald-700">Éxitos</div>
                <div className="text-2xl font-semibold text-emerald-900">
                  {currentExecution.metrics.successful_samples ?? 0}
                </div>
              </div>
              <div className="bg-red-50 rounded p-3">
                <div className="text-xs text-red-700">Errores</div>
                <div className="text-2xl font-semibold text-red-900">
                  {currentExecution.metrics.failed_samples ?? 0}
                </div>
              </div>
              <div className="bg-blue-50 rounded p-3 col-span-2">
                <div className="text-xs text-blue-700">Response time promedio</div>
                <div className="text-2xl font-semibold text-blue-900">
                  {currentExecution.metrics.avg_response_ms ?? 0}<span className="text-sm font-normal text-blue-700"> ms</span>
                </div>
              </div>
            </div>

            {/* Tasa de error */}
            {(currentExecution.metrics.error_rate_pct ?? 0) > 0 && (
              <div className="bg-amber-50 border border-amber-200 rounded p-3">
                <div className="flex items-center gap-2 text-sm">
                  <AlertTriangle className="w-4 h-4 text-amber-600" />
                  <span>Tasa de errores: <strong>{currentExecution.metrics.error_rate_pct?.toFixed(2)}%</strong></span>
                </div>
              </div>
            )}

            {/* HF13: Mini-chart de response time (placeholder hasta Sprint 2.6) */}
            {metricsHistory.length > 1 && (
              <div className="bg-white border border-gray-200 rounded-lg p-3">
                <div className="flex items-center justify-between mb-2">
                  <h4 className="text-xs font-medium text-gray-700">Response time avg (ms)</h4>
                  <span className="text-xs text-gray-400">últimos {metricsHistory.length} puntos</span>
                </div>
                <div style={{ width: '100%', height: 140 }}>
                  <ResponsiveContainer>
                    <LineChart data={metricsHistory} margin={{ top: 5, right: 10, left: 0, bottom: 5 }}>
                      <XAxis
                        dataKey="time"
                        tick={{ fontSize: 10 }}
                        label={{ value: 'seg', position: 'insideBottomRight', offset: -5, style: { fontSize: 10 } }}
                      />
                      <YAxis tick={{ fontSize: 10 }} />
                      <Tooltip
                        contentStyle={{ fontSize: 11, padding: '4px 8px' }}
                        formatter={(value: number) => [`${value} ms`, 'Avg']}
                        labelFormatter={(label) => `${label}s`}
                      />
                      <Line
                        type="monotone"
                        dataKey="avg_response_ms"
                        stroke="#4f46e5"
                        strokeWidth={2}
                        dot={false}
                        isAnimationActive={false}
                      />
                    </LineChart>
                  </ResponsiveContainer>
                </div>
                <p className="text-xs text-gray-400 mt-1 italic">
                  Vista simplificada — listeners en vivo vendrán en Sprint 2.6
                </p>
              </div>
            )}

            {/* Sprint 2.5e.2: Generar análisis IA */}
            {currentExecution.status === 'completed' && !analysisResult && (
              <div className="bg-indigo-50 border border-indigo-200 rounded-lg p-3">
                <p className="text-sm text-indigo-900 mb-2 font-medium">
                  Ejecución completada
                </p>
                <p className="text-xs text-indigo-700 mb-3">
                  Genera el análisis IA del JTL (12 secciones + verdict + conclusiones).
                  Tarda aproximadamente 1 minuto.
                </p>
                {analysisError && (
                  <div className="bg-red-50 border border-red-200 rounded p-2 mb-2 text-xs text-red-700">
                    {analysisError}
                  </div>
                )}
                <button
                  onClick={handleAnalyzeAI}
                  disabled={analyzingAI}
                  className="w-full px-3 py-2 text-sm bg-indigo-600 text-white rounded hover:bg-indigo-700 disabled:opacity-50 flex items-center justify-center gap-2"
                >
                  {analyzingAI ? (
                    <>
                      <Loader2 className="w-4 h-4 animate-spin" />
                      Generando análisis IA (~1 min)…
                    </>
                  ) : (
                    <>
                      <Sparkles className="w-4 h-4" />
                      Generar análisis IA del JTL
                    </>
                  )}
                </button>
              </div>
            )}

            {analysisResult && (
              <div className="bg-emerald-50 border border-emerald-200 rounded-lg p-3">
                <div className="flex items-center gap-2 mb-2">
                  <CheckCircle2 className="w-5 h-5 text-emerald-600" />
                  <p className="text-sm font-medium text-emerald-900">Análisis IA generado</p>
                </div>
                <p className="text-xs text-emerald-700 mb-3">
                  El dashboard contiene: resumen ejecutivo, análisis por sección, verdict
                  vs criterios de aceptación, recomendaciones y conclusiones.
                </p>
                <button
                  onClick={handleOpenDashboard}
                  className="w-full px-3 py-2 text-sm bg-emerald-600 text-white rounded hover:bg-emerald-700 flex items-center justify-center gap-2"
                >
                  Abrir Dashboard completo
                  <ExternalLink className="w-4 h-4" />
                </button>
              </div>
            )}
          </div>

          {/* Footer: botón Detener */}
          {currentExecution.status === 'running' && (
            <div className="px-4 py-3 border-t border-gray-200 bg-gray-50">
              <button
                onClick={handleStopExecution}
                disabled={stopRequesting}
                className="w-full px-3 py-2 text-sm bg-red-600 text-white rounded hover:bg-red-700 disabled:opacity-50 flex items-center justify-center gap-2"
              >
                {stopRequesting ? (
                  <>
                    <Loader2 className="w-4 h-4 animate-spin" />
                    Deteniendo…
                  </>
                ) : (
                  <>
                    <X className="w-4 h-4" />
                    Detener ejecución
                  </>
                )}
              </button>
            </div>
          )}
        </div>
      )}

      {/* Sprint 2.5e.2: Drawer del historial de ejecuciones */}
      {historyOpen && (
        <div className="fixed inset-y-0 right-0 w-[480px] bg-white shadow-2xl z-40 flex flex-col border-l border-gray-200">
          <div className="px-4 py-3 border-b border-gray-200 flex items-center justify-between bg-gradient-to-r from-gray-50 to-slate-50">
            <div className="flex items-center gap-2">
              <History className="w-5 h-5 text-gray-600" />
              <h3 className="font-semibold">Historial de ejecuciones</h3>
            </div>
            <button
              onClick={() => setHistoryOpen(false)}
              className="text-gray-400 hover:text-gray-600"
            >
              <X className="w-5 h-5" />
            </button>
          </div>

          <div className="flex-1 overflow-y-auto px-4 py-3">
            {historyLoading ? (
              <div className="flex items-center justify-center py-12">
                <Loader2 className="w-6 h-6 text-gray-400 animate-spin" />
              </div>
            ) : executionHistory.length === 0 ? (
              <div className="text-center py-12">
                <History className="w-12 h-12 text-gray-300 mx-auto mb-2" />
                <p className="text-sm text-gray-500">
                  No hay ejecuciones aún para este diseño.
                </p>
                <p className="text-xs text-gray-400 mt-1">
                  Click en "Ejecutar" para iniciar tu primera ejecución.
                </p>
              </div>
            ) : (
              <div className="space-y-2">
                {executionHistory.map((ex) => (
                  <div
                    key={ex.id}
                    className="border border-gray-200 rounded-lg p-3 hover:border-gray-300 hover:shadow-sm transition-all"
                  >
                    <div className="flex items-center justify-between mb-2">
                      <div className="flex items-center gap-2">
                        <span className="text-xs text-gray-400">#</span>
                        <span className="font-semibold text-sm">{ex.id}</span>
                        <span className={`text-xs px-2 py-0.5 rounded font-medium ${
                          ex.status === 'completed' ? 'bg-emerald-100 text-emerald-700' :
                          ex.status === 'running' ? 'bg-purple-100 text-purple-700' :
                          ex.status === 'error' ? 'bg-red-100 text-red-700' :
                          ex.status === 'cancelled' ? 'bg-gray-100 text-gray-700' :
                          'bg-blue-100 text-blue-700'
                        }`}>
                          {ex.status}
                        </span>
                      </div>
                      <span className="text-xs text-gray-500">
                        {ex.started_at ? new Date(ex.started_at).toLocaleString('es-CO', {
                          day: '2-digit', month: 'short', hour: '2-digit', minute: '2-digit',
                        }) : '—'}
                      </span>
                    </div>

                    {ex.summary_metrics && Object.keys(ex.summary_metrics).length > 0 && (
                      <div className="grid grid-cols-3 gap-2 text-xs text-gray-600 mt-2">
                        <div>
                          <div className="text-gray-400">Samples</div>
                          <div className="font-medium text-gray-900">
                            {ex.summary_metrics.total_samples ?? 0}
                          </div>
                        </div>
                        <div>
                          <div className="text-gray-400">Errores</div>
                          <div className={`font-medium ${(ex.summary_metrics.failed_samples ?? 0) > 0 ? 'text-red-600' : 'text-gray-900'}`}>
                            {ex.summary_metrics.failed_samples ?? 0}
                            {(ex.summary_metrics.error_rate_pct ?? 0) > 0 && (
                              <span className="text-xs text-gray-500"> ({ex.summary_metrics.error_rate_pct?.toFixed(1)}%)</span>
                            )}
                          </div>
                        </div>
                        <div>
                          <div className="text-gray-400">Throughput</div>
                          <div className="font-medium text-gray-900">
                            {ex.summary_metrics.throughput_per_sec?.toFixed(1) ?? '0.0'}/s
                          </div>
                        </div>
                      </div>
                    )}

                    {ex.error_message && (
                      <div className="mt-2 text-xs text-red-600 bg-red-50 px-2 py-1 rounded">
                        {ex.error_message}
                      </div>
                    )}
                  </div>
                ))}
              </div>
            )}
          </div>

          <div className="px-4 py-2 border-t border-gray-200 bg-gray-50 text-xs text-gray-500 text-center">
            Mostrando últimas {executionHistory.length} ejecuciones
          </div>
        </div>
      )}
    </div>
  );
}

// ============================================================================
// TreeView
// ============================================================================

interface TreeViewProps {
  structure: AIScriptStructure;
  selected: SelectedNode;
  expanded: ExpandedState;
  onSelect: (n: SelectedNode) => void;
  onToggleExpand: (key: string) => void;
  matchesFilter: (text: string) => boolean;
  dataFiles: AIDesignDataFile[];
  treeActions?: TreeActions; // HF7.A — opcional para no romper otros call sites
}

function TreeView({ structure, selected, expanded, onSelect, onToggleExpand, matchesFilter, dataFiles, treeActions }: TreeViewProps) {
  const isSelected = (s: SelectedNode): boolean => JSON.stringify(s) === JSON.stringify(selected);

  return (
    <ul className="text-sm">
      {/* Overview */}
      <TreeItem
        label="Resumen del JMX"
        icon={<Layers className="w-4 h-4 text-indigo-600" />}
        selected={isSelected({ kind: 'overview' })}
        onClick={() => onSelect({ kind: 'overview' })}
      />

      {/* Test Plan */}
      <TreeItem
        label={structure.test_plan.name || 'Test Plan'}
        icon={<FileCode className="w-4 h-4 text-gray-700" />}
        selected={isSelected({ kind: 'test_plan' })}
        onClick={() => onSelect({ kind: 'test_plan' })}
      />

      {/* Configuración global */}
      <TreeFolder
        label="Configuración global"
        icon={<Settings className="w-4 h-4 text-gray-700" />}
        expandKey="configElements"
        expanded={expanded}
        onToggleExpand={onToggleExpand}
      >
        <TreeItem
          label={`Variables (${structure.user_defined_variables.length})`}
          icon={<Sliders className="w-4 h-4 text-gray-500" />}
          selected={isSelected({ kind: 'udvs' })}
          onClick={() => onSelect({ kind: 'udvs' })}
          indent
          onAdd={treeActions ? () => treeActions.openAdd('udv') : undefined}
          addTitle="Agregar variable UDV"
        />
        {structure.http_defaults && (
          <TreeItem
            label="HTTP Request Defaults"
            icon={<Network className="w-4 h-4 text-gray-500" />}
            selected={isSelected({ kind: 'http_defaults' })}
            onClick={() => onSelect({ kind: 'http_defaults' })}
            indent
          />
        )}
        {structure.cookie_manager && (
          <TreeItem
            label="Cookie Manager"
            icon={<Settings className="w-4 h-4 text-gray-500" />}
            selected={isSelected({ kind: 'cookie_manager' })}
            onClick={() => onSelect({ kind: 'cookie_manager' })}
            indent
            enabled={structure.cookie_manager.enabled}
            onToggleEnabled={treeActions ? (v) => treeActions.onToggle('cookie_manager', '', v) : undefined}
          />
        )}
        {structure.cache_manager && (
          <TreeItem
            label="Cache Manager"
            icon={<Settings className="w-4 h-4 text-gray-500" />}
            selected={isSelected({ kind: 'cache_manager' })}
            onClick={() => onSelect({ kind: 'cache_manager' })}
            indent
            enabled={structure.cache_manager.enabled}
            onToggleEnabled={treeActions ? (v) => treeActions.onToggle('cache_manager', '', v) : undefined}
          />
        )}
        {structure.csv_data_sets.map((ds) => (
          <TreeItem
            key={ds.id}
            label={`CSV: ${ds.testname}`}
            icon={<Database className="w-4 h-4 text-purple-500" />}
            selected={isSelected({ kind: 'csv_data_set', id: ds.id })}
            onClick={() => onSelect({ kind: 'csv_data_set', id: ds.id })}
            indent
            visible={matchesFilter(ds.testname)}
            enabled={ds.enabled}
            onToggleEnabled={treeActions ? (v) => treeActions.onToggle('csv_data_set', ds.id, v) : undefined}
            onDelete={treeActions ? () => treeActions.onDelete('csv_data_set', ds.id) : undefined}
            deleteTitle={`Eliminar CSV ${ds.testname}`}
          />
        ))}
      </TreeFolder>

      {/* Thread Groups */}
      <TreeFolder
        label={`Thread Groups (${structure.thread_groups.length})`}
        icon={<UsersIcon className="w-4 h-4 text-indigo-700" />}
        expandKey="threadGroups"
        expanded={expanded}
        onToggleExpand={onToggleExpand}
      >
        {structure.thread_groups.map((tg) => (
          <ThreadGroupNode
            key={tg.id}
            tg={tg}
            selected={selected}
            expanded={expanded}
            onSelect={onSelect}
            onToggleExpand={onToggleExpand}
            matchesFilter={matchesFilter}
            treeActions={treeActions}
          />
        ))}
      </TreeFolder>

      {/* Listeners — HF7.B: el folder se muestra siempre cuando hay treeActions
          para que el usuario pueda agregar listeners aunque no tenga ninguno todavía. */}
      {(structure.listeners.length > 0 || treeActions) && (
        <TreeFolder
          label={`Listeners (${structure.listeners.length})`}
          icon={<Headphones className="w-4 h-4 text-gray-700" />}
          expandKey="listeners"
          expanded={expanded}
          onToggleExpand={onToggleExpand}
        >
          {treeActions && (
            <TreeItem
              label="Agregar listener…"
              icon={<Plus className="w-4 h-4 text-indigo-500" />}
              selected={false}
              onClick={() => treeActions.openAdd('listener')}
              indent
            />
          )}
          {structure.listeners.map((l) => (
            <TreeItem
              key={l.id}
              label={l.name}
              icon={<Eye className="w-4 h-4 text-gray-500" />}
              selected={isSelected({ kind: 'listener', id: l.id })}
              onClick={() => onSelect({ kind: 'listener', id: l.id })}
              indent
              visible={matchesFilter(l.name)}
              enabled={l.enabled}
              onToggleEnabled={treeActions ? (v) => treeActions.onToggle('listener', l.id, v) : undefined}
              onDelete={treeActions ? () => treeActions.onDelete('listener', l.id) : undefined}
              deleteTitle={`Eliminar listener ${l.name}`}
            />
          ))}
        </TreeFolder>
      )}

      {/* Data Files (Sprint 2.4-HF2) */}
      <TreeFolder
        label={`Data Files (${dataFiles.length})`}
        icon={<Database className="w-4 h-4 text-emerald-700" />}
        expandKey="dataFiles"
        expanded={expanded}
        onToggleExpand={onToggleExpand}
      >
        <TreeItem
          label="Gestionar archivos"
          icon={<Database className="w-4 h-4 text-gray-500" />}
          selected={isSelected({ kind: 'data_files_root' })}
          onClick={() => onSelect({ kind: 'data_files_root' })}
          indent
        />
        {dataFiles.map((df) => (
          <TreeItem
            key={df.id}
            label={df.original_filename}
            icon={<Database className="w-4 h-4 text-emerald-500" />}
            selected={isSelected({ kind: 'data_file', id: df.id })}
            onClick={() => onSelect({ kind: 'data_file', id: df.id })}
            indent
            visible={matchesFilter(df.original_filename)}
          />
        ))}
      </TreeFolder>

      {/* Unmapped */}
      {structure.unmapped.length > 0 && (
        <TreeFolder
          label={`No editables (${structure.unmapped.length})`}
          icon={<AlertTriangle className="w-4 h-4 text-amber-600" />}
          expandKey="unmapped"
          expanded={expanded}
          onToggleExpand={onToggleExpand}
        >
          {structure.unmapped.map((u) => (
            <TreeItem
              key={u.id}
              label={u.name || u.kind}
              icon={<AlertTriangle className="w-4 h-4 text-amber-500" />}
              selected={isSelected({ kind: 'unmapped', id: u.id })}
              onClick={() => onSelect({ kind: 'unmapped', id: u.id })}
              indent
              visible={matchesFilter(u.kind + (u.name || ''))}
            />
          ))}
        </TreeFolder>
      )}
    </ul>
  );
}

// ============================================================================
// ThreadGroupNode (recursivo: TG → Sampler → Children)
// ============================================================================

interface ThreadGroupNodeProps {
  tg: ThreadGroupModel;
  selected: SelectedNode;
  expanded: ExpandedState;
  onSelect: (n: SelectedNode) => void;
  onToggleExpand: (key: string) => void;
  matchesFilter: (text: string) => boolean;
  treeActions?: TreeActions;
}

function ThreadGroupNode({ tg, selected, expanded, onSelect, onToggleExpand, matchesFilter, treeActions }: ThreadGroupNodeProps) {
  const isSelected = (s: SelectedNode): boolean => JSON.stringify(s) === JSON.stringify(selected);
  const tgExpandKey = `tg-${tg.id}`;
  const tgExpanded = expanded[tgExpandKey] !== false; // default true
  const tgLabel = `${tg.name} (${tg.kind === 'stepping' ? 'Stepping' : 'Standard'})`;

  return (
    <li className="ml-2">
      <div
        className={`group flex items-center gap-1 py-1 px-2 rounded ${
          isSelected({ kind: 'thread_group', id: tg.id }) ? 'bg-indigo-50 text-indigo-700' : 'hover:bg-gray-50'
        }`}
      >
        <button
          onClick={(e) => { e.stopPropagation(); onToggleExpand(tgExpandKey); }}
          className="p-0.5 hover:bg-gray-200 rounded"
        >
          {tgExpanded ? <ChevronDown className="w-3 h-3" /> : <ChevronRight className="w-3 h-3" />}
        </button>
        {treeActions && (
          <input
            type="checkbox"
            checked={tg.enabled}
            onChange={(e) => { e.stopPropagation(); treeActions.onToggle('thread_group', tg.id, e.target.checked); }}
            onClick={(e) => e.stopPropagation()}
            className="w-3 h-3 accent-indigo-600"
            title={tg.enabled ? 'Habilitado' : 'Deshabilitado'}
          />
        )}
        <div
          className="flex items-center gap-2 flex-1 cursor-pointer"
          onClick={() => onSelect({ kind: 'thread_group', id: tg.id })}
        >
          <UsersIcon className={`w-4 h-4 ${tg.kind === 'stepping' ? 'text-purple-600' : 'text-indigo-600'}`} />
          <span className={`truncate ${!tg.enabled ? 'text-gray-400 line-through' : ''}`}>{tgLabel}</span>
          {!tg.enabled && <span className="text-xs text-gray-400">(off)</span>}
        </div>
        {treeActions && (
          <>
            <button
              type="button"
              onClick={(e) => { e.stopPropagation(); treeActions.openAdd('sampler', tg.id); }}
              className="opacity-0 group-hover:opacity-100 p-0.5 hover:bg-indigo-100 rounded text-indigo-600 transition-opacity"
              title="Agregar HTTP Sampler"
            >
              <Plus className="w-3.5 h-3.5" />
            </button>
            <button
              type="button"
              onClick={(e) => { e.stopPropagation(); treeActions.onDelete('thread_group', tg.id); }}
              className="opacity-0 group-hover:opacity-100 p-0.5 hover:bg-red-100 rounded text-red-500 transition-opacity"
              title={`Eliminar Thread Group ${tg.name}`}
            >
              <Trash2 className="w-3.5 h-3.5" />
            </button>
          </>
        )}
      </div>

      {tgExpanded && (
        <ul className="ml-4">
          {tg.children.map((ch) => (
            <TGChildNode
              key={
                ch.type === 'sampler' ? ch.sampler!.id :
                ch.type === 'controller' ? ch.controller!.id :
                ch.unsupported!.id
              }
              child={ch}
              tg_id={tg.id}
              selected={selected}
              expanded={expanded}
              onSelect={onSelect}
              onToggleExpand={onToggleExpand}
              matchesFilter={matchesFilter}
              treeActions={treeActions}
            />
          ))}
        </ul>
      )}
    </li>
  );
}

// ============================================================================
// TGChildNode (Sampler, Controller, o Unsupported)
// ============================================================================

interface TGChildNodeProps {
  child: TGChild;
  tg_id: string;
  selected: SelectedNode;
  expanded: ExpandedState;
  onSelect: (n: SelectedNode) => void;
  onToggleExpand: (key: string) => void;
  matchesFilter: (text: string) => boolean;
  treeActions?: TreeActions;
}

function TGChildNode({ child, tg_id, selected, expanded, onSelect, onToggleExpand, matchesFilter, treeActions }: TGChildNodeProps) {
  const isSelected = (s: SelectedNode): boolean => JSON.stringify(s) === JSON.stringify(selected);

  if (child.type === 'sampler' && child.sampler) {
    const sampler = child.sampler;
    const sampExpandKey = `samp-${sampler.id}`;
    const sampExpanded = expanded[sampExpandKey] === true;
    const hasChildren = sampler.children.length > 0;
    if (!matchesFilter(sampler.name)) return null;

    return (
      <li>
        <div
          className={`group flex items-center gap-1 py-1 px-2 rounded ${
            isSelected({ kind: 'sampler', tg_id, sampler_id: sampler.id }) ? 'bg-indigo-50 text-indigo-700' : 'hover:bg-gray-50'
          }`}
        >
          {hasChildren ? (
            <button
              onClick={(e) => { e.stopPropagation(); onToggleExpand(sampExpandKey); }}
              className="p-0.5 hover:bg-gray-200 rounded"
            >
              {sampExpanded ? <ChevronDown className="w-3 h-3" /> : <ChevronRight className="w-3 h-3" />}
            </button>
          ) : (
            <span className="w-4" />
          )}
          {treeActions && (
            <input
              type="checkbox"
              checked={sampler.enabled}
              onChange={(e) => { e.stopPropagation(); treeActions.onToggle('sampler', sampler.id, e.target.checked); }}
              onClick={(e) => e.stopPropagation()}
              className="w-3 h-3 accent-indigo-600 flex-shrink-0"
              title={sampler.enabled ? 'Habilitado' : 'Deshabilitado'}
            />
          )}
          <div
            className="flex items-center gap-2 flex-1 min-w-0 cursor-pointer"
            onClick={() => onSelect({ kind: 'sampler', tg_id, sampler_id: sampler.id })}
          >
            <span className={`px-1.5 py-0.5 text-xs rounded font-mono ${methodColor(sampler.method)}`}>
              {sampler.method}
            </span>
            <span className={`truncate text-sm ${!sampler.enabled ? 'text-gray-400 line-through' : ''}`}>
              {sampler.name}
            </span>
          </div>
          {treeActions && (
            <>
              <button
                type="button"
                onClick={(e) => { e.stopPropagation(); treeActions.openAdd('sampler_child', sampler.id); }}
                className="opacity-0 group-hover:opacity-100 p-0.5 hover:bg-indigo-100 rounded text-indigo-600 transition-opacity flex-shrink-0"
                title="Agregar componente (Header, Assertion, Extractor, Timer)"
              >
                <Plus className="w-3.5 h-3.5" />
              </button>
              <button
                type="button"
                onClick={(e) => { e.stopPropagation(); treeActions.onDelete('sampler', sampler.id); }}
                className="opacity-0 group-hover:opacity-100 p-0.5 hover:bg-red-100 rounded text-red-500 transition-opacity flex-shrink-0"
                title={`Eliminar sampler ${sampler.name}`}
              >
                <Trash2 className="w-3.5 h-3.5" />
              </button>
            </>
          )}
        </div>

        {sampExpanded && (
          <ul className="ml-6">
            {sampler.children.map((sc) => (
              <SamplerChildNode
                key={(sc.data as any).id}
                sc={sc}
                tg_id={tg_id}
                sampler_id={sampler.id}
                selected={selected}
                onSelect={onSelect}
                treeActions={treeActions}
              />
            ))}
          </ul>
        )}
      </li>
    );
  }

  if (child.type === 'controller' && child.controller) {
    const ctrl = child.controller;
    if (!matchesFilter(ctrl.name)) return null;
    return (
      <li>
        <div
          className={`flex items-center gap-2 py-1 px-2 rounded cursor-pointer ${
            isSelected({ kind: 'controller', tg_id, controller_id: ctrl.id }) ? 'bg-indigo-50 text-indigo-700' : 'hover:bg-gray-50'
          }`}
          onClick={() => onSelect({ kind: 'controller', tg_id, controller_id: ctrl.id })}
        >
          <span className="w-4" />
          <Layers className="w-4 h-4 text-amber-600" />
          <span className="truncate text-sm">{ctrl.name}</span>
          <span className="text-xs text-gray-400">({ctrl.kind})</span>
        </div>
        {/* Recursión opcional para children del controller — Sprint 2.4 futuro */}
      </li>
    );
  }

  if (child.type === 'unsupported' && child.unsupported) {
    const u = child.unsupported;
    if (!matchesFilter(u.kind + (u.name || ''))) return null;
    return (
      <li>
        <div
          className={`flex items-center gap-2 py-1 px-2 rounded cursor-pointer ${
            isSelected({ kind: 'unmapped', id: u.id }) ? 'bg-amber-50 text-amber-700' : 'hover:bg-gray-50'
          }`}
          onClick={() => onSelect({ kind: 'unmapped', id: u.id })}
        >
          <span className="w-4" />
          <AlertTriangle className="w-4 h-4 text-amber-500" />
          <span className="truncate text-sm text-gray-600">{u.name || u.kind}</span>
        </div>
      </li>
    );
  }

  return null;
}

// ============================================================================
// SamplerChildNode
// ============================================================================

interface SamplerChildNodeProps {
  sc: SamplerChild;
  tg_id: string;
  sampler_id: string;
  selected: SelectedNode;
  onSelect: (n: SelectedNode) => void;
  treeActions?: TreeActions;
}

function SamplerChildNode({ sc, tg_id, sampler_id, selected, onSelect, treeActions }: SamplerChildNodeProps) {
  const isSelected = (s: SelectedNode): boolean => JSON.stringify(s) === JSON.stringify(selected);
  const childId = (sc.data as any).id;
  const childName = (sc.data as any).name || sc.type;
  const childEnabled = (sc.data as any).enabled !== false;
  const isUnmapped = sc.type === 'unsupported';

  const icon = (() => {
    switch (sc.type) {
      case 'header_manager': return <Network className="w-3.5 h-3.5 text-blue-500" />;
      case 'response_assertion': return <CheckCircle2 className="w-3.5 h-3.5 text-green-500" />;
      case 'regex_extractor':
      case 'json_extractor':
      case 'xpath_extractor':
      case 'boundary_extractor':
        return <Sliders className="w-3.5 h-3.5 text-purple-500" />;
      case 'constant_timer':
      case 'uniform_random_timer':
      case 'gaussian_random_timer':
        return <Loader2 className="w-3.5 h-3.5 text-orange-500" />;
      default:
        return <AlertTriangle className="w-3.5 h-3.5 text-amber-500" />;
    }
  })();

  return (
    <li>
      <div
        className={`group flex items-center gap-2 py-0.5 px-2 rounded ${
          isSelected({ kind: 'sampler_child', tg_id, sampler_id, child_id: childId })
            ? 'bg-indigo-50 text-indigo-700'
            : 'hover:bg-gray-50'
        }`}
      >
        {treeActions && !isUnmapped && (
          <input
            type="checkbox"
            checked={childEnabled}
            onChange={(e) => { e.stopPropagation(); treeActions.onToggle('sampler_child', childId, e.target.checked, { sampler_id }); }}
            onClick={(e) => e.stopPropagation()}
            className="w-3 h-3 accent-indigo-600 flex-shrink-0"
            title={childEnabled ? 'Habilitado' : 'Deshabilitado'}
          />
        )}
        <div
          className={`flex items-center gap-2 flex-1 min-w-0 cursor-pointer ${!childEnabled ? 'opacity-50' : ''}`}
          onClick={() => onSelect({ kind: 'sampler_child', tg_id, sampler_id, child_id: childId })}
        >
          {icon}
          <span className={`truncate text-xs ${isUnmapped ? 'text-amber-700' : 'text-gray-600'}`}>
            {childName}
          </span>
        </div>
        {treeActions && !isUnmapped && (
          <button
            type="button"
            onClick={(e) => { e.stopPropagation(); treeActions.onDelete('sampler_child', childId, { sampler_id }); }}
            className="opacity-0 group-hover:opacity-100 p-0.5 hover:bg-red-100 rounded text-red-500 transition-opacity flex-shrink-0"
            title={`Eliminar ${childName}`}
          >
            <Trash2 className="w-3 h-3" />
          </button>
        )}
      </div>
    </li>
  );
}

// ============================================================================
// Helpers de UI
// ============================================================================

function methodColor(method: string): string {
  const m = method.toUpperCase();
  if (m === 'GET') return 'bg-green-100 text-green-700';
  if (m === 'POST') return 'bg-blue-100 text-blue-700';
  if (m === 'PUT') return 'bg-orange-100 text-orange-700';
  if (m === 'DELETE') return 'bg-red-100 text-red-700';
  if (m === 'PATCH') return 'bg-purple-100 text-purple-700';
  return 'bg-gray-100 text-gray-700';
}

// ============================================================================
// TreeItem (item simple del árbol)
// ============================================================================

interface TreeItemProps {
  label: string;
  icon: React.ReactNode;
  selected: boolean;
  onClick: () => void;
  indent?: boolean;
  visible?: boolean;
  badge?: string;
  // HF7.A — props opcionales para botones de mutación estructural.
  enabled?: boolean;
  onToggleEnabled?: (next: boolean) => void;
  onAdd?: () => void;
  addTitle?: string;
  onDelete?: () => void;
  deleteTitle?: string;
}

function TreeItem({
  label, icon, selected, onClick, indent, visible = true, badge,
  enabled, onToggleEnabled, onAdd, addTitle, onDelete, deleteTitle,
}: TreeItemProps) {
  if (!visible) return null;
  return (
    <li className={indent ? 'ml-4' : ''}>
      <div
        className={`group flex items-center gap-2 py-1 px-2 rounded text-sm ${
          selected ? 'bg-indigo-50 text-indigo-700 font-medium' : 'hover:bg-gray-50 text-gray-700'
        }`}
      >
        {onToggleEnabled !== undefined && (
          <input
            type="checkbox"
            checked={enabled ?? true}
            onChange={(e) => { e.stopPropagation(); onToggleEnabled(e.target.checked); }}
            onClick={(e) => e.stopPropagation()}
            className="w-3 h-3 accent-indigo-600 flex-shrink-0"
            title={enabled === false ? 'Deshabilitado' : 'Habilitado'}
          />
        )}
        <div
          className={`flex items-center gap-2 flex-1 min-w-0 cursor-pointer ${enabled === false ? 'opacity-50' : ''}`}
          onClick={onClick}
        >
          {icon}
          <span className="truncate">{label}</span>
          {badge && <span className="text-xs text-gray-400">({badge})</span>}
        </div>
        {onAdd && (
          <button
            type="button"
            onClick={(e) => { e.stopPropagation(); onAdd(); }}
            className="opacity-0 group-hover:opacity-100 p-0.5 hover:bg-indigo-100 rounded text-indigo-600 transition-opacity flex-shrink-0"
            title={addTitle || 'Agregar'}
          >
            <Plus className="w-3.5 h-3.5" />
          </button>
        )}
        {onDelete && (
          <button
            type="button"
            onClick={(e) => { e.stopPropagation(); onDelete(); }}
            className="opacity-0 group-hover:opacity-100 p-0.5 hover:bg-red-100 rounded text-red-500 transition-opacity flex-shrink-0"
            title={deleteTitle || 'Eliminar'}
          >
            <Trash2 className="w-3.5 h-3.5" />
          </button>
        )}
      </div>
    </li>
  );
}

// ============================================================================
// TreeFolder (carpeta colapsable del árbol)
// ============================================================================

interface TreeFolderProps {
  label: string;
  icon: React.ReactNode;
  expandKey: string;
  expanded: ExpandedState;
  onToggleExpand: (key: string) => void;
  children: React.ReactNode;
}

function TreeFolder({ label, icon, expandKey, expanded, onToggleExpand, children }: TreeFolderProps) {
  const isOpen = expanded[expandKey] !== false;
  return (
    <li>
      <div
        className="flex items-center gap-1 py-1 px-2 rounded hover:bg-gray-50 cursor-pointer text-sm font-medium text-gray-800"
        onClick={() => onToggleExpand(expandKey)}
      >
        {isOpen ? <ChevronDown className="w-3 h-3" /> : <ChevronRight className="w-3 h-3" />}
        {icon}
        <span className="truncate">{label}</span>
      </div>
      {isOpen && <ul>{children}</ul>}
    </li>
  );
}

// ============================================================================
// DetailPanel (panel derecho con detalle según selección)
// ============================================================================

interface DetailPanelProps {
  structure: AIScriptStructure;
  selected: SelectedNode;
  onUpdateStructure: (s: AIScriptStructure) => void;
  designId: string;
  dataFiles: AIDesignDataFile[];
  dataFilesLoading: boolean;
  reloadDataFiles: () => void;
  reloadStructure: () => void;
  onDataFileSelect: (n: SelectedNode) => void;
}

function DetailPanel({
  structure,
  selected,
  onUpdateStructure,
  designId,
  dataFiles,
  dataFilesLoading,
  reloadDataFiles,
  reloadStructure,
  onDataFileSelect,
}: DetailPanelProps) {
  if (selected.kind === 'overview') {
    return <OverviewPanel structure={structure} />;
  }

  if (selected.kind === 'thread_group') {
    const tg = structure.thread_groups.find((t) => t.id === selected.id);
    if (!tg) return <NotFoundPanel kind="thread_group" />;
    return (
      <ThreadGroupEditPanel
        tg={tg}
        onUpdate={(updates) => onUpdateStructure(updateThreadGroup(structure, tg.id, updates))}
      />
    );
  }

  if (selected.kind === 'sampler') {
    const tg = structure.thread_groups.find((t) => t.id === selected.tg_id);
    const samplerChild = tg?.children.find(
      (ch) => ch.type === 'sampler' && ch.sampler?.id === selected.sampler_id,
    );
    const sampler = samplerChild?.sampler;
    if (!tg || !sampler) return <NotFoundPanel kind="sampler" />;
    return (
      <HTTPSamplerEditPanel
        sampler={sampler}
        onUpdate={(updates) => onUpdateStructure(updateSampler(structure, tg.id, sampler.id, updates))}
      />
    );
  }

  if (selected.kind === 'sampler_child') {
    const tg = structure.thread_groups.find((t) => t.id === selected.tg_id);
    const samplerChild = tg?.children.find(
      (ch) => ch.type === 'sampler' && ch.sampler?.id === selected.sampler_id,
    );
    const sampler = samplerChild?.sampler;
    const child = sampler?.children.find((c) => (c.data as any).id === selected.child_id);
    if (!tg || !sampler || !child) return <NotFoundPanel kind="sampler_child" />;
    return (
      <SamplerChildEditPanel
        child={child}
        onUpdate={(updates) =>
          onUpdateStructure(updateSamplerChild(structure, tg.id, sampler.id, selected.child_id, updates))
        }
      />
    );
  }

  if (selected.kind === 'test_plan') {
    return (
      <TestPlanEditPanel
        tp={structure.test_plan}
        onUpdate={(updates) =>
          onUpdateStructure({
            ...structure,
            test_plan: { ...structure.test_plan, ...updates, is_dirty: true },
          })
        }
      />
    );
  }

  if (selected.kind === 'udvs') {
    return (
      <UDVsEditPanel
        udvs={structure.user_defined_variables}
        onUpdate={(newUdvs) =>
          onUpdateStructure({ ...structure, user_defined_variables: newUdvs })
        }
      />
    );
  }

  if (selected.kind === 'csv_data_set') {
    const ds = structure.csv_data_sets.find((d) => d.id === selected.id);
    if (!ds) return <NotFoundPanel kind="csv_data_set" />;
    return (
      <CSVDataSetEditPanel
        ds={ds}
        onUpdate={(updates) =>
          onUpdateStructure({
            ...structure,
            csv_data_sets: structure.csv_data_sets.map((d) =>
              d.id === ds.id ? { ...d, ...updates, is_dirty: true } : d,
            ),
          })
        }
      />
    );
  }

  if (selected.kind === 'http_defaults' && structure.http_defaults) {
    return (
      <HttpDefaultsEditPanel
        hd={structure.http_defaults}
        onUpdate={(updates) =>
          onUpdateStructure({
            ...structure,
            http_defaults: { ...structure.http_defaults!, ...updates, is_dirty: true },
          })
        }
      />
    );
  }

  if (selected.kind === 'cookie_manager' && structure.cookie_manager) {
    return (
      <CookieManagerEditPanel
        cm={structure.cookie_manager}
        onUpdate={(updates) =>
          onUpdateStructure({
            ...structure,
            cookie_manager: { ...structure.cookie_manager!, ...updates, is_dirty: true },
          })
        }
      />
    );
  }

  if (selected.kind === 'cache_manager' && structure.cache_manager) {
    return (
      <CacheManagerEditPanel
        cm={structure.cache_manager}
        onUpdate={(updates) =>
          onUpdateStructure({
            ...structure,
            cache_manager: { ...structure.cache_manager!, ...updates, is_dirty: true },
          })
        }
      />
    );
  }

  if (selected.kind === 'data_files_root') {
    return (
      <DataFilesPanel
        designId={designId}
        dataFiles={dataFiles}
        loading={dataFilesLoading}
        onReload={reloadDataFiles}
        onReloadStructure={reloadStructure}
      />
    );
  }

  if (selected.kind === 'data_file') {
    return (
      <DataFileDetailPanel
        designId={designId}
        fileId={selected.id}
        onDeleted={() => {
          reloadDataFiles();
          onDataFileSelect({ kind: 'data_files_root' });
        }}
      />
    );
  }

  // Fallback: tipos aún no implementados
  return (
    <div className="p-6 max-w-3xl">
      <div className="bg-amber-50 border border-amber-200 rounded-lg p-4">
        <div className="flex items-center gap-2 mb-2">
          <Info className="w-5 h-5 text-amber-600" />
          <h3 className="font-semibold text-amber-900">Edición disponible próximamente</h3>
        </div>
        <p className="text-sm text-amber-800">
          Tipo: <code className="bg-amber-100 px-1 rounded">{selected.kind}</code>
        </p>
        <p className="text-sm text-amber-700 mt-1">
          Esta funcionalidad se habilita en sub-sprints posteriores (2.4c-e).
        </p>
      </div>
    </div>
  );
}

// ============================================================================
// Sprint 2.6b: Listener Live Viewer (placeholder).
// Los renderers reales por kind vienen en 2.6c-g; aquí solo se enruta y se
// muestra un resumen del estado capturado del polling.
// ============================================================================

interface ListenerLiveViewerProps {
  listenerKind: string;
  listenerName: string | null;
  state: ListenersState | null;
  loading: boolean;
  executionStatus: string;
}

// Mapa kind → label visible (alineado con ListenerKind del frontend).
const LISTENER_KIND_LABELS: Record<string, string> = {
  view_results_tree: 'Ver Árbol de Resultados',
  summary_report: 'Informe Resumen',
  aggregate_report: 'Informe Agregado',
  graph_results: 'Gráfico de Resultados',
  kg_apc_response_times_over_time: 'jp@gc - Response Times Over Time',
  kg_apc_response_codes_per_second: 'jp@gc - Response Codes per Second',
  kg_apc_transactions_per_second: 'jp@gc - Transactions per Second',
  kg_apc_active_threads_over_time: 'jp@gc - Active Threads Over Time',
  kg_apc_hits_per_second: 'jp@gc - Hits per Second',
  other: 'Listener (Backend / otro)',
};

function ListenerLiveViewer({
  listenerKind,
  listenerName,
  state,
  loading,
  executionStatus,
}: ListenerLiveViewerProps) {
  const label = LISTENER_KIND_LABELS[listenerKind] || listenerName || 'Listener';
  const isRunning = executionStatus === 'running' || executionStatus === 'starting';

  return (
    <div className="h-full flex flex-col bg-gray-50">
      {/* Header del viewer */}
      <div className="bg-white border-b border-gray-200 px-5 py-3">
        <div className="flex items-center justify-between">
          <div>
            <h3 className="font-semibold text-gray-900">{label}</h3>
            {listenerName && listenerName !== label && (
              <p className="text-xs text-gray-500 mt-0.5">{listenerName}</p>
            )}
          </div>
          {isRunning && (
            <div className="flex items-center gap-1.5 text-xs text-purple-700 bg-purple-50 px-2 py-1 rounded">
              <Loader2 className="w-3 h-3 animate-spin" />
              Actualizando cada 2s
            </div>
          )}
          {executionStatus === 'completed' && (
            <div className="flex items-center gap-1.5 text-xs text-emerald-700 bg-emerald-50 px-2 py-1 rounded">
              <CheckCircle2 className="w-3 h-3" />
              Datos congelados
            </div>
          )}
        </div>
      </div>

      {/* Body del viewer — despacha al renderer según el kind del listener */}
      <div className="flex-1 overflow-y-auto px-5 py-4">
        {loading && !state && (
          <div className="flex items-center justify-center py-12">
            <Loader2 className="w-6 h-6 text-gray-400 animate-spin" />
          </div>
        )}

        {state && (
          <>
            {/* Sprint 2.6c: Summary Report */}
            {listenerKind === 'summary_report' && (
              <SummaryReportViewer
                perSamplerStats={state.per_sampler_stats}
                totalSamples={state.total_samples_parsed}
              />
            )}

            {/* Sprint 2.6c: Aggregate Report */}
            {listenerKind === 'aggregate_report' && (
              <AggregateReportViewer
                perSamplerStats={state.per_sampler_stats}
                totalSamples={state.total_samples_parsed}
              />
            )}

            {/* Sprint 2.6d: View Results Tree (la variante "with CSV" usa el mismo viewer) */}
            {listenerKind === 'view_results_tree' && (
              <ViewResultsTreeViewer
                samplesTail={state.samples_tail}
                totalSamplesParsed={state.total_samples_parsed}
              />
            )}

            {/* Sprint 2.6e: jp@gc Response Times Over Time */}
            {listenerKind === 'kg_apc_response_times_over_time' && (
              <ResponseTimesOverTimeViewer timeBuckets={state.time_buckets} />
            )}

            {/* Sprint 2.6e: jp@gc Response Codes per Second */}
            {listenerKind === 'kg_apc_response_codes_per_second' && (
              <ResponseCodesPerSecondViewer timeBuckets={state.time_buckets} />
            )}

            {/* Sprint 2.6f: jp@gc Transactions per Second */}
            {listenerKind === 'kg_apc_transactions_per_second' && (
              <TransactionsPerSecondViewer timeBuckets={state.time_buckets} />
            )}

            {/* Sprint 2.6f: jp@gc Active Threads Over Time */}
            {listenerKind === 'kg_apc_active_threads_over_time' && (
              <ActiveThreadsOverTimeViewer timeBuckets={state.time_buckets} />
            )}

            {/* Sprint 2.6f: Response Time Graph nativo (kind real del frontend: graph_results) */}
            {listenerKind === 'graph_results' && (
              <ResponseTimeGraphViewer timeBuckets={state.time_buckets} />
            )}

            {/* Sprint 2.6g: jp@gc Hits per Second */}
            {listenerKind === 'kg_apc_hits_per_second' && (
              <HitsPerSecondViewer
                timeBuckets={state.time_buckets}
                bucketSizeSec={state.bucket_size_sec}
              />
            )}

            {/* Sprint 2.6g: Backend Listener (caso especial — no usa datos del JTL) */}
            {listenerKind === 'other' && (
              <BackendListenerViewer
                listenerName={listenerName}
                executionStatus={executionStatus}
              />
            )}

            {/* Placeholder defensivo para kinds desconocidos futuros */}
            {![
              'summary_report',
              'aggregate_report',
              'view_results_tree',
              'kg_apc_response_times_over_time',
              'kg_apc_response_codes_per_second',
              'kg_apc_transactions_per_second',
              'kg_apc_active_threads_over_time',
              'graph_results',
              'kg_apc_hits_per_second',
              'other',
            ].includes(listenerKind) && (
              <div className="space-y-3">
                <div className="bg-white border border-gray-200 rounded p-3">
                  <div className="text-xs text-gray-500 mb-2">Resumen</div>
                  <div className="grid grid-cols-3 gap-3 text-sm">
                    <div>
                      <div className="text-xs text-gray-500">Samples</div>
                      <div className="font-semibold">{state.total_samples_parsed}</div>
                    </div>
                    <div>
                      <div className="text-xs text-gray-500">Samplers únicos</div>
                      <div className="font-semibold">{Object.keys(state.per_sampler_stats).length}</div>
                    </div>
                    <div>
                      <div className="text-xs text-gray-500">Buckets de tiempo</div>
                      <div className="font-semibold">{state.time_buckets.length}</div>
                    </div>
                  </div>
                </div>

                <div className="bg-indigo-50 border border-indigo-200 rounded p-4 text-sm text-indigo-900">
                  <p className="font-medium mb-1">Renderer en construcción</p>
                  <p className="text-indigo-700 text-xs">
                    Renderer específico para "{label}" llegará en próximos sub-sprints del Sprint 2.6.
                  </p>
                  <p className="text-indigo-700 text-xs mt-2">
                    kind: <code className="bg-indigo-100 px-1 rounded">{listenerKind}</code>
                  </p>
                </div>
              </div>
            )}
          </>
        )}

        {!loading && !state && (
          <div className="text-center py-12 text-sm text-gray-500">
            No hay datos disponibles todavía.
          </div>
        )}
      </div>
    </div>
  );
}

// ============================================================================
// Sprint 2.6c: Summary Report Viewer
// Tabla simple con métricas por sampler (estilo JMeter Summary Report) + fila TOTAL.
// ============================================================================

interface SummaryReportViewerProps {
  perSamplerStats: Record<string, SamplerStats>;
  totalSamples: number;
}

function SummaryReportViewer({ perSamplerStats, totalSamples }: SummaryReportViewerProps) {
  const samplers = Object.entries(perSamplerStats);

  // Totales globales (avg ponderado por count, min/max globales).
  const totals = useMemo(() => {
    if (samplers.length === 0) {
      return { count: 0, avg: 0, min: 0, max: 0, errors: 0, throughput: 0, kb_per_sec: 0, error_pct: 0 };
    }
    let totalCount = 0;
    let totalErrors = 0;
    let weightedAvgSum = 0;
    let globalMin = Infinity;
    let globalMax = 0;
    let totalThroughput = 0;
    let totalKbRecv = 0;

    for (const [, stats] of samplers) {
      totalCount += stats.count;
      totalErrors += stats.errors;
      weightedAvgSum += stats.avg * stats.count;
      globalMin = Math.min(globalMin, stats.min);
      globalMax = Math.max(globalMax, stats.max);
      totalThroughput += stats.throughput_per_sec;
      totalKbRecv += stats.kb_received_per_sec;
    }

    return {
      count: totalCount,
      avg: totalCount > 0 ? Math.round(weightedAvgSum / totalCount) : 0,
      min: globalMin === Infinity ? 0 : globalMin,
      max: globalMax,
      errors: totalErrors,
      throughput: Math.round(totalThroughput * 100) / 100,
      kb_per_sec: Math.round(totalKbRecv * 100) / 100,
      error_pct: totalCount > 0 ? Math.round((totalErrors / totalCount) * 10000) / 100 : 0,
    };
  }, [samplers]);

  if (samplers.length === 0) {
    return (
      <div className="text-center py-12 text-sm text-gray-500">
        Esperando samples del JTL…
      </div>
    );
  }

  return (
    <div className="bg-white border border-gray-200 rounded-lg overflow-hidden">
      <div className="overflow-x-auto">
        <table className="w-full text-xs">
          <thead className="bg-gray-100 border-b border-gray-200">
            <tr>
              <th className="text-left px-3 py-2 font-semibold text-gray-700">Sampler</th>
              <th className="text-right px-3 py-2 font-semibold text-gray-700">#</th>
              <th className="text-right px-3 py-2 font-semibold text-gray-700">Avg</th>
              <th className="text-right px-3 py-2 font-semibold text-gray-700">Min</th>
              <th className="text-right px-3 py-2 font-semibold text-gray-700">Max</th>
              <th className="text-right px-3 py-2 font-semibold text-gray-700">Err %</th>
              <th className="text-right px-3 py-2 font-semibold text-gray-700">Throughput</th>
              <th className="text-right px-3 py-2 font-semibold text-gray-700">KB/sec</th>
            </tr>
          </thead>
          <tbody className="divide-y divide-gray-100">
            {samplers.map(([label, stats]) => (
              <tr key={label} className="hover:bg-gray-50">
                <td className="px-3 py-2 font-medium text-gray-900">{label}</td>
                <td className="text-right px-3 py-2 font-mono">{stats.count}</td>
                <td className="text-right px-3 py-2 font-mono">{Math.round(stats.avg)}</td>
                <td className="text-right px-3 py-2 font-mono">{stats.min}</td>
                <td className="text-right px-3 py-2 font-mono">{stats.max}</td>
                <td className={`text-right px-3 py-2 font-mono ${stats.error_pct > 0 ? 'text-red-600 font-semibold' : ''}`}>
                  {stats.error_pct.toFixed(2)}%
                </td>
                <td className="text-right px-3 py-2 font-mono">{stats.throughput_per_sec.toFixed(2)}/s</td>
                <td className="text-right px-3 py-2 font-mono">{stats.kb_received_per_sec.toFixed(2)}</td>
              </tr>
            ))}
            {/* Fila TOTAL */}
            <tr className="bg-gray-100 font-semibold border-t-2 border-gray-300">
              <td className="px-3 py-2 text-gray-900">TOTAL</td>
              <td className="text-right px-3 py-2 font-mono">{totals.count}</td>
              <td className="text-right px-3 py-2 font-mono">{totals.avg}</td>
              <td className="text-right px-3 py-2 font-mono">{totals.min}</td>
              <td className="text-right px-3 py-2 font-mono">{totals.max}</td>
              <td className={`text-right px-3 py-2 font-mono ${totals.error_pct > 0 ? 'text-red-600' : ''}`}>
                {totals.error_pct.toFixed(2)}%
              </td>
              <td className="text-right px-3 py-2 font-mono">{totals.throughput.toFixed(2)}/s</td>
              <td className="text-right px-3 py-2 font-mono">{totals.kb_per_sec.toFixed(2)}</td>
            </tr>
          </tbody>
        </table>
      </div>
      <div className="bg-gray-50 px-3 py-2 text-xs text-gray-500 border-t border-gray-200">
        Total samples: <span className="font-semibold text-gray-700">{totalSamples}</span> ·
        Samplers únicos: <span className="font-semibold text-gray-700">{samplers.length}</span>
      </div>
    </div>
  );
}


// ============================================================================
// Sprint 2.6c: Aggregate Report Viewer
// Tabla con métricas completas: percentiles, std dev, KB recibidos/enviados.
// ============================================================================

interface AggregateReportViewerProps {
  perSamplerStats: Record<string, SamplerStats>;
  totalSamples: number;
}

function AggregateReportViewer({ perSamplerStats, totalSamples }: AggregateReportViewerProps) {
  const samplers = Object.entries(perSamplerStats);

  if (samplers.length === 0) {
    return (
      <div className="text-center py-12 text-sm text-gray-500">
        Esperando samples del JTL…
      </div>
    );
  }

  return (
    <div className="bg-white border border-gray-200 rounded-lg overflow-hidden">
      <div className="overflow-x-auto">
        <table className="w-full text-xs">
          <thead className="bg-gray-100 border-b border-gray-200">
            <tr>
              <th className="text-left px-3 py-2 font-semibold text-gray-700">Sampler</th>
              <th className="text-right px-3 py-2 font-semibold text-gray-700">#</th>
              <th className="text-right px-3 py-2 font-semibold text-gray-700">Avg</th>
              <th className="text-right px-3 py-2 font-semibold text-gray-700">Median</th>
              <th className="text-right px-3 py-2 font-semibold text-gray-700">90%</th>
              <th className="text-right px-3 py-2 font-semibold text-gray-700">95%</th>
              <th className="text-right px-3 py-2 font-semibold text-gray-700">99%</th>
              <th className="text-right px-3 py-2 font-semibold text-gray-700">Min</th>
              <th className="text-right px-3 py-2 font-semibold text-gray-700">Max</th>
              <th className="text-right px-3 py-2 font-semibold text-gray-700">Std Dev</th>
              <th className="text-right px-3 py-2 font-semibold text-gray-700">Err %</th>
              <th className="text-right px-3 py-2 font-semibold text-gray-700">TPS</th>
              <th className="text-right px-3 py-2 font-semibold text-gray-700">KB recv/s</th>
              <th className="text-right px-3 py-2 font-semibold text-gray-700">KB sent/s</th>
            </tr>
          </thead>
          <tbody className="divide-y divide-gray-100">
            {samplers.map(([label, stats]) => (
              <tr key={label} className="hover:bg-gray-50">
                <td className="px-3 py-2 font-medium text-gray-900 whitespace-nowrap">{label}</td>
                <td className="text-right px-3 py-2 font-mono">{stats.count}</td>
                <td className="text-right px-3 py-2 font-mono">{Math.round(stats.avg)}</td>
                <td className="text-right px-3 py-2 font-mono">{stats.median}</td>
                <td className="text-right px-3 py-2 font-mono">{stats.p90}</td>
                <td className="text-right px-3 py-2 font-mono font-semibold">{stats.p95}</td>
                <td className="text-right px-3 py-2 font-mono">{stats.p99}</td>
                <td className="text-right px-3 py-2 font-mono">{stats.min}</td>
                <td className="text-right px-3 py-2 font-mono">{stats.max}</td>
                <td className="text-right px-3 py-2 font-mono">{stats.std_dev.toFixed(2)}</td>
                <td className={`text-right px-3 py-2 font-mono ${stats.error_pct > 0 ? 'text-red-600 font-semibold' : ''}`}>
                  {stats.error_pct.toFixed(2)}%
                </td>
                <td className="text-right px-3 py-2 font-mono">{stats.throughput_per_sec.toFixed(2)}</td>
                <td className="text-right px-3 py-2 font-mono">{stats.kb_received_per_sec.toFixed(2)}</td>
                <td className="text-right px-3 py-2 font-mono">{stats.kb_sent_per_sec.toFixed(2)}</td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
      <div className="bg-gray-50 px-3 py-2 text-xs text-gray-500 border-t border-gray-200">
        Total samples: <span className="font-semibold text-gray-700">{totalSamples}</span> ·
        Samplers únicos: <span className="font-semibold text-gray-700">{samplers.length}</span>
      </div>
    </div>
  );
}


// ============================================================================
// Sprint 2.6d: View Results Tree Viewer
// Lista cronológica de samples (samples_tail) con detalle por sample seleccionado.
// ============================================================================

interface ViewResultsTreeViewerProps {
  samplesTail: Array<Record<string, string>>;
  totalSamplesParsed: number;
}

function ViewResultsTreeViewer({ samplesTail, totalSamplesParsed }: ViewResultsTreeViewerProps) {
  const [selectedIdx, setSelectedIdx] = useState<number | null>(null);
  const [filterErrors, setFilterErrors] = useState(false);
  const [filterLabel, setFilterLabel] = useState<string>('');
  const [searchText, setSearchText] = useState('');

  // Filtrado (orden cronológico inverso: más reciente primero).
  const filteredSamples = useMemo(() => {
    let items = [...samplesTail];

    if (filterErrors) {
      items = items.filter((s) => (s.success || '').toLowerCase() !== 'true');
    }

    if (filterLabel) {
      items = items.filter((s) => s.label === filterLabel);
    }

    if (searchText.trim()) {
      const q = searchText.toLowerCase();
      items = items.filter((s) => {
        return (
          (s.label || '').toLowerCase().includes(q) ||
          (s.responseMessage || '').toLowerCase().includes(q) ||
          (s.URL || '').toLowerCase().includes(q) ||
          (s.responseCode || '').toLowerCase().includes(q)
        );
      });
    }

    return items.reverse();
  }, [samplesTail, filterErrors, filterLabel, searchText]);

  // Labels únicos para el dropdown de filtro.
  const uniqueLabels = useMemo(() => {
    const set = new Set<string>();
    for (const s of samplesTail) {
      if (s.label) set.add(s.label);
    }
    return Array.from(set).sort();
  }, [samplesTail]);

  const selectedSample = selectedIdx !== null ? filteredSamples[selectedIdx] : null;

  // Formatea timestamp epoch ms a hora local legible.
  const formatTimestamp = (tsStr: string): string => {
    try {
      const ts = parseInt(tsStr, 10);
      if (isNaN(ts)) return tsStr;
      const d = new Date(ts);
      return d.toLocaleTimeString('es-CO', {
        hour: '2-digit',
        minute: '2-digit',
        second: '2-digit',
        fractionalSecondDigits: 3,
      } as Intl.DateTimeFormatOptions);
    } catch {
      return tsStr;
    }
  };

  // Badge color según código HTTP.
  const codeBadgeClass = (code: string): string => {
    if (!code) return 'bg-gray-100 text-gray-700';
    if (code.startsWith('2')) return 'bg-emerald-100 text-emerald-700';
    if (code.startsWith('3')) return 'bg-blue-100 text-blue-700';
    if (code.startsWith('4')) return 'bg-amber-100 text-amber-700';
    return 'bg-red-100 text-red-700';
  };

  if (samplesTail.length === 0) {
    return (
      <div className="text-center py-12 text-sm text-gray-500">
        Esperando samples del JTL…
      </div>
    );
  }

  return (
    <div className="flex flex-col h-full bg-white border border-gray-200 rounded-lg overflow-hidden">
      {/* Filtros */}
      <div className="bg-gray-50 border-b border-gray-200 px-3 py-2 flex flex-wrap items-center gap-2">
        <label className="flex items-center gap-1 text-xs cursor-pointer">
          <input
            type="checkbox"
            checked={filterErrors}
            onChange={(e) => {
              setFilterErrors(e.target.checked);
              setSelectedIdx(null);
            }}
            className="rounded"
          />
          <span>Solo errores</span>
        </label>

        <select
          value={filterLabel}
          onChange={(e) => {
            setFilterLabel(e.target.value);
            setSelectedIdx(null);
          }}
          className="text-xs px-2 py-1 border border-gray-300 rounded"
        >
          <option value="">Todos los samplers</option>
          {uniqueLabels.map((l) => (
            <option key={l} value={l}>{l}</option>
          ))}
        </select>

        <input
          type="text"
          value={searchText}
          onChange={(e) => {
            setSearchText(e.target.value);
            setSelectedIdx(null);
          }}
          placeholder="Buscar en label / código / URL…"
          className="text-xs px-2 py-1 border border-gray-300 rounded flex-1 min-w-[200px]"
        />

        <div className="text-xs text-gray-500 ml-auto">
          {filteredSamples.length} / {samplesTail.length} mostrados (cap 100)
          {totalSamplesParsed > samplesTail.length && (
            <span className="ml-1 text-gray-400">· {totalSamplesParsed} total</span>
          )}
        </div>
      </div>

      {/* Cuerpo: lista a la izquierda + detalle a la derecha */}
      <div className="flex-1 flex overflow-hidden min-h-[300px]">
        {/* Lista de samples */}
        <div className="w-[420px] border-r border-gray-200 overflow-y-auto bg-gray-50">
          {filteredSamples.length === 0 ? (
            <div className="text-center py-8 text-xs text-gray-500">
              No hay samples que coincidan con el filtro.
            </div>
          ) : (
            <ul className="divide-y divide-gray-100">
              {filteredSamples.map((s, idx) => {
                const isSuccess = (s.success || '').toLowerCase() === 'true';
                const isSelected = selectedIdx === idx;
                return (
                  <li key={idx}>
                    <button
                      onClick={() => setSelectedIdx(idx)}
                      className={`w-full text-left px-3 py-2 text-xs hover:bg-white transition-colors ${isSelected ? 'bg-white border-l-2 border-l-indigo-500' : ''}`}
                    >
                      <div className="flex items-center gap-2">
                        {isSuccess ? (
                          <CheckCircle2 className="w-3.5 h-3.5 text-emerald-500 flex-shrink-0" />
                        ) : (
                          <XCircle className="w-3.5 h-3.5 text-red-500 flex-shrink-0" />
                        )}
                        <span className="font-medium text-gray-900 truncate">{s.label || '—'}</span>
                      </div>
                      <div className="flex items-center gap-2 mt-1 ml-5">
                        <code className={`text-xs px-1.5 py-0.5 rounded ${codeBadgeClass(s.responseCode || '')}`}>
                          {s.responseCode || '—'}
                        </code>
                        <span className="text-gray-500 font-mono">{s.elapsed || 0}ms</span>
                        <span className="text-gray-400 text-xs ml-auto">{formatTimestamp(s.timeStamp || '')}</span>
                      </div>
                    </button>
                  </li>
                );
              })}
            </ul>
          )}
        </div>

        {/* Panel de detalle del sample seleccionado */}
        <div className="flex-1 overflow-y-auto bg-white">
          {!selectedSample ? (
            <div className="flex items-center justify-center h-full text-sm text-gray-400">
              Selecciona un sample para ver el detalle
            </div>
          ) : (
            <div className="p-4">
              <SampleDetailView sample={selectedSample} />
            </div>
          )}
        </div>
      </div>
    </div>
  );
}


// ============================================================================
// Sprint 2.6d: Detalle de un sample individual (tabs Resultado / Request / Response Data).
// ============================================================================

interface SampleDetailViewProps {
  sample: Record<string, string>;
}

function SampleDetailView({ sample }: SampleDetailViewProps) {
  const [activeTab, setActiveTab] = useState<'result' | 'request' | 'response_data'>('result');

  const isSuccess = (sample.success || '').toLowerCase() === 'true';

  return (
    <div className="space-y-3">
      {/* Header con estado */}
      <div className="flex items-center gap-2 pb-2 border-b border-gray-200">
        {isSuccess ? (
          <CheckCircle2 className="w-5 h-5 text-emerald-500" />
        ) : (
          <XCircle className="w-5 h-5 text-red-500" />
        )}
        <h3 className="font-semibold text-gray-900">{sample.label || '—'}</h3>
      </div>

      {/* Tabs */}
      <div className="flex gap-1 border-b border-gray-200">
        {(['result', 'request', 'response_data'] as const).map((tab) => (
          <button
            key={tab}
            onClick={() => setActiveTab(tab)}
            className={`px-3 py-1.5 text-xs font-medium transition-colors ${
              activeTab === tab
                ? 'border-b-2 border-indigo-500 text-indigo-700'
                : 'text-gray-600 hover:text-gray-900'
            }`}
          >
            {tab === 'result' && 'Resultado'}
            {tab === 'request' && 'Request'}
            {tab === 'response_data' && 'Response Data'}
          </button>
        ))}
      </div>

      {/* Contenido de tabs */}
      <div>
        {activeTab === 'result' && (
          <dl className="grid grid-cols-2 gap-x-4 gap-y-2 text-xs">
            <div>
              <dt className="text-gray-500">Estado</dt>
              <dd className={`font-mono font-semibold ${isSuccess ? 'text-emerald-700' : 'text-red-700'}`}>
                {isSuccess ? 'SUCCESS' : 'FAIL'}
              </dd>
            </div>
            <div>
              <dt className="text-gray-500">Código HTTP</dt>
              <dd className="font-mono">{sample.responseCode || '—'}</dd>
            </div>
            <div>
              <dt className="text-gray-500">Mensaje</dt>
              <dd className="font-mono">{sample.responseMessage || '—'}</dd>
            </div>
            <div>
              <dt className="text-gray-500">Response time</dt>
              <dd className="font-mono">{sample.elapsed || 0} ms</dd>
            </div>
            <div>
              <dt className="text-gray-500">Latency</dt>
              <dd className="font-mono">{sample.Latency || 0} ms</dd>
            </div>
            <div>
              <dt className="text-gray-500">Connect time</dt>
              <dd className="font-mono">{sample.Connect || 0} ms</dd>
            </div>
            <div>
              <dt className="text-gray-500">Bytes recibidos</dt>
              <dd className="font-mono">{sample.bytes || 0}</dd>
            </div>
            <div>
              <dt className="text-gray-500">Bytes enviados</dt>
              <dd className="font-mono">{sample.sentBytes || 0}</dd>
            </div>
            {sample.failureMessage && (
              <div className="col-span-2 mt-2 bg-red-50 border border-red-200 rounded p-2">
                <dt className="text-red-700 text-xs font-semibold mb-1">Failure message</dt>
                <dd className="text-red-900 text-xs font-mono whitespace-pre-wrap">{sample.failureMessage}</dd>
              </div>
            )}
          </dl>
        )}

        {activeTab === 'request' && (
          <dl className="grid grid-cols-2 gap-x-4 gap-y-2 text-xs">
            <div className="col-span-2">
              <dt className="text-gray-500">URL</dt>
              <dd className="font-mono text-xs break-all">{sample.URL || sample.url || '—'}</dd>
            </div>
            <div>
              <dt className="text-gray-500">Thread</dt>
              <dd className="font-mono">{sample.threadName || '—'}</dd>
            </div>
            <div>
              <dt className="text-gray-500">Timestamp</dt>
              <dd className="font-mono">{sample.timeStamp || '—'}</dd>
            </div>
            <div>
              <dt className="text-gray-500">Group threads</dt>
              <dd className="font-mono">{sample.grpThreads || '—'}</dd>
            </div>
            <div>
              <dt className="text-gray-500">All threads</dt>
              <dd className="font-mono">{sample.allThreads || '—'}</dd>
            </div>
            <div>
              <dt className="text-gray-500">DataType</dt>
              <dd className="font-mono">{sample.dataType || '—'}</dd>
            </div>
            <div>
              <dt className="text-gray-500">IdleTime</dt>
              <dd className="font-mono">{sample.IdleTime || 0} ms</dd>
            </div>
          </dl>
        )}

        {activeTab === 'response_data' && (
          <div className="bg-amber-50 border border-amber-200 rounded p-3 text-xs text-amber-800">
            <p className="font-medium mb-1">Response Data no disponible</p>
            <p>
              Por defecto JMeter NO guarda el body de la respuesta en el JTL.
              Para verlo desde Kinetix, habilita <code className="bg-amber-100 px-1 rounded">saveResponseData</code> en
              el Result Collector del listener "View Results Tree (con CSV)".
            </p>
            <p className="mt-2 text-xs text-amber-700">
              Alternativa: descarga el JMX, ábrelo en JMeter desktop y ejecuta con
              View Results Tree en GUI para ver request/response completos.
            </p>
          </div>
        )}
      </div>
    </div>
  );
}


// ============================================================================
// Sprint 2.6e: Helpers de transformación de time_buckets a series Recharts.
// ============================================================================

// time_buckets → puntos { time, [sampler]: avg_ms, ... } para LineChart.
function bucketsToResponseTimeSeries(buckets: TimeBucket[]): Array<Record<string, number>> {
  return buckets.map((b) => {
    const point: Record<string, number> = { time: b.bucket_start_sec };
    for (const [label, stats] of Object.entries(b.per_sampler)) {
      point[label] = stats.avg_response_ms;
    }
    return point;
  });
}

// time_buckets → puntos { time, "200": count, "500": count, ... } para AreaChart.
function bucketsToCodesPerSecondSeries(buckets: TimeBucket[]): Array<Record<string, number>> {
  return buckets.map((b) => {
    const point: Record<string, number> = { time: b.bucket_start_sec };
    for (const [code, count] of Object.entries(b.totals.codes)) {
      point[code] = count;
    }
    return point;
  });
}

// Lista única de samplers presentes en todos los buckets.
function uniqueSamplersFromBuckets(buckets: TimeBucket[]): string[] {
  const set = new Set<string>();
  for (const b of buckets) {
    for (const label of Object.keys(b.per_sampler)) {
      set.add(label);
    }
  }
  return Array.from(set).sort();
}

// Lista única de códigos HTTP (orden lógico 2xx → 3xx → 4xx → 5xx).
function uniqueCodesFromBuckets(buckets: TimeBucket[]): string[] {
  const set = new Set<string>();
  for (const b of buckets) {
    for (const code of Object.keys(b.totals.codes)) {
      set.add(code);
    }
  }
  return Array.from(set).sort((a, b) => a.charAt(0).localeCompare(b.charAt(0)));
}

// Paleta cíclica para líneas por sampler.
const CHART_COLORS = [
  '#4f46e5', // indigo
  '#10b981', // emerald
  '#f59e0b', // amber
  '#ef4444', // red
  '#3b82f6', // blue
  '#8b5cf6', // violet
  '#ec4899', // pink
  '#14b8a6', // teal
  '#f97316', // orange
  '#6366f1', // indigo-500
];

// Color por familia de código HTTP.
function colorForCode(code: string): string {
  if (code.startsWith('2')) return '#10b981'; // emerald
  if (code.startsWith('3')) return '#3b82f6'; // blue
  if (code.startsWith('4')) return '#f59e0b'; // amber
  if (code.startsWith('5')) return '#ef4444'; // red
  return '#6b7280'; // gray
}


// ============================================================================
// Sprint 2.6e: jp@gc - Response Times Over Time (línea por sampler).
// ============================================================================

interface ResponseTimesOverTimeViewerProps {
  timeBuckets: TimeBucket[];
}

function ResponseTimesOverTimeViewer({ timeBuckets }: ResponseTimesOverTimeViewerProps) {
  const series = useMemo(() => bucketsToResponseTimeSeries(timeBuckets), [timeBuckets]);
  const samplers = useMemo(() => uniqueSamplersFromBuckets(timeBuckets), [timeBuckets]);

  if (timeBuckets.length === 0) {
    return (
      <div className="text-center py-12 text-sm text-gray-500">
        Esperando datos para graficar…
      </div>
    );
  }

  return (
    <div className="bg-white border border-gray-200 rounded-lg p-3">
      <div className="mb-3">
        <h4 className="text-sm font-semibold text-gray-900">Response Times Over Time</h4>
        <p className="text-xs text-gray-500">Tiempo de respuesta promedio por sampler (ms) vs tiempo (s)</p>
      </div>

      <div style={{ width: '100%', height: 380 }}>
        <ResponsiveContainer>
          <LineChart data={series} margin={{ top: 10, right: 20, left: 10, bottom: 30 }}>
            <CartesianGrid strokeDasharray="3 3" stroke="#e5e7eb" />
            <XAxis
              dataKey="time"
              type="number"
              domain={['dataMin', 'dataMax']}
              tick={{ fontSize: 11 }}
              label={{ value: 'Tiempo (s)', position: 'insideBottom', offset: -15, style: { fontSize: 11 } }}
            />
            <YAxis
              tick={{ fontSize: 11 }}
              label={{ value: 'Response time (ms)', angle: -90, position: 'insideLeft', style: { fontSize: 11 } }}
            />
            <Tooltip
              contentStyle={{ fontSize: 11, padding: '6px 10px' }}
              labelFormatter={(label) => `t = ${label}s`}
              formatter={(value: number, name: string) => [`${value} ms`, name]}
            />
            <Legend wrapperStyle={{ fontSize: 11 }} />
            {samplers.map((sampler, idx) => (
              <Line
                key={sampler}
                type="monotone"
                dataKey={sampler}
                stroke={CHART_COLORS[idx % CHART_COLORS.length]}
                strokeWidth={2}
                dot={false}
                isAnimationActive={false}
                connectNulls={false}
              />
            ))}
          </LineChart>
        </ResponsiveContainer>
      </div>

      <div className="mt-2 text-xs text-gray-500">
        Buckets: {timeBuckets.length} · Samplers: {samplers.length}
      </div>
    </div>
  );
}


// ============================================================================
// Sprint 2.6e: jp@gc - Response Codes per Second (área apilada por código HTTP).
// ============================================================================

interface ResponseCodesPerSecondViewerProps {
  timeBuckets: TimeBucket[];
}

function ResponseCodesPerSecondViewer({ timeBuckets }: ResponseCodesPerSecondViewerProps) {
  const series = useMemo(() => bucketsToCodesPerSecondSeries(timeBuckets), [timeBuckets]);
  const codes = useMemo(() => uniqueCodesFromBuckets(timeBuckets), [timeBuckets]);

  if (timeBuckets.length === 0) {
    return (
      <div className="text-center py-12 text-sm text-gray-500">
        Esperando datos para graficar…
      </div>
    );
  }

  return (
    <div className="bg-white border border-gray-200 rounded-lg p-3">
      <div className="mb-3">
        <h4 className="text-sm font-semibold text-gray-900">Response Codes per Second</h4>
        <p className="text-xs text-gray-500">Códigos HTTP por intervalo (apilados) vs tiempo (s)</p>
      </div>

      <div style={{ width: '100%', height: 380 }}>
        <ResponsiveContainer>
          <AreaChart data={series} margin={{ top: 10, right: 20, left: 10, bottom: 30 }}>
            <CartesianGrid strokeDasharray="3 3" stroke="#e5e7eb" />
            <XAxis
              dataKey="time"
              type="number"
              domain={['dataMin', 'dataMax']}
              tick={{ fontSize: 11 }}
              label={{ value: 'Tiempo (s)', position: 'insideBottom', offset: -15, style: { fontSize: 11 } }}
            />
            <YAxis
              tick={{ fontSize: 11 }}
              label={{ value: 'Samples / intervalo', angle: -90, position: 'insideLeft', style: { fontSize: 11 } }}
            />
            <Tooltip
              contentStyle={{ fontSize: 11, padding: '6px 10px' }}
              labelFormatter={(label) => `t = ${label}s`}
              formatter={(value: number, name: string) => [value, `Código ${name}`]}
            />
            <Legend wrapperStyle={{ fontSize: 11 }} />
            {codes.map((code) => (
              <Area
                key={code}
                type="monotone"
                dataKey={code}
                stackId="1"
                stroke={colorForCode(code)}
                fill={colorForCode(code)}
                fillOpacity={0.6}
                isAnimationActive={false}
              />
            ))}
          </AreaChart>
        </ResponsiveContainer>
      </div>

      <div className="mt-2 text-xs text-gray-500">
        Buckets: {timeBuckets.length} · Códigos detectados: {codes.join(', ') || '—'}
      </div>
    </div>
  );
}


// ============================================================================
// Sprint 2.6f: Helpers de transformación adicionales (reusan tipos de 2.6e).
// ============================================================================

// time_buckets → serie TPS por sampler + total (clave reservada '__total__').
function bucketsToTpsSeries(buckets: TimeBucket[]): Array<Record<string, number>> {
  return buckets.map((b) => {
    const point: Record<string, number> = { time: b.bucket_start_sec };
    for (const [label, stats] of Object.entries(b.per_sampler)) {
      point[label] = stats.throughput;
    }
    point['__total__'] = b.totals.throughput;
    return point;
  });
}

// time_buckets → serie de usuarios virtuales activos (pico) en el tiempo.
function bucketsToActiveThreadsSeries(buckets: TimeBucket[]): Array<{ time: number; activeThreads: number }> {
  return buckets.map((b) => ({
    time: b.bucket_start_sec,
    activeThreads: b.totals.active_threads_max,
  }));
}


// ============================================================================
// Sprint 2.6f: jp@gc - Transactions per Second (total destacado + líneas por sampler).
// ============================================================================

interface TransactionsPerSecondViewerProps {
  timeBuckets: TimeBucket[];
}

function TransactionsPerSecondViewer({ timeBuckets }: TransactionsPerSecondViewerProps) {
  const series = useMemo(() => bucketsToTpsSeries(timeBuckets), [timeBuckets]);
  const samplers = useMemo(() => uniqueSamplersFromBuckets(timeBuckets), [timeBuckets]);

  if (timeBuckets.length === 0) {
    return (
      <div className="text-center py-12 text-sm text-gray-500">
        Esperando datos para graficar…
      </div>
    );
  }

  return (
    <div className="bg-white border border-gray-200 rounded-lg p-3">
      <div className="mb-3">
        <h4 className="text-sm font-semibold text-gray-900">Transactions per Second</h4>
        <p className="text-xs text-gray-500">Transacciones por segundo por sampler vs tiempo (s)</p>
      </div>

      <div style={{ width: '100%', height: 380 }}>
        <ResponsiveContainer>
          <LineChart data={series} margin={{ top: 10, right: 20, left: 10, bottom: 30 }}>
            <CartesianGrid strokeDasharray="3 3" stroke="#e5e7eb" />
            <XAxis
              dataKey="time"
              type="number"
              domain={['dataMin', 'dataMax']}
              tick={{ fontSize: 11 }}
              label={{ value: 'Tiempo (s)', position: 'insideBottom', offset: -15, style: { fontSize: 11 } }}
            />
            <YAxis
              tick={{ fontSize: 11 }}
              label={{ value: 'TPS', angle: -90, position: 'insideLeft', style: { fontSize: 11 } }}
            />
            <Tooltip
              contentStyle={{ fontSize: 11, padding: '6px 10px' }}
              labelFormatter={(label) => `t = ${label}s`}
              formatter={(value: number, name: string) => {
                if (name === '__total__') return [`${value.toFixed(2)} tps`, 'Total'];
                return [`${value.toFixed(2)} tps`, name];
              }}
            />
            <Legend
              wrapperStyle={{ fontSize: 11 }}
              formatter={(value) => (value === '__total__' ? 'Total' : value)}
            />
            {/* Línea total destacada */}
            <Line
              type="monotone"
              dataKey="__total__"
              stroke="#1f2937"
              strokeWidth={3}
              dot={false}
              isAnimationActive={false}
              name="__total__"
            />
            {samplers.map((sampler, idx) => (
              <Line
                key={sampler}
                type="monotone"
                dataKey={sampler}
                stroke={CHART_COLORS[idx % CHART_COLORS.length]}
                strokeWidth={1.5}
                strokeDasharray="3 3"
                dot={false}
                isAnimationActive={false}
              />
            ))}
          </LineChart>
        </ResponsiveContainer>
      </div>

      <div className="mt-2 text-xs text-gray-500">
        La línea negra gruesa es el TPS total. Las líneas punteadas son por sampler.
      </div>
    </div>
  );
}


// ============================================================================
// Sprint 2.6f: jp@gc - Active Threads Over Time (usuarios concurrentes).
// ============================================================================

interface ActiveThreadsOverTimeViewerProps {
  timeBuckets: TimeBucket[];
}

function ActiveThreadsOverTimeViewer({ timeBuckets }: ActiveThreadsOverTimeViewerProps) {
  const series = useMemo(() => bucketsToActiveThreadsSeries(timeBuckets), [timeBuckets]);

  if (timeBuckets.length === 0) {
    return (
      <div className="text-center py-12 text-sm text-gray-500">
        Esperando datos para graficar…
      </div>
    );
  }

  const maxThreads = series.reduce((acc, p) => Math.max(acc, p.activeThreads), 0);

  return (
    <div className="bg-white border border-gray-200 rounded-lg p-3">
      <div className="mb-3">
        <h4 className="text-sm font-semibold text-gray-900">Active Threads Over Time</h4>
        <p className="text-xs text-gray-500">Usuarios virtuales activos vs tiempo (s)</p>
      </div>

      <div style={{ width: '100%', height: 380 }}>
        <ResponsiveContainer>
          <AreaChart data={series} margin={{ top: 10, right: 20, left: 10, bottom: 30 }}>
            <CartesianGrid strokeDasharray="3 3" stroke="#e5e7eb" />
            <XAxis
              dataKey="time"
              type="number"
              domain={['dataMin', 'dataMax']}
              tick={{ fontSize: 11 }}
              label={{ value: 'Tiempo (s)', position: 'insideBottom', offset: -15, style: { fontSize: 11 } }}
            />
            <YAxis
              tick={{ fontSize: 11 }}
              label={{ value: 'Usuarios activos', angle: -90, position: 'insideLeft', style: { fontSize: 11 } }}
              allowDecimals={false}
            />
            <Tooltip
              contentStyle={{ fontSize: 11, padding: '6px 10px' }}
              labelFormatter={(label) => `t = ${label}s`}
              formatter={(value: number) => [`${value} usuarios`, 'Activos']}
            />
            <Area
              type="stepAfter"
              dataKey="activeThreads"
              stroke="#8b5cf6"
              fill="#8b5cf6"
              fillOpacity={0.3}
              strokeWidth={2}
              isAnimationActive={false}
            />
          </AreaChart>
        </ResponsiveContainer>
      </div>

      <div className="mt-2 text-xs text-gray-500">
        Pico máximo: <span className="font-semibold text-gray-700">{maxThreads}</span> usuarios concurrentes
      </div>
    </div>
  );
}


// ============================================================================
// Sprint 2.6f: Response Time Graph (nativo de JMeter).
// Equivalente al jp@gc Response Times pero sin línea por sampler: solo el
// response time avg total. Kind real del frontend: 'graph_results'.
// ============================================================================

interface ResponseTimeGraphViewerProps {
  timeBuckets: TimeBucket[];
}

function ResponseTimeGraphViewer({ timeBuckets }: ResponseTimeGraphViewerProps) {
  const series = useMemo(() => {
    return timeBuckets.map((b) => ({
      time: b.bucket_start_sec,
      avg: b.totals.avg_response_ms,
    }));
  }, [timeBuckets]);

  if (timeBuckets.length === 0) {
    return (
      <div className="text-center py-12 text-sm text-gray-500">
        Esperando datos para graficar…
      </div>
    );
  }

  return (
    <div className="bg-white border border-gray-200 rounded-lg p-3">
      <div className="mb-3">
        <h4 className="text-sm font-semibold text-gray-900">Response Time Graph</h4>
        <p className="text-xs text-gray-500">Response time promedio total vs tiempo (s) — listener nativo JMeter</p>
      </div>

      <div style={{ width: '100%', height: 380 }}>
        <ResponsiveContainer>
          <LineChart data={series} margin={{ top: 10, right: 20, left: 10, bottom: 30 }}>
            <CartesianGrid strokeDasharray="3 3" stroke="#e5e7eb" />
            <XAxis
              dataKey="time"
              type="number"
              domain={['dataMin', 'dataMax']}
              tick={{ fontSize: 11 }}
              label={{ value: 'Tiempo (s)', position: 'insideBottom', offset: -15, style: { fontSize: 11 } }}
            />
            <YAxis
              tick={{ fontSize: 11 }}
              label={{ value: 'Response time (ms)', angle: -90, position: 'insideLeft', style: { fontSize: 11 } }}
            />
            <Tooltip
              contentStyle={{ fontSize: 11, padding: '6px 10px' }}
              labelFormatter={(label) => `t = ${label}s`}
              formatter={(value: number) => [`${value} ms`, 'Promedio']}
            />
            <Line
              type="monotone"
              dataKey="avg"
              stroke="#4f46e5"
              strokeWidth={2.5}
              dot={false}
              isAnimationActive={false}
            />
          </LineChart>
        </ResponsiveContainer>
      </div>

      <div className="mt-2 text-xs text-gray-500">
        Para ver por sampler individual, usa el listener jp@gc Response Times Over Time.
      </div>
    </div>
  );
}


// ============================================================================
// Sprint 2.6g: jp@gc - Hits per Second (hits totales por segundo).
// ============================================================================

interface HitsPerSecondViewerProps {
  timeBuckets: TimeBucket[];
  bucketSizeSec: number;
}

function HitsPerSecondViewer({ timeBuckets, bucketSizeSec }: HitsPerSecondViewerProps) {
  const series = useMemo(() => {
    return timeBuckets.map((b) => ({
      time: b.bucket_start_sec,
      // hits/sec = count del bucket / tamaño del bucket en segundos.
      hitsPerSec: bucketSizeSec > 0 ? Math.round((b.totals.count / bucketSizeSec) * 100) / 100 : 0,
    }));
  }, [timeBuckets, bucketSizeSec]);

  if (timeBuckets.length === 0) {
    return (
      <div className="text-center py-12 text-sm text-gray-500">
        Esperando datos para graficar…
      </div>
    );
  }

  return (
    <div className="bg-white border border-gray-200 rounded-lg p-3">
      <div className="mb-3">
        <h4 className="text-sm font-semibold text-gray-900">Hits per Second</h4>
        <p className="text-xs text-gray-500">Total de hits por segundo vs tiempo (s)</p>
      </div>

      <div style={{ width: '100%', height: 380 }}>
        <ResponsiveContainer>
          <LineChart data={series} margin={{ top: 10, right: 20, left: 10, bottom: 30 }}>
            <CartesianGrid strokeDasharray="3 3" stroke="#e5e7eb" />
            <XAxis
              dataKey="time"
              type="number"
              domain={['dataMin', 'dataMax']}
              tick={{ fontSize: 11 }}
              label={{ value: 'Tiempo (s)', position: 'insideBottom', offset: -15, style: { fontSize: 11 } }}
            />
            <YAxis
              tick={{ fontSize: 11 }}
              label={{ value: 'Hits/sec', angle: -90, position: 'insideLeft', style: { fontSize: 11 } }}
            />
            <Tooltip
              contentStyle={{ fontSize: 11, padding: '6px 10px' }}
              labelFormatter={(label) => `t = ${label}s`}
              formatter={(value: number) => [`${value} hits/s`, 'Hits']}
            />
            <Line
              type="monotone"
              dataKey="hitsPerSec"
              stroke="#10b981"
              strokeWidth={2.5}
              dot={false}
              isAnimationActive={false}
            />
          </LineChart>
        </ResponsiveContainer>
      </div>
    </div>
  );
}


// ============================================================================
// Sprint 2.6g: Backend Listener Viewer (CASO ESPECIAL).
// No muestra datos del JTL — muestra configuración del listener y guía sobre
// cómo ver las métricas en Grafana.
// ============================================================================

interface BackendListenerViewerProps {
  listenerName: string | null;
  executionStatus: string;
}

function BackendListenerViewer({ listenerName, executionStatus }: BackendListenerViewerProps) {
  const isRunning = executionStatus === 'running';

  return (
    <div className="bg-white border border-gray-200 rounded-lg p-5">
      <div className="flex items-start gap-3 mb-4">
        <div className="bg-orange-100 rounded-lg p-2">
          <Zap className="w-5 h-5 text-orange-600" />
        </div>
        <div>
          <h3 className="font-semibold text-gray-900">Backend Listener</h3>
          <p className="text-xs text-gray-500 mt-0.5">{listenerName || 'InfluxDB'}</p>
        </div>
      </div>

      <div className="space-y-3">
        {/* Estado actual */}
        <div className={`rounded-lg p-3 border ${isRunning ? 'bg-emerald-50 border-emerald-200' : 'bg-gray-50 border-gray-200'}`}>
          <div className="flex items-center gap-2 mb-1">
            {isRunning ? (
              <>
                <Loader2 className="w-4 h-4 text-emerald-600 animate-spin" />
                <span className="text-sm font-medium text-emerald-900">Enviando métricas a InfluxDB</span>
              </>
            ) : (
              <>
                <CheckCircle2 className="w-4 h-4 text-gray-500" />
                <span className="text-sm font-medium text-gray-700">Sesión finalizada</span>
              </>
            )}
          </div>
          <p className="text-xs text-gray-600">
            {isRunning
              ? 'JMeter está publicando métricas en tiempo real al stack InfluxDB de Kinetix.'
              : 'Las métricas históricas siguen disponibles en InfluxDB.'}
          </p>
        </div>

        {/* Configuración */}
        <div className="bg-blue-50 border border-blue-200 rounded-lg p-3">
          <h4 className="text-sm font-semibold text-blue-900 mb-2">Configuración del listener</h4>
          <dl className="text-xs space-y-1.5 text-blue-800">
            <div className="flex gap-2">
              <dt className="font-medium w-32 flex-shrink-0">URL InfluxDB:</dt>
              <dd className="font-mono bg-blue-100 px-1.5 py-0.5 rounded text-xs">
                http://influxdb:8086/api/v2/write?org=performance&amp;bucket=jmeter
              </dd>
            </div>
            <div className="flex gap-2">
              <dt className="font-medium w-32 flex-shrink-0">Bucket:</dt>
              <dd className="font-mono">jmeter</dd>
            </div>
            <div className="flex gap-2">
              <dt className="font-medium w-32 flex-shrink-0">Implementación:</dt>
              <dd className="font-mono text-xs">InfluxdbBackendListenerClient</dd>
            </div>
            <div className="flex gap-2">
              <dt className="font-medium w-32 flex-shrink-0">Percentiles:</dt>
              <dd className="font-mono">90, 95, 99</dd>
            </div>
          </dl>
        </div>

        {/* Cómo ver gráficas */}
        <div className="bg-amber-50 border border-amber-200 rounded-lg p-3">
          <h4 className="text-sm font-semibold text-amber-900 mb-2">Cómo ver las gráficas</h4>
          <p className="text-xs text-amber-800 mb-2">
            El Backend Listener envía métricas detalladas a InfluxDB, que son consumidas
            por Grafana. Para visualizar las gráficas profesionales:
          </p>
          <ol className="list-decimal list-inside text-xs text-amber-800 space-y-1 ml-2">
            <li>Verifica que tu stack Grafana esté configurado con un dashboard JMeter</li>
            <li>Accede a Grafana (típicamente <code className="bg-amber-100 px-1 rounded">http://localhost:3000</code>)</li>
            <li>Busca el dashboard "JMeter" o similar</li>
          </ol>
          <p className="text-xs text-amber-700 mt-2 italic">
            Nota: el provisionamiento automático de dashboard Grafana queda pendiente
            para sprints futuros del proyecto.
          </p>
        </div>

        {/* Renderers alternativos */}
        <div className="bg-indigo-50 border border-indigo-200 rounded-lg p-3">
          <h4 className="text-sm font-semibold text-indigo-900 mb-2">Mientras tanto, dentro de Kinetix</h4>
          <p className="text-xs text-indigo-800">
            Si quieres ver gráficas en vivo dentro de Kinetix sin abrir Grafana,
            agrega cualquiera de estos listeners a tu diseño:
          </p>
          <ul className="list-disc list-inside text-xs text-indigo-800 mt-1.5 ml-2">
            <li>jp@gc - Response Times Over Time</li>
            <li>jp@gc - Response Codes per Second</li>
            <li>jp@gc - Transactions per Second</li>
            <li>jp@gc - Active Threads Over Time</li>
            <li>jp@gc - Hits per Second</li>
          </ul>
        </div>
      </div>
    </div>
  );
}


// ============================================================================
// OverviewPanel (vista resumen)
// ============================================================================

function OverviewPanel({ structure }: { structure: AIScriptStructure }) {
  const totalSamplers = useMemo(() => {
    let n = 0;
    const countInChildren = (children: TGChild[]) => {
      for (const ch of children) {
        if (ch.type === 'sampler') n++;
        else if (ch.type === 'controller' && ch.controller) countInChildren(ch.controller.children);
      }
    };
    structure.thread_groups.forEach((tg) => countInChildren(tg.children));
    return n;
  }, [structure]);

  const totalChildren = useMemo(() => {
    let n = 0;
    const visit = (children: TGChild[]) => {
      for (const ch of children) {
        if (ch.type === 'sampler' && ch.sampler) n += ch.sampler.children.length;
        else if (ch.type === 'controller' && ch.controller) visit(ch.controller.children);
      }
    };
    structure.thread_groups.forEach((tg) => visit(tg.children));
    return n;
  }, [structure]);

  return (
    <div className="p-6 max-w-4xl space-y-4">
      {/* Stats grid */}
      <div className="grid grid-cols-2 md:grid-cols-4 gap-3">
        <StatCard label="Thread Groups" value={structure.thread_groups.length} icon={<UsersIcon className="w-5 h-5" />} color="indigo" />
        <StatCard label="Samplers" value={totalSamplers} icon={<Network className="w-5 h-5" />} color="blue" />
        <StatCard label="Sampler Children" value={totalChildren} icon={<Layers className="w-5 h-5" />} color="purple" />
        <StatCard label="CSV Data Sets" value={structure.csv_data_sets.length} icon={<Database className="w-5 h-5" />} color="emerald" />
        <StatCard label="Variables UDV" value={structure.user_defined_variables.length} icon={<Sliders className="w-5 h-5" />} color="cyan" />
        <StatCard label="Listeners" value={structure.listeners.length} icon={<Headphones className="w-5 h-5" />} color="gray" />
        <StatCard label="No editables" value={structure.metadata.unmapped_count} icon={<AlertTriangle className="w-5 h-5" />} color="amber" />
        <StatCard label="Vars referenciadas" value={structure.metadata.referenced_variables.length} icon={<ListChecks className="w-5 h-5" />} color="teal" />
      </div>

      {/* Variables indefinidas (warning crítico) */}
      {structure.metadata.undefined_variables.length > 0 && (
        <div className="bg-red-50 border border-red-200 rounded-lg p-4">
          <div className="flex items-start gap-3">
            <AlertCircle className="w-6 h-6 text-red-600 flex-shrink-0 mt-0.5" />
            <div className="flex-1">
              <h3 className="font-semibold text-red-900">
                {structure.metadata.undefined_variables.length} variable{structure.metadata.undefined_variables.length !== 1 ? 's' : ''} sin definir
              </h3>
              <p className="text-sm text-red-700 mt-1">
                Estas variables se referencian con <code className="bg-red-100 px-1 rounded">${'{var}'}</code> pero no existen en UDV, CSV ni Extractors. El script fallará en ejecución.
              </p>
              <div className="mt-2 flex flex-wrap gap-1.5">
                {structure.metadata.undefined_variables.map((v) => (
                  <code key={v} className="px-2 py-0.5 bg-red-100 text-red-800 text-xs rounded font-mono">
                    ${'{' + v + '}'}
                  </code>
                ))}
              </div>
            </div>
          </div>
        </div>
      )}

      {/* Variables definidas */}
      {structure.metadata.defined_variables.length > 0 && (
        <div className="bg-white border border-gray-200 rounded-lg p-4">
          <h3 className="font-semibold text-gray-900 mb-2">
            Variables definidas ({structure.metadata.defined_variables.length})
          </h3>
          <div className="flex flex-wrap gap-1.5">
            {structure.metadata.defined_variables.map((v) => (
              <code key={v} className="px-2 py-0.5 bg-green-50 text-green-700 text-xs rounded font-mono border border-green-200">
                ${'{' + v + '}'}
              </code>
            ))}
          </div>
        </div>
      )}

      {/* Elementos no editables (unmapped) */}
      {structure.unmapped.length > 0 && (
        <div className="bg-amber-50 border border-amber-200 rounded-lg p-4">
          <h3 className="font-semibold text-amber-900 mb-2">
            Elementos no editables ({structure.unmapped.length})
          </h3>
          <p className="text-sm text-amber-700 mb-3">
            Estos elementos se preservan al exportar pero no son editables visualmente:
          </p>
          <ul className="space-y-1.5">
            {structure.unmapped.map((u) => (
              <li key={u.id} className="flex items-start gap-2 text-sm">
                <AlertTriangle className="w-4 h-4 text-amber-600 flex-shrink-0 mt-0.5" />
                <div>
                  <code className="text-xs bg-amber-100 px-1 rounded">{u.kind}</code>
                  {u.name && <span className="ml-2 text-gray-700">{u.name}</span>}
                  <p className="text-xs text-gray-600 mt-0.5">{u.reason}</p>
                </div>
              </li>
            ))}
          </ul>
        </div>
      )}

      {/* Warnings de parse */}
      {structure.metadata.parse_warnings.length > 0 && (
        <div className="bg-yellow-50 border border-yellow-200 rounded-lg p-4">
          <h3 className="font-semibold text-yellow-900 mb-2">Warnings del parser</h3>
          <ul className="text-sm text-yellow-800 space-y-1">
            {structure.metadata.parse_warnings.map((w, i) => (
              <li key={i}>• {w}</li>
            ))}
          </ul>
        </div>
      )}
    </div>
  );
}

// ============================================================================
// StatCard
// ============================================================================

function StatCard({ label, value, icon, color }: { label: string; value: number; icon: React.ReactNode; color: string }) {
  const colorMap: Record<string, string> = {
    indigo: 'bg-indigo-50 text-indigo-700 border-indigo-200',
    blue: 'bg-blue-50 text-blue-700 border-blue-200',
    purple: 'bg-purple-50 text-purple-700 border-purple-200',
    emerald: 'bg-emerald-50 text-emerald-700 border-emerald-200',
    cyan: 'bg-cyan-50 text-cyan-700 border-cyan-200',
    gray: 'bg-gray-50 text-gray-700 border-gray-200',
    amber: 'bg-amber-50 text-amber-700 border-amber-200',
    teal: 'bg-teal-50 text-teal-700 border-teal-200',
  };
  return (
    <div className={`border rounded-lg p-3 ${colorMap[color] || colorMap.gray}`}>
      <div className="flex items-center gap-2 mb-1 opacity-80">{icon}<span className="text-xs">{label}</span></div>
      <div className="text-2xl font-bold">{value}</div>
    </div>
  );
}

// ============================================================================
// XmlRawModal (read-only)
// ============================================================================

function XmlRawModal({ jmx, onClose }: { jmx: string; onClose: () => void }) {
  const handleCopy = () => {
    navigator.clipboard.writeText(jmx);
  };

  return (
    <div className="fixed inset-0 bg-black/60 flex items-center justify-center z-50 p-4">
      <div className="bg-white rounded-lg shadow-xl max-w-5xl w-full h-[80vh] flex flex-col">
        <div className="flex items-center justify-between px-4 py-3 border-b border-gray-200">
          <div className="flex items-center gap-2">
            <FileCode className="w-5 h-5 text-indigo-600" />
            <h2 className="text-lg font-semibold text-gray-900">XML raw del JMX</h2>
            <span className="text-xs text-gray-500">({jmx.length.toLocaleString()} chars)</span>
          </div>
          <div className="flex items-center gap-2">
            <button
              onClick={handleCopy}
              className="px-3 py-1 text-sm text-gray-700 border border-gray-300 rounded hover:bg-gray-50"
            >
              Copiar
            </button>
            <button onClick={onClose} className="p-1 hover:bg-gray-100 rounded">
              <X className="w-5 h-5" />
            </button>
          </div>
        </div>
        <pre className="flex-1 overflow-auto p-4 text-xs font-mono bg-gray-50 text-gray-800">
          {jmx}
        </pre>
      </div>
    </div>
  );
}


// ============================================================================
// Helpers reutilizables para paneles de edición (Sprint 2.4b-e)
// ============================================================================

function SectionCard({ title, children }: { title: string; children: React.ReactNode }) {
  return (
    <div className="bg-white border border-gray-200 rounded-lg p-4">
      <h3 className="text-sm font-semibold text-gray-900 mb-3">{title}</h3>
      <div className="space-y-3">{children}</div>
    </div>
  );
}

function FormField({ label, hint, children }: { label: string; hint?: string; children: React.ReactNode }) {
  return (
    <div>
      <label className="block text-xs font-medium text-gray-700 mb-1">
        {label}
        {hint && <span className="ml-2 text-gray-400 font-normal">({hint})</span>}
      </label>
      {children}
    </div>
  );
}

function NotFoundPanel({ kind }: { kind: string }) {
  return (
    <div className="p-6 max-w-3xl">
      <div className="bg-red-50 border border-red-200 rounded-lg p-4 text-red-700">
        Elemento <code className="bg-red-100 px-1 rounded">{kind}</code> no encontrado en la estructura. Probablemente fue eliminado o el árbol está desactualizado.
      </div>
    </div>
  );
}

function formatRelativeTime(date: Date): string {
  const seconds = Math.floor((Date.now() - date.getTime()) / 1000);
  if (seconds < 5) return 'ahora';
  if (seconds < 60) return `hace ${seconds}s`;
  if (seconds < 3600) return `hace ${Math.floor(seconds / 60)} min`;
  return `hace ${Math.floor(seconds / 3600)} h`;
}

function updateThreadGroup(
  structure: AIScriptStructure,
  tgId: string,
  updates: Partial<ThreadGroupModel>,
): AIScriptStructure {
  return {
    ...structure,
    thread_groups: structure.thread_groups.map((tg) =>
      tg.id === tgId ? { ...tg, ...updates, is_dirty: true } : tg,
    ),
  };
}


// ============================================================================
// Panel de edición Thread Group (Standard + Stepping)
// ============================================================================

interface ThreadGroupEditPanelProps {
  tg: ThreadGroupModel;
  onUpdate: (updates: Partial<ThreadGroupModel>) => void;
}

function ThreadGroupEditPanel({ tg, onUpdate }: ThreadGroupEditPanelProps) {
  return (
    <div className="p-6 max-w-4xl space-y-5">
      {/* Header */}
      <div className="flex items-center gap-3">
        <UsersIcon className={`w-7 h-7 ${tg.kind === 'stepping' ? 'text-purple-600' : 'text-indigo-600'}`} />
        <div className="flex-1">
          <h2 className="text-xl font-semibold text-gray-900">{tg.name}</h2>
          <p className="text-sm text-gray-500">
            {tg.kind === 'stepping' ? 'Stepping Thread Group (kg.apc)' : 'Standard Thread Group'}
          </p>
        </div>
        <span
          className={`px-2.5 py-1 text-xs rounded-full font-medium ${
            tg.enabled ? 'bg-green-100 text-green-700' : 'bg-gray-100 text-gray-500'
          }`}
        >
          {tg.enabled ? 'Habilitado' : 'Deshabilitado'}
        </span>
      </div>

      {/* General */}
      <SectionCard title="General">
        <FormField label="Nombre">
          <input
            type="text"
            value={tg.name}
            onChange={(e) => onUpdate({ name: e.target.value })}
            className="w-full px-3 py-1.5 text-sm border border-gray-300 rounded-md focus:ring-2 focus:ring-indigo-500"
          />
        </FormField>
        <FormField label="Comentarios">
          <textarea
            value={tg.comments || ''}
            onChange={(e) => onUpdate({ comments: e.target.value })}
            rows={2}
            className="w-full px-3 py-1.5 text-sm border border-gray-300 rounded-md focus:ring-2 focus:ring-indigo-500"
          />
        </FormField>
        <div className="flex items-center gap-6">
          <label className="flex items-center gap-2 text-sm">
            <input
              type="checkbox"
              checked={tg.enabled}
              onChange={(e) => onUpdate({ enabled: e.target.checked })}
            />
            Habilitado
          </label>
          <FormField label="Acción en error">
            <select
              value={tg.on_sample_error || 'continue'}
              onChange={(e) => onUpdate({ on_sample_error: e.target.value as ThreadGroupModel['on_sample_error'] })}
              className="px-3 py-1.5 text-sm border border-gray-300 rounded-md"
            >
              <option value="continue">Continuar</option>
              <option value="startnextloop">Iniciar siguiente iteración</option>
              <option value="stopthread">Detener hilo</option>
              <option value="stoptest">Detener test</option>
              <option value="stoptestnow">Detener test ya</option>
            </select>
          </FormField>
        </div>
      </SectionCard>

      {/* Configuración según kind */}
      {tg.kind === 'standard' ? (
        <StandardConfigSection tg={tg} onUpdate={onUpdate} />
      ) : (
        <SteppingConfigSection tg={tg} onUpdate={onUpdate} />
      )}

      {/* Visualización */}
      <LoadVisualization tg={tg} />
    </div>
  );
}

function StandardConfigSection({
  tg,
  onUpdate,
}: {
  tg: ThreadGroupModel;
  onUpdate: (u: Partial<ThreadGroupModel>) => void;
}) {
  return (
    <SectionCard title="Configuración Standard">
      <div className="grid grid-cols-2 gap-4">
        <FormField label="Número de usuarios">
          <input
            type="number"
            min={1}
            value={tg.num_threads}
            onChange={(e) => onUpdate({ num_threads: parseInt(e.target.value) || 1 })}
            className="w-full px-3 py-1.5 text-sm border border-gray-300 rounded-md"
          />
        </FormField>
        <FormField label="Ramp-up (segundos)">
          <input
            type="number"
            min={0}
            value={tg.ramp_time}
            onChange={(e) => onUpdate({ ramp_time: parseInt(e.target.value) || 0 })}
            className="w-full px-3 py-1.5 text-sm border border-gray-300 rounded-md"
          />
        </FormField>
        <FormField label="Loops">
          <input
            type="number"
            value={tg.loops}
            onChange={(e) => onUpdate({ loops: parseInt(e.target.value) || 1 })}
            disabled={tg.continue_forever}
            className="w-full px-3 py-1.5 text-sm border border-gray-300 rounded-md disabled:bg-gray-100"
          />
        </FormField>
        <FormField label=" ">
          <label className="flex items-center gap-2 text-sm pt-1.5">
            <input
              type="checkbox"
              checked={tg.continue_forever}
              onChange={(e) => onUpdate({ continue_forever: e.target.checked })}
            />
            Iterar indefinidamente
          </label>
        </FormField>
      </div>
      <div className="mt-3 flex items-center gap-3 flex-wrap">
        <label className="flex items-center gap-2 text-sm">
          <input
            type="checkbox"
            checked={tg.scheduler}
            onChange={(e) => onUpdate({ scheduler: e.target.checked })}
          />
          Usar scheduler
        </label>
        {tg.scheduler && (
          <>
            <FormField label="Duración (s)">
              <input
                type="number"
                value={tg.duration || 0}
                onChange={(e) => onUpdate({ duration: parseInt(e.target.value) || 0 })}
                className="w-32 px-3 py-1.5 text-sm border border-gray-300 rounded-md"
              />
            </FormField>
            <FormField label="Delay (s)">
              <input
                type="number"
                value={tg.delay || 0}
                onChange={(e) => onUpdate({ delay: parseInt(e.target.value) || 0 })}
                className="w-32 px-3 py-1.5 text-sm border border-gray-300 rounded-md"
              />
            </FormField>
          </>
        )}
      </div>
    </SectionCard>
  );
}

function SteppingConfigSection({
  tg,
  onUpdate,
}: {
  tg: ThreadGroupModel;
  onUpdate: (u: Partial<ThreadGroupModel>) => void;
}) {
  if (!tg.stepping) {
    return (
      <SectionCard title="Configuración Stepping">
        <div className="text-sm text-amber-700 bg-amber-50 border border-amber-200 rounded p-3">
          Este Thread Group no tiene configuración Stepping. (Edición de tipo TG es funcionalidad futura.)
        </div>
      </SectionCard>
    );
  }
  const s = tg.stepping;

  const updateStepping = (updates: Partial<SteppingConfig>) => {
    onUpdate({ stepping: { ...s, ...updates } });
  };

  const inputCls = 'w-24 px-2 py-1 text-sm border border-gray-300 rounded-md text-center';

  return (
    <SectionCard title="Stepping Thread Group (kg.apc) — Threads Scheduling Parameters">
      <div className="space-y-3">
        <div className="flex items-center gap-2 text-sm flex-wrap">
          <span className="text-gray-700">Este grupo va a iniciar</span>
          <input
            type="number"
            min={1}
            value={tg.num_threads}
            onChange={(e) => onUpdate({ num_threads: parseInt(e.target.value) || 1 })}
            className={inputCls}
          />
          <span className="text-gray-700">threads (usuarios totales).</span>
        </div>

        <div className="flex items-center gap-2 text-sm flex-wrap">
          <span className="text-gray-700">Primero, esperar</span>
          <input
            type="number"
            min={0}
            value={s.initial_delay}
            onChange={(e) => updateStepping({ initial_delay: parseInt(e.target.value) || 0 })}
            className={inputCls}
          />
          <span className="text-gray-700">segundos.</span>
        </div>

        <div className="flex items-center gap-2 text-sm flex-wrap">
          <span className="text-gray-700">Después arrancar con</span>
          <input
            type="number"
            min={0}
            value={s.start_users_count}
            onChange={(e) => updateStepping({ start_users_count: parseInt(e.target.value) || 0 })}
            className={inputCls}
          />
          <span className="text-gray-700">threads iniciales.</span>
        </div>

        <div className="flex items-center gap-2 text-sm flex-wrap">
          <span className="text-gray-700">Luego, agregar</span>
          <input
            type="number"
            min={0}
            value={s.start_users_count_burst}
            onChange={(e) => updateStepping({ start_users_count_burst: parseInt(e.target.value) || 0 })}
            className={inputCls}
            title="Cuántos threads se añaden por escalón (Next, add N threads)"
          />
          <span className="text-gray-700">threads cada</span>
          <input
            type="number"
            min={0}
            value={s.start_users_period}
            onChange={(e) => updateStepping({ start_users_period: parseInt(e.target.value) || 0 })}
            className={inputCls}
            title="Tiempo entre escalones (every M seconds)"
          />
          <span className="text-gray-700">segundos, con ramp-up de</span>
          <input
            type="number"
            min={0}
            value={s.ramp_up}
            onChange={(e) => updateStepping({ ramp_up: parseInt(e.target.value) || 0 })}
            className={inputCls}
            title="Ramp-up por escalón (using ramp-up R seconds)"
          />
          <span className="text-gray-700">segundos.</span>
        </div>

        <div className="flex items-center gap-2 text-sm flex-wrap">
          <span className="text-gray-700">Después mantener carga por</span>
          <input
            type="number"
            min={0}
            value={s.flight_time}
            onChange={(e) => updateStepping({ flight_time: parseInt(e.target.value) || 0 })}
            className={inputCls}
          />
          <span className="text-gray-700">segundos.</span>
        </div>

        <div className="flex items-center gap-2 text-sm flex-wrap">
          <span className="text-gray-700">Finalmente, detener</span>
          <input
            type="number"
            min={0}
            value={s.stop_users_count}
            onChange={(e) => updateStepping({ stop_users_count: parseInt(e.target.value) || 0 })}
            className={inputCls}
          />
          <span className="text-gray-700">threads cada</span>
          <input
            type="number"
            min={0}
            value={s.stop_users_period}
            onChange={(e) => updateStepping({ stop_users_period: parseInt(e.target.value) || 0 })}
            className={inputCls}
          />
          <span className="text-gray-700">segundos.</span>
        </div>
      </div>

      <div className="mt-4 text-xs text-gray-500 bg-gray-50 border border-gray-200 rounded p-3">
        <strong className="text-gray-700">Equivalencias JMeter:</strong> "This group will start N threads", "First, wait for X seconds", "Then start X threads", "Next, add X threads every X seconds, using ramp-up X seconds", "Then hold load for X seconds", "Finally, stop X threads every X seconds".
      </div>
    </SectionCard>
  );
}

function LoadVisualization({ tg }: { tg: ThreadGroupModel }) {
  const points = useMemo(() => computeLoadCurve(tg), [tg]);
  if (points.length === 0) return null;

  const maxUsers = Math.max(...points.map((p) => p.users), 1);
  const maxTime = Math.max(...points.map((p) => p.time), 1);
  const width = 600;
  const height = 220;
  const padding = { top: 20, right: 20, bottom: 35, left: 50 };
  const w = width - padding.left - padding.right;
  const h = height - padding.top - padding.bottom;

  const pathD = points
    .map((p, i) => {
      const x = padding.left + (p.time / maxTime) * w;
      const y = padding.top + h - (p.users / maxUsers) * h;
      return `${i === 0 ? 'M' : 'L'} ${x.toFixed(1)} ${y.toFixed(1)}`;
    })
    .join(' ');

  const areaD = `${pathD} L ${padding.left + w} ${padding.top + h} L ${padding.left} ${padding.top + h} Z`;

  return (
    <SectionCard title="Visualización de carga">
      <div className="bg-gray-50 rounded p-3">
        <svg viewBox={`0 0 ${width} ${height}`} className="w-full h-auto" preserveAspectRatio="xMidYMid meet">
          <line x1={padding.left} y1={padding.top + h} x2={padding.left + w} y2={padding.top + h} stroke="#9ca3af" strokeWidth="1" />
          <line x1={padding.left} y1={padding.top} x2={padding.left} y2={padding.top + h} stroke="#9ca3af" strokeWidth="1" />
          <text x={padding.left - 5} y={padding.top + 5} textAnchor="end" fontSize="10" fill="#6b7280">{maxUsers}</text>
          <text x={padding.left - 5} y={padding.top + h / 2} textAnchor="end" fontSize="10" fill="#6b7280">{Math.round(maxUsers / 2)}</text>
          <text x={padding.left - 5} y={padding.top + h} textAnchor="end" fontSize="10" fill="#6b7280">0</text>
          <text x={padding.left} y={padding.top + h + 18} textAnchor="start" fontSize="10" fill="#6b7280">0s</text>
          <text x={padding.left + w} y={padding.top + h + 18} textAnchor="end" fontSize="10" fill="#6b7280">{maxTime}s</text>
          <text x={padding.left + w / 2} y={height - 5} textAnchor="middle" fontSize="10" fill="#6b7280">tiempo</text>
          <text x={15} y={padding.top + h / 2} textAnchor="middle" fontSize="10" fill="#6b7280" transform={`rotate(-90, 15, ${padding.top + h / 2})`}>usuarios</text>
          <path d={areaD} fill="rgba(99,102,241,0.15)" />
          <path d={pathD} fill="none" stroke="#4f46e5" strokeWidth="2" />
          {points.map((p, i) => {
            const x = padding.left + (p.time / maxTime) * w;
            const y = padding.top + h - (p.users / maxUsers) * h;
            return <circle key={i} cx={x} cy={y} r="3" fill="#4f46e5" />;
          })}
        </svg>
        <div className="flex items-center gap-4 mt-2 text-xs text-gray-600">
          <span><strong>Pico:</strong> {maxUsers} usuarios</span>
          <span><strong>Duración total:</strong> ~{maxTime}s</span>
        </div>
      </div>
    </SectionCard>
  );
}

function computeLoadCurve(tg: ThreadGroupModel): { time: number; users: number }[] {
  if (tg.kind === 'standard') {
    const pts = [{ time: 0, users: 0 }, { time: tg.ramp_time, users: tg.num_threads }];
    if (tg.scheduler && tg.duration) {
      pts.push({ time: tg.ramp_time + tg.duration, users: tg.num_threads });
      pts.push({ time: tg.ramp_time + tg.duration, users: 0 });
    }
    return pts;
  }
  // Stepping (kg.apc): start_users_count = usuarios añadidos por paso,
  // start_users_period = tiempo entre pasos, ramp_up = tiempo de ramp dentro del paso,
  // flight_time = tiempo sostenido al alcanzar el peak.
  if (!tg.stepping) return [];
  const s = tg.stepping;
  const pts: { time: number; users: number }[] = [];
  let t = s.initial_delay;
  pts.push({ time: 0, users: 0 });
  if (t > 0) pts.push({ time: t, users: 0 });

  let u = Math.min(s.start_users_count_burst || s.start_users_count, tg.num_threads);
  t += s.ramp_up;
  pts.push({ time: t, users: u });

  let safety = 0;
  while (u < tg.num_threads && safety < 1000) {
    t += s.start_users_period;
    pts.push({ time: t, users: u });
    const nextU = Math.min(u + s.start_users_count, tg.num_threads);
    t += s.ramp_up;
    pts.push({ time: t, users: nextU });
    u = nextU;
    safety++;
  }
  t += s.flight_time;
  pts.push({ time: t, users: tg.num_threads });
  return pts;
}


// ============================================================================
// updateSampler — mutación inmutable de un sampler dentro de un TG
// ============================================================================

function updateSampler(
  structure: AIScriptStructure,
  tgId: string,
  samplerId: string,
  updates: Partial<HTTPSamplerModel>,
): AIScriptStructure {
  return {
    ...structure,
    thread_groups: structure.thread_groups.map((tg) => {
      if (tg.id !== tgId) return tg;
      return {
        ...tg,
        children: tg.children.map((ch) => {
          if (ch.type !== 'sampler' || !ch.sampler || ch.sampler.id !== samplerId) return ch;
          return { ...ch, sampler: { ...ch.sampler, ...updates, is_dirty: true } };
        }),
      };
    }),
  };
}


// ============================================================================
// Panel de edición HTTP Sampler (Sprint 2.4c)
// ============================================================================

interface SamplerEditPanelProps {
  sampler: HTTPSamplerModel;
  onUpdate: (updates: Partial<HTTPSamplerModel>) => void;
}

function HTTPSamplerEditPanel({ sampler, onUpdate }: SamplerEditPanelProps) {
  const updateBody = (bodyUpdates: Partial<SamplerBody>) => {
    onUpdate({ body: { ...sampler.body, ...bodyUpdates } });
  };

  return (
    <div className="p-6 max-w-4xl space-y-5">
      {/* Header */}
      <div className="flex items-center gap-3">
        <span className={`px-2 py-1 text-xs rounded font-mono ${methodColor(sampler.method)}`}>
          {sampler.method}
        </span>
        <div className="flex-1">
          <h2 className="text-xl font-semibold text-gray-900">{sampler.name}</h2>
          <p className="text-sm text-gray-500">HTTP Sampler</p>
        </div>
        <span
          className={`px-2.5 py-1 text-xs rounded-full font-medium ${
            sampler.enabled ? 'bg-green-100 text-green-700' : 'bg-gray-100 text-gray-500'
          }`}
        >
          {sampler.enabled ? 'Habilitado' : 'Deshabilitado'}
        </span>
      </div>

      {/* General */}
      <SectionCard title="General">
        <FormField label="Nombre">
          <input
            type="text"
            value={sampler.name}
            onChange={(e) => onUpdate({ name: e.target.value })}
            className="w-full px-3 py-1.5 text-sm border border-gray-300 rounded-md focus:ring-2 focus:ring-indigo-500"
          />
        </FormField>
        <label className="flex items-center gap-2 text-sm">
          <input
            type="checkbox"
            checked={sampler.enabled}
            onChange={(e) => onUpdate({ enabled: e.target.checked })}
          />
          Habilitado
        </label>
      </SectionCard>

      {/* URL y método */}
      <SectionCard title="URL y método">
        <div className="grid grid-cols-12 gap-3 items-end">
          <div className="col-span-2">
            <FormField label="Método">
              <select
                value={sampler.method}
                onChange={(e) => onUpdate({ method: e.target.value })}
                className="w-full px-3 py-1.5 text-sm border border-gray-300 rounded-md font-mono"
              >
                {['GET', 'POST', 'PUT', 'DELETE', 'PATCH', 'HEAD', 'OPTIONS'].map((m) => (
                  <option key={m} value={m}>{m}</option>
                ))}
              </select>
            </FormField>
          </div>
          <div className="col-span-3">
            <FormField label="Protocolo">
              <select
                value={sampler.protocol || ''}
                onChange={(e) => onUpdate({ protocol: e.target.value })}
                className="w-full px-3 py-1.5 text-sm border border-gray-300 rounded-md font-mono"
              >
                <option value="">(default)</option>
                <option value="http">http</option>
                <option value="https">https</option>
              </select>
            </FormField>
          </div>
          <div className="col-span-5">
            <FormField label="Dominio">
              <InputWithFx
                value={sampler.domain || ''}
                onChange={(v) => onUpdate({ domain: v })}
                placeholder="${host} o api.example.com"
                className="flex-1 px-3 py-1.5 text-sm border border-gray-300 rounded-md font-mono"
              />
            </FormField>
          </div>
          <div className="col-span-2">
            <FormField label="Puerto">
              <input
                type="text"
                value={sampler.port || ''}
                onChange={(e) => onUpdate({ port: e.target.value })}
                placeholder="${port}"
                className="w-full px-3 py-1.5 text-sm border border-gray-300 rounded-md font-mono"
              />
            </FormField>
          </div>
        </div>
        <FormField label="Path">
          <InputWithFx
            value={sampler.path || ''}
            onChange={(v) => onUpdate({ path: v })}
            placeholder="/api/v1/resource"
            className="flex-1 px-3 py-1.5 text-sm border border-gray-300 rounded-md font-mono"
          />
        </FormField>
      </SectionCard>

      {/* Body */}
      <SectionCard title="Cuerpo de la petición">
        <FormField label="Tipo de body">
          <select
            value={sampler.body.mode}
            onChange={(e) => {
              const newMode = e.target.value as SamplerBody['mode'];
              if (newMode === 'none') {
                updateBody({ mode: newMode, raw_text: null, form_args: [] });
              } else if (newMode === 'raw') {
                updateBody({ mode: newMode, raw_text: sampler.body.raw_text || '', form_args: [] });
              } else {
                updateBody({ mode: newMode, raw_text: null, form_args: sampler.body.form_args || [] });
              }
            }}
            className="w-56 px-3 py-1.5 text-sm border border-gray-300 rounded-md"
          >
            <option value="none">Sin body</option>
            <option value="raw">Raw (JSON, XML, texto)</option>
            <option value="form">Form parameters</option>
          </select>
        </FormField>

        {sampler.body.mode === 'raw' && (
          <FormField label="Contenido raw">
            <TextareaWithFx
              value={sampler.body.raw_text || ''}
              onChange={(v) => updateBody({ raw_text: v })}
              rows={8}
              placeholder='{"key": "value"}'
              className="w-full px-3 py-2 text-xs font-mono border border-gray-300 rounded-md bg-gray-50 focus:ring-2 focus:ring-indigo-500"
            />
          </FormField>
        )}

        {sampler.body.mode === 'form' && (
          <FormParamsEditor
            params={sampler.body.form_args || []}
            onChange={(newParams) => updateBody({ form_args: newParams })}
          />
        )}

        {sampler.body.mode === 'none' && (
          <p className="text-xs text-gray-500 italic">Este sampler no envía body.</p>
        )}
      </SectionCard>

      {/* Opciones avanzadas */}
      <SectionCard title="Opciones avanzadas">
        <div className="grid grid-cols-2 gap-3">
          <label className="flex items-center gap-2 text-sm">
            <input
              type="checkbox"
              checked={sampler.follow_redirects}
              onChange={(e) => onUpdate({ follow_redirects: e.target.checked })}
            />
            Seguir redirects
          </label>
          <label className="flex items-center gap-2 text-sm">
            <input
              type="checkbox"
              checked={sampler.auto_redirects}
              onChange={(e) => onUpdate({ auto_redirects: e.target.checked })}
            />
            Auto redirects
          </label>
          <label className="flex items-center gap-2 text-sm">
            <input
              type="checkbox"
              checked={sampler.use_keepalive}
              onChange={(e) => onUpdate({ use_keepalive: e.target.checked })}
            />
            Keep-alive
          </label>
          <FormField label="Encoding">
            <input
              type="text"
              value={sampler.content_encoding || ''}
              onChange={(e) => onUpdate({ content_encoding: e.target.value })}
              placeholder="UTF-8"
              className="w-full px-3 py-1.5 text-sm border border-gray-300 rounded-md"
            />
          </FormField>
        </div>
      </SectionCard>
    </div>
  );
}

// ============================================================================
// FormParamsEditor (params editor para body=form)
// ============================================================================

function FormParamsEditor({
  params,
  onChange,
}: {
  params: FormArgument[];
  onChange: (p: FormArgument[]) => void;
}) {
  const addParam = () => {
    onChange([...params, { name: '', value: '', metadata: '=', always_encode: false, use_equals: true }]);
  };
  const updateParam = (idx: number, updates: Partial<FormArgument>) => {
    onChange(params.map((p, i) => (i === idx ? { ...p, ...updates } : p)));
  };
  const removeParam = (idx: number) => {
    onChange(params.filter((_, i) => i !== idx));
  };

  return (
    <div className="space-y-2">
      {params.length === 0 && (
        <p className="text-xs text-gray-500 italic">Sin parámetros. Click "+ Añadir parámetro" para agregar.</p>
      )}
      {params.length > 0 && (
        <div className="grid grid-cols-12 gap-2 px-2 text-xs font-medium text-gray-600">
          <div className="col-span-4">Nombre</div>
          <div className="col-span-5">Valor</div>
          <div className="col-span-2 text-center">URL encode</div>
          <div className="col-span-1"></div>
        </div>
      )}
      {params.map((p, idx) => (
        <div key={idx} className="grid grid-cols-12 gap-2 items-center">
          <input
            type="text"
            value={p.name}
            onChange={(e) => updateParam(idx, { name: e.target.value })}
            placeholder="nombre"
            className="col-span-4 px-2 py-1 text-sm border border-gray-300 rounded font-mono"
          />
          <div className="col-span-5">
            <InputWithFx
              value={p.value}
              onChange={(v) => updateParam(idx, { value: v })}
              placeholder="valor"
              className="flex-1 px-2 py-1 text-sm border border-gray-300 rounded font-mono"
            />
          </div>
          <div className="col-span-2 text-center">
            <input
              type="checkbox"
              checked={p.always_encode}
              onChange={(e) => updateParam(idx, { always_encode: e.target.checked })}
            />
          </div>
          <button
            onClick={() => removeParam(idx)}
            className="col-span-1 p-1 text-red-500 hover:bg-red-50 rounded justify-self-end"
            title="Eliminar parámetro"
          >
            <X className="w-4 h-4" />
          </button>
        </div>
      ))}
      <button
        onClick={addParam}
        className="text-sm text-indigo-600 hover:bg-indigo-50 px-3 py-1.5 rounded font-medium"
      >
        + Añadir parámetro
      </button>
    </div>
  );
}


// ============================================================================
// Sprint 2.4d — Edición de children del HTTP Sampler
// ============================================================================

function updateSamplerChild(
  structure: AIScriptStructure,
  tgId: string,
  samplerId: string,
  childId: string,
  updates: any,
): AIScriptStructure {
  return {
    ...structure,
    thread_groups: structure.thread_groups.map((tg) => {
      if (tg.id !== tgId) return tg;
      return {
        ...tg,
        children: tg.children.map((ch) => {
          if (ch.type !== 'sampler' || !ch.sampler || ch.sampler.id !== samplerId) return ch;
          return {
            ...ch,
            sampler: {
              ...ch.sampler,
              is_dirty: true, // padre marcado también para invalidar cache del wrapper
              children: ch.sampler.children.map((sc) => {
                const scId = (sc.data as any).id;
                if (scId !== childId) return sc;
                return { ...sc, data: { ...sc.data, ...updates, is_dirty: true } } as any;
              }),
            },
          };
        }),
      };
    }),
  };
}


interface ChildEditorProps<T> {
  data: T;
  onUpdate: (updates: Partial<T>) => void;
}

// ----------------------------------------------------------------------------
// SamplerChildEditPanel — discriminador principal
// ----------------------------------------------------------------------------

function SamplerChildEditPanel({
  child,
  onUpdate,
}: {
  child: SamplerChild;
  onUpdate: (updates: any) => void;
}) {
  switch (child.type) {
    case 'header_manager':
      return <HeaderManagerEdit data={child.data as HeaderManagerModel} onUpdate={onUpdate} />;
    case 'response_assertion':
      return <ResponseAssertionEdit data={child.data as ResponseAssertionModel} onUpdate={onUpdate} />;
    case 'regex_extractor':
      return <RegexExtractorEdit data={child.data as RegexExtractorModel} onUpdate={onUpdate} />;
    case 'json_extractor':
      return <JsonExtractorEdit data={child.data as JsonExtractorModel} onUpdate={onUpdate} />;
    case 'xpath_extractor':
      return <XPathExtractorEdit data={child.data as XPathExtractorModel} onUpdate={onUpdate} />;
    case 'boundary_extractor':
      return <BoundaryExtractorEdit data={child.data as BoundaryExtractorModel} onUpdate={onUpdate} />;
    case 'constant_timer':
      return <ConstantTimerEdit data={child.data as ConstantTimerModel} onUpdate={onUpdate} />;
    case 'uniform_random_timer':
      return <UniformRandomTimerEdit data={child.data as UniformRandomTimerModel} onUpdate={onUpdate} />;
    case 'gaussian_random_timer':
      return <GaussianRandomTimerEdit data={child.data as GaussianRandomTimerModel} onUpdate={onUpdate} />;
    default:
      return <UnsupportedChildView child={child} />;
  }
}

function UnsupportedChildView({ child }: { child: SamplerChild }) {
  const data = child.data as any;
  const kind = data.kind || (child as any).type || 'unknown';
  const name = data.name || '(sin nombre)';
  const reason = data.reason || 'Tipo no soportado por el editor visual';
  const rawXml = data.raw_xml || '';

  return (
    <div className="p-6 max-w-4xl space-y-4">
      <div className="flex items-center gap-2">
        <AlertTriangle className="w-6 h-6 text-amber-600" />
        <div className="flex-1">
          <h2 className="text-xl font-semibold text-gray-900">{name}</h2>
          <p className="text-sm text-gray-500">Elemento no editable visualmente</p>
        </div>
      </div>

      <SectionCard title="Información del elemento">
        <FormField label="Tipo (JMeter)">
          <code className="block px-3 py-1.5 text-sm bg-gray-100 rounded font-mono text-gray-800">
            {kind}
          </code>
        </FormField>
        <FormField label="Motivo">
          <p className="text-sm text-gray-700">{reason}</p>
        </FormField>
        <div className="bg-blue-50 border border-blue-200 rounded p-3 text-xs text-blue-800">
          <strong>Nota:</strong> Este elemento se preserva intacto al exportar el JMX. Se conserva el XML original para que JMeter lo pueda ejecutar sin problemas.
        </div>
      </SectionCard>

      {rawXml && (
        <SectionCard title="XML original (raw_xml)">
          <pre className="text-xs font-mono bg-gray-900 text-gray-100 rounded p-3 overflow-auto max-h-96 whitespace-pre-wrap">
            {rawXml}
          </pre>
          <button
            onClick={() => {
              navigator.clipboard.writeText(rawXml);
            }}
            className="text-sm text-indigo-600 hover:bg-indigo-50 px-3 py-1.5 rounded font-medium mt-2"
          >
            Copiar XML
          </button>
        </SectionCard>
      )}
    </div>
  );
}

// ----------------------------------------------------------------------------
// HeaderManager
// ----------------------------------------------------------------------------

function HeaderManagerEdit({ data, onUpdate }: ChildEditorProps<HeaderManagerModel>) {
  const updateHeader = (idx: number, updates: Partial<HeaderModel>) => {
    onUpdate({ headers: data.headers.map((h, i) => (i === idx ? { ...h, ...updates } : h)) });
  };
  const addHeader = () => {
    onUpdate({ headers: [...data.headers, { name: '', value: '' }] });
  };
  const removeHeader = (idx: number) => {
    onUpdate({ headers: data.headers.filter((_, i) => i !== idx) });
  };

  return (
    <div className="p-6 max-w-4xl space-y-4">
      <div className="flex items-center gap-2">
        <Network className="w-6 h-6 text-blue-600" />
        <h2 className="text-xl font-semibold">HTTP Header Manager</h2>
      </div>
      <SectionCard title="Headers">
        {data.headers.length === 0 && (
          <p className="text-xs text-gray-500 italic">Sin headers definidos.</p>
        )}
        {data.headers.length > 0 && (
          <div className="grid grid-cols-12 gap-2 px-2 text-xs font-medium text-gray-600">
            <div className="col-span-4">Nombre</div>
            <div className="col-span-7">Valor</div>
            <div className="col-span-1"></div>
          </div>
        )}
        {data.headers.map((h, idx) => (
          <div key={idx} className="grid grid-cols-12 gap-2 items-center">
            <input
              type="text"
              value={h.name}
              onChange={(e) => updateHeader(idx, { name: e.target.value })}
              placeholder="Content-Type"
              className="col-span-4 px-2 py-1 text-sm border border-gray-300 rounded font-mono"
            />
            <div className="col-span-7">
              <InputWithFx
                value={h.value}
                onChange={(v) => updateHeader(idx, { value: v })}
                placeholder="application/json"
                className="flex-1 px-2 py-1 text-sm border border-gray-300 rounded font-mono"
              />
            </div>
            <button
              onClick={() => removeHeader(idx)}
              className="col-span-1 p-1 text-red-500 hover:bg-red-50 rounded justify-self-end"
              title="Eliminar header"
            >
              <X className="w-4 h-4" />
            </button>
          </div>
        ))}
        <button
          onClick={addHeader}
          className="text-sm text-indigo-600 hover:bg-indigo-50 px-3 py-1.5 rounded font-medium"
        >
          + Añadir header
        </button>
      </SectionCard>
    </div>
  );
}

// ----------------------------------------------------------------------------
// ResponseAssertion
// ----------------------------------------------------------------------------

function ResponseAssertionEdit({ data, onUpdate }: ChildEditorProps<ResponseAssertionModel>) {
  const testTypeOptions = [
    { value: 1, label: 'Match (regex completo)' },
    { value: 2, label: 'Contains (regex parcial)' },
    { value: 8, label: 'Equals' },
    { value: 16, label: 'Substring' },
    { value: 33, label: 'No Match (Match negado)' },
    { value: 34, label: 'Not Contains' },
  ];

  return (
    <div className="p-6 max-w-4xl space-y-4">
      <div className="flex items-center gap-2">
        <CheckCircle2 className="w-6 h-6 text-green-600" />
        <h2 className="text-xl font-semibold">{data.name || 'Response Assertion'}</h2>
      </div>
      <SectionCard title="Configuración">
        <FormField label="Nombre">
          <input
            type="text"
            value={data.name || ''}
            onChange={(e) => onUpdate({ name: e.target.value })}
            className="w-full px-3 py-1.5 text-sm border border-gray-300 rounded-md"
          />
        </FormField>
        <FormField label="Campo a verificar">
          <select
            value={data.test_field}
            onChange={(e) => onUpdate({ test_field: e.target.value })}
            className="w-full px-3 py-1.5 text-sm border border-gray-300 rounded-md"
          >
            <option value="Assertion.response_data">Texto de respuesta</option>
            <option value="Assertion.response_code">Código de respuesta</option>
            <option value="Assertion.response_message">Mensaje de respuesta</option>
            <option value="Assertion.response_headers">Headers de respuesta</option>
            <option value="Assertion.request_data">Datos de petición</option>
            <option value="Assertion.request_headers">Headers de petición</option>
            <option value="Assertion.sample_label">Sample label</option>
          </select>
        </FormField>
        <FormField label="Tipo de patrón">
          <select
            value={data.test_type}
            onChange={(e) => onUpdate({ test_type: parseInt(e.target.value) })}
            className="w-full px-3 py-1.5 text-sm border border-gray-300 rounded-md"
          >
            {testTypeOptions.map((opt) => (
              <option key={opt.value} value={opt.value}>{opt.label}</option>
            ))}
          </select>
        </FormField>
        <FormField label="Patrones (uno por línea)">
          <textarea
            value={data.test_strings.join('\n')}
            onChange={(e) =>
              onUpdate({ test_strings: e.target.value.split('\n').filter((s) => s.length > 0) })
            }
            rows={4}
            spellCheck={false}
            className="w-full px-3 py-1.5 text-xs font-mono border border-gray-300 rounded-md"
            placeholder="200"
          />
        </FormField>
        <FormField label="Mensaje de error custom">
          <input
            type="text"
            value={data.custom_message || ''}
            onChange={(e) => onUpdate({ custom_message: e.target.value })}
            className="w-full px-3 py-1.5 text-sm border border-gray-300 rounded-md"
          />
        </FormField>
        <label className="flex items-center gap-2 text-sm">
          <input
            type="checkbox"
            checked={data.assume_success}
            onChange={(e) => onUpdate({ assume_success: e.target.checked })}
          />
          Asumir éxito si la aserción pasa
        </label>
      </SectionCard>
    </div>
  );
}

// ----------------------------------------------------------------------------
// RegexExtractor
// ----------------------------------------------------------------------------

function RegexExtractorEdit({ data, onUpdate }: ChildEditorProps<RegexExtractorModel>) {
  return (
    <div className="p-6 max-w-4xl space-y-4">
      <div className="flex items-center gap-2">
        <Sliders className="w-6 h-6 text-purple-600" />
        <h2 className="text-xl font-semibold">{data.name || 'Regex Extractor'}</h2>
        <span className="text-sm text-gray-500">Regular Expression Extractor</span>
      </div>
      <SectionCard title="Configuración">
        <FormField label="Nombre">
          <input
            type="text"
            value={data.name || ''}
            onChange={(e) => onUpdate({ name: e.target.value })}
            className="w-full px-3 py-1.5 text-sm border border-gray-300 rounded-md"
          />
        </FormField>
        <FormField label="Nombre de variable (refname)" hint="se accede como ${refname}">
          <input
            type="text"
            value={data.refname}
            onChange={(e) => onUpdate({ refname: e.target.value })}
            className="w-full px-3 py-1.5 text-sm border border-gray-300 rounded-md font-mono"
            placeholder="token"
          />
        </FormField>
        <FormField label="Expresión regular">
          <input
            type="text"
            value={data.regex}
            onChange={(e) => onUpdate({ regex: e.target.value })}
            spellCheck={false}
            className="w-full px-3 py-1.5 text-sm border border-gray-300 rounded-md font-mono"
            placeholder='"token":"([^"]+)"'
          />
        </FormField>
        <div className="grid grid-cols-3 gap-3">
          <FormField label="Template">
            <InputWithFx
              value={data.template}
              onChange={(v) => onUpdate({ template: v })}
              placeholder="$1$"
              className="flex-1 px-3 py-1.5 text-sm border border-gray-300 rounded-md font-mono"
            />
          </FormField>
          <FormField label="Match number">
            <input
              type="text"
              value={data.match_number}
              onChange={(e) => onUpdate({ match_number: e.target.value })}
              className="w-full px-3 py-1.5 text-sm border border-gray-300 rounded-md"
              placeholder="1"
            />
          </FormField>
          <FormField label="Default">
            <InputWithFx
              value={data.default}
              onChange={(v) => onUpdate({ default: v })}
              placeholder="NOT_FOUND"
              className="flex-1 px-3 py-1.5 text-sm border border-gray-300 rounded-md font-mono"
            />
          </FormField>
        </div>
        <FormField label="Aplicar sobre">
          <select
            value={data.use_headers}
            onChange={(e) => onUpdate({ use_headers: e.target.value as RegexExtractorModel['use_headers'] })}
            className="w-full px-3 py-1.5 text-sm border border-gray-300 rounded-md"
          >
            <option value="false">Body de la respuesta</option>
            <option value="true">Response Headers</option>
            <option value="URL">URL</option>
            <option value="code">Response code</option>
            <option value="message">Response message</option>
          </select>
        </FormField>
      </SectionCard>
    </div>
  );
}

// ----------------------------------------------------------------------------
// JsonExtractor
// ----------------------------------------------------------------------------

function JsonExtractorEdit({ data, onUpdate }: ChildEditorProps<JsonExtractorModel>) {
  return (
    <div className="p-6 max-w-4xl space-y-4">
      <div className="flex items-center gap-2">
        <Sliders className="w-6 h-6 text-purple-600" />
        <h2 className="text-xl font-semibold">{data.name || 'JSON Extractor'}</h2>
        <span className="text-sm text-gray-500">JSON Post-Processor</span>
      </div>
      <SectionCard title="Configuración">
        <FormField label="Nombre">
          <input
            type="text"
            value={data.name || ''}
            onChange={(e) => onUpdate({ name: e.target.value })}
            className="w-full px-3 py-1.5 text-sm border border-gray-300 rounded-md"
          />
        </FormField>
        <FormField label="Refname" hint="se accede como ${refname}">
          <input
            type="text"
            value={data.refname}
            onChange={(e) => onUpdate({ refname: e.target.value })}
            className="w-full px-3 py-1.5 text-sm border border-gray-300 rounded-md font-mono"
          />
        </FormField>
        <FormField label="JSON Path">
          <input
            type="text"
            value={data.json_path}
            onChange={(e) => onUpdate({ json_path: e.target.value })}
            spellCheck={false}
            className="w-full px-3 py-1.5 text-sm border border-gray-300 rounded-md font-mono"
            placeholder="$.data.token"
          />
        </FormField>
        <div className="grid grid-cols-2 gap-3">
          <FormField label="Match number">
            <input
              type="text"
              value={data.match_number}
              onChange={(e) => onUpdate({ match_number: e.target.value })}
              className="w-full px-3 py-1.5 text-sm border border-gray-300 rounded-md"
            />
          </FormField>
          <FormField label="Default">
            <input
              type="text"
              value={data.default}
              onChange={(e) => onUpdate({ default: e.target.value })}
              className="w-full px-3 py-1.5 text-sm border border-gray-300 rounded-md font-mono"
            />
          </FormField>
        </div>
      </SectionCard>
    </div>
  );
}

// ----------------------------------------------------------------------------
// XPathExtractor
// ----------------------------------------------------------------------------

function XPathExtractorEdit({ data, onUpdate }: ChildEditorProps<XPathExtractorModel>) {
  return (
    <div className="p-6 max-w-4xl space-y-4">
      <div className="flex items-center gap-2">
        <Sliders className="w-6 h-6 text-purple-600" />
        <h2 className="text-xl font-semibold">{data.name || 'XPath Extractor'}</h2>
      </div>
      <SectionCard title="Configuración">
        <FormField label="Nombre">
          <input
            type="text"
            value={data.name || ''}
            onChange={(e) => onUpdate({ name: e.target.value })}
            className="w-full px-3 py-1.5 text-sm border border-gray-300 rounded-md"
          />
        </FormField>
        <FormField label="Refname">
          <input
            type="text"
            value={data.refname}
            onChange={(e) => onUpdate({ refname: e.target.value })}
            className="w-full px-3 py-1.5 text-sm border border-gray-300 rounded-md font-mono"
          />
        </FormField>
        <FormField label="XPath Query">
          <input
            type="text"
            value={data.xpath}
            onChange={(e) => onUpdate({ xpath: e.target.value })}
            spellCheck={false}
            className="w-full px-3 py-1.5 text-sm border border-gray-300 rounded-md font-mono"
            placeholder="//book[1]/title"
          />
        </FormField>
        <FormField label="Default">
          <input
            type="text"
            value={data.default}
            onChange={(e) => onUpdate({ default: e.target.value })}
            className="w-full px-3 py-1.5 text-sm border border-gray-300 rounded-md font-mono"
          />
        </FormField>
      </SectionCard>
    </div>
  );
}

// ----------------------------------------------------------------------------
// BoundaryExtractor
// ----------------------------------------------------------------------------

function BoundaryExtractorEdit({ data, onUpdate }: ChildEditorProps<BoundaryExtractorModel>) {
  return (
    <div className="p-6 max-w-4xl space-y-4">
      <div className="flex items-center gap-2">
        <Sliders className="w-6 h-6 text-purple-600" />
        <h2 className="text-xl font-semibold">{data.name || 'Boundary Extractor'}</h2>
      </div>
      <SectionCard title="Configuración">
        <FormField label="Nombre">
          <input
            type="text"
            value={data.name || ''}
            onChange={(e) => onUpdate({ name: e.target.value })}
            className="w-full px-3 py-1.5 text-sm border border-gray-300 rounded-md"
          />
        </FormField>
        <FormField label="Refname">
          <input
            type="text"
            value={data.refname}
            onChange={(e) => onUpdate({ refname: e.target.value })}
            className="w-full px-3 py-1.5 text-sm border border-gray-300 rounded-md font-mono"
          />
        </FormField>
        <div className="grid grid-cols-2 gap-3">
          <FormField label="Left boundary">
            <input
              type="text"
              value={data.left_boundary}
              onChange={(e) => onUpdate({ left_boundary: e.target.value })}
              spellCheck={false}
              className="w-full px-3 py-1.5 text-sm border border-gray-300 rounded-md font-mono"
              placeholder='"token":"'
            />
          </FormField>
          <FormField label="Right boundary">
            <input
              type="text"
              value={data.right_boundary}
              onChange={(e) => onUpdate({ right_boundary: e.target.value })}
              spellCheck={false}
              className="w-full px-3 py-1.5 text-sm border border-gray-300 rounded-md font-mono"
              placeholder='"'
            />
          </FormField>
        </div>
        <div className="grid grid-cols-2 gap-3">
          <FormField label="Match number">
            <input
              type="text"
              value={data.match_number}
              onChange={(e) => onUpdate({ match_number: e.target.value })}
              className="w-full px-3 py-1.5 text-sm border border-gray-300 rounded-md"
            />
          </FormField>
          <FormField label="Default">
            <input
              type="text"
              value={data.default}
              onChange={(e) => onUpdate({ default: e.target.value })}
              className="w-full px-3 py-1.5 text-sm border border-gray-300 rounded-md font-mono"
            />
          </FormField>
        </div>
      </SectionCard>
    </div>
  );
}

// ----------------------------------------------------------------------------
// Timers
// ----------------------------------------------------------------------------

function ConstantTimerEdit({ data, onUpdate }: ChildEditorProps<ConstantTimerModel>) {
  return (
    <div className="p-6 max-w-4xl space-y-4">
      <div className="flex items-center gap-2">
        <Clock className="w-6 h-6 text-orange-600" />
        <h2 className="text-xl font-semibold">{data.name || 'Constant Timer'}</h2>
      </div>
      <SectionCard title="Configuración">
        <FormField label="Nombre">
          <input
            type="text"
            value={data.name || ''}
            onChange={(e) => onUpdate({ name: e.target.value })}
            className="w-full px-3 py-1.5 text-sm border border-gray-300 rounded-md"
          />
        </FormField>
        <FormField label="Delay (ms)">
          <input
            type="number"
            min={0}
            value={data.delay_ms}
            onChange={(e) => onUpdate({ delay_ms: parseInt(e.target.value) || 0 })}
            className="w-48 px-3 py-1.5 text-sm border border-gray-300 rounded-md"
          />
        </FormField>
      </SectionCard>
    </div>
  );
}

function UniformRandomTimerEdit({ data, onUpdate }: ChildEditorProps<UniformRandomTimerModel>) {
  return (
    <div className="p-6 max-w-4xl space-y-4">
      <div className="flex items-center gap-2">
        <Clock className="w-6 h-6 text-orange-600" />
        <h2 className="text-xl font-semibold">{data.name || 'Uniform Random Timer'}</h2>
      </div>
      <SectionCard title="Configuración">
        <FormField label="Nombre">
          <input
            type="text"
            value={data.name || ''}
            onChange={(e) => onUpdate({ name: e.target.value })}
            className="w-full px-3 py-1.5 text-sm border border-gray-300 rounded-md"
          />
        </FormField>
        <div className="grid grid-cols-2 gap-3">
          <FormField label="Constant delay (ms)">
            <input
              type="number"
              min={0}
              value={data.constant_delay_ms}
              onChange={(e) => onUpdate({ constant_delay_ms: parseInt(e.target.value) || 0 })}
              className="w-full px-3 py-1.5 text-sm border border-gray-300 rounded-md"
            />
          </FormField>
          <FormField label="Random max (ms)" hint="suma uniformemente entre 0 y este valor">
            <input
              type="number"
              min={0}
              value={data.random_delay_ms}
              onChange={(e) => onUpdate({ random_delay_ms: parseInt(e.target.value) || 0 })}
              className="w-full px-3 py-1.5 text-sm border border-gray-300 rounded-md"
            />
          </FormField>
        </div>
      </SectionCard>
    </div>
  );
}

function GaussianRandomTimerEdit({ data, onUpdate }: ChildEditorProps<GaussianRandomTimerModel>) {
  return (
    <div className="p-6 max-w-4xl space-y-4">
      <div className="flex items-center gap-2">
        <Clock className="w-6 h-6 text-orange-600" />
        <h2 className="text-xl font-semibold">{data.name || 'Gaussian Random Timer'}</h2>
      </div>
      <SectionCard title="Configuración">
        <FormField label="Nombre">
          <input
            type="text"
            value={data.name || ''}
            onChange={(e) => onUpdate({ name: e.target.value })}
            className="w-full px-3 py-1.5 text-sm border border-gray-300 rounded-md"
          />
        </FormField>
        <div className="grid grid-cols-2 gap-3">
          <FormField label="Constant delay (ms)">
            <input
              type="number"
              min={0}
              value={data.constant_delay_ms}
              onChange={(e) => onUpdate({ constant_delay_ms: parseInt(e.target.value) || 0 })}
              className="w-full px-3 py-1.5 text-sm border border-gray-300 rounded-md"
            />
          </FormField>
          <FormField label="Deviation (ms)">
            <input
              type="number"
              min={0}
              value={data.deviation_ms}
              onChange={(e) => onUpdate({ deviation_ms: parseInt(e.target.value) || 0 })}
              className="w-full px-3 py-1.5 text-sm border border-gray-300 rounded-md"
            />
          </FormField>
        </div>
      </SectionCard>
    </div>
  );
}


// ============================================================================
// Sprint 2.4e — Paneles de configuración global
// ============================================================================

// ----------------------------------------------------------------------------
// TestPlan
// ----------------------------------------------------------------------------

function TestPlanEditPanel({
  tp,
  onUpdate,
}: {
  tp: TestPlanModel;
  onUpdate: (u: Partial<TestPlanModel>) => void;
}) {
  return (
    <div className="p-6 max-w-4xl space-y-4">
      <div className="flex items-center gap-2">
        <FileCode className="w-6 h-6 text-gray-700" />
        <h2 className="text-xl font-semibold">{tp.name || 'Test Plan'}</h2>
      </div>
      <SectionCard title="General">
        <FormField label="Nombre">
          <input
            type="text"
            value={tp.name || ''}
            onChange={(e) => onUpdate({ name: e.target.value })}
            className="w-full px-3 py-1.5 text-sm border border-gray-300 rounded-md"
          />
        </FormField>
        <FormField label="Comentarios">
          <textarea
            value={tp.comments || ''}
            onChange={(e) => onUpdate({ comments: e.target.value })}
            rows={3}
            className="w-full px-3 py-1.5 text-sm border border-gray-300 rounded-md"
          />
        </FormField>
        <div className="flex flex-col gap-2">
          <label className="flex items-center gap-2 text-sm">
            <input
              type="checkbox"
              checked={tp.functional_mode}
              onChange={(e) => onUpdate({ functional_mode: e.target.checked })}
            />
            Modo funcional (guardar response data de todos los samples)
          </label>
          <label className="flex items-center gap-2 text-sm">
            <input
              type="checkbox"
              checked={tp.serialize_threadgroups}
              onChange={(e) => onUpdate({ serialize_threadgroups: e.target.checked })}
            />
            Ejecutar Thread Groups en serie (no en paralelo)
          </label>
          <label className="flex items-center gap-2 text-sm">
            <input
              type="checkbox"
              checked={tp.tearDown_on_shutdown}
              onChange={(e) => onUpdate({ tearDown_on_shutdown: e.target.checked })}
            />
            Ejecutar tearDown al detener (si los hay)
          </label>
        </div>
      </SectionCard>
    </div>
  );
}

// ----------------------------------------------------------------------------
// User Defined Variables
// ----------------------------------------------------------------------------

function UDVsEditPanel({
  udvs,
  onUpdate,
}: {
  udvs: UserDefinedVariable[];
  onUpdate: (u: UserDefinedVariable[]) => void;
}) {
  const addVar = () => onUpdate([...udvs, { name: '', value: '', metadata: '=' }]);
  const updateVar = (idx: number, updates: Partial<UserDefinedVariable>) =>
    onUpdate(udvs.map((v, i) => (i === idx ? { ...v, ...updates } : v)));
  const removeVar = (idx: number) => onUpdate(udvs.filter((_, i) => i !== idx));

  return (
    <div className="p-6 max-w-4xl space-y-4">
      <div className="flex items-center gap-2">
        <Sliders className="w-6 h-6 text-cyan-600" />
        <h2 className="text-xl font-semibold">Variables Globales (UDV)</h2>
        <span className="text-sm text-gray-500">
          {udvs.length} variable{udvs.length !== 1 ? 's' : ''}
        </span>
      </div>
      <SectionCard title="Variables">
        {udvs.length === 0 && (
          <p className="text-xs text-gray-500 italic">Sin variables. Click "+ Añadir" para agregar una.</p>
        )}
        {udvs.length > 0 && (
          <div className="grid grid-cols-12 gap-2 px-2 text-xs font-medium text-gray-600">
            <div className="col-span-4">Nombre</div>
            <div className="col-span-7">Valor</div>
            <div className="col-span-1"></div>
          </div>
        )}
        {udvs.map((v, idx) => (
          <div key={idx} className="grid grid-cols-12 gap-2 items-center">
            <input
              type="text"
              value={v.name}
              onChange={(e) => updateVar(idx, { name: e.target.value })}
              placeholder="host"
              className="col-span-4 px-2 py-1 text-sm border border-gray-300 rounded font-mono"
            />
            <div className="col-span-7">
              <InputWithFx
                value={v.value}
                onChange={(val) => updateVar(idx, { value: val })}
                placeholder="api.example.com"
                className="flex-1 px-2 py-1 text-sm border border-gray-300 rounded font-mono"
              />
            </div>
            <button
              onClick={() => removeVar(idx)}
              className="col-span-1 p-1 text-red-500 hover:bg-red-50 rounded justify-self-end"
              title="Eliminar variable"
            >
              <X className="w-4 h-4" />
            </button>
          </div>
        ))}
        <button
          onClick={addVar}
          className="text-sm text-indigo-600 hover:bg-indigo-50 px-3 py-1.5 rounded font-medium"
        >
          + Añadir variable
        </button>
      </SectionCard>
      <p className="text-xs text-gray-500">
        Las variables se acceden con la sintaxis{' '}
        <code className="bg-gray-100 px-1 rounded font-mono">${'{nombre}'}</code> en cualquier campo del script.
      </p>
    </div>
  );
}

// ----------------------------------------------------------------------------
// CSV Data Set
// ----------------------------------------------------------------------------

function CSVDataSetEditPanel({
  ds,
  onUpdate,
}: {
  ds: CSVDataSetModel;
  onUpdate: (u: Partial<CSVDataSetModel>) => void;
}) {
  const updateVarNames = (text: string) => {
    onUpdate({
      variable_names: text
        .split(',')
        .map((s) => s.trim())
        .filter((s) => s.length > 0),
    });
  };

  return (
    <div className="p-6 max-w-4xl space-y-4">
      <div className="flex items-center gap-2">
        <Database className="w-6 h-6 text-emerald-600" />
        <h2 className="text-xl font-semibold">{ds.testname || 'CSV Data Set'}</h2>
      </div>
      <SectionCard title="Archivo y variables">
        <FormField label="Nombre del data set">
          <input
            type="text"
            value={ds.testname || ''}
            onChange={(e) => onUpdate({ testname: e.target.value })}
            className="w-full px-3 py-1.5 text-sm border border-gray-300 rounded-md"
          />
        </FormField>
        <FormField label="Ruta del archivo CSV">
          <InputWithFx
            value={ds.filename || ''}
            onChange={(v) => onUpdate({ filename: v })}
            placeholder="data/usuarios.csv"
            className="flex-1 px-3 py-1.5 text-sm border border-gray-300 rounded-md font-mono"
          />
        </FormField>
        <FormField label="Variables (separadas por coma)" hint="orden = columnas del CSV">
          <input
            type="text"
            value={ds.variable_names.join(',')}
            onChange={(e) => updateVarNames(e.target.value)}
            className="w-full px-3 py-1.5 text-sm border border-gray-300 rounded-md font-mono"
            placeholder="username,password,email"
          />
        </FormField>
      </SectionCard>
      <SectionCard title="Formato y comportamiento">
        <div className="grid grid-cols-2 gap-3">
          <FormField label="Delimitador">
            <input
              type="text"
              value={ds.delimiter}
              onChange={(e) => onUpdate({ delimiter: e.target.value })}
              maxLength={3}
              className="w-full px-3 py-1.5 text-sm border border-gray-300 rounded-md font-mono"
            />
          </FormField>
          <FormField label="Encoding">
            <input
              type="text"
              value={ds.file_encoding || ''}
              onChange={(e) => onUpdate({ file_encoding: e.target.value })}
              placeholder="UTF-8"
              className="w-full px-3 py-1.5 text-sm border border-gray-300 rounded-md"
            />
          </FormField>
        </div>
        <FormField label="Modo de compartir entre threads">
          <select
            value={ds.share_mode}
            onChange={(e) => onUpdate({ share_mode: e.target.value as CSVShareMode })}
            className="w-full px-3 py-1.5 text-sm border border-gray-300 rounded-md"
          >
            <option value="shareMode.all">All threads (compartido global)</option>
            <option value="shareMode.group">Current thread group</option>
            <option value="shareMode.thread">Current thread (cada thread tiene su propio cursor)</option>
          </select>
        </FormField>
        <div className="grid grid-cols-2 gap-2">
          <label className="flex items-center gap-2 text-sm">
            <input
              type="checkbox"
              checked={ds.ignore_first_line}
              onChange={(e) => onUpdate({ ignore_first_line: e.target.checked })}
            />
            Ignorar primera línea (header)
          </label>
          <label className="flex items-center gap-2 text-sm">
            <input
              type="checkbox"
              checked={ds.recycle}
              onChange={(e) => onUpdate({ recycle: e.target.checked })}
            />
            Reciclar al final del archivo
          </label>
          <label className="flex items-center gap-2 text-sm">
            <input
              type="checkbox"
              checked={ds.stop_thread}
              onChange={(e) => onUpdate({ stop_thread: e.target.checked })}
            />
            Detener hilo al final (si no recicla)
          </label>
          <label className="flex items-center gap-2 text-sm">
            <input
              type="checkbox"
              checked={ds.quoted_data}
              onChange={(e) => onUpdate({ quoted_data: e.target.checked })}
            />
            Datos entre comillas
          </label>
        </div>
      </SectionCard>
    </div>
  );
}

// ----------------------------------------------------------------------------
// HTTP Defaults
// ----------------------------------------------------------------------------

function HttpDefaultsEditPanel({
  hd,
  onUpdate,
}: {
  hd: HttpDefaultsModel;
  onUpdate: (u: Partial<HttpDefaultsModel>) => void;
}) {
  return (
    <div className="p-6 max-w-4xl space-y-4">
      <div className="flex items-center gap-2">
        <Network className="w-6 h-6 text-gray-700" />
        <h2 className="text-xl font-semibold">HTTP Request Defaults</h2>
      </div>
      <SectionCard title="Valores por defecto para todos los samplers">
        <div className="grid grid-cols-2 gap-3">
          <FormField label="Protocolo">
            <select
              value={hd.protocol || ''}
              onChange={(e) => onUpdate({ protocol: e.target.value })}
              className="w-full px-3 py-1.5 text-sm border border-gray-300 rounded-md font-mono"
            >
              <option value="">(vacío)</option>
              <option value="http">http</option>
              <option value="https">https</option>
            </select>
          </FormField>
          <FormField label="Dominio">
            <input
              type="text"
              value={hd.domain || ''}
              onChange={(e) => onUpdate({ domain: e.target.value })}
              placeholder="${host}"
              className="w-full px-3 py-1.5 text-sm border border-gray-300 rounded-md font-mono"
            />
          </FormField>
          <FormField label="Puerto">
            <input
              type="text"
              value={hd.port || ''}
              onChange={(e) => onUpdate({ port: e.target.value })}
              placeholder="${port}"
              className="w-full px-3 py-1.5 text-sm border border-gray-300 rounded-md font-mono"
            />
          </FormField>
          <FormField label="Encoding">
            <input
              type="text"
              value={hd.encoding || ''}
              onChange={(e) => onUpdate({ encoding: e.target.value })}
              placeholder="UTF-8"
              className="w-full px-3 py-1.5 text-sm border border-gray-300 rounded-md"
            />
          </FormField>
        </div>
        <FormField label="Path base">
          <input
            type="text"
            value={hd.path || ''}
            onChange={(e) => onUpdate({ path: e.target.value })}
            placeholder="/api/v1"
            className="w-full px-3 py-1.5 text-sm border border-gray-300 rounded-md font-mono"
          />
        </FormField>
      </SectionCard>
      <p className="text-xs text-gray-500">
        Los samplers HTTP que no especifiquen dominio/puerto/protocolo heredan estos valores.
      </p>
    </div>
  );
}

// ----------------------------------------------------------------------------
// Cookie Manager
// ----------------------------------------------------------------------------

function CookieManagerEditPanel({
  cm,
  onUpdate,
}: {
  cm: CookieManagerModel;
  onUpdate: (u: Partial<CookieManagerModel>) => void;
}) {
  return (
    <div className="p-6 max-w-4xl space-y-4">
      <h2 className="text-xl font-semibold flex items-center gap-2">
        <Settings className="w-6 h-6 text-gray-700" />
        HTTP Cookie Manager
      </h2>
      <SectionCard title="Configuración">
        <label className="flex items-center gap-2 text-sm">
          <input
            type="checkbox"
            checked={cm.enabled}
            onChange={(e) => onUpdate({ enabled: e.target.checked })}
          />
          Habilitado
        </label>
        <label className="flex items-center gap-2 text-sm">
          <input
            type="checkbox"
            checked={cm.clear_each_iteration}
            onChange={(e) => onUpdate({ clear_each_iteration: e.target.checked })}
          />
          Limpiar cookies en cada iteración
        </label>
        <FormField label="Policy" hint="ej. standard, strict, netscape">
          <input
            type="text"
            value={cm.policy || ''}
            onChange={(e) => onUpdate({ policy: e.target.value })}
            placeholder="standard"
            className="w-full px-3 py-1.5 text-sm border border-gray-300 rounded-md font-mono"
          />
        </FormField>
      </SectionCard>
    </div>
  );
}

// ----------------------------------------------------------------------------
// Cache Manager
// ----------------------------------------------------------------------------

function CacheManagerEditPanel({
  cm,
  onUpdate,
}: {
  cm: CacheManagerModel;
  onUpdate: (u: Partial<CacheManagerModel>) => void;
}) {
  return (
    <div className="p-6 max-w-4xl space-y-4">
      <h2 className="text-xl font-semibold flex items-center gap-2">
        <Settings className="w-6 h-6 text-gray-700" />
        HTTP Cache Manager
      </h2>
      <SectionCard title="Configuración">
        <label className="flex items-center gap-2 text-sm">
          <input
            type="checkbox"
            checked={cm.enabled}
            onChange={(e) => onUpdate({ enabled: e.target.checked })}
          />
          Habilitado
        </label>
        <label className="flex items-center gap-2 text-sm">
          <input
            type="checkbox"
            checked={cm.clear_each_iteration}
            onChange={(e) => onUpdate({ clear_each_iteration: e.target.checked })}
          />
          Limpiar caché en cada iteración
        </label>
        <label className="flex items-center gap-2 text-sm">
          <input
            type="checkbox"
            checked={cm.use_expires}
            onChange={(e) => onUpdate({ use_expires: e.target.checked })}
          />
          Usar header Expires
        </label>
      </SectionCard>
    </div>
  );
}


// ============================================================================
// Sprint 2.4-HF2: Data Files
// ============================================================================

interface DataFilesPanelProps {
  designId: string;
  dataFiles: AIDesignDataFile[];
  loading: boolean;
  onReload: () => void;
  onReloadStructure: () => void;
}

function DataFilesPanel({ designId, dataFiles, loading, onReload, onReloadStructure }: DataFilesPanelProps) {
  const [uploading, setUploading] = useState(false);
  const [uploadError, setUploadError] = useState<string | null>(null);
  const fileInputRef = useRef<HTMLInputElement>(null);
  const [delimiter, setDelimiter] = useState(',');
  const [hasHeader, setHasHeader] = useState(true);
  // Sprint 2.5c.1 (HF2.1): variables declaradas → autocrea CSV Data Set
  const [variableNames, setVariableNames] = useState('');
  // Sprint 2.5c.1-HF12 (UX): modal obligatorio de variables si no se declararon
  const [showVariablesPrompt, setShowVariablesPrompt] = useState(false);
  const [pendingVariables, setPendingVariables] = useState('');
  const [pendingFile, setPendingFile] = useState<File | null>(null);

  // Al seleccionar archivo: si no hay variables declaradas, exigirlas en modal.
  const handleFilePicked = (file: File) => {
    if (variableNames.trim()) {
      void doUpload(file, variableNames.trim());
    } else {
      setPendingFile(file);
      setPendingVariables('');
      setShowVariablesPrompt(true);
    }
  };

  const doUpload = async (file: File, declared: string) => {
    setUploading(true);
    setUploadError(null);
    try {
      await aiDesignDataFilesAPI.upload(
        designId,
        file,
        delimiter,
        hasHeader ? 'true' : 'false',
        'UTF-8',
        declared,
      );
      onReload();
      // Con variables declaradas el backend autocreó un CSV Data Set →
      // refrescar el árbol para que aparezca.
      if (declared) {
        onReloadStructure();
      }
      setVariableNames('');
      setShowVariablesPrompt(false);
      setPendingFile(null);
      setPendingVariables('');
    } catch (e: any) {
      setUploadError(e?.response?.data?.detail || e?.message || 'Error al subir');
    } finally {
      setUploading(false);
      if (fileInputRef.current) fileInputRef.current.value = '';
    }
  };

  const handleConfirmVariables = () => {
    if (!pendingVariables.trim() || !pendingFile) return;
    setVariableNames(pendingVariables.trim());
    void doUpload(pendingFile, pendingVariables.trim());
  };

  const handleCancelUpload = () => {
    setShowVariablesPrompt(false);
    setPendingVariables('');
    setPendingFile(null);
    if (fileInputRef.current) fileInputRef.current.value = '';
  };

  const handleDelete = async (fileId: string) => {
    if (!confirm('¿Eliminar este archivo?')) return;
    try {
      await aiDesignDataFilesAPI.remove(designId, fileId);
      onReload();
    } catch (e) {
      console.error('Error eliminando:', e);
    }
  };

  return (
    <div className="p-6 max-w-4xl space-y-4">
      <div className="flex items-center gap-2">
        <Database className="w-6 h-6 text-emerald-600" />
        <h2 className="text-xl font-semibold">Data Files</h2>
        <span className="text-sm text-gray-500">
          {dataFiles.length} archivo{dataFiles.length !== 1 ? 's' : ''}
        </span>
      </div>

      <SectionCard title="Subir nuevo CSV">
        <div className="grid grid-cols-2 gap-3">
          <FormField label="Delimitador">
            <select
              value={delimiter}
              onChange={(e) => setDelimiter(e.target.value)}
              className="w-full px-3 py-1.5 text-sm border border-gray-300 rounded-md"
            >
              <option value=",">Coma (,)</option>
              <option value=";">Punto y coma (;)</option>
              <option value="\t">Tabulador</option>
              <option value="|">Pipe (|)</option>
              <option value="auto">Detectar automáticamente</option>
            </select>
          </FormField>
          <FormField label="">
            <label className="flex items-center gap-2 text-sm pt-1.5">
              <input
                type="checkbox"
                checked={hasHeader}
                onChange={(e) => setHasHeader(e.target.checked)}
              />
              Primera fila es header
            </label>
          </FormField>
        </div>
        <FormField label="Nombres de variables JMeter (separadas por coma)">
          <input
            type="text"
            value={variableNames}
            onChange={(e) => setVariableNames(e.target.value)}
            placeholder="ej. firstname,lastname"
            className="w-full px-3 py-1.5 text-sm border border-gray-300 rounded-md font-mono"
          />
          <p className="text-xs text-gray-500 mt-1">
            Se autocrea un CSV Data Set en el árbol apuntando a este archivo
            (filename <code>${'{Data}'}/&lt;archivo&gt;</code>, portable para descarga).
            Si no las declaras aquí, se te pedirán al seleccionar el archivo.
          </p>
        </FormField>
        <input
          ref={fileInputRef}
          type="file"
          accept=".csv,.txt"
          className="hidden"
          onChange={(e) => {
            const f = e.target.files?.[0];
            if (f) handleFilePicked(f);
          }}
        />
        <button
          onClick={() => fileInputRef.current?.click()}
          disabled={uploading}
          className="px-4 py-2 bg-emerald-600 text-white text-sm font-medium rounded hover:bg-emerald-700 disabled:opacity-50"
        >
          {uploading ? 'Subiendo...' : '+ Subir CSV'}
        </button>
        {uploadError && (
          <div className="bg-red-50 border border-red-200 rounded p-3 text-sm text-red-700">
            {uploadError}
          </div>
        )}
      </SectionCard>

      <SectionCard title="Archivos asociados">
        {loading ? (
          <p className="text-sm text-gray-500">Cargando...</p>
        ) : dataFiles.length === 0 ? (
          <p className="text-sm text-gray-500 italic">Aún no hay archivos.</p>
        ) : (
          <ul className="space-y-2">
            {dataFiles.map((df) => (
              <li key={df.id} className="border border-gray-200 rounded p-3 flex items-center justify-between">
                <div>
                  <div className="font-medium text-sm">{df.original_filename}</div>
                  <div className="text-xs text-gray-500">
                    {df.row_count} filas · {df.columns.length} columnas · {(df.file_size / 1024).toFixed(1)} KB
                  </div>
                  <div className="text-xs text-gray-600 mt-1">
                    Columnas: {df.columns.join(', ')}
                  </div>
                </div>
                <button
                  onClick={() => handleDelete(df.id)}
                  className="text-red-500 hover:bg-red-50 p-1.5 rounded"
                  title="Eliminar"
                >
                  <X className="w-4 h-4" />
                </button>
              </li>
            ))}
          </ul>
        )}
      </SectionCard>

      <div className="bg-blue-50 border border-blue-200 rounded p-3 text-xs text-blue-800">
        <strong>Tip:</strong> los archivos subidos quedan asociados al diseño. Para usarlos en un sampler, crea un CSV Data Set en el árbol y referencia el archivo desde el campo "Archivo CSV".
      </div>

      {/* Sprint 2.5c.1-HF12 — modal obligatorio de variables */}
      {showVariablesPrompt && (
        <div className="fixed inset-0 bg-black/40 z-50 flex items-center justify-center p-4">
          <div className="bg-white rounded-lg shadow-xl w-[500px] max-w-full">
            <div className="px-5 py-4 border-b border-gray-200">
              <div className="flex items-center gap-2">
                <AlertTriangle className="w-5 h-5 text-amber-600" />
                <h3 className="text-lg font-semibold">Variables JMeter requeridas</h3>
              </div>
            </div>

            <div className="px-5 py-4">
              <p className="text-sm text-gray-700 mb-3">
                Para que <strong>{pendingFile?.name}</strong> sea utilizable por JMeter, necesitas
                declarar las variables que se mapearán a cada columna del archivo.
              </p>

              <div className="bg-blue-50 border border-blue-200 rounded p-3 mb-3 text-xs">
                <p className="font-medium text-blue-900 mb-1">¿Cómo funciona?</p>
                <p className="text-blue-800">
                  Si tu archivo tiene 2 columnas (ej. <code className="bg-blue-100 px-1">Sally,Brown</code>) y
                  declaras <code className="bg-blue-100 px-1">firstname,lastname</code>, entonces
                  en tu JMX podrás usar <code className="bg-blue-100 px-1">{'${firstname}'}</code> y <code className="bg-blue-100 px-1">{'${lastname}'}</code>.
                </p>
              </div>

              <label className="block text-xs font-medium mb-1">
                Nombres de variables (separadas por coma)
              </label>
              <input
                type="text"
                value={pendingVariables}
                onChange={(e) => setPendingVariables(e.target.value)}
                placeholder="ej. firstname,lastname"
                autoFocus
                className="w-full px-3 py-2 text-sm border border-gray-300 rounded-md font-mono focus:ring-2 focus:ring-indigo-200 focus:border-indigo-400"
                onKeyDown={(e) => {
                  if (e.key === 'Enter' && pendingVariables.trim()) {
                    handleConfirmVariables();
                  }
                }}
              />
              <p className="text-xs text-gray-500 mt-1">
                El número de variables debe coincidir con el número de columnas del CSV.
              </p>
            </div>

            <div className="flex justify-end gap-2 px-5 py-3 border-t border-gray-200 bg-gray-50">
              <button
                onClick={handleCancelUpload}
                className="px-3 py-1.5 text-sm border border-gray-300 rounded hover:bg-white"
              >
                Cancelar
              </button>
              <button
                onClick={handleConfirmVariables}
                disabled={!pendingVariables.trim() || uploading}
                className="px-3 py-1.5 text-sm bg-indigo-600 text-white rounded hover:bg-indigo-700 disabled:opacity-50 disabled:cursor-not-allowed"
              >
                {uploading ? 'Subiendo...' : 'Subir con variables'}
              </button>
            </div>
          </div>
        </div>
      )}
    </div>
  );
}

function DataFileDetailPanel({
  designId,
  fileId,
  onDeleted,
}: {
  designId: string;
  fileId: string;
  onDeleted: () => void;
}) {
  const [df, setDf] = useState<AIDesignDataFile | null>(null);
  const [preview, setPreview] = useState<AIDesignDataFilePreview | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    let cancelled = false;
    const load = async () => {
      setLoading(true);
      setError(null);
      try {
        const all = await aiDesignDataFilesAPI.list(designId);
        const found = all.find((x) => x.id === fileId);
        if (!found) {
          setError('Archivo no encontrado');
          return;
        }
        if (cancelled) return;
        setDf(found);
        const pv = await aiDesignDataFilesAPI.preview(designId, fileId);
        if (cancelled) return;
        setPreview(pv);
      } catch (e: any) {
        if (!cancelled) setError(e?.response?.data?.detail || e?.message || 'Error');
      } finally {
        if (!cancelled) setLoading(false);
      }
    };
    load();
    return () => {
      cancelled = true;
    };
  }, [designId, fileId]);

  const handleDelete = async () => {
    if (!confirm('¿Eliminar este archivo?')) return;
    await aiDesignDataFilesAPI.remove(designId, fileId);
    onDeleted();
  };

  if (loading) return <div className="p-6"><Loader2 className="w-5 h-5 animate-spin" /></div>;
  if (error || !df) return <NotFoundPanel kind="data_file" />;

  return (
    <div className="p-6 max-w-4xl space-y-4">
      <div className="flex items-center justify-between">
        <div className="flex items-center gap-2">
          <Database className="w-6 h-6 text-emerald-600" />
          <div>
            <h2 className="text-xl font-semibold">{df.original_filename}</h2>
            <p className="text-sm text-gray-500">
              {df.row_count} filas · {df.columns.length} columnas
            </p>
          </div>
        </div>
        <button
          onClick={handleDelete}
          className="px-3 py-1.5 text-sm text-red-600 border border-red-300 rounded hover:bg-red-50"
        >
          Eliminar archivo
        </button>
      </div>

      <SectionCard title="Información">
        <div className="grid grid-cols-2 gap-3 text-sm">
          <div><strong>Delimitador:</strong> <code className="bg-gray-100 px-1 rounded">{df.delimiter}</code></div>
          <div><strong>Encoding:</strong> {df.encoding}</div>
          <div><strong>Tamaño:</strong> {(df.file_size / 1024).toFixed(1)} KB</div>
          <div><strong>Filas:</strong> {df.row_count}</div>
        </div>
      </SectionCard>

      <SectionCard title="Columnas y variables JMeter">
        <p className="text-xs text-gray-600 mb-2">
          Por defecto cada columna del CSV se convierte en una variable JMeter con el mismo nombre.
          Las columnas aquí son: <code className="bg-gray-100 px-1 rounded font-mono">{df.columns.join(', ')}</code>
        </p>
        <p className="text-xs text-gray-600">
          Para usar este archivo en un sampler, ve a un CSV Data Set del árbol y pon{' '}
          <code className="bg-gray-100 px-1 rounded font-mono">{df.original_filename}</code> en el campo "Archivo CSV", y{' '}
          <code className="bg-gray-100 px-1 rounded font-mono">{df.columns.join(',')}</code> en "Variables".
        </p>
      </SectionCard>

      {preview && (
        <SectionCard title={`Preview (primeras ${preview.rows.length} filas)`}>
          <div className="overflow-x-auto">
            <table className="w-full text-xs border border-gray-200">
              <thead className="bg-gray-50">
                <tr>
                  {preview.columns.map((c, i) => (
                    <th key={i} className="text-left px-3 py-1.5 font-semibold text-gray-700 border-b border-gray-200">{c}</th>
                  ))}
                </tr>
              </thead>
              <tbody>
                {preview.rows.map((row, i) => (
                  <tr key={i} className="border-b border-gray-100">
                    {row.map((cell, j) => (
                      <td key={j} className="px-3 py-1 font-mono">{cell}</td>
                    ))}
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </SectionCard>
      )}
    </div>
  );
}


// ============================================================================
// Sprint 2.4-HF3: Function Helper (JMeter __functions)
// ============================================================================

interface FnParam {
  name: string;
  label: string;
  default?: string;
  hint?: string;
  type?: 'text' | 'select' | 'date_format';
  options?: string[];
}

interface JMeterFunction {
  name: string;
  category: string;
  syntax: string;
  description: string;
  params: FnParam[];
}

const DATE_FORMATS = [
  'yyyy-MM-dd',
  'yyyy-MM-dd HH:mm:ss',
  'dd/MM/yyyy',
  'dd-MM-yyyy HH:mm',
  "yyyy-MM-dd'T'HH:mm:ss",
  "yyyy-MM-dd'T'HH:mm:ss.SSS'Z'",
  'EEE, dd MMM yyyy HH:mm:ss zzz',
  'yyyyMMdd',
  'yyyyMMddHHmmss',
  'HH:mm:ss',
  'MM/dd/yyyy',
  'dd MMM yyyy',
];

const JMETER_FUNCTIONS: JMeterFunction[] = [
  // Aleatorios
  { name: '__Random', category: 'Aleatorios', syntax: '${__Random(min,max)}', description: 'Entero aleatorio entre min y max.', params: [
    { name: 'min', label: 'Mínimo', default: '1' },
    { name: 'max', label: 'Máximo', default: '100' },
  ]},
  { name: '__RandomString', category: 'Aleatorios', syntax: '${__RandomString(length,chars)}', description: 'String aleatorio.', params: [
    { name: 'length', label: 'Longitud', default: '10' },
    { name: 'chars', label: 'Caracteres permitidos', default: 'abcdefghijklmnopqrstuvwxyz0123456789' },
  ]},
  { name: '__UUID', category: 'Aleatorios', syntax: '${__UUID()}', description: 'UUID v4 aleatorio.', params: [] },
  { name: '__RandomFromMultipleVars', category: 'Aleatorios', syntax: '${__RandomFromMultipleVars(vars,separator)}', description: 'Elige aleatoriamente entre varias variables.', params: [
    { name: 'vars', label: 'Variables (separadas por pipe)', default: 'var1|var2|var3' },
    { name: 'separator', label: 'Separador interno', default: '|' },
  ]},

  // Fechas
  { name: '__time', category: 'Fechas', syntax: '${__time(format)}', description: 'Timestamp actual con formato.', params: [
    { name: 'format', label: 'Formato', default: 'yyyy-MM-dd', type: 'date_format' },
  ]},
  { name: '__timeShift', category: 'Fechas', syntax: '${__timeShift(format,date,shift,locale)}', description: 'Fecha desplazada (ej. P1D, -P2M, P3W).', params: [
    { name: 'format', label: 'Formato', default: 'yyyy-MM-dd', type: 'date_format' },
    { name: 'date', label: 'Fecha base (vacío = hoy)', default: '' },
    { name: 'shift', label: 'Desplazamiento', default: 'P1D', hint: 'ISO-8601: P1D, -P2M, P3W' },
    { name: 'locale', label: 'Locale (opcional)', default: '' },
  ]},
  { name: '__RandomDate', category: 'Fechas', syntax: '${__RandomDate(format,start,end,locale)}', description: 'Fecha aleatoria entre 2 fechas.', params: [
    { name: 'format', label: 'Formato', default: 'yyyy-MM-dd', type: 'date_format' },
    { name: 'start', label: 'Fecha inicio (vacío = hoy)', default: '' },
    { name: 'end', label: 'Fecha fin', default: '2030-12-31' },
    { name: 'locale', label: 'Locale (opcional)', default: '' },
  ]},
  { name: '__dateTimeConvert', category: 'Fechas', syntax: '${__dateTimeConvert(date,sourceFormat,targetFormat)}', description: 'Convierte fecha entre formatos.', params: [
    { name: 'date', label: 'Fecha origen', default: '' },
    { name: 'sourceFormat', label: 'Formato origen', default: 'yyyy-MM-dd', type: 'date_format' },
    { name: 'targetFormat', label: 'Formato destino', default: 'dd/MM/yyyy', type: 'date_format' },
  ]},

  // Contadores y matemáticas
  { name: '__counter', category: 'Contadores', syntax: '${__counter(per_user,varname)}', description: 'Contador incremental.', params: [
    { name: 'per_user', label: 'Por usuario', default: 'FALSE', type: 'select', options: ['TRUE', 'FALSE'] },
    { name: 'varname', label: 'Nombre variable (opcional)', default: '' },
  ]},
  { name: '__intSum', category: 'Contadores', syntax: '${__intSum(a,b)}', description: 'Suma de enteros.', params: [
    { name: 'a', label: 'A', default: '1' },
    { name: 'b', label: 'B', default: '1' },
  ]},
  { name: '__longSum', category: 'Contadores', syntax: '${__longSum(a,b)}', description: 'Suma de longs.', params: [
    { name: 'a', label: 'A', default: '1' },
    { name: 'b', label: 'B', default: '1' },
  ]},

  // Hilos y propiedades
  { name: '__threadNum', category: 'Hilos', syntax: '${__threadNum}', description: 'Número del hilo actual.', params: [] },
  { name: '__machineName', category: 'Hilos', syntax: '${__machineName()}', description: 'Nombre del host JMeter.', params: [] },
  { name: '__machineIP', category: 'Hilos', syntax: '${__machineIP()}', description: 'IP del host JMeter.', params: [] },
  { name: '__property', category: 'Hilos', syntax: '${__property(name,var,default)}', description: 'Propiedad de JMeter.', params: [
    { name: 'name', label: 'Nombre propiedad', default: '' },
    { name: 'var', label: 'Variable destino (opcional)', default: '' },
    { name: 'default', label: 'Default (opcional)', default: '' },
  ]},
  { name: '__P', category: 'Hilos', syntax: '${__P(name,default)}', description: 'Propiedad simplificada.', params: [
    { name: 'name', label: 'Nombre propiedad', default: '' },
    { name: 'default', label: 'Default', default: '' },
  ]},

  // Variables y archivos
  { name: '__V', category: 'Variables', syntax: '${__V(varname)}', description: 'Interpolar variable.', params: [
    { name: 'varname', label: 'Nombre variable', default: '' },
  ]},
  { name: '__eval', category: 'Variables', syntax: '${__eval(expression)}', description: 'Evaluar expresión.', params: [
    { name: 'expression', label: 'Expresión', default: '' },
  ]},
  { name: '__StringFromFile', category: 'Variables', syntax: '${__StringFromFile(filename)}', description: 'Lee línea de archivo.', params: [
    { name: 'filename', label: 'Archivo', default: '' },
  ]},

  // Strings
  { name: '__char', category: 'Strings', syntax: '${__char(int)}', description: 'Carácter desde código.', params: [
    { name: 'int', label: 'Código', default: '65' },
  ]},
  { name: '__changeCase', category: 'Strings', syntax: '${__changeCase(text,mode)}', description: 'Cambiar case de texto.', params: [
    { name: 'text', label: 'Texto', default: '' },
    { name: 'mode', label: 'Modo', default: 'UPPER', type: 'select', options: ['UPPER', 'LOWER', 'CAPITALIZE'] },
  ]},
  { name: '__urlencode', category: 'Strings', syntax: '${__urlencode(text)}', description: 'URL-encode texto.', params: [
    { name: 'text', label: 'Texto', default: '' },
  ]},
  { name: '__urldecode', category: 'Strings', syntax: '${__urldecode(text)}', description: 'URL-decode texto.', params: [
    { name: 'text', label: 'Texto', default: '' },
  ]},
  { name: '__escapeHtml', category: 'Strings', syntax: '${__escapeHtml(text)}', description: 'Escape HTML.', params: [
    { name: 'text', label: 'Texto', default: '' },
  ]},
];

function buildFunctionExpression(fn: JMeterFunction, values: Record<string, string>): string {
  if (fn.params.length === 0) return fn.syntax;
  const args = fn.params.map((p) => values[p.name] || '');
  return `\${${fn.name}(${args.join(',')})}`;
}

const FN_CATEGORIES = Array.from(new Set(JMETER_FUNCTIONS.map((f) => f.category)));

function FunctionHelperButton({ onInsert }: { onInsert: (expression: string) => void }) {
  const [open, setOpen] = useState(false);
  const [selectedFn, setSelectedFn] = useState<JMeterFunction | null>(null);
  const [values, setValues] = useState<Record<string, string>>({});
  const [activeCategory, setActiveCategory] = useState(FN_CATEGORIES[0]);
  const ref = useRef<HTMLDivElement>(null);

  useEffect(() => {
    if (selectedFn) {
      const initial: Record<string, string> = {};
      selectedFn.params.forEach((p) => {
        initial[p.name] = p.default || '';
      });
      setValues(initial);
    }
  }, [selectedFn]);

  useEffect(() => {
    const handleClickOutside = (e: MouseEvent) => {
      if (ref.current && !ref.current.contains(e.target as Node)) {
        setOpen(false);
        setSelectedFn(null);
      }
    };
    if (open) document.addEventListener('mousedown', handleClickOutside);
    return () => document.removeEventListener('mousedown', handleClickOutside);
  }, [open]);

  const handleInsert = () => {
    if (!selectedFn) return;
    onInsert(buildFunctionExpression(selectedFn, values));
    setOpen(false);
    setSelectedFn(null);
  };

  return (
    <div className="relative inline-block" ref={ref}>
      <button
        type="button"
        onClick={() => setOpen(!open)}
        className="px-2 py-1 text-xs font-mono text-indigo-700 bg-indigo-50 border border-indigo-200 rounded hover:bg-indigo-100"
        title="Insertar función JMeter"
      >
        fx
      </button>

      {open && (
        <div className="absolute z-50 right-0 top-8 w-[500px] bg-white border border-gray-300 rounded-lg shadow-xl">
          {!selectedFn ? (
            <>
              <div className="flex border-b border-gray-200 overflow-x-auto">
                {FN_CATEGORIES.map((c) => (
                  <button
                    key={c}
                    onClick={() => setActiveCategory(c)}
                    className={`px-3 py-2 text-xs whitespace-nowrap ${
                      activeCategory === c
                        ? 'bg-indigo-50 text-indigo-700 border-b-2 border-indigo-600'
                        : 'text-gray-600'
                    }`}
                  >
                    {c}
                  </button>
                ))}
              </div>
              <ul className="max-h-80 overflow-y-auto">
                {JMETER_FUNCTIONS.filter((f) => f.category === activeCategory).map((f) => (
                  <li
                    key={f.name}
                    onClick={() => setSelectedFn(f)}
                    className="px-3 py-2 hover:bg-gray-50 cursor-pointer border-b border-gray-100"
                  >
                    <div className="font-mono text-sm text-indigo-700">{f.name}</div>
                    <div className="text-xs text-gray-600">{f.description}</div>
                  </li>
                ))}
              </ul>
            </>
          ) : (
            <div className="p-4">
              <div className="flex items-center gap-2 mb-3">
                <button
                  onClick={() => setSelectedFn(null)}
                  className="text-xs text-gray-500 hover:text-indigo-600"
                >
                  ← Volver
                </button>
                <h3 className="font-mono text-sm text-indigo-700">{selectedFn.name}</h3>
              </div>
              <p className="text-xs text-gray-600 mb-3">{selectedFn.description}</p>
              {selectedFn.params.length === 0 ? (
                <p className="text-xs text-gray-500 italic mb-3">Sin parámetros.</p>
              ) : (
                <div className="space-y-2">
                  {selectedFn.params.map((p) => (
                    <div key={p.name}>
                      <label className="block text-xs font-medium text-gray-700 mb-0.5">
                        {p.label}
                        {p.hint && (
                          <span className="ml-1 text-gray-400 font-normal">({p.hint})</span>
                        )}
                      </label>
                      {p.type === 'date_format' ? (
                        <div className="flex gap-1">
                          <select
                            value={values[p.name] || ''}
                            onChange={(e) => setValues({ ...values, [p.name]: e.target.value })}
                            className="flex-1 px-2 py-1 text-xs border border-gray-300 rounded font-mono"
                          >
                            <option value="">(custom)</option>
                            {DATE_FORMATS.map((fmt) => (
                              <option key={fmt} value={fmt}>{fmt}</option>
                            ))}
                          </select>
                          <input
                            type="text"
                            value={values[p.name] || ''}
                            onChange={(e) => setValues({ ...values, [p.name]: e.target.value })}
                            placeholder="formato libre"
                            className="flex-1 px-2 py-1 text-xs border border-gray-300 rounded font-mono"
                          />
                        </div>
                      ) : p.type === 'select' ? (
                        <select
                          value={values[p.name] || ''}
                          onChange={(e) => setValues({ ...values, [p.name]: e.target.value })}
                          className="w-full px-2 py-1 text-xs border border-gray-300 rounded"
                        >
                          {(p.options || []).map((o) => (
                            <option key={o} value={o}>{o}</option>
                          ))}
                        </select>
                      ) : (
                        <input
                          type="text"
                          value={values[p.name] || ''}
                          onChange={(e) => setValues({ ...values, [p.name]: e.target.value })}
                          className="w-full px-2 py-1 text-xs border border-gray-300 rounded font-mono"
                        />
                      )}
                    </div>
                  ))}
                </div>
              )}
              <div className="mt-3 p-2 bg-gray-50 rounded font-mono text-xs text-gray-700 break-all">
                {buildFunctionExpression(selectedFn, values)}
              </div>
              <button
                onClick={handleInsert}
                className="mt-3 w-full px-3 py-1.5 bg-indigo-600 text-white text-sm font-medium rounded hover:bg-indigo-700"
              >
                Insertar
              </button>
            </div>
          )}
        </div>
      )}
    </div>
  );
}

function InputWithFx({
  value,
  onChange,
  placeholder,
  className,
  disabled,
}: {
  value: string;
  onChange: (v: string) => void;
  placeholder?: string;
  className?: string;
  disabled?: boolean;
}) {
  const inputRef = useRef<HTMLInputElement>(null);

  const handleInsert = (expr: string) => {
    const input = inputRef.current;
    if (!input) {
      onChange(value + expr);
      return;
    }
    const start = input.selectionStart ?? value.length;
    const end = input.selectionEnd ?? value.length;
    const newValue = value.substring(0, start) + expr + value.substring(end);
    onChange(newValue);
    setTimeout(() => {
      input.focus();
      const newPos = start + expr.length;
      input.setSelectionRange(newPos, newPos);
    }, 0);
  };

  return (
    <div className="flex items-center gap-1">
      <input
        ref={inputRef}
        type="text"
        value={value}
        onChange={(e) => onChange(e.target.value)}
        placeholder={placeholder}
        disabled={disabled}
        className={className || 'flex-1 px-3 py-1.5 text-sm border border-gray-300 rounded-md font-mono'}
      />
      <FunctionHelperButton onInsert={handleInsert} />
    </div>
  );
}

function TextareaWithFx({
  value,
  onChange,
  rows,
  placeholder,
  className,
}: {
  value: string;
  onChange: (v: string) => void;
  rows?: number;
  placeholder?: string;
  className?: string;
}) {
  const textareaRef = useRef<HTMLTextAreaElement>(null);

  const handleInsert = (expr: string) => {
    const ta = textareaRef.current;
    if (!ta) {
      onChange(value + expr);
      return;
    }
    const start = ta.selectionStart ?? value.length;
    const end = ta.selectionEnd ?? value.length;
    const newValue = value.substring(0, start) + expr + value.substring(end);
    onChange(newValue);
    setTimeout(() => {
      ta.focus();
      const newPos = start + expr.length;
      ta.setSelectionRange(newPos, newPos);
    }, 0);
  };

  return (
    <div className="relative">
      <textarea
        ref={textareaRef}
        value={value}
        onChange={(e) => onChange(e.target.value)}
        rows={rows || 4}
        spellCheck={false}
        placeholder={placeholder}
        className={className || 'w-full px-3 py-2 text-xs font-mono border border-gray-300 rounded-md bg-gray-50'}
      />
      <div className="absolute top-1 right-1">
        <FunctionHelperButton onInsert={handleInsert} />
      </div>
    </div>
  );
}


// ============================================================================
// HF7.A — AddElementModal (modal de creación de elementos)
// ============================================================================

interface AddElementModalProps {
  open: boolean;
  elementType: AddElementType;
  onClose: () => void;
  onConfirm: (data: any) => void;
}

function AddElementModal({ open, elementType, onClose, onConfirm }: AddElementModalProps) {
  const [formData, setFormData] = useState<any>({});
  const [childKind, setChildKind] = useState<string>('header_manager');

  useEffect(() => {
    if (!open) return;
    const defaults: Record<AddElementType, any> = {
      sampler: { name: 'Nuevo Sampler', method: 'GET', path: '/', domain: '' },
      sampler_child: { name: '' },
      udv: { name: '', value: '' },
      csv_dataset: { testname: 'CSV Data Set', filename: '', variable_names: '' },
      listener: { listener_kind: 'view_results_tree', name: '' },
    };
    setFormData(defaults[elementType] || {});
    setChildKind('header_manager');
  }, [open, elementType]);

  if (!open) return null;

  const titles: Record<AddElementType, string> = {
    sampler: 'Nuevo HTTP Sampler',
    sampler_child: 'Agregar componente al Sampler',
    udv: 'Nueva variable (UDV)',
    csv_dataset: 'Nuevo CSV Data Set',
    listener: 'Nuevo Listener',
  };

  const handleConfirm = () => {
    if (elementType === 'sampler_child') {
      onConfirm({ child_kind: childKind, data: formData });
    } else if (elementType === 'csv_dataset') {
      const vars = String(formData.variable_names || '')
        .split(',')
        .map((s: string) => s.trim())
        .filter(Boolean);
      onConfirm({ ...formData, variable_names: vars });
    } else if (elementType === 'listener') {
      onConfirm({
        listener_kind: formData.listener_kind || 'view_results_tree',
        name: formData.name || undefined,
      });
    } else {
      onConfirm(formData);
    }
    onClose();
  };

  const disabled =
    (elementType === 'udv' && !formData.name) ||
    (elementType === 'csv_dataset' && !formData.filename);

  return (
    <div className="fixed inset-0 bg-black/40 z-50 flex items-center justify-center p-4">
      <div className="bg-white rounded-lg shadow-xl w-[520px] max-w-[90vw] p-5">
        <div className="flex items-center justify-between mb-4">
          <h3 className="text-lg font-semibold text-gray-900">{titles[elementType]}</h3>
          <button
            type="button"
            onClick={onClose}
            className="text-gray-400 hover:text-gray-600"
            aria-label="Cerrar"
          >
            <X className="w-5 h-5" />
          </button>
        </div>

        {elementType === 'sampler' && (
          <div className="space-y-3">
            <div>
              <label className="block text-xs font-medium mb-1 text-gray-700">Nombre</label>
              <input
                type="text"
                value={formData.name || ''}
                onChange={(e) => setFormData({ ...formData, name: e.target.value })}
                className="w-full px-3 py-1.5 text-sm border border-gray-300 rounded-md"
                autoFocus
              />
            </div>
            <div className="grid grid-cols-2 gap-3">
              <div>
                <label className="block text-xs font-medium mb-1 text-gray-700">Método</label>
                <select
                  value={formData.method || 'GET'}
                  onChange={(e) => setFormData({ ...formData, method: e.target.value })}
                  className="w-full px-3 py-1.5 text-sm border border-gray-300 rounded-md"
                >
                  {['GET', 'POST', 'PUT', 'PATCH', 'DELETE', 'HEAD', 'OPTIONS'].map((m) => (
                    <option key={m} value={m}>{m}</option>
                  ))}
                </select>
              </div>
              <div>
                <label className="block text-xs font-medium mb-1 text-gray-700">Path</label>
                <input
                  type="text"
                  value={formData.path || ''}
                  onChange={(e) => setFormData({ ...formData, path: e.target.value })}
                  className="w-full px-3 py-1.5 text-sm border border-gray-300 rounded-md font-mono"
                />
              </div>
            </div>
            <div>
              <label className="block text-xs font-medium mb-1 text-gray-700">Dominio</label>
              <input
                type="text"
                value={formData.domain || ''}
                onChange={(e) => setFormData({ ...formData, domain: e.target.value })}
                placeholder="vacío = usa HTTP Request Defaults"
                className="w-full px-3 py-1.5 text-sm border border-gray-300 rounded-md font-mono"
              />
            </div>
          </div>
        )}

        {elementType === 'sampler_child' && (
          <div className="space-y-3">
            <div>
              <label className="block text-xs font-medium mb-1 text-gray-700">Tipo de componente</label>
              <select
                value={childKind}
                onChange={(e) => setChildKind(e.target.value)}
                className="w-full px-3 py-1.5 text-sm border border-gray-300 rounded-md"
                autoFocus
              >
                <option value="header_manager">Header Manager</option>
                <option value="response_assertion">Response Assertion (status 200)</option>
                <option value="regex_extractor">Regex Extractor</option>
                <option value="json_extractor">JSON Extractor</option>
                <option value="constant_timer">Constant Timer (1000 ms)</option>
              </select>
            </div>
            <p className="text-xs text-gray-500">
              Se creará con valores por defecto. Edítalo en el panel derecho tras agregarlo.
            </p>
          </div>
        )}

        {elementType === 'udv' && (
          <div className="space-y-3">
            <div>
              <label className="block text-xs font-medium mb-1 text-gray-700">Nombre de variable *</label>
              <input
                type="text"
                value={formData.name || ''}
                onChange={(e) => setFormData({ ...formData, name: e.target.value })}
                placeholder="ej. host"
                className="w-full px-3 py-1.5 text-sm border border-gray-300 rounded-md font-mono"
                autoFocus
              />
            </div>
            <div>
              <label className="block text-xs font-medium mb-1 text-gray-700">Valor</label>
              <input
                type="text"
                value={formData.value || ''}
                onChange={(e) => setFormData({ ...formData, value: e.target.value })}
                placeholder="ej. api.example.com"
                className="w-full px-3 py-1.5 text-sm border border-gray-300 rounded-md font-mono"
              />
            </div>
          </div>
        )}

        {elementType === 'csv_dataset' && (
          <div className="space-y-3">
            <div>
              <label className="block text-xs font-medium mb-1 text-gray-700">Nombre (testname)</label>
              <input
                type="text"
                value={formData.testname || ''}
                onChange={(e) => setFormData({ ...formData, testname: e.target.value })}
                className="w-full px-3 py-1.5 text-sm border border-gray-300 rounded-md"
              />
            </div>
            <div>
              <label className="block text-xs font-medium mb-1 text-gray-700">Archivo CSV *</label>
              <input
                type="text"
                value={formData.filename || ''}
                onChange={(e) => setFormData({ ...formData, filename: e.target.value })}
                placeholder="ej. data/users.csv"
                className="w-full px-3 py-1.5 text-sm border border-gray-300 rounded-md font-mono"
              />
            </div>
            <div>
              <label className="block text-xs font-medium mb-1 text-gray-700">Variables (separadas por coma)</label>
              <input
                type="text"
                value={formData.variable_names || ''}
                onChange={(e) => setFormData({ ...formData, variable_names: e.target.value })}
                placeholder="firstname,lastname,email"
                className="w-full px-3 py-1.5 text-sm border border-gray-300 rounded-md font-mono"
              />
            </div>
          </div>
        )}

        {elementType === 'listener' && (
          <div className="space-y-3">
            <div>
              <label className="block text-xs font-medium mb-1 text-gray-700">Tipo de Listener</label>
              <select
                value={formData.listener_kind || 'view_results_tree'}
                onChange={(e) => setFormData({ ...formData, listener_kind: e.target.value })}
                className="w-full px-3 py-1.5 text-sm border border-gray-300 rounded-md"
                autoFocus
              >
                <optgroup label="Resultados">
                  <option value="view_results_tree">View Results Tree (debug)</option>
                  <option value="view_results_tree_with_csv">View Results Tree (errors + CSV)</option>
                  <option value="summary_report">Summary Report (resumen)</option>
                  <option value="aggregate_report">Informe Agregado</option>
                  <option value="aggregate_report_with_csv">Informe Agregado (con CSV)</option>
                  <option value="response_time_graph">Response Time Graph</option>
                </optgroup>
                <optgroup label="Gráficas jp@gc">
                  <option value="jpgc_response_times_over_time">jp@gc - Response Times Over Time</option>
                  <option value="jpgc_response_codes_per_second">jp@gc - Response Codes per Second</option>
                  <option value="jpgc_transactions_per_second">jp@gc - Transactions per Second</option>
                  <option value="jpgc_active_threads_over_time">jp@gc - Active Threads Over Time</option>
                </optgroup>
                <optgroup label="Otros">
                  <option value="backend_listener">Backend Listener (InfluxDB → Grafana)</option>
                </optgroup>
              </select>
            </div>
            <div>
              <label className="block text-xs font-medium mb-1 text-gray-700">Nombre</label>
              <input
                type="text"
                value={formData.name || ''}
                onChange={(e) => setFormData({ ...formData, name: e.target.value })}
                placeholder="(opcional, se autocompleta según el tipo)"
                className="w-full px-3 py-1.5 text-sm border border-gray-300 rounded-md"
              />
            </div>
            {formData.listener_kind === 'backend_listener' && (
              <div className="bg-blue-50 border border-blue-200 rounded p-3 text-xs text-blue-800">
                <strong>Backend Listener:</strong> se configurará apuntando al InfluxDB del stack Kinetix
                (<code className="font-mono">http://influxdb:8086</code>, bucket <code className="font-mono">jmeter</code>,
                org <code className="font-mono">performance</code>). Puedes ajustar la URL y argumentos editando el listener
                después de crearlo.
              </div>
            )}
          </div>
        )}

        <div className="flex justify-end gap-2 mt-5">
          <button
            type="button"
            onClick={onClose}
            className="px-3 py-1.5 text-sm border border-gray-300 rounded hover:bg-gray-50"
          >
            Cancelar
          </button>
          <button
            type="button"
            onClick={handleConfirm}
            disabled={disabled}
            className="px-3 py-1.5 text-sm bg-indigo-600 text-white rounded hover:bg-indigo-700 disabled:opacity-40 disabled:cursor-not-allowed"
          >
            Crear
          </button>
        </div>
      </div>
    </div>
  );
}


// ============================================================================
// Sprint 2.5c — SmokeTestModal
// ============================================================================

interface SmokeTestModalProps {
  open: boolean;
  running: boolean;
  result: SmokeTestResult | null;
  error: string | null;
  showLog: boolean;
  config: { numThreads: number; loops: number };
  onConfigChange: (c: { numThreads: number; loops: number }) => void;
  onRun: () => void;
  onClose: () => void;
  onRetry: () => void;
  onToggleLog: () => void;
}

function SmokeTestModal({
  open,
  running,
  result,
  error,
  showLog,
  config,
  onConfigChange,
  onRun,
  onClose,
  onRetry,
  onToggleLog,
}: SmokeTestModalProps) {
  if (!open) return null;

  const statusConfig: Record<
    SmokeTestResult['status'],
    { color: string; bg: string; icon: React.ReactNode; label: string }
  > = {
    success: {
      color: 'text-emerald-700',
      bg: 'bg-emerald-50 border-emerald-200',
      icon: <CheckCircle2 className="w-5 h-5" />,
      label: 'Éxito',
    },
    partial: {
      color: 'text-amber-700',
      bg: 'bg-amber-50 border-amber-200',
      icon: <AlertTriangle className="w-5 h-5" />,
      label: 'Parcial',
    },
    failed: {
      color: 'text-red-700',
      bg: 'bg-red-50 border-red-200',
      icon: <XCircle className="w-5 h-5" />,
      label: 'Fallido',
    },
    error: {
      color: 'text-red-700',
      bg: 'bg-red-50 border-red-200',
      icon: <XCircle className="w-5 h-5" />,
      label: 'Error de ejecución',
    },
  };

  return (
    <div className="fixed inset-0 bg-black/40 z-50 flex items-center justify-center p-4">
      <div className="bg-white rounded-lg shadow-xl w-[800px] max-w-full max-h-[90vh] flex flex-col">
        {/* Header */}
        <div className="flex items-center justify-between px-5 py-4 border-b border-gray-200">
          <div className="flex items-center gap-2">
            <Play className="w-5 h-5 text-emerald-600" />
            <h3 className="text-lg font-semibold">Smoke Test</h3>
            <span className="text-xs text-gray-500">(1 usuario, 1 iteración)</span>
          </div>
          <button onClick={onClose} className="text-gray-400 hover:text-gray-600">
            <X className="w-5 h-5" />
          </button>
        </div>

        {/* Body */}
        <div className="flex-1 overflow-y-auto px-5 py-4">
          {/* Sprint 2.5c.1 — panel de configuración (antes de ejecutar) */}
          {!running && !result && !error && (
            <div className="bg-blue-50 border border-blue-200 rounded-lg p-4 mb-4">
              <h4 className="font-medium text-blue-900 mb-3 text-sm">Configuración del smoke test</h4>
              <div className="grid grid-cols-2 gap-3">
                <div>
                  <label className="block text-xs font-medium text-gray-700 mb-1">
                    Usuarios concurrentes
                  </label>
                  <input
                    type="number"
                    min={1}
                    max={20}
                    value={config.numThreads}
                    onChange={(e) =>
                      onConfigChange({
                        ...config,
                        numThreads: Math.max(1, Math.min(20, parseInt(e.target.value, 10) || 1)),
                      })
                    }
                    className="w-full px-3 py-1.5 text-sm border border-gray-300 rounded-md"
                  />
                  <p className="text-xs text-gray-500 mt-1">1-20 (útil para validar datos distintos del CSV)</p>
                </div>
                <div>
                  <label className="block text-xs font-medium text-gray-700 mb-1">
                    Iteraciones por usuario
                  </label>
                  <input
                    type="number"
                    min={1}
                    max={5}
                    value={config.loops}
                    onChange={(e) =>
                      onConfigChange({
                        ...config,
                        loops: Math.max(1, Math.min(5, parseInt(e.target.value, 10) || 1)),
                      })
                    }
                    className="w-full px-3 py-1.5 text-sm border border-gray-300 rounded-md"
                  />
                  <p className="text-xs text-gray-500 mt-1">1-5</p>
                </div>
              </div>
              <button
                onClick={onRun}
                className="mt-3 w-full px-3 py-1.5 bg-emerald-600 text-white text-sm font-medium rounded hover:bg-emerald-700"
              >
                Ejecutar smoke test
              </button>
            </div>
          )}

          {running && (
            <div className="flex flex-col items-center justify-center py-12">
              <Loader2 className="w-8 h-8 text-emerald-500 animate-spin mb-3" />
              <p className="text-sm text-gray-600">Ejecutando JMeter…</p>
              <p className="text-xs text-gray-400 mt-1">Puede tardar entre 5-15 segundos</p>
            </div>
          )}

          {!running && error && (
            <div className="bg-red-50 border border-red-200 rounded-lg p-4">
              <div className="flex items-start gap-2">
                <XCircle className="w-5 h-5 text-red-600 mt-0.5" />
                <div className="flex-1">
                  <p className="font-medium text-red-900">No se pudo ejecutar el smoke test</p>
                  <p className="text-sm text-red-700 mt-1 break-words">{error}</p>
                </div>
              </div>
            </div>
          )}

          {!running && result && (
            <>
              {/* Resumen */}
              <div
                className={`rounded-lg border p-4 mb-4 ${
                  statusConfig[result.status]?.bg || 'bg-gray-50 border-gray-200'
                }`}
              >
                <div className="flex items-center justify-between gap-3">
                  <div className="flex items-center gap-2">
                    <span className={statusConfig[result.status]?.color}>
                      {statusConfig[result.status]?.icon}
                    </span>
                    <div>
                      <p className={`font-medium ${statusConfig[result.status]?.color}`}>
                        {statusConfig[result.status]?.label}
                      </p>
                      <p className="text-xs text-gray-600">
                        {result.successful_samples} / {result.total_samples} samplers OK · {result.duration_sec.toFixed(1)}s
                      </p>
                    </div>
                  </div>
                  {result.error_message && (
                    <p className="text-xs text-red-700 max-w-md text-right break-words">
                      {result.error_message}
                    </p>
                  )}
                </div>
              </div>

              {/* Tabla de samplers */}
              {result.samplers.length > 0 ? (
                <div className="border border-gray-200 rounded-lg overflow-hidden">
                  <table className="w-full text-sm">
                    <thead className="bg-gray-50">
                      <tr>
                        <th className="text-left px-3 py-2 font-medium text-gray-700 w-8"></th>
                        <th className="text-left px-3 py-2 font-medium text-gray-700">Sampler</th>
                        <th className="text-left px-3 py-2 font-medium text-gray-700 w-20">Código</th>
                        <th className="text-right px-3 py-2 font-medium text-gray-700 w-20">Tiempo</th>
                      </tr>
                    </thead>
                    <tbody className="divide-y divide-gray-100">
                      {result.samplers.map((s, idx) => (
                        <tr key={idx} className={s.success ? '' : 'bg-red-50/40'}>
                          <td className="px-3 py-2 align-top">
                            {s.success ? (
                              <CheckCircle2 className="w-4 h-4 text-emerald-500" />
                            ) : (
                              <XCircle className="w-4 h-4 text-red-500" />
                            )}
                          </td>
                          <td className="px-3 py-2">
                            <div className="font-medium text-gray-900">{s.label || '(sin nombre)'}</div>
                            {s.failure_message && (
                              <div className="text-xs text-red-600 mt-0.5 font-mono break-all">
                                {s.failure_message}
                              </div>
                            )}
                            {s.response_message && !s.success && (
                              <div className="text-xs text-gray-500 mt-0.5">{s.response_message}</div>
                            )}
                          </td>
                          <td className="px-3 py-2 align-top">
                            <code
                              className={`text-xs px-1.5 py-0.5 rounded ${
                                s.response_code.startsWith('2')
                                  ? 'bg-emerald-100 text-emerald-700'
                                  : s.response_code.startsWith('3')
                                  ? 'bg-blue-100 text-blue-700'
                                  : s.response_code.startsWith('4')
                                  ? 'bg-amber-100 text-amber-700'
                                  : 'bg-red-100 text-red-700'
                              }`}
                            >
                              {s.response_code || '—'}
                            </code>
                          </td>
                          <td className="px-3 py-2 text-right font-mono text-xs text-gray-600 align-top">
                            {s.elapsed_ms}ms
                          </td>
                        </tr>
                      ))}
                    </tbody>
                  </table>
                </div>
              ) : (
                <div className="bg-amber-50 border border-amber-200 rounded-lg p-3 text-sm text-amber-800">
                  No se ejecutó ningún sampler. Verifica que el JMX tenga samplers habilitados.
                </div>
              )}

              {/* Log de JMeter expandible */}
              {result.jmeter_log_tail && (
                <div className="mt-4">
                  <button
                    onClick={onToggleLog}
                    className="text-xs text-gray-600 hover:text-gray-900 flex items-center gap-1"
                  >
                    {showLog ? (
                      <ChevronDown className="w-3 h-3" />
                    ) : (
                      <ChevronRight className="w-3 h-3" />
                    )}
                    Log de JMeter ({result.jmeter_log_tail.length} chars)
                  </button>
                  {showLog && (
                    <pre className="mt-2 p-3 bg-gray-900 text-gray-100 text-xs font-mono rounded overflow-auto max-h-64 whitespace-pre-wrap">
                      {result.jmeter_log_tail}
                    </pre>
                  )}
                </div>
              )}
            </>
          )}
        </div>

        {/* Footer */}
        <div className="flex items-center justify-between px-5 py-3 border-t border-gray-200 bg-gray-50">
          <p className="text-xs text-gray-500">
            El smoke test ejecuta el JMX con 1 usuario y 1 iteración. No envía métricas a InfluxDB.
          </p>
          <div className="flex gap-2">
            {!running && (result || error) && (
              <button
                onClick={onRetry}
                className="px-3 py-1.5 text-sm border border-gray-300 rounded hover:bg-white"
              >
                Reintentar
              </button>
            )}
            <button
              onClick={onClose}
              className="px-3 py-1.5 text-sm bg-gray-700 text-white rounded hover:bg-gray-800"
            >
              Cerrar
            </button>
          </div>
        </div>
      </div>
    </div>
  );
}
