/** @type {import('tailwindcss').Config} */

// Rediseño (Etapa 0): cada color apunta a una variable de src/styles/tokens.css,
// guardada como canales RGB sueltos para que funcionen las opacidades
// (`bg-primary/50`). Solo se AÑADE: la paleta por defecto de Tailwind y `sqa`
// siguen aquí mientras queden pantallas sin migrar.
const token = (nombre) => `rgb(var(--${nombre}) / <alpha-value>)`;
const tokens = (nombres) => Object.fromEntries(nombres.map((n) => [n, token(n)]));

export default {
  // `dark:` = tema oscuro (data-theme en <html>), salvo dentro de .tema-claro,
  // que es el contenido de las pantallas aún no migradas.
  darkMode: ['variant', '&:is([data-theme="dark"] *):not(:is(.tema-claro *))'],
  content: [
    "./index.html",
    "./src/**/*.{js,ts,jsx,tsx}",
  ],
  theme: {
    extend: {
      // Cortes del armazón del mockup: bajo 1100 px la navegación superior pasa a
      // menú desplegable y el riel a sub-pestañas; bajo 900 px la cabecera
      // esconde el nombre del usuario y el atajo de teclado.
      screens: {
        cabecera: '901px',
        nav: '1100px',
      },
      gridTemplateColumns: {
        login: 'minmax(0, 1.3fr) minmax(19rem, 27rem)',
      },
      backgroundImage: {
        // Velo que oscurece el lienzo detrás del titular (mockup: .login::before).
        'velo-login': 'radial-gradient(120% 90% at 0% 45%, rgb(var(--lg-bg)) 0%, transparent 62%)',
      },
      height: {
        'bajo-cabecera': 'calc(100vh - var(--hdr-h))',
      },
      colors: {
        sqa: {
          navy: '#0a1628',
          'navy-light': '#111d35',
          gold: '#f5a623',
          'gold-dark': '#d4891a',
          'gold-light': '#f7b84e',
          card: '#162040',
          border: '#1e3a5f',
        },
        // Superficies y texto. `canvas` es --bg y `ink` es --text: con los
        // nombres del mockup saldrían clases como `bg-bg` o `text-text`.
        canvas: token('bg'),
        surface: token('surface'),
        'surface-2': token('surface-2'),
        line: token('border'),
        'line-strong': token('border-strong'),
        ink: token('text'),
        'ink-muted': token('text-muted'),
        ...tokens([
          'link',
          'primary', 'on-primary', 'primary-hover', 'primary-soft', 'on-primary-soft',
          'accent', 'accent-text', 'cta', 'on-cta', 'cta-hover',
          'nav-bg', 'nav-text', 'nav-muted', 'nav-hover', 'nav-active-bg', 'nav-active-text',
          'nav-border', 'nav-label',
          'hdr-bg', 'hdr-text', 'hdr-muted', 'hdr-border',
          'lg-bg', 'lg-2', 'lg-text', 'lg-muted', 'lg-line', 'lg-hot',
          'brand-bg', 'brand-text', 'brand-muted',
          'hero-bg', 'hero-2', 'hero-text', 'hero-muted', 'hero-line',
          'ok', 'ok-bg', 'warn', 'warn-bg', 'err', 'err-bg', 'info', 'info-bg',
          'danger', 'on-danger',
          'focus', 'focus-nav', 'focus-hdr', 'focus-hero',
          'chart-1', 'chart-2', 'chart-3',
          'scrim',
        ]),
      },
      fontFamily: {
        display: 'var(--font-display)',
        body: 'var(--font-body)',
        num: 'var(--font-num)',
        code: 'var(--font-code)',
        titular: 'var(--font-titular)',
      },
      // `rounded-s` ya existe en Tailwind (radio lógico de inicio): de ahí los
      // nombres en español.
      borderRadius: {
        chico: 'var(--r-s)',
        control: 'var(--r-m)',
        panel: 'var(--r-l)',
        pill: 'var(--r-pill)',
        'tarjeta-login': 'calc(var(--r-l) + 6px)',
      },
      boxShadow: {
        card: 'var(--sh-card)',
        pop: 'var(--sh-pop)',
        seg: 'var(--sh-seg)',
        login: 'var(--sh-login)',
        // El resplandor del botón primario en Índigo.
        boton: '0 8px 18px -8px rgb(var(--primary))',
        // Línea izquierda de la columna de acciones fija.
        'borde-izq': '-1px 0 0 rgb(var(--border))',
      },
      // Tamaños del mockup que no están en la escala de Tailwind.
      fontSize: {
        mini: '.6875rem',
        nota: '.8125rem',
        control: '.9375rem',
        destacado: '1.0625rem',
        h2: '1.1875rem',
        h1: 'var(--h1)',
        kpi: '2rem',
        tarjeta: '1.625rem',
        // Inicio de sesión: tamaños fluidos del mockup (.lg-copy h2, .lg-hud b, .lg-copy>p).
        titular: ['clamp(2.5rem, 6.2vw, 5.75rem)', { lineHeight: '.98' }],
        'cifra-login': ['clamp(1.5rem, 2.6vw, 2.5rem)', { lineHeight: '1.1' }],
        lema: 'clamp(1rem, 1.3vw, 1.25rem)',
      },
      spacing: {
        '4.5': '1.125rem',
        '5.5': '1.375rem',
        '8.5': '2.125rem',
        '76': '19rem',
        // Inicio de sesión: márgenes y separaciones fluidos del mockup (.login).
        'login-x': 'clamp(1.25rem, 5vw, 5.5rem)',
        'login-y': 'clamp(2rem, 9vh, 6rem)',
        'login-gap': 'clamp(1.5rem, 5vw, 5rem)',
        'login-copia': 'clamp(1.25rem, 3vh, 2.25rem)',
        'tarjeta-login': 'clamp(1.5rem, 2.5vw, 2.25rem)',
        control: '2.625rem',
        'control-sm': '2rem',
        'control-lg': '3.125rem',
        hdr: 'var(--hdr-h)',
        riel: 'var(--riel-w)',
      },
      maxHeight: {
        lista: '50vh',
      },
      minWidth: {
        cifra: '5ch',
      },
      maxWidth: {
        titular: '12ch',
        lema: '34rem',
        'tarjeta-login': '27rem',
        pagina: 'var(--page-max)',
        lectura: 'var(--read-max)',
        dialogo: '34rem',
        'dialogo-ancho': '52rem',
      },
      outlineWidth: {
        3: '3px',
      },
      zIndex: {
        cabecera: '30',
        menu: '45',
        modal: '80',
        aviso: '90',
      },
      // `aria-invalid:` (Tailwind no lo trae): el error de un campo se pinta
      // desde el mismo atributo que lo anuncia.
      aria: {
        invalid: 'invalid="true"',
        current: 'current="page"',
      },
      letterSpacing: {
        display: 'var(--ls-display)',
        titular: '-.035em',
      },
      // Movimiento del mockup (bloques BASE y zz-motion). Se usan siempre con
      // `motion-safe:`; la pausa global está en src/styles/ui.css.
      keyframes: {
        pop: { from: { opacity: '0', transform: 'translateY(8px) scale(.98)' } },
        rise: { from: { opacity: '0', transform: 'translateY(6px)' } },
        sube: { from: { opacity: '0', transform: 'translateY(18px)' } },
        tarjeta: { from: { opacity: '0', transform: 'translateY(46px) scale(.97)' } },
        pulso: { '50%': { opacity: '.45' } },
        parpadeo: { '50%': { opacity: '0' } },
        crece: { from: { transform: 'scaleX(0)' } },
        flota: { '50%': { transform: 'translateY(-6px)' } },
      },
      animation: {
        pop: 'pop .18s cubic-bezier(.2,.8,.2,1)',
        rise: 'rise .32s cubic-bezier(.2,.8,.2,1) both',
        sube: 'sube .7s cubic-bezier(.2,.8,.2,1) both',
        tarjeta: 'tarjeta .7s .2s cubic-bezier(.2,.8,.2,1) both',
        pulso: 'pulso 1.2s ease-in-out infinite',
        parpadeo: 'parpadeo 1.4s ease-in-out infinite',
        crece: 'crece 1s .35s cubic-bezier(.2,.8,.2,1) both',
        flota: 'flota 1.8s ease-in-out infinite',
      },
      transitionTimingFunction: {
        suave: 'cubic-bezier(.2,.8,.2,1)',
      },
    },
  },
  plugins: [],
}
