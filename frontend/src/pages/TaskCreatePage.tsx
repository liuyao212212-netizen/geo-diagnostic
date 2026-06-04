import { useState, useEffect } from 'react';
import { useNavigate } from 'react-router-dom';
import { getPlatforms, createTask, type Platform, type TaskCreate } from '../api';
import { ChevronDown, ChevronUp, Sparkles } from 'lucide-react';

export default function TaskCreatePage({ onCreated }: { onCreated: () => void }) {
  const navigate = useNavigate();
  const [platforms, setPlatforms] = useState<Platform[]>([]);
  const [loading, setLoading] = useState(false);
  const [submitting, setSubmitting] = useState(false);

  const [brandName, setBrandName] = useState('');
  const [selectedPlatforms, setSelectedPlatforms] = useState<string[]>([]);
  const [showAdvanced, setShowAdvanced] = useState(false);
  const [brandAliases, setBrandAliases] = useState('');
  const [apiError, setApiError] = useState('');

  // 兜底平台列表（当后端不可用时显示）
  const FALLBACK_PLATFORMS: Platform[] = [
    { id: 'dashscope', name: '千问', type: 'api', model: 'qwen-plus' },
    { id: 'deepseek', name: 'DeepSeek', type: 'api', model: 'deepseek-chat' },
    { id: 'volcengine', name: '豆包', type: 'api', model: 'doubao-pro-4k' },
  ];

  useEffect(() => {
    setLoading(true);
    getPlatforms()
      .then(({ data }) => {
        if (Array.isArray(data) && data.length > 0) {
          setPlatforms(data);
        } else {
          setPlatforms(FALLBACK_PLATFORMS);
          setApiError('后端连接失败，已使用默认平台列表。如需完整功能，请确保本地后端已启动。');
        }
      })
      .catch((e) => {
        console.warn('Failed to load platforms:', e);
        setPlatforms(FALLBACK_PLATFORMS);
        setApiError('后端连接失败，已使用默认平台列表。如需完整功能，请确保本地后端已启动 (localhost:8900)。');
      })
      .finally(() => setLoading(false));
  }, []);

  const togglePlatform = (platformName: string) => {
    setSelectedPlatforms(prev =>
      prev.includes(platformName) ? prev.filter(p => p !== platformName) : [...prev, platformName]
    );
  };

  const selectAll = () => {
    setSelectedPlatforms(platforms.map(p => p.name));
  };

  const handleSubmit = async () => {
    if (!brandName.trim()) return alert('请输入品牌名称');
    if (selectedPlatforms.length === 0) return alert('请选择至少一个AI平台');

    const payload: TaskCreate = {
      brand_name: brandName.trim(),
      brand_aliases: brandAliases.split(/[,，]/).map(s => s.trim()).filter(Boolean),
      scenarios: [],
      platforms: selectedPlatforms.map(name => ({
        platform_name: name,
        platform_version: 'default',
        platform_type: 'api',
      })),
      competitors: [],
    };

    setSubmitting(true);
    try {
      const { data } = await createTask(payload);
      onCreated();
      navigate(`/task/${data.id}`);
    } catch (e: any) {
      alert('创建失败: ' + (e.response?.data?.detail || e.message));
    } finally {
      setSubmitting(false);
    }
  };

  return (
    <div className="max-w-2xl mx-auto">
      {/* 页面标题 */}
      <div className="mb-8">
        <h2 className="text-2xl font-bold text-gray-900 mb-2">新建品牌诊断</h2>
        <p className="text-gray-500 text-sm">
          输入品牌名 + 选择AI平台，系统自动完成竞品发现、关键词生成、批量查询和报告生成
        </p>
      </div>

      {/* API 错误提示 */}
      {apiError && (
        <div className="bg-amber-50 border border-amber-200 rounded-xl p-4 mb-6 text-sm text-amber-800">
          <div className="flex items-start gap-2">
            <span className="shrink-0">⚠️</span>
            <span>{apiError}</span>
          </div>
        </div>
      )}

      {/* 品牌名称 */}
      <div className="bg-white rounded-xl border border-gray-200 p-6 mb-6">
        <h3 className="text-sm font-semibold text-gray-500 uppercase tracking-wider mb-4">品牌名称</h3>
        <input
          type="text"
          value={brandName}
          onChange={e => setBrandName(e.target.value)}
          placeholder="如：海尔、耐特康赛、美的"
          className="w-full px-4 py-3 border border-gray-300 rounded-lg text-lg focus:ring-2 focus:ring-indigo-500 focus:border-indigo-500 outline-none"
          autoFocus
        />
        <p className="text-xs text-gray-400 mt-2">
          💡 系统会自动识别行业、发现竞品、生成搜索关键词，你只需输入品牌名
        </p>
      </div>

      {/* AI 平台选择 */}
      <div className="bg-white rounded-xl border border-gray-200 p-6 mb-6">
        <div className="flex items-center justify-between mb-4">
          <h3 className="text-sm font-semibold text-gray-500 uppercase tracking-wider">选择 AI 平台</h3>
          {platforms.length > 1 && (
            <button
              onClick={selectAll}
              className="text-xs text-indigo-600 hover:text-indigo-700 font-medium"
            >
              全选
            </button>
          )}
        </div>
        {loading ? (
          <p className="text-sm text-gray-400">加载平台中...</p>
        ) : (
          <div className="grid grid-cols-1 sm:grid-cols-3 gap-3">
            {platforms.map(p => {
              const selected = selectedPlatforms.includes(p.name);
              return (
                <button
                  key={p.id}
                  onClick={() => togglePlatform(p.name)}
                  className={`p-4 rounded-lg border-2 text-left transition ${
                    selected ? 'border-indigo-500 bg-indigo-50' : 'border-gray-200 hover:border-gray-300'
                  }`}
                >
                  <div className="font-medium text-gray-900 text-sm">{p.name}</div>
                  <div className="text-xs text-gray-500 mt-1">{p.model}</div>
                </button>
              );
            })}
          </div>
        )}
      </div>

      {/* 高级选项（折叠） */}
      <div className="bg-white rounded-xl border border-gray-200 mb-6 overflow-hidden">
        <button
          onClick={() => setShowAdvanced(!showAdvanced)}
          className="w-full px-6 py-4 flex items-center justify-between text-sm text-gray-500 hover:bg-gray-50 transition"
        >
          <span className="font-medium">高级选项</span>
          {showAdvanced ? <ChevronUp size={16} /> : <ChevronDown size={16} />}
        </button>
        {showAdvanced && (
          <div className="px-6 pb-5 border-t border-gray-100 pt-4">
            <div>
              <label className="block text-sm font-medium text-gray-700 mb-1">品牌别名</label>
              <input
                type="text"
                value={brandAliases}
                onChange={e => setBrandAliases(e.target.value)}
                placeholder="如：Haier, 海尔集团（逗号分隔，选填）"
                className="w-full px-4 py-2.5 border border-gray-300 rounded-lg focus:ring-2 focus:ring-indigo-500 focus:border-indigo-500 outline-none text-sm"
              />
              <p className="text-xs text-gray-400 mt-1">
                填写品牌的英文名、曾用名等，帮助系统更准确识别品牌提及
              </p>
            </div>
          </div>
        )}
      </div>

      {/* 系统自动完成说明 */}
      <div className="bg-gradient-to-r from-indigo-50 to-purple-50 rounded-xl border border-indigo-100 p-5 mb-6">
        <div className="flex items-start gap-3">
          <Sparkles size={20} className="text-indigo-500 mt-0.5 shrink-0" />
          <div className="text-sm text-indigo-700">
            <p className="font-medium mb-2">系统将自动完成以下工作：</p>
            <div className="grid grid-cols-1 sm:grid-cols-2 gap-2 text-xs text-indigo-600">
              <div className="flex items-center gap-2">
                <span className="bg-indigo-200 text-indigo-800 rounded-full w-5 h-5 flex items-center justify-center text-xs font-bold shrink-0">1</span>
                <span>AI 识别行业 + 发现 3-5 个核心竞品</span>
              </div>
              <div className="flex items-center gap-2">
                <span className="bg-indigo-200 text-indigo-800 rounded-full w-5 h-5 flex items-center justify-center text-xs font-bold shrink-0">2</span>
                <span>生成 15-20 个消费者真实搜索关键词</span>
              </div>
              <div className="flex items-center gap-2">
                <span className="bg-indigo-200 text-indigo-800 rounded-full w-5 h-5 flex items-center justify-center text-xs font-bold shrink-0">3</span>
                <span>逐个关键词查询选中 AI 平台</span>
              </div>
              <div className="flex items-center gap-2">
                <span className="bg-indigo-200 text-indigo-800 rounded-full w-5 h-5 flex items-center justify-center text-xs font-bold shrink-0">4</span>
                <span>解析品牌提及/排名/情感，生成诊断报告</span>
              </div>
            </div>
          </div>
        </div>
      </div>

      {/* 提交 */}
      <div className="flex justify-end">
        <button
          onClick={handleSubmit}
          disabled={submitting || !brandName.trim() || selectedPlatforms.length === 0}
          className="bg-indigo-600 text-white px-8 py-3 rounded-lg font-medium hover:bg-indigo-700 transition disabled:opacity-50 disabled:cursor-not-allowed flex items-center gap-2"
        >
          {submitting ? (
            <>
              <span className="animate-spin rounded-full h-4 w-4 border-b-2 border-white"></span>
              创建中...
            </>
          ) : (
            '开始诊断'
          )}
        </button>
      </div>
    </div>
  );
}
