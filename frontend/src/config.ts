// API 和 WebSocket 配置
const config = {
  // 开发环境
  development: {
    apiUrl: 'http://localhost:8000',
    wsUrl: 'ws://localhost:8000'
  },
  // 生产环境
  production: {
    apiUrl: 'https://backend-468274160217.us-central1.run.app',
    wsUrl: 'wss://backend-468274160217.us-central1.run.app'
  }
};

// 根据当前环境选择配置
const env = import.meta.env.MODE || 'development';
export const { apiUrl, wsUrl } = config[env as keyof typeof config];

// 导出完整的配置对象，以便将来扩展
export default config[env as keyof typeof config]; 