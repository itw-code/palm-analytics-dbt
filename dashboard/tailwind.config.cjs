/** Project-level Tailwind preset — picked up by .evidence/template/tailwind.config.cjs.
 *  Serif display stack (system fonts only: no network fetch, offline CI-safe)
 *  + system sans. Evidence merges this as a preset. */
module.exports = {
  theme: {
    extend: {
      fontFamily: {
        display: ['Georgia', '"Iowan Old Style"', 'Palatino', 'serif'],
        sans: ['Inter', 'system-ui', '-apple-system', '"Segoe UI"', 'sans-serif'],
        mono: ['"IBM Plex Mono"', 'ui-monospace', 'monospace'],
      },
    },
  },
};
