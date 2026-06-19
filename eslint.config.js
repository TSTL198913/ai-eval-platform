import globals from 'globals'
import pluginJs from '@eslint/js'
import pluginReact from 'eslint-plugin-react'
import pluginReactHooks from 'eslint-plugin-react-hooks'
import pluginReactRefresh from 'eslint-plugin-react-refresh'
import tseslint from 'typescript-eslint'

export default [
  {
    files: ['**/*.{js,jsx,ts,tsx}'],
    ignores: ['node_modules/', 'dist/', 'build/', '.next/', 'src/test/', '**/*.test.ts', '**/*.test.tsx', 'htmlcov/', 'htmlcov_cache/'],
    languageOptions: {
      ecmaVersion: 'latest',
      sourceType: 'module',
      parser: tseslint.parser,
      globals: {
        ...globals.browser,
        ...globals.node,
        vi: 'readonly',
        describe: 'readonly',
        it: 'readonly',
        test: 'readonly',
        expect: 'readonly',
        beforeEach: 'readonly',
        afterEach: 'readonly',
      },
    },
    plugins: {
      react: pluginReact,
      'react-hooks': pluginReactHooks,
      'react-refresh': pluginReactRefresh,
      '@typescript-eslint': tseslint.plugin,
    },
    rules: {
      ...pluginJs.configs.recommended.rules,
      ...tseslint.configs.recommended.rules,
      ...pluginReact.configs.recommended.rules,
      ...pluginReact.configs['jsx-runtime'].rules,
      ...pluginReactHooks.configs.recommended.rules,
      'react/jsx-no-target-blank': 'off',
      'react-refresh/only-export-components': ['warn', { allowConstantExport: true }],
      'no-unused-vars': 'off',
      '@typescript-eslint/no-unused-vars': ['warn', { varsIgnorePattern: '^_', argsIgnorePattern: '^_' }],
    },
  },
]
