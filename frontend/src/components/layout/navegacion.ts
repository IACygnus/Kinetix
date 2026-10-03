/**
 * El menú de Kinetix: módulos, pantallas, rutas y roles. Una sola definición
 * para la cabecera, el riel de sección, el menú desplegable y el buscador.
 *
 * Copiado ÍTEM POR ÍTEM de `Sidebar.tsx` (el menú viejo, borrado en la Etapa
 * 1): mismas rutas, mismo orden y mismos `roles`. Los
 * únicos cambios son las tildes de «Administración» y «Configuración IA».
 *
 * Deuda conocida, a propósito sin corregir (decisión de Fredy, Etapa 0):
 * «Nuevo Reporte» e «Historial Integrado» no llevan `roles`, así que el visor
 * los ve, pero sus rutas exigen admin o analista y lo devuelven al inicio
 * (auditoría 153 §1d).
 */
import {
  Activity,
  Brain,
  Building2,
  CalendarClock,
  ClipboardList,
  Clock,
  Code,
  FileBarChart,
  FileBarChart2,
  FileText,
  FlaskConical,
  FolderKanban,
  Gauge,
  GitCompare,
  LayoutDashboard,
  ListChecks,
  Monitor,
  PenTool,
  Radar,
  Search,
  Server,
  ShieldCheck,
  Sparkles,
  Upload,
  UserCheck,
  Users,
} from 'lucide-react';
import type { LucideIcon } from 'lucide-react';

export type Rol = 'admin' | 'analyst' | 'viewer';

export interface Pantalla {
  etiqueta: string;
  ruta: string;
  icono: LucideIcon;
  roles?: Rol[];
  /** Rutas fuera del menú que pertenecen a esta pantalla (p. ej. un id). */
  tambien?: string[];
}

export interface Modulo {
  id: string;
  etiqueta: string;
  icono: LucideIcon;
  roles?: Rol[];
  /** Módulo de una sola pantalla (Dashboard, Ejecución). */
  ruta?: string;
  pantallas?: Pantalla[];
  /** Prefijos de ruta que abren este módulo aunque no casen con una pantalla. */
  prefijos?: string[];
}

const AA: Rol[] = ['admin', 'analyst'];

export const MODULOS: Modulo[] = [
  { id: 'dashboard', etiqueta: 'Dashboard', icono: LayoutDashboard, ruta: '/dashboard' },
  {
    id: 'diseno',
    etiqueta: 'Diseño',
    icono: PenTool,
    roles: AA,
    prefijos: ['/script-designer', '/ai-script-designer', '/ai-script-editor'],
    pantallas: [
      { etiqueta: 'Editor', ruta: '/script-designer', icono: PenTool },
      { etiqueta: 'Diseñador IA', ruta: '/ai-script-designer', icono: Sparkles, roles: AA },
      { etiqueta: 'Mis Diseños IA', ruta: '/ai-script-designer/history', icono: ClipboardList, roles: AA },
      { etiqueta: 'Editor IA', ruta: '/ai-script-editor', icono: Code, roles: AA, tambien: ['/ai-script-designer/editor'] },
      { etiqueta: 'Guardados', ruta: '/script-designer/history', icono: ClipboardList },
    ],
  },
  { id: 'ejecucion', etiqueta: 'Ejecución', icono: Gauge, ruta: '/execution-dashboard', roles: AA },
  {
    id: 'analisis',
    etiqueta: 'Análisis',
    icono: FlaskConical,
    prefijos: ['/performance'],
    pantallas: [
      { etiqueta: 'Nuevo Reporte', ruta: '/performance/new', icono: FileText },
      { etiqueta: 'Analista IA', ruta: '/performance/analista', icono: Sparkles, roles: AA },
      { etiqueta: 'Reporte', ruta: '/performance/report-latest', icono: FileBarChart, tambien: ['/performance/report'] },
      { etiqueta: 'Historial Reporte', ruta: '/performance/history', icono: ClipboardList },
      { etiqueta: 'Capturas de infraestructura', ruta: '/performance/monitoring', icono: Monitor },
      { etiqueta: 'Evidencias', ruta: '/performance/evidence', icono: Search },
      { etiqueta: 'Informe Integrado', ruta: '/performance/integrated', icono: GitCompare },
      { etiqueta: 'Historial Integrado', ruta: '/performance/integrated/history', icono: ClipboardList },
    ],
  },
  {
    id: 'observabilidad',
    etiqueta: 'Observabilidad',
    icono: Radar,
    // O-D31: las rutas antiguas redirigen; mientras pasan, el módulo es este.
    prefijos: ['/observabilidad', '/monitoring/vivo'],
    pantallas: [
      { etiqueta: 'Sesiones de monitoreo', ruta: '/observabilidad/sesiones', icono: Radar, roles: AA },
      { etiqueta: 'Servidores', ruta: '/observabilidad/servidores', icono: Server, roles: AA },
      { etiqueta: 'Monitoreo en vivo', ruta: '/observabilidad/vivo', icono: Activity, roles: AA, tambien: ['/monitoring/vivo'] },
    ],
  },
  {
    // Sin `roles`: en horas todos ven todo (§8).
    id: 'horas',
    etiqueta: 'Horas',
    icono: Clock,
    prefijos: ['/horas'],
    pantallas: [
      { etiqueta: 'Registro', ruta: '/horas/registro', icono: CalendarClock },
      { etiqueta: 'Consulta', ruta: '/horas/consulta', icono: Search },
      { etiqueta: 'Proyectos', ruta: '/horas/proyectos', icono: FolderKanban },
      { etiqueta: 'Actividades', ruta: '/horas/actividades', icono: ListChecks },
      { etiqueta: 'Importar', ruta: '/horas/importar', icono: Upload },
      { etiqueta: 'Informes', ruta: '/horas/informes', icono: FileBarChart2 },
    ],
  },
  // El bloque «Monitoreo» (Real-Time, Configuración) sigue oculto como en
  // Sidebar.tsx: /monitoring/realtime y /monitoring/settings no tienen entrada.
  {
    id: 'admin',
    etiqueta: 'Administración',
    icono: ShieldCheck,
    roles: ['admin'],
    prefijos: ['/admin', '/users'],
    pantallas: [
      { etiqueta: 'Usuarios', ruta: '/users', icono: Users, roles: ['admin'] },
      { etiqueta: 'Clientes', ruta: '/admin/clients', icono: Building2, roles: ['admin'] },
      { etiqueta: 'Asignaciones', ruta: '/admin/assignments', icono: UserCheck, roles: ['admin'] },
      { etiqueta: 'Configuración IA', ruta: '/admin/ai-config', icono: Brain, roles: ['admin'] },
    ],
  },
];

/** Pantallas fuera del menú que el buscador también ofrece. */
export const PANTALLAS_SUELTAS: Pantalla[] = [
  { etiqueta: 'Mi perfil', ruta: '/profile', icono: Users },
];

const puede = (roles: Rol[] | undefined, rol: string | undefined) => !roles || (!!rol && roles.includes(rol as Rol));

/**
 * Los módulos que ve un rol, con sus pantallas ya filtradas. Igual que
 * `isItemVisible` de Sidebar.tsx: un módulo sin ninguna pantalla visible no sale.
 */
export function modulosVisibles(rol: string | undefined): Modulo[] {
  return MODULOS.filter((m) => puede(m.roles, rol))
    .map((m) => (m.pantallas ? { ...m, pantallas: m.pantallas.filter((p) => puede(p.roles, rol)) } : m))
    .filter((m) => !m.pantallas || m.pantallas.length > 0);
}

/** La primera ruta de un módulo: a donde lleva pulsarlo en la cabecera. */
export const rutaDeModulo = (m: Modulo): string => m.ruta ?? m.pantallas?.[0]?.ruta ?? '/dashboard';

const casa = (ruta: string, base: string) => ruta === base || ruta.startsWith(`${base}/`);

export interface Ubicacion {
  modulo: Modulo | null;
  pantalla: Pantalla | null;
}

/**
 * Dónde está una ruta: la pantalla cuya ruta (o `tambien`) casa con más
 * caracteres gana —así /performance/integrated/history es «Historial
 * Integrado» y no «Informe Integrado»—; si ninguna casa, el módulo por sus
 * prefijos (p. ej. /performance/report/<id> abre Análisis sin pantalla activa).
 */
export function ubicar(ruta: string, modulos: Modulo[]): Ubicacion {
  let mejor: Ubicacion = { modulo: null, pantalla: null };
  let largo = -1;
  for (const m of modulos) {
    if (m.ruta && casa(ruta, m.ruta) && m.ruta.length > largo) {
      mejor = { modulo: m, pantalla: null };
      largo = m.ruta.length;
    }
    for (const p of m.pantallas ?? []) {
      for (const base of [p.ruta, ...(p.tambien ?? [])]) {
        if (casa(ruta, base) && base.length > largo) {
          mejor = { modulo: m, pantalla: p };
          largo = base.length;
        }
      }
    }
  }
  if (mejor.modulo) return mejor;
  const porPrefijo = modulos.find((m) => m.prefijos?.some((b) => casa(ruta, b)));
  return { modulo: porPrefijo ?? null, pantalla: null };
}
