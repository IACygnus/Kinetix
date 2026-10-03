/**
 * «Ir a una pantalla» (mockup: ACT.palette). Se abre con Ctrl + K o con la
 * lupa de la cabecera. Ofrece SOLO las pantallas que el rol puede abrir, más
 * «Mi perfil».
 *
 * Teclado: escribir filtra; flechas arriba/abajo mueven la selección; Intro
 * abre. La lista es un listbox con aria-activedescendant, así el foco no sale
 * del campo de búsqueda.
 */
import { KeyboardEvent, useEffect, useMemo, useRef, useState } from 'react';
import { useNavigate } from 'react-router-dom';
import { Modal } from '../ui/Modal';
import { Field } from '../ui/Field';
import { Input } from '../ui/Input';
import { cx } from '../ui/cx';
import { Modulo, PANTALLAS_SUELTAS } from './navegacion';

interface Opcion {
  etiqueta: string;
  modulo: string;
  ruta: string;
}

const normalizar = (s: string) => s.normalize('NFD').replace(/\p{Diacritic}/gu, '').toLowerCase();

export function BuscadorPantallas({ abierto, onCerrar, modulos }: { abierto: boolean; onCerrar: () => void; modulos: Modulo[] }) {
  const navigate = useNavigate();
  const campo = useRef<HTMLInputElement>(null);
  const [q, setQ] = useState('');
  const [sel, setSel] = useState(0);

  const todas = useMemo<Opcion[]>(() => {
    const out: Opcion[] = [];
    for (const m of modulos) {
      if (m.ruta) out.push({ etiqueta: m.etiqueta, modulo: '', ruta: m.ruta });
      for (const p of m.pantallas ?? []) out.push({ etiqueta: p.etiqueta, modulo: m.etiqueta, ruta: p.ruta });
    }
    for (const p of PANTALLAS_SUELTAS) out.push({ etiqueta: p.etiqueta, modulo: '', ruta: p.ruta });
    return out;
  }, [modulos]);

  const lista = useMemo(() => {
    const n = normalizar(q.trim());
    return n ? todas.filter((o) => normalizar(`${o.etiqueta} ${o.modulo}`).includes(n)) : todas;
  }, [q, todas]);

  useEffect(() => {
    if (abierto) {
      setQ('');
      setSel(0);
    }
  }, [abierto]);

  useEffect(() => setSel(0), [q]);

  // La opción elegida con las flechas, siempre a la vista.
  useEffect(() => {
    if (abierto) document.getElementById(`buscador-opcion-${sel}`)?.scrollIntoView({ block: 'nearest' });
  }, [sel, abierto]);

  const ir = (o: Opcion | undefined) => {
    if (!o) return;
    onCerrar();
    navigate(o.ruta);
  };

  const alTeclear = (e: KeyboardEvent<HTMLInputElement>) => {
    if (e.key === 'ArrowDown') {
      e.preventDefault();
      setSel((s) => Math.min(lista.length - 1, s + 1));
    } else if (e.key === 'ArrowUp') {
      e.preventDefault();
      setSel((s) => Math.max(0, s - 1));
    } else if (e.key === 'Enter') {
      e.preventDefault();
      ir(lista[sel]);
    }
  };

  const idOpcion = (i: number) => `buscador-opcion-${i}`;

  return (
    <Modal abierto={abierto} onCerrar={onCerrar} titulo="Ir a una pantalla" focoInicial={campo}>
      <Field id="buscador-q" etiqueta="Buscar">
        <Input
          ref={campo}
          id="buscador-q"
          value={q}
          onChange={(e) => setQ(e.target.value)}
          onKeyDown={alTeclear}
          placeholder="Escribe el nombre de la pantalla"
          autoComplete="off"
          role="combobox"
          aria-expanded="true"
          aria-controls="buscador-lista"
          aria-activedescendant={lista.length ? idOpcion(sel) : undefined}
        />
      </Field>
      {lista.length ? (
        <ul id="buscador-lista" role="listbox" aria-label="Pantallas" className="grid max-h-lista gap-0.5 overflow-auto">
          {lista.map((o, i) => (
            <li
              key={o.ruta}
              id={idOpcion(i)}
              role="option"
              aria-selected={i === sel}
              onMouseEnter={() => setSel(i)}
              onClick={() => ir(o)}
              className={cx(
                'flex min-h-10 items-center justify-between gap-4 rounded-control px-3 py-1 cursor-pointer',
                i === sel ? 'bg-primary-soft text-on-primary-soft' : 'text-ink',
              )}
            >
              <span>{o.etiqueta}</span>
              <small className="opacity-80">{o.modulo}</small>
            </li>
          ))}
        </ul>
      ) : (
        <p role="status" className="text-sm text-ink-muted">
          Ninguna pantalla coincide.
        </p>
      )}
    </Modal>
  );
}
