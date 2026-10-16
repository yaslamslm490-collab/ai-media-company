import { useState } from 'react';
import { useApp } from '@/context/AppContext';
import type { VaultAsset } from '@/types';
import {
  Search,
  Download,
  Plus,
  FileText,
  Image,
  Mic,
  Video,
} from 'lucide-react';

export function VaultView() {
  const { vaultAssets, addVaultAsset } = useApp();
  const [searchQuery, setSearchQuery] = useState('');
  const [filterType, setFilterType] = useState<string>('all');
  const [showAddModal, setShowAddModal] = useState(false);

  // New Asset State
  const [assetName, setAssetName] = useState('');
  const [assetType, setAssetType] = useState<VaultAsset['type']>('document');
  const [characterOrProject, setCharacterOrProject] = useState('ليان (CHAR-001)');
  const [format, setFormat] = useState('PDF / JSON');
  const [fileSize, setFileSize] = useState('1.5 MB');

  const filtered = vaultAssets.filter((a) => {
    const matchesSearch =
      a.name.toLowerCase().includes(searchQuery.toLowerCase()) ||
      a.characterOrProject.toLowerCase().includes(searchQuery.toLowerCase());
    const matchesType = filterType === 'all' || a.type === filterType;
    return matchesSearch && matchesType;
  });

  const handleCreate = (e: React.FormEvent) => {
    e.preventDefault();
    const created: VaultAsset = {
      id: 'v-' + Date.now(),
      name: assetName || 'أصل رقمي جديد',
      type: assetType,
      characterOrProject,
      format,
      fileSize,
      createdDate: new Date().toISOString().slice(0, 10),
      version: '1.0',
      license: 'حقوق ملكية حصرية — NADA AI Media OS',
      reviewStatus: 'verified',
    };
    addVaultAsset(created);
    setShowAddModal(false);
    setAssetName('');
  };

  const getIcon = (type: VaultAsset['type']) => {
    switch (type) {
      case 'image':
        return <Image className="w-5 h-5 text-accent" />;
      case 'voice':
        return <Mic className="w-5 h-5 text-info" />;
      case 'video':
        return <Video className="w-5 h-5 text-purple-400" />;
      default:
        return <FileText className="w-5 h-5 text-warning" />;
    }
  };

  return (
    <div className="space-y-6 animate-fade-up">
      {/* Header Banner */}
      <div className="card p-6 bg-gradient-to-l from-[var(--bg-card)] to-[var(--bg-elevated)] flex flex-col md:flex-row md:items-center justify-between gap-4">
        <div>
          <div className="flex items-center gap-2">
            <span className="text-xs px-2.5 py-0.5 rounded-full bg-accent/20 text-accent font-bold">
              القسم 5.13 & 12 — ASSETS AND MEDIA VAULT
            </span>
            <span className="text-xs text-muted">المستودع الرقمي المركزي</span>
          </div>
          <h1 className="font-display font-bold text-2xl text-primary mt-1">
            خزينة الأصول الرقمية والإعلامية السيادية
          </h1>
          <p className="text-sm text-secondary">
            أرشفة الصور المرجعية، ملفات الصوت، الستوريبورد، السكريبتات، والفيديوهات المعتمدة بحقوق ملكية موثقة.
          </p>
        </div>

        <button
          onClick={() => setShowAddModal(true)}
          className="px-4 py-2.5 rounded-xl bg-accent text-white text-xs font-bold hover:opacity-90 transition-opacity flex items-center gap-2 self-start md:self-auto shadow"
        >
          <Plus className="w-4 h-4" />
          <span>إيداع أصل رقمي جديد</span>
        </button>
      </div>

      {/* Search and Filters */}
      <div className="flex flex-col sm:flex-row items-stretch sm:items-center justify-between gap-3">
        <div className="relative flex-1 max-w-md">
          <Search className="w-4 h-4 text-muted absolute right-3.5 top-1/2 -translate-y-1/2" />
          <input
            type="text"
            value={searchQuery}
            onChange={(e) => setSearchQuery(e.target.value)}
            placeholder="بحث في الأصول (الاسم، الشخصية، أو المشروع)..."
            className="w-full pl-4 pr-10 py-2.5 rounded-xl bg-elevated border border-default text-sm text-primary placeholder:text-muted outline-none focus:border-accent"
          />
        </div>

        <div className="flex items-center gap-2 overflow-x-auto pb-1 sm:pb-0">
          {[
            { key: 'all', label: 'الكل' },
            { key: 'document', label: 'وثائق وBible' },
            { key: 'voice', label: 'أصوات وبصمات' },
            { key: 'image', label: 'صور ومراجع' },
            { key: 'script', label: 'سيناريوهات' },
            { key: 'video', label: 'فيديوهات' },
          ].map((t) => (
            <button
              key={t.key}
              onClick={() => setFilterType(t.key)}
              className={`px-3 py-1.5 rounded-xl text-xs font-medium whitespace-nowrap transition-colors ${
                filterType === t.key
                  ? 'bg-accent text-white'
                  : 'bg-elevated border border-default text-secondary hover:text-primary'
              }`}
            >
              {t.label}
            </button>
          ))}
        </div>
      </div>

      {/* Assets Grid */}
      <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-4">
        {filtered.map((asset) => (
          <div
            key={asset.id}
            className="card p-5 hover:border-accent/40 transition-all flex flex-col justify-between"
          >
            <div>
              <div className="flex items-start justify-between gap-2 mb-3">
                <div className="flex items-center gap-2.5">
                  <div className="w-10 h-10 rounded-xl bg-elevated border border-default flex items-center justify-center">
                    {getIcon(asset.type)}
                  </div>
                  <div>
                    <h4 className="font-bold text-sm text-primary leading-snug line-clamp-1">
                      {asset.name}
                    </h4>
                    <span className="text-[10px] text-muted">{asset.characterOrProject}</span>
                  </div>
                </div>
                <span className="text-[10px] px-2 py-0.5 rounded bg-accent/15 text-accent font-bold">
                  {asset.version}
                </span>
              </div>

              <div className="p-3 rounded-xl bg-elevated/60 border border-default/50 space-y-1.5 text-xs mb-3">
                <div className="flex items-center justify-between">
                  <span className="text-muted">الصيغة والحجم:</span>
                  <span className="font-mono text-secondary">
                    {asset.format} • {asset.fileSize}
                  </span>
                </div>
                <div className="flex items-center justify-between">
                  <span className="text-muted">الترخيص:</span>
                  <span className="text-secondary truncate text-[11px]">{asset.license}</span>
                </div>
              </div>
            </div>

            <div className="pt-3 border-t border-default/50 flex items-center justify-between text-xs text-muted">
              <span>تاريخ الإيداع: {asset.createdDate}</span>
              <button
                onClick={() => alert(`تم بدء تنزيل أصل: ${asset.name}`)}
                className="text-accent hover:underline font-bold flex items-center gap-1"
              >
                <Download className="w-3.5 h-3.5" />
                تحميل
              </button>
            </div>
          </div>
        ))}
      </div>

      {/* Add Asset Modal */}
      {showAddModal && (
        <div className="fixed inset-0 z-50 bg-black/60 flex items-center justify-center p-4">
          <form
            onSubmit={handleCreate}
            className="card p-6 max-w-md w-full animate-fade-up space-y-4"
          >
            <div className="flex items-center justify-between pb-3 border-b border-default">
              <h3 className="font-bold text-base text-primary">إيداع أصل رقمي في الخزينة</h3>
              <button
                type="button"
                onClick={() => setShowAddModal(false)}
                className="text-muted hover:text-primary font-bold px-2"
              >
                ✕
              </button>
            </div>

            <div>
              <label className="text-xs text-muted block mb-1">اسم الأصل:</label>
              <input
                type="text"
                required
                value={assetName}
                onChange={(e) => setAssetName(e.target.value)}
                placeholder="مثال: بصمة صوتية 48kHz..."
                className="w-full p-2.5 rounded-xl bg-elevated border border-default text-xs text-primary outline-none focus:border-accent"
              />
            </div>

            <div className="grid grid-cols-2 gap-3">
              <div>
                <label className="text-xs text-muted block mb-1">النوع:</label>
                <select
                  value={assetType}
                  onChange={(e) => setAssetType(e.target.value as VaultAsset['type'])}
                  className="w-full p-2.5 rounded-xl bg-elevated border border-default text-xs text-primary outline-none focus:border-accent"
                >
                  <option value="document">وثيقة / Bible</option>
                  <option value="voice">صوت (Audio)</option>
                  <option value="image">صورة (Image)</option>
                  <option value="script">سيناريو (Script)</option>
                  <option value="video">فيديو (Video)</option>
                </select>
              </div>

              <div>
                <label className="text-xs text-muted block mb-1">الشخصية أو المشروع:</label>
                <input
                  type="text"
                  value={characterOrProject}
                  onChange={(e) => setCharacterOrProject(e.target.value)}
                  className="w-full p-2.5 rounded-xl bg-elevated border border-default text-xs text-primary outline-none focus:border-accent"
                />
              </div>
            </div>

            <div className="grid grid-cols-2 gap-3">
              <div>
                <label className="text-xs text-muted block mb-1">الصيغة (Format):</label>
                <input
                  type="text"
                  value={format}
                  onChange={(e) => setFormat(e.target.value)}
                  className="w-full p-2.5 rounded-xl bg-elevated border border-default text-xs text-primary outline-none focus:border-accent"
                />
              </div>

              <div>
                <label className="text-xs text-muted block mb-1">حجم الملف:</label>
                <input
                  type="text"
                  value={fileSize}
                  onChange={(e) => setFileSize(e.target.value)}
                  className="w-full p-2.5 rounded-xl bg-elevated border border-default text-xs text-primary outline-none focus:border-accent"
                />
              </div>
            </div>

            <div className="flex items-center justify-end gap-2 pt-2">
              <button
                type="button"
                onClick={() => setShowAddModal(false)}
                className="px-4 py-2 rounded-xl bg-elevated text-xs font-bold text-muted hover:text-primary"
              >
                إلغاء
              </button>
              <button
                type="submit"
                className="px-5 py-2 rounded-xl bg-accent text-white text-xs font-bold hover:opacity-90"
              >
                حفظ في الخزينة
              </button>
            </div>
          </form>
        </div>
      )}
    </div>
  );
}
