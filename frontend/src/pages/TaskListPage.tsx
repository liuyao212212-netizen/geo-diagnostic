import { useNavigate } from 'react-router-dom';
import { deleteTask, type Task } from '../api';
import { Play, Trash2, Clock, CheckCircle, XCircle, Loader2 } from 'lucide-react';

const statusConfig: Record<string, { color: string; bg: string; icon: React.ReactNode; label: string }> = {
  pending: { color: 'text-amber-600', bg: 'bg-amber-50', icon: <Clock size={14} />, label: '待执行' },
  running: { color: 'text-blue-600', bg: 'bg-blue-50', icon: <Loader2 size={14} className="animate-spin" />, label: '执行中' },
  completed: { color: 'text-green-600', bg: 'bg-green-50', icon: <CheckCircle size={14} />, label: '已完成' },
  failed: { color: 'text-red-600', bg: 'bg-red-50', icon: <XCircle size={14} />, label: '失败' },
};

export default function TaskListPage({ tasks, loading, onRefresh }: {
  tasks: Task[];
  loading: boolean;
  onRefresh: () => void;
}) {
  const navigate = useNavigate();

  const handleDelete = async (id: string) => {
    if (!confirm('确定要删除这个诊断任务吗？')) return;
    await deleteTask(id);
    onRefresh();
  };

  const formatDate = (iso: string) => {
    const d = new Date(iso);
    return d.toLocaleString('zh-CN', { month: '2-digit', day: '2-digit', hour: '2-digit', minute: '2-digit' });
  };

  return (
    <div>
      <div className="flex items-center justify-between mb-6">
        <h2 className="text-2xl font-bold text-gray-900">诊断任务</h2>
        <span className="text-sm text-gray-500">{tasks.length} 个任务</span>
      </div>

      {loading ? (
        <div className="flex items-center justify-center py-20">
          <Loader2 className="animate-spin text-indigo-500" size={32} />
        </div>
      ) : tasks.length === 0 ? (
        <div className="text-center py-20">
          <p className="text-gray-400 mb-4">还没有诊断任务</p>
          <button
            onClick={() => navigate('/create')}
            className="bg-indigo-600 text-white px-6 py-2.5 rounded-lg hover:bg-indigo-700 transition text-sm font-medium"
          >
            创建第一个诊断
          </button>
        </div>
      ) : (
        <div className="space-y-4">
          {tasks.map(task => {
            const status = statusConfig[task.status] || statusConfig.pending;
            return (
              <div
                key={task.id}
                className="bg-white rounded-xl border border-gray-200 p-5 hover:shadow-md transition-shadow cursor-pointer"
                onClick={() => navigate(`/task/${task.id}`)}
              >
                <div className="flex items-center justify-between">
                  <div className="flex items-center gap-4">
                    <div className={`p-2 rounded-lg ${status.bg}`}>
                      <span className={status.color}>{status.icon}</span>
                    </div>
                    <div>
                      <div className="font-semibold text-gray-900">{task.brand_name}</div>
                      <div className="text-sm text-gray-500 mt-0.5">
                        {task.scenarios.length} 个场景 · {task.platforms.length} 个平台
                        {task.competitors.length > 0 && ` · 竞品: ${task.competitors.join(', ')}`}
                      </div>
                    </div>
                  </div>
                  <div className="flex items-center gap-4">
                    <div className="text-right">
                      <div className={`inline-flex items-center gap-1.5 px-3 py-1 rounded-full text-xs font-medium ${status.bg} ${status.color}`}>
                        {status.icon} {status.label}
                      </div>
                      <div className="text-xs text-gray-400 mt-1">{formatDate(task.created_at)}</div>
                    </div>
                    <button
                      onClick={e => { e.stopPropagation(); handleDelete(task.id); }}
                      className="p-2 text-gray-400 hover:text-red-500 transition"
                    >
                      <Trash2 size={16} />
                    </button>
                  </div>
                </div>
              </div>
            );
          })}
        </div>
      )}
    </div>
  );
}
