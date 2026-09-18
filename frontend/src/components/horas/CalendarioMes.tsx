/**
 * El calendario del mes (ETAPA H2b.3, especificación de horas v1.1 §4.1).
 *
 * Una casilla por día, y cada una dice su estado de un vistazo. **No calcula
 * nada**: el estado, las horas que faltan y la marca de desfase vienen resueltos
 * de `GET /time/month`, que a su vez los saca de `services/horas/calendario.py`.
 *
 * El color solo no basta —hay quien no lo distingue—, así que cada casilla lleva
 * además su cifra y su palabra: «faltan 6,5 h», el nombre del festivo, «extra».
 */
import { Zap } from 'lucide-react';
import {
  DiaDelMes, columnaLunesPrimero, diaDelMes, fechaLarga, horas,
} from '../../api/horasApi';

export type EstadoDia =
  | 'completo' | 'incompleto' | 'festivo' | 'ausencia' | 'finde' | 'porVenir';

/** El estado de la casilla, en un solo sitio para que el color y la leyenda no
 *  puedan discrepar. El orden es el de §4.1: primero lo que no se reclama. */
export function estadoDe(d: DiaDelMes): EstadoDia {
  if (d.is_holiday) return 'festivo';
  if (d.is_absence) return 'ausencia';
  if (parseFloat(String(d.expected_hours)) === 0) return 'finde';
  if (d.incomplete) return 'incompleto';
  if (parseFloat(String(d.total_hours)) > 0) return 'completo';
  return 'porVenir';   // día laborable que todavía no ha llegado
}

const COLOR: Record<EstadoDia, string> = {
  completo:   'bg-emerald-50 border-emerald-300 text-emerald-900',
  incompleto: 'bg-amber-50 border-amber-300 text-amber-900',
  festivo:    'bg-indigo-50 border-indigo-200 text-indigo-900',
  ausencia:   'bg-purple-50 border-purple-200 text-purple-900',
  finde:      'bg-gray-50 border-gray-200 text-gray-400',
  porVenir:   'bg-white border-gray-200 text-gray-600',
};

const LEYENDA: [EstadoDia, string][] = [
  ['completo', 'Jornada completa'],
  ['incompleto', 'Incompleto o sin registrar'],
  ['festivo', 'Festivo'],
  ['ausencia', 'Ausencia'],
  ['finde', 'Fin de semana'],
  ['porVenir', 'Por venir'],
];

const CABECERA = ['lun', 'mar', 'mié', 'jue', 'vie', 'sáb', 'dom'];

interface Props {
  dias: DiaDelMes[];
  hoy: string;
  seleccionado: string;
  onElegir: (iso: string) => void;
}

export default function CalendarioMes({ dias, hoy, seleccionado, onElegir }: Props) {
  if (!dias.length) return null;
  const huecos = columnaLunesPrimero(dias[0].date);

  return (
    <div>
      <div className="grid grid-cols-7 gap-2 mb-2">
        {CABECERA.map((d) => (
          <div key={d} className="text-center text-base font-semibold text-gray-500 uppercase">{d}</div>
        ))}
      </div>

      <div className="grid grid-cols-7 gap-2" data-testid="calendario">
        {Array.from({ length: huecos }, (_, i) => <div key={`hueco-${i}`} />)}

        {dias.map((d) => {
          const estado = estadoDe(d);
          const elegido = d.date === seleccionado;
          const esHoy = d.date === hoy;
          const extra = parseFloat(String(d.overtime_hours));
          const registradas = parseFloat(String(d.ordinary_hours));

          return (
            <button key={d.date} type="button" onClick={() => onElegir(d.date)}
              data-testid="casilla" data-fecha={d.date} data-estado={estado}
              data-desfase={d.has_over_estimate ? 'si' : 'no'}
              aria-pressed={elegido}
              aria-label={`${fechaLarga(d.date)}. ${
                estado === 'festivo' ? d.non_working_reason || 'Festivo'
                  : estado === 'ausencia' ? d.non_working_reason || 'Ausencia'
                  : estado === 'finde' ? 'Fin de semana'
                  : estado === 'incompleto' ? `Faltan ${horas(d.missing_hours)} horas`
                  : estado === 'completo' ? `${horas(d.total_hours)} horas registradas`
                  : 'Sin registrar'}`}
              className={`min-h-[96px] p-2 rounded-xl border-2 text-left transition ${COLOR[estado]} ${
                elegido ? 'ring-2 ring-[#f5a623] border-[#f5a623]' : 'hover:brightness-95'}`}>

              <div className="flex items-start justify-between">
                <span className={`text-lg font-bold tabular-nums ${
                  esHoy ? 'bg-[#0a1628] text-white rounded-lg px-2' : ''}`}>
                  {diaDelMes(d.date)}
                </span>
                {extra > 0 && (
                  <span className="flex items-center gap-0.5 text-sm text-indigo-700"
                    data-testid="casilla-extra" title="Horas extra">
                    <Zap className="w-3.5 h-3.5" />{horas(extra)}
                  </span>
                )}
              </div>

              {estado === 'festivo' || estado === 'ausencia' ? (
                <div className="mt-1 text-sm leading-tight" data-testid="casilla-motivo">
                  {d.non_working_reason || (estado === 'festivo' ? 'Festivo' : 'Ausencia')}
                </div>
              ) : estado === 'finde' ? (
                <div className="mt-1 text-sm">—</div>
              ) : (
                <div className="mt-1">
                  <div className="text-base font-semibold tabular-nums">
                    {registradas > 0 ? `${horas(registradas)} h` : '—'}
                  </div>
                  {estado === 'incompleto' && (
                    <div className="text-sm leading-tight" data-testid="casilla-faltan">
                      {d.entries_count === 0 ? 'sin registrar' : `faltan ${horas(d.missing_hours)} h`}
                    </div>
                  )}
                </div>
              )}

              {d.has_over_estimate && (
                <div className="mt-1 text-sm font-semibold text-amber-800" data-testid="casilla-desfase">
                  desfase
                </div>
              )}
            </button>
          );
        })}
      </div>

      <div className="flex flex-wrap gap-x-5 gap-y-2 mt-4" data-testid="leyenda">
        {LEYENDA.map(([estado, texto]) => (
          <span key={estado} className="flex items-center gap-2 text-base text-gray-600">
            <span className={`w-4 h-4 rounded border-2 ${COLOR[estado]}`} />
            {texto}
          </span>
        ))}
      </div>
    </div>
  );
}
