/**
 * Sidebar - Navegacion lateral colapsable - SQA Corporate Branding
 */
import { useState, useEffect } from 'react';
import { NavLink, useLocation } from 'react-router-dom';
import {
  LayoutDashboard,
  FlaskConical,
  FileText,
  ClipboardList,
  // Activity, BarChart3, Settings — unused while Monitoreo section is hidden
  Users,
  Building2,
  UserCheck,
  ShieldCheck,
  Brain,
  ChevronLeft,
  ChevronRight,
  ChevronDown,
  ChevronUp,
  LogOut,
  UserCircle,
  PenTool,
  Gauge,
  FileBarChart,
  Monitor,
  Search,
  GitCompare,
  Sparkles,
  Code,
} from 'lucide-react';
import { useAuth } from '../../context/AuthContext';

interface SidebarProps {
  collapsed: boolean;
  onToggle: () => void;
}

interface SubMenuItem {
  label: string;
  path: string;
  icon: React.ReactNode;
  roles?: string[];
}

interface MenuItem {
  label: string;
  path?: string;
  icon: React.ReactNode;
  roles?: string[];
  children?: SubMenuItem[];
}

export default function Sidebar({ collapsed, onToggle }: SidebarProps) {
  const { user, logout } = useAuth();
  const location = useLocation();
  const [expandedMenus, setExpandedMenus] = useState<Record<string, boolean>>({});

  const menuItems: MenuItem[] = [
    {
      label: 'Dashboard',
      path: '/dashboard',
      icon: <LayoutDashboard className="w-7 h-7" />,
    },
    {
      label: 'Diseño',
      icon: <PenTool className="w-7 h-7" />,
      roles: ['admin', 'analyst'],
      children: [
        {
          label: 'Editor',
          path: '/script-designer',
          icon: <PenTool className="w-6 h-6" />,
        },
        {
          label: 'Diseñador IA',
          path: '/ai-script-designer',
          icon: <Sparkles className="w-6 h-6" />,
          roles: ['admin', 'analyst'],
        },
        {
          label: 'Mis Diseños IA',
          path: '/ai-script-designer/history',
          icon: <ClipboardList className="w-6 h-6" />,
          roles: ['admin', 'analyst'],
        },
        {
          label: 'Editor IA',
          path: '/ai-script-editor',
          icon: <Code className="w-6 h-6" />,
          roles: ['admin', 'analyst'],
        },
        {
          label: 'Guardados',
          path: '/script-designer/history',
          icon: <ClipboardList className="w-6 h-6" />,
        },
      ],
    },
    {
      label: 'Ejecución',
      path: '/execution-dashboard',
      icon: <Gauge className="w-7 h-7" />,
      roles: ['admin', 'analyst'],
    },
    {
      label: 'Análisis',
      icon: <FlaskConical className="w-7 h-7" />,
      children: [
        {
          label: 'Nuevo Reporte',
          path: '/performance/new',
          icon: <FileText className="w-6 h-6" />,
        },
        {
          label: 'Reporte',
          path: '/performance/report-latest',
          icon: <FileBarChart className="w-6 h-6" />,
        },
        {
          label: 'Metricas Monitoreo',
          path: '/performance/monitoring',
          icon: <Monitor className="w-6 h-6" />,
        },
        {
          label: 'Evidencias',
          path: '/performance/evidence',
          icon: <Search className="w-6 h-6" />,
        },
        {
          label: 'Informe Integrado',
          path: '/performance/integrated',
          icon: <GitCompare className="w-6 h-6" />,
        },
        {
          label: 'Historial Integrado',
          path: '/performance/integrated/history',
          icon: <ClipboardList className="w-6 h-6" />,
        },
        {
          label: 'Historial',
          path: '/performance/history',
          icon: <ClipboardList className="w-6 h-6" />,
        },
      ],
    },
    /* OCULTO — Monitoreo Grafana (desarrollo futuro)
    {
      label: 'Monitoreo',
      icon: <Activity className="w-7 h-7" />,
      children: [
        {
          label: 'Real-Time',
          path: '/monitoring/realtime',
          icon: <BarChart3 className="w-6 h-6" />,
        },
        {
          label: 'Configuracion',
          path: '/monitoring/settings',
          icon: <Settings className="w-6 h-6" />,
          roles: ['admin'],
        },
      ],
    },
    */
    {
      label: 'Administracion',
      icon: <ShieldCheck className="w-7 h-7" />,
      roles: ['admin'],
      children: [
        {
          label: 'Usuarios',
          path: '/users',
          icon: <Users className="w-6 h-6" />,
          roles: ['admin'],
        },
        {
          label: 'Clientes',
          path: '/admin/clients',
          icon: <Building2 className="w-6 h-6" />,
          roles: ['admin'],
        },
        {
          label: 'Asignaciones',
          path: '/admin/assignments',
          icon: <UserCheck className="w-6 h-6" />,
          roles: ['admin'],
        },
        {
          label: 'Configuracion IA',
          path: '/admin/ai-config',
          icon: <Brain className="w-6 h-6" />,
          roles: ['admin'],
        },
      ],
    },
  ];

  // Auto-expand menu based on current route
  useEffect(() => {
    const performanceActive = location.pathname.startsWith('/performance');
    const monitoringActive = location.pathname.startsWith('/monitoring');
    const adminActive = location.pathname.startsWith('/admin') || location.pathname.startsWith('/users');
    const designActive =
      location.pathname.startsWith('/script-designer') ||
      location.pathname.startsWith('/ai-script-designer');
    setExpandedMenus((prev) => ({
      ...prev,
      ...(performanceActive ? { 'Análisis': true } : {}),
      ...(monitoringActive ? { Monitoreo: true } : {}),
      ...(adminActive ? { Administracion: true } : {}),
      ...(designActive ? { 'Diseño': true } : {}),
    }));
  }, [location.pathname]);

  const toggleSubmenu = (label: string) => {
    if (collapsed) return;
    setExpandedMenus((prev) => ({ ...prev, [label]: !prev[label] }));
  };

  const isItemVisible = (item: MenuItem | SubMenuItem): boolean => {
    if (!('roles' in item) || !item.roles) return true;
    return user ? item.roles.includes(user.role) : false;
  };

  const isActive = (path: string) => location.pathname === path;
  const isParentActive = (children: SubMenuItem[]) =>
    children.some((child) => location.pathname.startsWith(child.path));

  const navLinkClasses = (active: boolean) =>
    `flex items-center gap-3 px-4 py-3.5 rounded-xl transition-all duration-200 text-2xl font-medium ${
      active
        ? 'bg-sqa-gold/15 text-sqa-gold border-r-3 border-sqa-gold'
        : 'text-slate-400 hover:text-white hover:bg-white/5'
    }`;

  return (
    <aside
      className={`fixed left-0 top-0 h-full bg-gradient-to-b from-sqa-navy-light to-sqa-navy border-r border-sqa-border flex flex-col z-40 transition-all duration-300 ${
        collapsed ? 'w-16' : 'w-72'
      }`}
    >
      {/* Header */}
      <div className="flex items-center justify-between px-4 py-5 border-b border-sqa-border">
        {!collapsed && (
          <div className="flex items-center gap-3 min-w-0">
            <div className="min-w-0">
              <h1 className="text-3xl font-bold text-white truncate">
                sqa<span className="text-sqa-gold">_</span>
              </h1>
              <p className="text-xl text-slate-500 truncate">Quality Assurance</p>
            </div>
          </div>
        )}
        {collapsed && (
          <div className="flex items-center justify-center w-full">
            <span className="text-2xl font-bold text-white">
              s<span className="text-sqa-gold">_</span>
            </span>
          </div>
        )}
      </div>

      {/* Toggle button */}
      <button
        onClick={onToggle}
        className="absolute -right-3 top-7 w-6 h-6 bg-sqa-card border border-sqa-border rounded-full flex items-center justify-center text-slate-400 hover:text-sqa-gold hover:bg-sqa-navy-light transition-colors z-50"
      >
        {collapsed ? <ChevronRight className="w-3 h-3" /> : <ChevronLeft className="w-3 h-3" />}
      </button>

      {/* Navigation */}
      <nav className="flex-1 overflow-y-auto py-4 px-2 space-y-1">
        {menuItems.filter(isItemVisible).map((item) => {
          if (item.children) {
            const visibleChildren = item.children.filter(isItemVisible);
            if (visibleChildren.length === 0) return null;
            const parentActive = isParentActive(visibleChildren);
            const isExpanded = expandedMenus[item.label];

            return (
              <div key={item.label}>
                <button
                  onClick={() => toggleSubmenu(item.label)}
                  className={`w-full ${navLinkClasses(parentActive)} ${
                    collapsed ? 'justify-center' : 'justify-between'
                  }`}
                  title={collapsed ? item.label : undefined}
                >
                  <div className="flex items-center gap-3">
                    {item.icon}
                    {!collapsed && <span>{item.label}</span>}
                  </div>
                  {!collapsed &&
                    (isExpanded ? (
                      <ChevronUp className="w-6 h-6" />
                    ) : (
                      <ChevronDown className="w-6 h-6" />
                    ))}
                </button>

                {!collapsed && isExpanded && (
                  <div className="ml-4 mt-1 space-y-1 border-l border-sqa-border pl-3">
                    {visibleChildren.map((child) => (
                      <NavLink
                        key={child.path}
                        to={child.path}
                        className={navLinkClasses(isActive(child.path))}
                      >
                        {child.icon}
                        <span>{child.label}</span>
                      </NavLink>
                    ))}
                  </div>
                )}
              </div>
            );
          }

          return (
            <NavLink
              key={item.path}
              to={item.path!}
              className={navLinkClasses(isActive(item.path!))}
              title={collapsed ? item.label : undefined}
            >
              {item.icon}
              {!collapsed && <span>{item.label}</span>}
            </NavLink>
          );
        })}
      </nav>

      {/* User footer */}
      <div className="border-t border-sqa-border p-3">
        {!collapsed ? (
          <div className="space-y-2">
            <NavLink
              to="/profile"
              className="flex items-center gap-3 px-3 py-3 rounded-xl text-slate-400 hover:text-white hover:bg-white/5 transition-all"
            >
              <div className="w-10 h-10 bg-sqa-gold/20 rounded-full flex items-center justify-center flex-shrink-0">
                <span className="text-xl font-bold text-sqa-gold">
                  {user?.full_name?.charAt(0)?.toUpperCase() || 'U'}
                </span>
              </div>
              <div className="min-w-0">
                <p className="text-xl font-medium text-slate-200 truncate">
                  {user?.full_name || 'Usuario'}
                </p>
                <p className="text-lg text-slate-500 capitalize">{user?.role || 'viewer'}</p>
              </div>
            </NavLink>
            <button
              onClick={logout}
              className="flex items-center gap-3 px-3 py-3 rounded-xl text-slate-400 hover:text-red-400 hover:bg-red-900/20 transition-all w-full text-xl"
            >
              <LogOut className="w-6 h-6" />
              <span>Cerrar Sesion</span>
            </button>
          </div>
        ) : (
          <div className="space-y-2 flex flex-col items-center">
            <NavLink
              to="/profile"
              className="w-10 h-10 bg-sqa-gold/20 rounded-full flex items-center justify-center text-sqa-gold hover:bg-sqa-gold/30 transition-all"
              title="Perfil"
            >
              <UserCircle className="w-6 h-6" />
            </NavLink>
            <button
              onClick={logout}
              className="w-10 h-10 rounded-full flex items-center justify-center text-slate-400 hover:text-red-400 hover:bg-red-900/20 transition-all"
              title="Cerrar Sesion"
            >
              <LogOut className="w-6 h-6" />
            </button>
          </div>
        )}
      </div>
    </aside>
  );
}
