/** Une clases condicionales sin dependencias: cx('a', cond && 'b'). */
export function cx(...partes: Array<string | false | null | undefined>): string {
  return partes.filter(Boolean).join(' ');
}
