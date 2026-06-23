import { defineConfig } from 'vitest/config'
import react from '@vitejs/plugin-react'
import tsconfigPaths from 'vite-tsconfig-paths'
import path from 'path'

export default defineConfig({
  plugins: [react(), tsconfigPaths()],
  resolve: {
    alias: {
      '@': path.resolve(__dirname, './frontend/src'),
    },
  },
  test: {
    globals: true,
    environment: 'jsdom',
    setupFiles: ['./frontend/src/test/setup.ts'],
    include: ['frontend/src/**/*.test.ts', 'frontend/src/**/*.test.tsx'],
    exclude: ['node_modules', 'dist', '.next'],
    coverage: {
      provider: 'v8',
      exclude: [
        'node_modules/',
        'dist/',
        '.next/',
        'frontend/src/main.tsx',
        'frontend/src/App.tsx',
        'frontend/src/**/*.stories.tsx',
      ],
      thresholds: {
        global: {
          branches: 80,
          functions: 80,
          lines: 80,
          statements: 80,
        },
      },
    },
    mockReset: true,
    singleThread: true,
  },
})
