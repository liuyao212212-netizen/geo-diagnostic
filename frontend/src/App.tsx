import { useState, useEffect, Component, type ReactNode, type ErrorInfo } from 'react';
import { HashRouter, Routes, Route } from 'react-router-dom';
import { getTasks, type Task } from './api';
import TaskCreatePage from './pages/TaskCreatePage';
import TaskListPage from './pages/TaskListPage';
import TaskDetailPage from './pages/TaskDetailPage';

class ErrorBoundary extends Component<{ children: ReactNode }, { hasError: boolean; error: Error | null }> {
  constructor(props: { children: ReactNode }) {
    super(props);
    this.state = { hasError: false, error: null };
  }

  static getDerivedStateFromError(error: Error) {
    return { hasError: true, error };
  }

  componentDidCatch(error: Error, errorInfo: ErrorInfo) {
    console.error('React render error:', error, errorInfo);
  }

  render() {
    if (this.state.hasError) {
      return (
        <div className="min-h-screen flex items-center justify-center bg-gray-50">
          <div className="text-center p-8 max-w-md">
            <div className="text-6xl mb-4">💥</div>
            <h2 className="text-xl font-bold text-gray-900 mb-2">页面渲染出错</h2>
            <p className="text-sm text-gray-500 mb-4 break-all">{this.state.error?.message}</p>
            <button
              onClick={() => window.location.reload()}
              className="bg-indigo-600 text-white px-6 py-2 rounded-lg hover:bg-indigo-700 transition text-sm"
            >
              刷新页面
            </button>
          </div>
        </div>
      );
    }
    return this.props.children;
  }
}

export default function App() {
  const [tasks, setTasks] = useState<Task[]>([]);
  const [loading, setLoading] = useState(true);

  const refreshTasks = async () => {
    try {
      const { data } = await getTasks();
      // 防御性校验：确保 data 是数组（CloudStudio 静态部署可能返回 HTML）
      if (Array.isArray(data)) {
        setTasks(data);
      } else {
        console.warn('API returned non-array data, ignoring:', typeof data);
        setTasks([]);
      }
    } catch (e) {
      console.error('Failed to load tasks:', e);
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    refreshTasks();
  }, []);

  return (
    <ErrorBoundary>
      <HashRouter>
        <div className="min-h-screen bg-gray-50">
          {/* 顶部导航 */}
          <header className="bg-white border-b border-gray-200 sticky top-0 z-50">
            <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8">
              <div className="flex justify-between h-16 items-center">
                <div className="flex items-center gap-3">
                  <div className="w-8 h-8 rounded-lg bg-gradient-to-br from-indigo-500 to-purple-600 flex items-center justify-center">
                    <span className="text-white font-bold text-sm">G</span>
                  </div>
                  <h1 className="text-lg font-bold text-gray-900">GEO 品牌诊断</h1>
                </div>
                <nav className="flex items-center gap-6 text-sm">
                  <a href="#/" className="text-gray-600 hover:text-gray-900 transition">任务列表</a>
                  <a href="#/create" className="bg-indigo-600 text-white px-4 py-2 rounded-lg hover:bg-indigo-700 transition">新建诊断</a>
                </nav>
              </div>
            </div>
          </header>

          {/* 页面内容 */}
          <main className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8 py-8">
            <Routes>
              <Route path="/" element={<TaskListPage tasks={tasks} loading={loading} onRefresh={refreshTasks} />} />
              <Route path="/create" element={<TaskCreatePage onCreated={refreshTasks} />} />
              <Route path="/task/:id" element={<TaskDetailPage tasks={tasks} />} />
            </Routes>
          </main>
        </div>
      </HashRouter>
    </ErrorBoundary>
  );
}
