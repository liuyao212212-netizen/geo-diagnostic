import { useState, useEffect, useRef } from 'react';
import { useParams, useNavigate } from 'react-router-dom';
import { getTask, runTaskQueries, getQueryResults, getAnalysis, getReport, type Task, type QueryResult } from '../api';
import { Play, ArrowLeft, Loader2, BarChart3, FileText, Check, X, Eye } from 'lucide-react';

export default function TaskDetailPage({ tasks = [] }: { tasks?: Task[] }) {
  const { id } = useParams<{ id: string }>();
  const navigate = useNavigate();
  const [task, setTask] = useState<Task | null>(null);
  const [results, setResults] = useState<QueryResult[]>([]);
  const [analysis, setAnalysis] = useState<any>(null);
  const [reportHtml, setReportHtml] = useState<string>('');
  const [loading, setLoading] = useState(true);
  const [running, setRunning] = useState(false);
  const [activeTab, setActiveTab] = useState<'results' | 'analysis' | 'report'>('results');
  const [showReport, setShowReport] = useState(false);
  const [reviewStatus, setReviewStatus] = useState<any>(null);
  const [fetchError, setFetchError] = useState<string>('');
  const pollRef = useRef<ReturnType<typeof setInterval> | null>(null);

  const clearPoll = () => {
    if (pollRef.current) {
      clearInterval(pollRef.current);
      pollRef.current = null;
    }
  };

  useEffect(() => {
    return () => clearPoll();
  }, []);

  useEffect(() => {
    if (!id) return;
    setLoading(true);
    setFetchError('');

    // 先尝试从父组件 tasks 列表里找（避免 API 404 时完全空白）
    const cached = tasks.find(t => t.id === id);
    if (cached) {
      setTask(cached);
      if (cached.status === 'running') startPolling();
    }

    getTask(id)
      .then(({ data }) => {
        setTask(data);
        setFetchError('');
        if (data.status === 'running') {
          startPolling();
        }
      })
      .catch((err: any) => {
        console.error('获取任务详情失败:', err);
        const msg = err.response?.data?.detail || err.message || '未知错误';
        setFetchError(`API 错误: ${msg}`);
        // 如果父组件没有缓存，才显示不存在
        if (!cached) {
          setTask(null);
        }
      })
      .finally(() => setLoading(false));
  }, [id]);

  const startPolling = () => {
    clearPoll();
    setRunning(true);

    pollRef.current = setInterval(async () => {
      try {
        const { data: taskData } = await getTask(id!);
        setTask(taskData);

        if (taskData.status === 'completed' || taskData.status === 'failed') {
          clearPoll();
          setRunning(false);
          const { data: resultsData } = await getQueryResults(id!);
          setResults(resultsData.results);
        }
      } catch (e) {
        console.error('轮询失败:', e);
      }
    }, 3000);
  };

  const handleRun = async () => {
    if (!id) return;
    try {
      await runTaskQueries(id);
      startPolling();
    } catch (e: any) {
      const msg = e.response?.data?.detail || e.message || '未知错误';
      alert('执行失败: ' + msg);
      setRunning(false);
    }
  };

  const loadAnalysis = async () => {
    if (!id) return;
    try {
      const { data } = await getAnalysis(id);
      setAnalysis(data);
      setActiveTab('analysis');
    } catch (e: any) {
      alert('分析失败: ' + (e.response?.data?.detail || e.message));
    }
  };

  const loadReport = async () => {
    if (!id) return;
    try {
      const { data } = await getReport(id);
      setReportHtml(data.html_content);
      setShowReport(true);
      setActiveTab('report');
      // 同时加载审核状态
      loadReviewStatus();
    } catch (e: any) {
      alert('报告生成失败: ' + (e.response?.data?.detail || e.message));
    }
  };

  const loadReviewStatus = async () => {
    if (!id) return;
    try {
      const resp = await fetch(`http://localhost:8900/api/reports/${id}/review-status`);
      if (resp.ok) {
        const data = await resp.json();
        setReviewStatus(data);
      }
    } catch (e) {
      console.error('获取审核状态失败:', e);
    }
  };

  const handleReview = async (action: 'approve' | 'reject') => {
    if (!id) return;
    const note = action === 'reject' ? prompt('请填写驳回原因（可选）：') || '' : '';
    try {
      const resp = await fetch(`http://localhost:8900/api/reports/${id}/review`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ action, note }),
      });
      if (resp.ok) {
        const data = await resp.json();
        setReviewStatus(prev => ({ ...prev, review_status: data.review_status }));
        alert(data.message);
      }
    } catch (e) {
      alert('审核操作失败');
    }
  };

  if (loading) return (
    <div className="flex items-center justify-center py-20">
      <Loader2 className="animate-spin text-indigo-500" size={32} />
    </div>
  );

  if (!task) return (
    <div className="text-center py-20">
      <p className="text-gray-400 mb-2">任务不存在</p>
      {fetchError && (
        <p className="text-xs text-red-500 max-w-md mx-auto">{fetchError}</p>
      )}
    </div>
  );

  const statusLabel = {
    pending: '待执行',
    running: '执行中',
    completed: '已完成',
    failed: '失败',
  }[task.status] || task.status;

  const reviewLabel = {
    none: '',
    approved: '已审核通过',
    rejected: '已驳回',
  }[reviewStatus?.review_status || 'none'];

  return (
    <div>
      {/* 返回 + 标题 */}
      <div className="flex items-center gap-3 mb-6">
        <button onClick={() => navigate('/')} className="p-2 text-gray-400 hover:text-gray-600 transition">
          <ArrowLeft size={20} />
        </button>
        <h2 className="text-2xl font-bold text-gray-900">{task.brand_name} — 诊断详情</h2>
        {reviewLabel && (
          <span className={`text-xs px-2.5 py-0.5 rounded-full font-medium ${
            reviewStatus?.review_status === 'approved' ? 'bg-green-50 text-green-700' : 'bg-red-50 text-red-700'
          }`}>{reviewLabel}</span>
        )}
      </div>

      {/* API 错误提示（任务从缓存加载时显示） */}
      {fetchError && (
        <div className="bg-amber-50 border border-amber-200 rounded-xl p-4 mb-6 text-sm text-amber-800">
          <div className="flex items-start gap-2">
            <span className="shrink-0">⚠️</span>
            <div>
              <p className="font-medium">后端 API 连接异常</p>
              <p className="text-xs text-amber-600 mt-0.5">{fetchError}</p>
              <p className="text-xs text-amber-600 mt-1">当前显示的是列表页缓存数据，部分功能可能不可用。</p>
            </div>
          </div>
        </div>
      )}

      {/* 操作栏 */}
      <div className="bg-white rounded-xl border border-gray-200 p-5 mb-6">
        <div className="flex items-center justify-between flex-wrap gap-4">
          <div className="flex items-center gap-6 text-sm">
            <div><span className="text-gray-500">状态：</span><span className={`font-medium ${
              task.status === 'completed' ? 'text-green-600' :
              task.status === 'running' ? 'text-blue-600' :
              task.status === 'failed' ? 'text-red-600' : 'text-amber-600'
            }`}>{statusLabel}</span></div>
            <div><span className="text-gray-500">场景：</span><span className="font-medium">{task.scenarios.length} 个</span></div>
            <div><span className="text-gray-500">平台：</span><span className="font-medium">{task.platforms.length} 个</span></div>
          </div>
          <div className="flex items-center gap-3">
            {task.status === 'completed' && (
              <>
                <button onClick={loadAnalysis} className="flex items-center gap-2 px-4 py-2 text-sm font-medium border border-gray-300 rounded-lg hover:bg-gray-50 transition">
                  <BarChart3 size={16} /> 查看分析
                </button>
                <button onClick={loadReport} className="flex items-center gap-2 px-4 py-2 text-sm font-medium border border-gray-300 rounded-lg hover:bg-gray-50 transition">
                  <Eye size={16} /> 生成报告
                </button>
              </>
            )}
            {(task.status === 'pending' || task.status === 'failed') && (
              <button
                onClick={handleRun}
                disabled={running}
                className="flex items-center gap-2 bg-indigo-600 text-white px-5 py-2 rounded-lg hover:bg-indigo-700 transition disabled:opacity-50 text-sm font-medium"
              >
                {running ? <><Loader2 size={16} className="animate-spin" /> 查询中...</> : <><Play size={16} /> 执行诊断</>}
              </button>
            )}
            {task.status === 'running' && (
              <div className="flex items-center gap-2 text-blue-600 text-sm font-medium">
                <Loader2 size={16} className="animate-spin" /> 查询中...
              </div>
            )}
          </div>
        </div>
      </div>

      {/* 查询结果 */}
      <div className="bg-white rounded-xl border border-gray-200 overflow-hidden">
        <div className="px-5 py-4 border-b border-gray-100 flex items-center gap-4">
          <h3 className="font-semibold text-gray-900">查询结果</h3>
          <span className="text-sm text-gray-400">{results.length} 条</span>
        </div>
        {results.length === 0 ? (
          <div className="py-12 text-center text-gray-400 text-sm">
            {task.status === 'pending' ? '点击"执行诊断"开始查询 AI 平台' : '暂无结果'}
          </div>
        ) : (
          <div className="divide-y divide-gray-100">
            {results.map(r => (
              <div key={r.id} className="p-5 hover:bg-gray-50 transition">
                <div className="flex items-center gap-3 mb-2">
                  <span className="px-2.5 py-0.5 bg-indigo-50 text-indigo-700 text-xs font-medium rounded-full">{r.platform_name}</span>
                  <span className="px-2.5 py-0.5 bg-gray-100 text-gray-600 text-xs rounded-full">{r.scenario_category}</span>
                  {r.query_duration_ms && <span className="text-xs text-gray-400">{r.query_duration_ms}ms</span>}
                  {r.error_message && <span className="px-2.5 py-0.5 bg-red-50 text-red-600 text-xs rounded-full">错误</span>}
                </div>
                <p className="text-sm text-gray-700 line-clamp-3">{r.ai_response_text || r.error_message || '无数据'}</p>
                {r.brand_mentions && r.brand_mentions.length > 0 && (
                  <div className="flex gap-2 mt-2 flex-wrap">
                    {r.brand_mentions.map((m, i) => (
                      <span key={i} className={`text-xs px-2 py-0.5 rounded-full ${
                        m.is_primary_brand ? 'bg-purple-50 text-purple-700' : 'bg-gray-50 text-gray-600'
                      }`}>
                        #{m.mention_rank} {m.brand_name} ({m.sentiment})
                      </span>
                    ))}
                  </div>
                )}
              </div>
            ))}
          </div>
        )}
      </div>

      {/* 分析结果 */}
      {analysis && activeTab === 'analysis' && (
        <div className="mt-6 bg-white rounded-xl border border-gray-200 p-6">
          <h3 className="font-semibold text-gray-900 mb-4">品牌竞争分析</h3>
          <div className="overflow-x-auto">
            <table className="w-full text-sm">
              <thead>
                <tr className="border-b border-gray-200">
                  <th className="py-2 text-left text-gray-500 font-medium">品牌</th>
                  <th className="py-2 text-right text-gray-500 font-medium">GEO 得分</th>
                  <th className="py-2 text-right text-gray-500 font-medium">提及率</th>
                  <th className="py-2 text-right text-gray-500 font-medium">平台覆盖</th>
                  <th className="py-2 text-right text-gray-500 font-medium">平均排名</th>
                  <th className="py-2 text-right text-gray-500 font-medium">正面率</th>
                </tr>
              </thead>
              <tbody>
                {analysis.brand_scores?.map((s: any, i: number) => (
                  <tr key={i} className={`border-b border-gray-100 ${s.brand_name === analysis.brand_name ? 'bg-purple-50/50' : ''}`}>
                    <td className="py-3 font-medium">{s.brand_name}</td>
                    <td className="py-3 text-right font-bold">{s.geo_score}</td>
                    <td className="py-3 text-right">{s.mention_rate}%</td>
                    <td className="py-3 text-right">{s.platform_coverage}%</td>
                    <td className="py-3 text-right">#{s.avg_rank}</td>
                    <td className="py-3 text-right">{s.positive_rate}%</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>

          {/* 交叉验证摘要 */}
          {analysis.cross_validation && (
            <div className="mt-6 pt-6 border-t border-gray-100">
              <h4 className="font-semibold text-gray-900 mb-3">交叉验证可信度</h4>
              <div className="grid grid-cols-3 gap-4">
                <div className="text-center p-3 bg-green-50 rounded-lg">
                  <div className="text-2xl font-bold text-green-700">{analysis.cross_validation.summary?.high || 0}</div>
                  <div className="text-xs text-green-600">高可信</div>
                </div>
                <div className="text-center p-3 bg-amber-50 rounded-lg">
                  <div className="text-2xl font-bold text-amber-700">{analysis.cross_validation.summary?.medium || 0}</div>
                  <div className="text-xs text-amber-600">中可信</div>
                </div>
                <div className="text-center p-3 bg-red-50 rounded-lg">
                  <div className="text-2xl font-bold text-red-700">{analysis.cross_validation.summary?.low || 0}</div>
                  <div className="text-xs text-red-600">需核实</div>
                </div>
              </div>
            </div>
          )}
        </div>
      )}

      {/* 报告弹窗 */}
      {showReport && reportHtml && (
        <div className="fixed inset-0 z-50 bg-black/50 flex items-center justify-center p-4" onClick={() => setShowReport(false)}>
          <div className="bg-white rounded-2xl w-full max-w-5xl max-h-[90vh] overflow-hidden shadow-2xl" onClick={e => e.stopPropagation()}>
            <div className="flex items-center justify-between px-6 py-4 border-b border-gray-200">
              <h3 className="font-semibold text-gray-900">诊断报告预览</h3>
              <div className="flex items-center gap-3">
                {/* 审核按钮 */}
                {task.status === 'completed' && reviewStatus?.review_status === 'none' && (
                  <>
                    <button
                      onClick={() => handleReview('reject')}
                      className="flex items-center gap-1 px-3 py-1.5 text-sm text-red-600 border border-red-200 rounded-lg hover:bg-red-50 transition"
                    >
                      <X size={14} /> 驳回
                    </button>
                    <button
                      onClick={() => handleReview('approve')}
                      className="flex items-center gap-1 px-3 py-1.5 text-sm text-green-600 border border-green-200 rounded-lg hover:bg-green-50 transition"
                    >
                      <Check size={14} /> 审核通过
                    </button>
                  </>
                )}
                <a
                  href={`data:text/html;charset=utf-8,${encodeURIComponent(reportHtml)}`}
                  download={`${task.brand_name}-GEO诊断报告.html`}
                  className="text-sm text-indigo-600 hover:text-indigo-700 font-medium"
                >
                  下载 HTML
                </a>
                <button onClick={() => setShowReport(false)} className="text-gray-400 hover:text-gray-600 text-xl">&times;</button>
              </div>
            </div>
            <iframe
              srcDoc={reportHtml}
              className="w-full h-[75vh] border-0"
              title="诊断报告"
            />
          </div>
        </div>
      )}
    </div>
  );
}
