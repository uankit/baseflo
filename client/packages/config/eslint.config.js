import js from '@eslint/js';
import tsParser from '@typescript-eslint/parser';
import tsPlugin from '@typescript-eslint/eslint-plugin';
import reactPlugin from 'eslint-plugin-react';
import reactHooksPlugin from 'eslint-plugin-react-hooks';
import a11yPlugin from 'eslint-plugin-jsx-a11y';
import importPlugin from 'eslint-plugin-import';
import globals from 'globals';

/**
 * Shared ESLint flat config. Re-exported from each package's eslint.config.js.
 * Enforces the architectural boundaries from docs/06-design.md §6.
 */
export default [
  js.configs.recommended,
  {
    files: ['**/*.{ts,tsx,js,jsx}'],
    languageOptions: {
      parser: tsParser,
      parserOptions: {
        ecmaVersion: 'latest',
        sourceType: 'module',
        ecmaFeatures: { jsx: true },
      },
      globals: {
        ...globals.browser,
        ...globals.node,
        ...globals.es2022,
      },
    },
    plugins: {
      '@typescript-eslint': tsPlugin,
      react: reactPlugin,
      'react-hooks': reactHooksPlugin,
      'jsx-a11y': a11yPlugin,
      import: importPlugin,
    },
    settings: {
      react: { version: 'detect' },
      'import/resolver': {
        typescript: { alwaysTryTypes: true },
        node: true,
      },
    },
    rules: {
      // Type safety — locked by 06-design.md §2 ADRs.
      'no-unused-vars': 'off',
      '@typescript-eslint/no-explicit-any': 'error',
      '@typescript-eslint/consistent-type-imports': ['error', { prefer: 'type-imports' }],
      '@typescript-eslint/no-unused-vars': [
        'error',
        { argsIgnorePattern: '^_', varsIgnorePattern: '^_' },
      ],

      // React
      'react/react-in-jsx-scope': 'off',
      'react/prop-types': 'off',
      'react/jsx-uses-react': 'off',
      'react-hooks/rules-of-hooks': 'error',
      'react-hooks/exhaustive-deps': 'error',

      // Accessibility — WCAG 2.1 AA per docs/40-features/WEB-APP.md §9.
      'jsx-a11y/alt-text': 'error',
      'jsx-a11y/anchor-is-valid': 'error',
      'jsx-a11y/aria-props': 'error',
      'jsx-a11y/aria-role': 'error',
      'jsx-a11y/click-events-have-key-events': 'error',
      'jsx-a11y/no-static-element-interactions': 'error',
      'jsx-a11y/label-has-associated-control': 'error',

      // Import discipline — boundaries from 06-design.md §6.
      'import/no-cycle': 'error',
      'import/no-self-import': 'error',
      'import/no-restricted-paths': [
        'error',
        {
          zones: [
            {
              target: './src/routes',
              from: './src/features/**/services',
              message:
                'Routes cannot import services directly. Go through hooks. (06-design.md §6)',
            },
            {
              target: './src/features/**/components',
              from: './src/features/**/services',
              message:
                'Components cannot import services directly. Use hooks. (06-design.md §6)',
            },
          ],
        },
      ],
      'no-restricted-imports': [
        'error',
        {
          patterns: [
            {
              group: ['@radix-ui/*'],
              message:
                'Import from @baseflo/ui, not @radix-ui directly. (06-design.md §2.8)',
            },
            {
              group: ['lucide-react'],
              message:
                'Import icons from @baseflo/ui/icons, not lucide-react directly. (06-design.md §2.14)',
            },
          ],
        },
      ],

      // Process discipline.
      'no-console': ['error', { allow: ['warn', 'error'] }],
      'no-debugger': 'error',
    },
  },
  {
    files: [
      'packages/ui/src/icons/index.ts',
      'packages/ui/src/primitives/**/*.{ts,tsx}',
    ],
    rules: {
      'no-restricted-imports': 'off',
    },
  },
  {
    // Test files relax some rules.
    files: ['**/*.test.{ts,tsx}', '**/*.spec.{ts,tsx}', '**/tests/**/*.{ts,tsx}'],
    rules: {
      '@typescript-eslint/no-explicit-any': 'off',
      'no-console': 'off',
    },
  },
  {
    ignores: [
      '**/dist/**',
      '**/.turbo/**',
      '**/.vite/**',
      '**/build/**',
      '**/coverage/**',
      '**/node_modules/**',
      '**/*.gen.ts',
      '**/routeTree.gen.ts',
    ],
  },
];
