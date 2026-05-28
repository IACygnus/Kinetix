/**
 * Tipos TypeScript para AIScriptStructure.
 * Espejo de backend/app/schemas/ai_script_structure.py.
 *
 * El modelo NO se persiste en DB: el frontend lo solicita on-demand al backend
 * llamando a POST /script-designer/ai/parse-jmx (Sprint 2.2) y lo envía de vuelta
 * en POST /script-designer/ai/regenerate-jmx (Sprint 2.3).
 *
 * Sprint 2.3a: campo `is_dirty?: boolean` añadido en 24 interfaces para habilitar
 * el regenerador edit-preserving. Es opcional para no romper código del Sprint 2.0.
 */

// ============================================================================
// Aliases para legibilidad
// ============================================================================

export type UUID = string;

// ============================================================================
// Test Plan
// ============================================================================

export interface TestPlanModel {
  name: string;
  functional_mode: boolean;
  serialize_threadgroups: boolean;
  tearDown_on_shutdown: boolean;
  comments?: string | null;
  is_dirty?: boolean;
}

// ============================================================================
// Variables
// ============================================================================

export interface UserDefinedVariable {
  name: string;
  value: string;
  metadata: string;
  description?: string | null;
  is_dirty?: boolean;
}

// ============================================================================
// HTTP Defaults
// ============================================================================

export interface HttpDefaultsModel {
  domain?: string | null;
  protocol?: string | null;
  port?: string | null;
  path?: string | null;
  implementation?: string | null;
  encoding?: string | null;
  is_dirty?: boolean;
}

// ============================================================================
// Cookie / Cache Manager
// ============================================================================

export interface CookieManagerModel {
  enabled: boolean;
  clear_each_iteration: boolean;
  policy?: string | null;
  is_dirty?: boolean;
}

export interface CacheManagerModel {
  enabled: boolean;
  clear_each_iteration: boolean;
  use_expires: boolean;
  is_dirty?: boolean;
}

// ============================================================================
// CSV Data Sets
// ============================================================================

export type CSVShareMode = 'shareMode.all' | 'shareMode.group' | 'shareMode.thread';

export interface CSVDataSetModel {
  id: UUID;
  testname: string;
  enabled: boolean;
  filename: string;
  variable_names: string[];
  delimiter: string;
  ignore_first_line: boolean;
  quoted_data: boolean;
  recycle: boolean;
  share_mode: CSVShareMode;
  stop_thread: boolean;
  file_encoding?: string | null;
  is_dirty?: boolean;
}

// ============================================================================
// Stepping config — los aliases del backend se respetan al recibir JSON
// (Pydantic serializa con field name por defecto; revisaremos en Sprint 2.1).
// ============================================================================

export interface SteppingConfig {
  initial_delay: number;
  start_users_count: number;
  start_users_count_burst: number;
  start_users_period: number;
  stop_users_count: number;
  stop_users_period: number;
  ramp_up: number;
  flight_time: number;
}

// ============================================================================
// Sampler children
// ============================================================================

export interface HeaderModel {
  name: string;
  value: string;
}

export interface HeaderManagerModel {
  id: UUID;
  enabled: boolean;
  headers: HeaderModel[];
  is_dirty?: boolean;
}

export type AssertionTestField =
  | 'Assertion.response_data'
  | 'Assertion.response_code'
  | 'Assertion.response_headers'
  | 'Assertion.response_message';

export type AssertionPatternMatch = 'contains' | 'matches' | 'equals' | 'substring';

export interface ResponseAssertionModel {
  id: UUID;
  enabled: boolean;
  name: string;
  test_field: AssertionTestField | string;
  test_type: number;
  test_strings: string[];
  custom_message?: string | null;
  assume_success: boolean;
  negate: boolean;
  pattern_match: AssertionPatternMatch;
  is_dirty?: boolean;
}

export type ExtractFrom = 'body' | 'header' | 'url' | 'code' | 'message';
export type RegexUseHeaders = 'false' | 'true' | 'URL' | 'code' | 'message';

export interface RegexExtractorModel {
  id: UUID;
  enabled: boolean;
  name: string;
  refname: string;
  regex: string;
  template: string;
  match_number: string;
  default: string;
  default_empty_value: boolean;
  use_headers: RegexUseHeaders;
  scope?: 'all' | 'parent' | 'children' | null;
  extract_from: ExtractFrom;
  is_dirty?: boolean;
}

export interface JsonExtractorModel {
  id: UUID;
  enabled: boolean;
  name: string;
  refname: string;
  json_path: string;
  match_number: string;
  default: string;
  is_dirty?: boolean;
}

export interface XPathExtractorModel {
  id: UUID;
  enabled: boolean;
  name: string;
  refname: string;
  xpath: string;
  default: string;
  is_dirty?: boolean;
}

export interface BoundaryExtractorModel {
  id: UUID;
  enabled: boolean;
  name: string;
  refname: string;
  left_boundary: string;
  right_boundary: string;
  match_number: string;
  default: string;
  is_dirty?: boolean;
}

export interface ConstantTimerModel {
  id: UUID;
  enabled: boolean;
  name: string;
  delay_ms: number;
  is_dirty?: boolean;
}

export interface UniformRandomTimerModel {
  id: UUID;
  enabled: boolean;
  name: string;
  constant_delay_ms: number;
  random_delay_ms: number;
  is_dirty?: boolean;
}

export interface GaussianRandomTimerModel {
  id: UUID;
  enabled: boolean;
  name: string;
  constant_delay_ms: number;
  deviation_ms: number;
  is_dirty?: boolean;
}

// ============================================================================
// Sampler body
// ============================================================================

export interface FormArgument {
  name: string;
  value: string;
  always_encode: boolean;
  use_equals: boolean;
  metadata: string;
}

export type BodyMode = 'raw' | 'form' | 'none';
export type BodyType = 'json' | 'xml' | 'form' | 'raw' | 'auto';

export interface SamplerBody {
  mode: BodyMode;
  raw_text?: string | null;
  form_args: FormArgument[];
  body_type: BodyType;
}

// ============================================================================
// Sampler child (discriminado)
// ============================================================================

export type SamplerChildType =
  | 'header_manager'
  | 'response_assertion'
  | 'regex_extractor'
  | 'json_extractor'
  | 'xpath_extractor'
  | 'boundary_extractor'
  | 'constant_timer'
  | 'uniform_random_timer'
  | 'gaussian_random_timer'
  | 'unsupported';

export interface UnsupportedElement {
  id: UUID;
  type: 'unsupported';
  kind: string;
  name?: string | null;
  reason: string;
  severity: 'warning' | 'info';
  raw_xml: string;
  parent_sampler_id?: UUID | null;
}

export type SamplerChildData =
  | HeaderManagerModel
  | ResponseAssertionModel
  | RegexExtractorModel
  | JsonExtractorModel
  | XPathExtractorModel
  | BoundaryExtractorModel
  | ConstantTimerModel
  | UniformRandomTimerModel
  | GaussianRandomTimerModel
  | UnsupportedElement;

export interface SamplerChild {
  type: SamplerChildType;
  order: number;
  data: SamplerChildData;
}

// ============================================================================
// HTTP Sampler
// ============================================================================

export interface HTTPSamplerModel {
  id: UUID;
  type: 'sampler';
  enabled: boolean;
  name: string;
  method: string;
  protocol?: string | null;
  domain?: string | null;
  port?: string | null;
  path: string;
  content_encoding: string;
  follow_redirects: boolean;
  use_keepalive: boolean;
  auto_redirects: boolean;
  body: SamplerBody;
  children: SamplerChild[];
  raw_xml: string;
  is_dirty?: boolean;
}

// ============================================================================
// Controllers
// ============================================================================

export type ControllerKind =
  | 'generic_controller'
  | 'loop_controller'
  | 'if_controller'
  | 'while_controller'
  | 'throughput_controller';

interface ControllerBase {
  id: UUID;
  type: 'controller';
  enabled: boolean;
  name: string;
  children: TGChild[];
  is_dirty?: boolean;
}

export interface GenericControllerModel extends ControllerBase {
  kind: 'generic_controller';
}

export interface LoopControllerModel extends ControllerBase {
  kind: 'loop_controller';
  loops: number;
  continue_forever: boolean;
}

export interface IfControllerModel extends ControllerBase {
  kind: 'if_controller';
  condition: string;
  use_expression: boolean;
  evaluate_all: boolean;
}

export interface WhileControllerModel extends ControllerBase {
  kind: 'while_controller';
  condition: string;
}

export interface ThroughputControllerModel extends ControllerBase {
  kind: 'throughput_controller';
  style: number;
  percent_throughput: string;
  per_thread: boolean;
}

export type ControllerUnion =
  | GenericControllerModel
  | LoopControllerModel
  | IfControllerModel
  | WhileControllerModel
  | ThroughputControllerModel;

// ============================================================================
// Thread Group child (discriminado)
// ============================================================================

export interface TGChild {
  type: 'sampler' | 'controller' | 'unsupported';
  order: number;
  sampler?: HTTPSamplerModel | null;
  controller?: ControllerUnion | null;
  unsupported?: UnsupportedElement | null;
}

// ============================================================================
// Thread Group
// ============================================================================

export type ThreadGroupKind = 'standard' | 'stepping' | 'concurrency' | 'ultimate';

export type OnSampleError =
  | 'continue'
  | 'startnextloop'
  | 'stopthread'
  | 'stoptest'
  | 'stoptestnow';

export interface ThreadGroupModel {
  id: UUID;
  kind: ThreadGroupKind;
  name: string;
  enabled: boolean;
  comments?: string | null;
  on_sample_error: OnSampleError;
  num_threads: number;
  ramp_time: number;
  duration?: number | null;
  delay?: number | null;
  scheduler: boolean;
  loops: number;
  continue_forever: boolean;
  stepping?: SteppingConfig | null;
  children: TGChild[];
  raw_xml: string;
  is_dirty?: boolean;
}

// ============================================================================
// Config elements
// ============================================================================

export type ConfigElementKind =
  | 'cookie_manager'
  | 'cache_manager'
  | 'auth_manager'
  | 'dns_cache_manager'
  | 'keystore_config'
  | 'other';

export interface ConfigElementModel {
  id: UUID;
  kind: ConfigElementKind;
  name: string;
  enabled: boolean;
  properties: Record<string, any>;
  raw_xml: string;
  is_dirty?: boolean;
}

// ============================================================================
// Listeners
// ============================================================================

export type ListenerKind =
  | 'view_results_tree'
  | 'summary_report'
  | 'aggregate_report'
  | 'graph_results'
  | 'kg_apc_response_times_over_time'
  | 'kg_apc_response_codes_per_second'
  | 'kg_apc_transactions_per_second'
  | 'kg_apc_active_threads_over_time'
  | 'kg_apc_hits_per_second'
  | 'other';

export interface ListenerModel {
  id: UUID;
  kind: ListenerKind;
  guiclass: string;
  name: string;
  enabled: boolean;
  filename?: string | null;
  raw_xml: string;
  is_dirty?: boolean;
}

// ============================================================================
// Metadata derivada
// ============================================================================

export interface StructureMetadata {
  jmx_version: string;
  parsed_at: string;
  referenced_variables: string[];
  defined_variables: string[];
  undefined_variables: string[];
  has_unmapped: boolean;
  unmapped_count: number;
  parse_warnings: string[];
}

// ============================================================================
// Modelo raíz
// ============================================================================

export interface AIScriptStructure {
  test_plan: TestPlanModel;
  user_defined_variables: UserDefinedVariable[];
  http_defaults?: HttpDefaultsModel | null;
  cookie_manager?: CookieManagerModel | null;
  cache_manager?: CacheManagerModel | null;
  csv_data_sets: CSVDataSetModel[];
  thread_groups: ThreadGroupModel[];
  config_elements: ConfigElementModel[];
  listeners: ListenerModel[];
  unmapped: UnsupportedElement[];
  metadata: StructureMetadata;
}
