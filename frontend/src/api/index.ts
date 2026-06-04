import axios from 'axios';

const API_BASE_URL = import.meta.env.VITE_API_URL || '/api';

const api = axios.create({
  baseURL: API_BASE_URL,
  timeout: 30000,
  // 关键：强制验证响应是 JSON，防止静态服务器返回 HTML 导致崩溃
  transformResponse: [
    (data, headers) => {
      if (typeof data === 'string') {
        // 静态部署时，/api 路径会返回 index.html（含 <!doctype）
        if (data.trimStart().startsWith('<!doctype') || data.trimStart().startsWith('<html') || data.trimStart().startsWith('<!DOCTYPE')) {
          console.warn('API received HTML instead of JSON — backend is likely not running. Request path:', API_BASE_URL);
          throw new axios.Cancel('API_UNAVAILABLE');
        }
        try {
          return JSON.parse(data);
        } catch {
          console.warn('API received non-JSON response:', data.substring(0, 200));
          throw new axios.Cancel('API_UNAVAILABLE');
        }
      }
      return data;
    },
  ],
});

// 统一处理 Cancel 信号（后端不可用时触发）
api.interceptors.response.use(
  (response) => response,
  (error) => {
    if (axios.isCancel(error) && error.message === 'API_UNAVAILABLE') {
      // 转为可被业务 catch 捕获的错误
      return Promise.reject(new Error('后端服务不可用，请确保 API 服务已启动'));
    }
    return Promise.reject(error);
  },
);

export interface Platform {
  id: string;
  name: string;
  type: string;
  model: string;
}

export interface Scenario {
  question: string;
  category: string;
}

export interface PlatformConfig {
  platform_name: string;
  platform_version: string;
  platform_type: string;
}

export interface TaskCreate {
  brand_name: string;
  brand_aliases: string[];
  scenarios: Scenario[];
  platforms: PlatformConfig[];
  competitors: string[];
}

export interface Task {
  id: string;
  brand_name: string;
  brand_aliases: string[];
  scenarios: Scenario[];
  platforms: PlatformConfig[];
  competitors: string[];
  status: string;
  created_at: string;
  completed_at: string | null;
}

export interface QueryResult {
  id: string;
  task_id: string;
  platform_name: string;
  platform_version: string;
  scenario_question: string;
  scenario_category: string;
  ai_response_text: string | null;
  query_duration_ms: number | null;
  queried_at: string;
  error_message: string | null;
  brand_mentions: BrandMention[];
  citation_sources: CitationSource[];
}

export interface BrandMention {
  brand_name: string;
  mention_rank: number;
  sentiment: string;
  mention_context: string;
  is_primary_brand: boolean;
}

export interface CitationSource {
  source_url: string;
  source_domain: string;
  source_type: string;
  source_title: string;
  citation_rank: number;
}

// API Calls
export const getPlatforms = () => api.get<Platform[]>('/tasks/platforms');

export const createTask = (data: TaskCreate) => api.post<Task>('/tasks', data);

export const getTasks = () => api.get<Task[]>('/tasks');

export const getTask = (id: string) => api.get<Task>(`/tasks/${id}`);

export const deleteTask = (id: string) => api.delete(`/tasks/${id}`);

export const runTaskQueries = (id: string) => api.post(`/queries/${id}/run`);

export const getQueryResults = (id: string) => api.get<{ total: number; results: QueryResult[] }>(`/queries/${id}/results`);

export const getTaskStatus = (id: string) => api.get(`/queries/${id}/status`);

export const getAnalysis = (id: string) => api.get(`/analysis/${id}`);

export const getReport = (id: string) => api.get(`/reports/${id}/html`);
