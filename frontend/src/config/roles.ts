/**
 * El nombre del rol, en español (ETAPA H6, H-D65).
 *
 * Vivía suelto dentro de `Profile.tsx`, así que la barra lateral y la pantalla
 * de asignaciones enseñaban el valor crudo de la base —`admin`, `analyst`— y
 * cada sitio decía una cosa distinta del mismo usuario. Una sola tabla.
 */
export const NOMBRE_ROL: Record<string, string> = {
  admin: 'Administrador',
  analyst: 'Analista',
  viewer: 'Visor',
};

export const nombreRol = (rol?: string | null): string =>
  NOMBRE_ROL[rol || 'viewer'] || 'Visor';
