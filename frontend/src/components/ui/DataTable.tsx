/**
 * Tabla de datos (mockup: «Tabla: acciones fijas, y tarjetas cuando el
 * contenedor es angosto»).
 *
 * - La columna de acciones queda FIJA a la derecha al desplazar en horizontal:
 *   el Historial de reportes la perdía entera a 1366 px (auditoría 153 §2.2).
 * - Si el CONTENEDOR mide menos de 58rem, cada fila pasa a tarjeta y cada
 *   celda lleva su encabezado delante (atributo data-l). Ver ui.css.
 * - `titulo` es el <caption> (oculto a la vista): el lector de pantalla
 *   anuncia la tabla por su nombre.
 * - Sin filas, pinta `vacio`. Los estados de carga y error NO son de la tabla:
 *   la pantalla pinta LoadingState o ErrorState en su lugar, nunca una tabla
 *   vacía que parezca «0 resultados».
 */
import { CSSProperties, ReactNode } from 'react';
import { cx } from './cx';

export interface Columna<T> {
  clave: string;
  encabezado: string;
  celda: (fila: T) => ReactNode;
  /** Números a la derecha y en tabular-nums. */
  numerica?: boolean;
  sinCorte?: boolean;
  /** En modo tarjeta, la celda ocupa toda la fila y no repite el encabezado. */
  completa?: boolean;
}

export interface DataTableProps<T> {
  titulo: string;
  columnas: Columna<T>[];
  filas: T[];
  claveFila: (fila: T) => string;
  /** Botones de la fila: van en la columna fija. */
  acciones?: (fila: T) => ReactNode;
  etiquetaAcciones?: string;
  vacio?: ReactNode;
  /** Ancho mínimo de la tabla antes de desplazar, en rem (por defecto, el de su contenido). */
  anchoMinimoRem?: number;
  className?: string;
}

export function DataTable<T>({
  titulo, columnas, filas, claveFila, acciones, etiquetaAcciones = 'Acciones', vacio, anchoMinimoRem, className,
}: DataTableProps<T>) {
  if (filas.length === 0 && vacio) return <>{vacio}</>;

  return (
    <div className={cx('kx-tabla-caja min-w-0', className)}>
      <div className="kx-tabla-scroll">
        <table
          className="kx-tabla w-full border-collapse"
          // Variable y no `min-width` en línea: en modo tarjeta, ui.css la anula.
          style={anchoMinimoRem ? ({ '--kx-tabla-min': `${anchoMinimoRem}rem` } as CSSProperties) : undefined}
        >
          <caption className="sr-only">{titulo}</caption>
          <thead>
            <tr>
              {columnas.map((c) => (
                <th
                  key={c.clave}
                  scope="col"
                  className={cx(
                    'whitespace-nowrap border-b border-line px-4 py-3 text-nota font-bold text-ink-muted',
                    c.numerica ? 'text-right' : 'text-left',
                  )}
                >
                  {c.encabezado}
                </th>
              ))}
              {acciones && (
                <th scope="col" className="kx-acciones border-b border-line px-4 py-3 text-right text-nota font-bold text-ink-muted">
                  {etiquetaAcciones}
                </th>
              )}
            </tr>
          </thead>
          <tbody>
            {filas.map((fila, i) => (
              <tr key={claveFila(fila)}>
                {columnas.map((c) => (
                  <td
                    key={c.clave}
                    data-l={c.completa ? undefined : c.encabezado}
                    className={cx(
                      'px-4 py-3 align-middle text-ink',
                      i > 0 && 'border-t border-line',
                      c.numerica && 'text-right font-num tabular-nums',
                      c.sinCorte && 'whitespace-nowrap',
                    )}
                  >
                    {c.celda(fila)}
                  </td>
                ))}
                {acciones && (
                  <td className={cx('kx-acciones px-4 py-3', i > 0 && 'border-t border-line')}>
                    <div className="flex items-center justify-end gap-0.5">{acciones(fila)}</div>
                  </td>
                )}
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    </div>
  );
}
