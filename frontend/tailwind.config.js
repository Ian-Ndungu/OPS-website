/** OPS design tokens. Colours are CSS variables (see index.css) so light/dark share one set of classes.
 *  If your app already has a Tailwind theme, merge `colors.ops`, the fonts and the CSS variables instead. */
const v = (n) => `rgb(var(--${n}) / <alpha-value>)`
export default {
  content: ['./index.html', './src/**/*.{js,jsx}'],
  theme: {
    extend: {
      colors: {
        white: v('ink'),
        slate: { 200: v('ink'), 300: v('ink-2'), 400: v('mute') },
        ops: {
          bg: v('bg'), card: v('card'), raised: v('raised'), line: v('line'),
          accent: v('accent'), 'on-accent': v('on-accent'), link: v('link'), gold: v('link'),
          mute: v('mute'), pink: v('pink'), ok: v('ok'), warn: v('warn'), bad: v('bad'), info: v('info'),
        },
      },
      fontFamily: {
        display: ['"Bricolage Grotesque Variable"', '"Bricolage Grotesque"', 'system-ui', 'sans-serif'],
        sans: ['"Instrument Sans Variable"', '"Instrument Sans"', 'system-ui', 'sans-serif'],
      },
    },
  },
  plugins: [],
}
