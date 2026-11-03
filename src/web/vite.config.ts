import { defineConfig } from 'vite'
import vue from '@vitejs/plugin-vue'

// dev 时 /api 代理到后端 8080;构建产物输出到 src/cmdb/static,由 FastAPI 托管
export default defineConfig({
  plugins: [vue()],
  server: {
    proxy: {
      '/api': 'http://localhost:8080',
    },
  },
  build: {
    outDir: '../cmdb/static',
    emptyOutDir: true,
    rollupOptions: {
      output: {
        // content-hash asset names: css-only changes must also bust the browser cache
        // (vite's default names css after its js chunk, so a pure-css fix kept the old name)
        assetFileNames: 'assets/[name]-[hash][extname]',
        // Element Plus 等第三方库拆分为独立 vendor chunk,避免主包过大
        manualChunks: {
          vendor: ['vue', 'vue-router', 'element-plus', '@element-plus/icons-vue'],
        },
      },
    },
  },
})
