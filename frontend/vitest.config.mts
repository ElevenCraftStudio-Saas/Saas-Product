import { defineConfig } from 'vitest/config';
import react from '@vitejs/plugin-react-swc';
import { fileURLToPath } from 'node:url';

export default defineConfig({
  plugins: [react()],
  resolve: {
    alias: { '@': fileURLToPath(new URL('./', import.meta.url)) },
  },
  test: {
    environment: 'jsdom',
    globals: true,
    setupFiles: ['./test/setup.ts'],
    css: false,
    include: ['test/**/*.test.{ts,tsx}'],
    coverage: {
      provider: 'v8',
      reporter: ['text-summary', 'text', 'lcov'],
      include: ['lib/**', 'services/**', 'components/**'],
      exclude: [
        '**/*.d.ts',
        'lib/firebase.ts', // SDK init — not unit-testable
        'components/ui/**', // upstream shadcn/base-ui primitives
      ],
      // Regression floor — set just under current (stmts 68.9 / branch 78.8 /
      // funcs 63.7). Raise as camera/viewer/page surfaces gain tests.
      thresholds: { statements: 65, branches: 75, functions: 60, lines: 65 },
    },
  },
});
