import react from '@vitejs/plugin-react'
import { defineConfig } from 'vite'

const repositoryName = process.env.GITHUB_REPOSITORY?.split('/')[1]
const isUserSite = repositoryName?.endsWith('.github.io')
const base =
  process.env.GITHUB_ACTIONS === 'true' && repositoryName && !isUserSite
    ? `/${repositoryName}/`
    : '/'

export default defineConfig({
  base,
  plugins: [react()],
  server: {
    host: '0.0.0.0',
    port: 4173,
    proxy: {
      '/api': {
        target: 'http://localhost:4000',
        changeOrigin: true,
      },
    },
  },
})
