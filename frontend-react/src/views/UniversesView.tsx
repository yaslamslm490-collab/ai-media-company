import { useState } from 'react';
import { useApp } from '@/context/AppContext';
import type { Universe } from '@/types';
import {
  Clock,
} from 'lucide-react';

export function UniversesView() {
  const { universes, characters } = useApp();
  const [selectedUniverse, setSelectedUniverse] = useState<Universe>(universes[0]);

  return (
    <div className="space-y-6 animate-fade-up">
      {/* Header Banner */}
      <div className="card p-6 bg-gradient-to-l from-[var(--bg-card)] to-[var(--bg-elevated)] flex flex-col md:flex-row md:items-center justify-between gap-4">
        <div>
          <div className="flex items-center gap-2">
            <span className="text-xs px-2.5 py-0.5 rounded-full bg-accent/20 text-accent font-bold">
              القسم 5.6 — STORY UNIVERSES
            </span>
            <span className="text-xs text-muted">العوالم القصصية والتقاطعات السردية</span>
          </div>
          <h1 className="font-display font-bold text-2xl text-primary mt-1">
            إدارة العوالم القصصية والعلاقات بين الشخصيات
          </h1>
          <p className="text-sm text-secondary">
            تنظيم العوالم المترابطة، الخطوط الزمنية، والسلاسل الإعلامية المشتركة بين شخصيات المنظومة.
          </p>
        </div>

        <div className="text-left px-4 py-2 rounded-xl bg-elevated border border-default">
          <span className="text-xs text-muted block">العوالم النشطة</span>
          <span className="text-sm font-bold text-accent">{universes.length} عوالم متصلة</span>
        </div>
      </div>

      {/* Universes Grid */}
      <div className="grid grid-cols-1 md:grid-cols-3 gap-5">
        {universes.map((univ) => {
          const isSelected = selectedUniverse.id === univ.id;
          return (
            <div
              key={univ.id}
              onClick={() => setSelectedUniverse(univ)}
              className={`card p-5 cursor-pointer transition-all border flex flex-col justify-between ${
                isSelected ? 'border-accent bg-accent/5 shadow-md' : 'hover:border-accent/40 bg-[var(--bg-card)]'
              }`}
            >
              <div>
                <div className="flex items-center justify-between mb-3">
                  <span className="text-xs font-mono font-bold px-2 py-0.5 rounded bg-elevated text-accent border border-default">
                    {univ.code}
                  </span>
                  <span className="status-dot status-active" />
                </div>

                <h3 className="font-display font-bold text-base text-primary mb-1">
                  {univ.name}
                </h3>
                <p className="text-xs text-accent font-medium mb-3">{univ.theme}</p>
                <p className="text-xs text-secondary leading-relaxed mb-4">
                  {univ.description}
                </p>
              </div>

              <div className="pt-3 border-t border-default/50 flex items-center justify-between text-xs text-muted">
                <span>{univ.charactersCount} شخصيات مشتركة</span>
                <span>{univ.activeSeriesCount} سلاسل جارية</span>
              </div>
            </div>
          );
        })}
      </div>

      {/* Selected Universe Deep Dive */}
      <div className="card p-6 space-y-5">
        <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-3 pb-3 border-b border-default">
          <div>
            <span className="text-xs text-muted font-mono">{selectedUniverse.code}</span>
            <h3 className="font-display font-bold text-lg text-primary">
              {selectedUniverse.name} — تفاصيل الشخصيات والسلاسل
            </h3>
          </div>
          <span className="text-xs px-3 py-1 rounded-full bg-accent/20 text-accent font-bold">
            عالم معتمد ونشط
          </span>
        </div>

        <div>
          <h4 className="font-bold text-xs text-muted mb-3">الشخصيات الفاعلة في هذا العالم:</h4>
          <div className="grid grid-cols-1 sm:grid-cols-2 md:grid-cols-4 gap-3">
            {selectedUniverse.characters.map((charName) => {
              const charObj = characters.find((c) => c.name === charName);
              return (
                <div
                  key={charName}
                  className="p-3.5 rounded-xl bg-elevated border border-default flex items-center gap-3"
                >
                  <div className="w-10 h-10 rounded-xl bg-accent-dim text-accent flex items-center justify-center font-bold text-sm">
                    {charName.slice(0, 2)}
                  </div>
                  <div className="min-w-0">
                    <span className="text-xs font-bold text-primary block truncate">{charName}</span>
                    <span className="text-[10px] text-muted truncate">
                      {charObj?.archetype || 'شخصية معتمدة'}
                    </span>
                  </div>
                </div>
              );
            })}
          </div>
        </div>

        {/* Timeline Cross-Over Simulation */}
        <div className="p-4 rounded-xl bg-elevated/70 border border-default space-y-2">
          <h4 className="font-bold text-xs text-primary flex items-center gap-2">
            <Clock className="w-4 h-4 text-accent" />
            الخط الزمني للحلقات والتقاطعات المشتركة (Cross-Over Episodes)
          </h4>
          <p className="text-xs text-secondary leading-relaxed">
            الحلقة المشتركة 1: عم حسن وعم رجب يحلان مشكلة السخان الكهربائي وتسريب المياه في شقة واحدة.
            <br />
            الحلقة المشتركة 2: المعلم فؤاد وعم سعيد ينسقان ديكور وتشطيب غرفة معيشة كلاسيكية بخشب الزان.
          </p>
        </div>
      </div>
    </div>
  );
}
