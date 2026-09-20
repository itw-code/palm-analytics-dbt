/** Project-level Tailwind preset — picked up by .evidence/template/tailwind.config.cjs.
 *  Serif display stack (system fonts only: no network fetch, offline CI-safe)
 *  + system sans. Evidence merges this as a preset. */
module.exports = {
  theme: {
    extend: {
      fontFamily: {
        display: ['"Iowan Old Style"', 'Palatino', 'Georgia', 'serif'],
        sans: ['system-ui', '-apple-system', '"Segoe UI"', 'Inter', 'sans-serif'],
      },
    },
  },
};
