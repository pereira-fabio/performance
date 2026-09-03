/** @type {import('tailwindcss').Config} */
export default {
  content: ['./index.html', './src/**/*.{js,ts,jsx,tsx}'],
  theme: {
    extend: {
      // Colours resolve to the CSS variables in index.css, so a single
      // definition serves both themes and utilities stay readable.
      colors: {
        bg: 'var(--bg)',
        surface: 'var(--surface)',
        fg: 'var(--fg)',
        'fg-strong': 'var(--fg-strong)',
        muted: 'var(--muted)',
        faint: 'var(--faint)',
        line: 'var(--line)',
        'line-strong': 'var(--line-strong)',
        accent: 'var(--accent)',
        'accent-soft': 'var(--accent-soft)',
        card: 'var(--card)',
        positive: 'var(--positive)',
        caution: 'var(--caution)',
        negative: 'var(--negative)',
        run: 'var(--run)',
        walk: 'var(--walk)',
        gym: 'var(--gym)',
      },
      fontSize: {
        '2xs': ['0.6875rem', { lineHeight: '1rem' }],
      },
      maxWidth: { content: '56rem' },
      boxShadow: { card: 'var(--card-shadow)' },
    },
  },
  plugins: [],
}
