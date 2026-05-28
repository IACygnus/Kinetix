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
} from 'lucide-react';
import { aiScriptDesignsAPI, aiScriptStructureAPI, aiDesignDataFilesAPI } from '../services/api';
import type {
  AIConversationMessage,
  AIDesignReferenceFileType,
  AIDesignDataFile,
  AIDesignDataFilePreview,
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

  // ==========================================================================
  // Auto-save state (Sprint 2.4b)
  // ==========================================================================
  const [saving, setSaving] = useState(false);
  const [lastSaved, setLastSaved] = useState<Date | null>(null);
  const [saveError, setSaveError] = useState<string | null>(null);
  const [, setTick] = useState(0); // forzar re-render del indicador "hace Xs"
  const saveTimerRef = useRef<ReturnType<typeof setTimeout> | null>(null);
  const isDirtyRef = useRef(false);

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
            />
          </div>
        </div>

        {/* Panel derecho: detalle */}
        <div className="flex-1 overflow-y-auto">
          <DetailPanel
            structure={structure}
            selected={selected}
            onUpdateStructure={updateStructure}
            designId={designId || ''}
            dataFiles={dataFiles}
            dataFilesLoading={dataFilesLoading}
            reloadDataFiles={reloadDataFiles}
            onDataFileSelect={setSelected}
          />
        </div>
      </div>

      {/* Modal XML raw */}
      {showXmlModal && (
        <XmlRawModal jmx={originalJmx} onClose={() => setShowXmlModal(false)} />
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
}

function TreeView({ structure, selected, expanded, onSelect, onToggleExpand, matchesFilter, dataFiles }: TreeViewProps) {
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
        {structure.user_defined_variables.length > 0 && (
          <TreeItem
            label={`Variables (${structure.user_defined_variables.length})`}
            icon={<Sliders className="w-4 h-4 text-gray-500" />}
            selected={isSelected({ kind: 'udvs' })}
            onClick={() => onSelect({ kind: 'udvs' })}
            indent
          />
        )}
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
          />
        )}
        {structure.cache_manager && (
          <TreeItem
            label="Cache Manager"
            icon={<Settings className="w-4 h-4 text-gray-500" />}
            selected={isSelected({ kind: 'cache_manager' })}
            onClick={() => onSelect({ kind: 'cache_manager' })}
            indent
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
          />
        ))}
      </TreeFolder>

      {/* Listeners */}
      {structure.listeners.length > 0 && (
        <TreeFolder
          label={`Listeners (${structure.listeners.length})`}
          icon={<Headphones className="w-4 h-4 text-gray-700" />}
          expandKey="listeners"
          expanded={expanded}
          onToggleExpand={onToggleExpand}
        >
          {structure.listeners.map((l) => (
            <TreeItem
              key={l.id}
              label={l.name}
              icon={<Eye className="w-4 h-4 text-gray-500" />}
              selected={isSelected({ kind: 'listener', id: l.id })}
              onClick={() => onSelect({ kind: 'listener', id: l.id })}
              indent
              visible={matchesFilter(l.name)}
              badge={!l.enabled ? 'off' : undefined}
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
}

function ThreadGroupNode({ tg, selected, expanded, onSelect, onToggleExpand, matchesFilter }: ThreadGroupNodeProps) {
  const isSelected = (s: SelectedNode): boolean => JSON.stringify(s) === JSON.stringify(selected);
  const tgExpandKey = `tg-${tg.id}`;
  const tgExpanded = expanded[tgExpandKey] !== false; // default true
  const tgLabel = `${tg.name} (${tg.kind === 'stepping' ? 'Stepping' : 'Standard'})`;

  return (
    <li className="ml-2">
      <div
        className={`flex items-center gap-1 py-1 px-2 rounded cursor-pointer ${
          isSelected({ kind: 'thread_group', id: tg.id }) ? 'bg-indigo-50 text-indigo-700' : 'hover:bg-gray-50'
        }`}
      >
        <button
          onClick={(e) => { e.stopPropagation(); onToggleExpand(tgExpandKey); }}
          className="p-0.5 hover:bg-gray-200 rounded"
        >
          {tgExpanded ? <ChevronDown className="w-3 h-3" /> : <ChevronRight className="w-3 h-3" />}
        </button>
        <div
          className="flex items-center gap-2 flex-1"
          onClick={() => onSelect({ kind: 'thread_group', id: tg.id })}
        >
          <UsersIcon className={`w-4 h-4 ${tg.kind === 'stepping' ? 'text-purple-600' : 'text-indigo-600'}`} />
          <span className={`truncate ${!tg.enabled ? 'text-gray-400 line-through' : ''}`}>{tgLabel}</span>
          {!tg.enabled && <span className="text-xs text-gray-400">(off)</span>}
        </div>
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
}

function TGChildNode({ child, tg_id, selected, expanded, onSelect, onToggleExpand, matchesFilter }: TGChildNodeProps) {
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
          className={`flex items-center gap-1 py-1 px-2 rounded cursor-pointer ${
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
          <div
            className="flex items-center gap-2 flex-1 min-w-0"
            onClick={() => onSelect({ kind: 'sampler', tg_id, sampler_id: sampler.id })}
          >
            <span className={`px-1.5 py-0.5 text-xs rounded font-mono ${methodColor(sampler.method)}`}>
              {sampler.method}
            </span>
            <span className={`truncate text-sm ${!sampler.enabled ? 'text-gray-400 line-through' : ''}`}>
              {sampler.name}
            </span>
          </div>
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
}

function SamplerChildNode({ sc, tg_id, sampler_id, selected, onSelect }: SamplerChildNodeProps) {
  const isSelected = (s: SelectedNode): boolean => JSON.stringify(s) === JSON.stringify(selected);
  const childId = (sc.data as any).id;
  const childName = (sc.data as any).name || sc.type;
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
        className={`flex items-center gap-2 py-0.5 px-2 rounded cursor-pointer ${
          isSelected({ kind: 'sampler_child', tg_id, sampler_id, child_id: childId })
            ? 'bg-indigo-50 text-indigo-700'
            : 'hover:bg-gray-50'
        }`}
        onClick={() => onSelect({ kind: 'sampler_child', tg_id, sampler_id, child_id: childId })}
      >
        {icon}
        <span className={`truncate text-xs ${isUnmapped ? 'text-amber-700' : 'text-gray-600'}`}>
          {childName}
        </span>
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
}

function TreeItem({ label, icon, selected, onClick, indent, visible = true, badge }: TreeItemProps) {
  if (!visible) return null;
  return (
    <li className={indent ? 'ml-4' : ''}>
      <div
        className={`flex items-center gap-2 py-1 px-2 rounded cursor-pointer text-sm ${
          selected ? 'bg-indigo-50 text-indigo-700 font-medium' : 'hover:bg-gray-50 text-gray-700'
        }`}
        onClick={onClick}
      >
        {icon}
        <span className="truncate">{label}</span>
        {badge && <span className="text-xs text-gray-400">({badge})</span>}
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
}

function DataFilesPanel({ designId, dataFiles, loading, onReload }: DataFilesPanelProps) {
  const [uploading, setUploading] = useState(false);
  const [uploadError, setUploadError] = useState<string | null>(null);
  const fileInputRef = useRef<HTMLInputElement>(null);
  const [delimiter, setDelimiter] = useState(',');
  const [hasHeader, setHasHeader] = useState(true);

  const handleUpload = async (file: File) => {
    setUploading(true);
    setUploadError(null);
    try {
      await aiDesignDataFilesAPI.upload(designId, file, delimiter, hasHeader ? 'true' : 'false', 'UTF-8');
      onReload();
    } catch (e: any) {
      setUploadError(e?.response?.data?.detail || e?.message || 'Error al subir');
    } finally {
      setUploading(false);
      if (fileInputRef.current) fileInputRef.current.value = '';
    }
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
        <input
          ref={fileInputRef}
          type="file"
          accept=".csv,.txt"
          className="hidden"
          onChange={(e) => {
            const f = e.target.files?.[0];
            if (f) handleUpload(f);
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
