import React, { createContext, useContext, useState, useEffect, useCallback } from 'react';
import type {
  UserRole,
  UserProfile,
  Character,
  Universe,
  Project,
  VaultAsset,
  MemoryEntry,
  SandboxExperiment,
  ReadinessItem,
  IntegrationConnector,
  AgentInfo,
  Route,
  Script,
  ApprovalItem,
  AuditLogEntry,
} from '../types';
import {
  initialCharacters,
  initialUniverses,
  initialProjects,
  initialVaultAssets,
  initialMemoryEntries,
  initialSandboxExperiments,
  initialReadinessItems,
  initialIntegrations,
  initialAgents,
  initialRoutes,
  initialScripts,
  initialApprovals,
  initialAuditLogs,
} from '../data/initialData';

const STORAGE_KEY = 'nada_ai_media_os_state_v3';

const ROLE_PROFILES: Record<UserRole, UserProfile> = {
  OWNER: {
    name: 'المالك (OWNER)',
    role: 'OWNER',
    title: 'صاحب القرار النهائي وسيادة المنظومة',
    email: 'owner@nada-media.os',
    avatar: '👑',
    canApprove: true,
    canModifySystem: true,
    canDeploy: true,
    canManageBudgets: true,
    canAccessSandbox: true,
  },
  ADMIN: {
    name: 'المدير العام (AI Orchestrator)',
    role: 'ADMIN',
    title: 'منسق العمليات وإدارة الفرق والأقسام',
    email: 'admin@nada-media.os',
    avatar: '⚡',
    canApprove: false, // Sensitive decisions require Owner
    canModifySystem: true,
    canDeploy: false,
    canManageBudgets: false,
    canAccessSandbox: true,
  },
  AGENT: {
    name: 'وكيل الإنتاج المتخصص',
    role: 'AGENT',
    title: 'وكيل ذكي لتوليد ومراجعة المحتوى',
    email: 'agent@nada-media.os',
    avatar: '🤖',
    canApprove: false,
    canModifySystem: false,
    canDeploy: false,
    canManageBudgets: false,
    canAccessSandbox: false,
  },
  GUEST: {
    name: 'مراقب ومراجع جودة',
    role: 'GUEST',
    title: 'صلاحيات قراءة واختبار محدودة',
    email: 'guest@nada-media.os',
    avatar: '🔍',
    canApprove: false,
    canModifySystem: false,
    canDeploy: false,
    canManageBudgets: false,
    canAccessSandbox: false,
  },
};

interface AppContextType {
  currentRole: UserRole;
  currentUser: UserProfile;
  characters: Character[];
  universes: Universe[];
  projects: Project[];
  vaultAssets: VaultAsset[];
  memoryEntries: MemoryEntry[];
  sandboxExperiments: SandboxExperiment[];
  readinessItems: ReadinessItem[];
  integrations: IntegrationConnector[];
  agents: AgentInfo[];
  routes: Route[];
  scripts: Script[];
  approvals: ApprovalItem[];
  auditLogs: AuditLogEntry[];
  dailyBudget: { max: number; used: number };
  lastSaved: string;

  // Actions
  switchRole: (role: UserRole) => void;
  approveItem: (id: string, notes?: string) => void;
  rejectItem: (id: string, notes?: string) => void;
  addCharacter: (char: Character) => void;
  updateCharacter: (char: Character) => void;
  deleteCharacter: (id: string) => void;
  addScript: (script: Script) => void;
  updateScript: (script: Script) => void;
  deleteScript: (id: string) => void;
  addProject: (prj: Project) => void;
  updateProject: (prj: Project) => void;
  addVaultAsset: (asset: VaultAsset) => void;
  deleteVaultAsset: (id: string) => void;
  addMemoryEntry: (entry: Omit<MemoryEntry, 'id' | 'updatedAt'>) => void;
  updateAgentStatus: (agentId: string, status: AgentInfo['status'], task?: string) => void;
  restartAgent: (agentId: string) => void;
  testRoute: (routeId: string) => void;
  promoteSandboxExperiment: (expId: string) => void;
  runSandboxExperiment: (expId: string) => void;
  pingIntegration: (intId: string) => void;
  exportStateToJson: () => string;
  importStateFromJson: (jsonStr: string) => boolean;
  resetToBlueprintDefaults: () => void;
  queryInstantMemory: (query: string) => { results: MemoryEntry[]; executionTimeMs: number; summary: string };
}

const AppContext = createContext<AppContextType | undefined>(undefined);

export const AppProvider: React.FC<{ children: React.ReactNode }> = ({ children }) => {
  const [currentRole, setCurrentRole] = useState<UserRole>('OWNER');
  const [characters, setCharacters] = useState<Character[]>(initialCharacters);
  const [universes, setUniverses] = useState<Universe[]>(initialUniverses);
  const [projects, setProjects] = useState<Project[]>(initialProjects);
  const [vaultAssets, setVaultAssets] = useState<VaultAsset[]>(initialVaultAssets);
  const [memoryEntries, setMemoryEntries] = useState<MemoryEntry[]>(initialMemoryEntries);
  const [sandboxExperiments, setSandboxExperiments] = useState<SandboxExperiment[]>(initialSandboxExperiments);
  const [readinessItems, setReadinessItems] = useState<ReadinessItem[]>(initialReadinessItems);
  const [integrations, setIntegrations] = useState<IntegrationConnector[]>(initialIntegrations);
  const [agents, setAgents] = useState<AgentInfo[]>(initialAgents);
  const [routes, setRoutes] = useState<Route[]>(initialRoutes);
  const [scripts, setScripts] = useState<Script[]>(initialScripts);
  const [approvals, setApprovals] = useState<ApprovalItem[]>(initialApprovals);
  const [auditLogs, setAuditLogs] = useState<AuditLogEntry[]>(initialAuditLogs);
  const [dailyBudget] = useState({ max: 50.0, used: 14.85 });
  const [lastSaved, setLastSaved] = useState<string>('تم الحفظ محلياً الآن');

  // Load from LocalStorage on mount
  useEffect(() => {
    try {
      const saved = localStorage.getItem(STORAGE_KEY);
      if (saved) {
        const parsed = JSON.parse(saved);
        if (parsed.characters && parsed.characters.length > 0) setCharacters(parsed.characters);
        if (parsed.universes) setUniverses(parsed.universes);
        if (parsed.projects) setProjects(parsed.projects);
        if (parsed.vaultAssets) setVaultAssets(parsed.vaultAssets);
        if (parsed.memoryEntries) setMemoryEntries(parsed.memoryEntries);
        if (parsed.sandboxExperiments) setSandboxExperiments(parsed.sandboxExperiments);
        if (parsed.readinessItems) setReadinessItems(parsed.readinessItems);
        if (parsed.integrations) setIntegrations(parsed.integrations);
        if (parsed.agents) setAgents(parsed.agents);
        if (parsed.routes) setRoutes(parsed.routes);
        if (parsed.scripts) setScripts(parsed.scripts);
        if (parsed.approvals) setApprovals(parsed.approvals);
        if (parsed.auditLogs) setAuditLogs(parsed.auditLogs);
        if (parsed.currentRole) setCurrentRole(parsed.currentRole);
      }
    } catch (e) {
      console.warn('Failed to load saved state from localStorage, using blueprint defaults:', e);
    }
  }, []);

  // Save to LocalStorage whenever critical data changes
  const persistState = useCallback(() => {
    try {
      const stateToSave = {
        characters,
        universes,
        projects,
        vaultAssets,
        memoryEntries,
        sandboxExperiments,
        readinessItems,
        integrations,
        agents,
        routes,
        scripts,
        approvals,
        auditLogs,
        currentRole,
      };
      localStorage.setItem(STORAGE_KEY, JSON.stringify(stateToSave));
      setLastSaved(new Date().toLocaleTimeString('ar-EG'));
    } catch (e) {
      console.error('Failed to save to localStorage:', e);
    }
  }, [
    characters,
    universes,
    projects,
    vaultAssets,
    memoryEntries,
    sandboxExperiments,
    readinessItems,
    integrations,
    agents,
    routes,
    scripts,
    approvals,
    auditLogs,
    currentRole,
  ]);

  useEffect(() => {
    persistState();
  }, [persistState]);

  // Log action helper
  const logAction = useCallback(
    (action: string, module: string, level: AuditLogEntry['level'] = 'info', details: string = '') => {
      const newEntry: AuditLogEntry = {
        id: 'log-' + Date.now(),
        timestamp: new Date().toLocaleString('ar-EG'),
        actor: ROLE_PROFILES[currentRole].name,
        action,
        module,
        level,
        details,
      };
      setAuditLogs((prev) => [newEntry, ...prev.slice(0, 99)]);
    },
    [currentRole]
  );

  const switchRole = useCallback(
    (role: UserRole) => {
      setCurrentRole(role);
      logAction(`تبديل الصلاحية إلى ${role}`, 'Security & Access', 'security', `تم تغيير دور الجلسة`);
    },
    [logAction]
  );

  const approveItem = useCallback(
    (id: string, notes: string = 'تم الاعتماد بموافقة صاحب القرار') => {
      setApprovals((prev) =>
        prev.map((item) => {
          if (item.id === id) {
            return {
              ...item,
              status: 'approved',
              decidedBy: ROLE_PROFILES[currentRole].name,
              decidedAt: new Date().toLocaleString('ar-EG'),
              decisionNotes: notes,
            };
          }
          return item;
        })
      );
      logAction(`اعتماد طلب: ${id}`, 'Approvals Center', 'info', notes);
    },
    [currentRole, logAction]
  );

  const rejectItem = useCallback(
    (id: string, notes: string = 'مرفوض للمراجعة والتعديل') => {
      setApprovals((prev) =>
        prev.map((item) => {
          if (item.id === id) {
            return {
              ...item,
              status: 'rejected',
              decidedBy: ROLE_PROFILES[currentRole].name,
              decidedAt: new Date().toLocaleString('ar-EG'),
              decisionNotes: notes,
            };
          }
          return item;
        })
      );
      logAction(`رفض طلب: ${id}`, 'Approvals Center', 'warn', notes);
    },
    [currentRole, logAction]
  );

  const addCharacter = useCallback(
    (char: Character) => {
      setCharacters((prev) => [char, ...prev]);
      logAction(`إضافة شخصية جديدة: ${char.name} (${char.code})`, 'Characters Studio', 'info');
    },
    [logAction]
  );

  const updateCharacter = useCallback(
    (char: Character) => {
      setCharacters((prev) => prev.map((c) => (c.id === char.id ? char : c)));
      logAction(`تحديث ملف الشخصية: ${char.name}`, 'Characters Studio', 'info');
    },
    [logAction]
  );

  const deleteCharacter = useCallback(
    (id: string) => {
      setCharacters((prev) => prev.filter((c) => c.id !== id));
      logAction(`حذف شخصية: ${id}`, 'Characters Studio', 'warn');
    },
    [logAction]
  );

  const addScript = useCallback(
    (script: Script) => {
      setScripts((prev) => [script, ...prev]);
      logAction(`إنشاء سكريبت جديد: ${script.title}`, 'Content Pipeline', 'info');
    },
    [logAction]
  );

  const updateScript = useCallback(
    (script: Script) => {
      setScripts((prev) => prev.map((s) => (s.id === script.id ? script : s)));
      logAction(`تعديل سكريبت: ${script.title}`, 'Content Pipeline', 'info');
    },
    [logAction]
  );

  const deleteScript = useCallback(
    (id: string) => {
      setScripts((prev) => prev.filter((s) => s.id !== id));
      logAction(`حذف سكريبت: ${id}`, 'Content Pipeline', 'warn');
    },
    [logAction]
  );

  const addProject = useCallback(
    (prj: Project) => {
      setProjects((prev) => [prj, ...prev]);
      logAction(`إضافة مشروع جديد: ${prj.title}`, 'Projects', 'info');
    },
    [logAction]
  );

  const updateProject = useCallback(
    (prj: Project) => {
      setProjects((prev) => prev.map((p) => (p.id === prj.id ? prj : p)));
      logAction(`تحديث مشروع: ${prj.title}`, 'Projects', 'info');
    },
    [logAction]
  );

  const addVaultAsset = useCallback(
    (asset: VaultAsset) => {
      setVaultAssets((prev) => [asset, ...prev]);
      logAction(`إيداع أصل رقمي: ${asset.name}`, 'Media Vault', 'info');
    },
    [logAction]
  );

  const deleteVaultAsset = useCallback(
    (id: string) => {
      setVaultAssets((prev) => prev.filter((a) => a.id !== id));
      logAction(`حذف أصل: ${id}`, 'Media Vault', 'warn');
    },
    [logAction]
  );

  const addMemoryEntry = useCallback(
    (entry: Omit<MemoryEntry, 'id' | 'updatedAt'>) => {
      const newEntry: MemoryEntry = {
        ...entry,
        id: 'mem-' + Date.now(),
        updatedAt: new Date().toLocaleString('ar-EG'),
      };
      setMemoryEntries((prev) => [newEntry, ...prev]);
      logAction(`تسجيل ذاكرة دائمة: ${entry.title}`, 'Memory System', 'info');
    },
    [logAction]
  );

  const updateAgentStatus = useCallback(
    (agentId: string, status: AgentInfo['status'], task?: string) => {
      setAgents((prev) =>
        prev.map((a) => {
          if (a.id === agentId) {
            return {
              ...a,
              status,
              task: task !== undefined ? task : a.task,
              lastActive: 'الآن',
            };
          }
          return a;
        })
      );
    },
    []
  );

  const restartAgent = useCallback(
    (agentId: string) => {
      updateAgentStatus(agentId, 'active', 'تمت إعادة التشغيل والجاهزية بنجاح');
      logAction(`إعادة تشغيل الوكيل: ${agentId}`, 'Dashboard Agents', 'info');
    },
    [updateAgentStatus, logAction]
  );

  const testRoute = useCallback(
    (routeId: string) => {
      setRoutes((prev) =>
        prev.map((r) => {
          if (r.id === routeId) {
            const latencies = ['45ms', '62ms', '88ms', '110ms', '135ms'];
            const newLat = latencies[Math.floor(Math.random() * latencies.length)];
            return { ...r, latency: newLat, status: 'running' };
          }
          return r;
        })
      );
      logAction(`فحص مسار توجيه النماذج: ${routeId}`, 'OmniRoute', 'info');
    },
    [logAction]
  );

  const promoteSandboxExperiment = useCallback(
    (expId: string) => {
      setSandboxExperiments((prev) =>
        prev.map((e) => {
          if (e.id === expId) {
            return {
              ...e,
              status: 'passed_benchmarks',
              logs: [...e.logs, `[PROMOTED] تم اعتماد الترقية للإنتاج بواسطة ${ROLE_PROFILES[currentRole].name}`],
            };
          }
          return e;
        })
      );
      logAction(`ترقية تجربة من Sandbox إلى الإنتاج: ${expId}`, 'Future Engineer 2350', 'security');
    },
    [currentRole, logAction]
  );

  const runSandboxExperiment = useCallback(
    (expId: string) => {
      setSandboxExperiments((prev) =>
        prev.map((e) => {
          if (e.id === expId) {
            return {
              ...e,
              status: 'evaluating',
              logs: [
                ...e.logs,
                `[RUN TEST] تم تشغيل المحاكاة المعزولة بنجاح عند ${new Date().toLocaleTimeString('ar-EG')}`,
              ],
            };
          }
          return e;
        })
      );
      logAction(`تشغيل تجربة معزولة في Sandbox: ${expId}`, 'Future Engineer 2350', 'info');
    },
    [logAction]
  );

  const pingIntegration = useCallback(
    (intId: string) => {
      setIntegrations((prev) =>
        prev.map((i) => {
          if (i.id === intId) {
            return {
              ...i,
              lastPing: 'منذ ثوانٍ (متصل بنجاح)',
              status: 'connected',
            };
          }
          return i;
        })
      );
      logAction(`فحص اتصال الخدمة الخارجية: ${intId}`, 'Integrations', 'info');
    },
    [logAction]
  );

  const exportStateToJson = useCallback(() => {
    const fullState = {
      version: '3.0.0-hybrid-unified',
      exportedAt: new Date().toISOString(),
      characters,
      universes,
      projects,
      vaultAssets,
      memoryEntries,
      sandboxExperiments,
      readinessItems,
      integrations,
      agents,
      routes,
      scripts,
      approvals,
      auditLogs,
    };
    logAction('تصدير لقطة الذاكرة الكاملة بتنسيق JSON', 'Security & Recovery', 'security');
    return JSON.stringify(fullState, null, 2);
  }, [
    characters,
    universes,
    projects,
    vaultAssets,
    memoryEntries,
    sandboxExperiments,
    readinessItems,
    integrations,
    agents,
    routes,
    scripts,
    approvals,
    auditLogs,
    logAction,
  ]);

  const importStateFromJson = useCallback(
    (jsonStr: string): boolean => {
      try {
        const parsed = JSON.parse(jsonStr);
        if (parsed.characters) setCharacters(parsed.characters);
        if (parsed.universes) setUniverses(parsed.universes);
        if (parsed.projects) setProjects(parsed.projects);
        if (parsed.vaultAssets) setVaultAssets(parsed.vaultAssets);
        if (parsed.memoryEntries) setMemoryEntries(parsed.memoryEntries);
        if (parsed.sandboxExperiments) setSandboxExperiments(parsed.sandboxExperiments);
        if (parsed.readinessItems) setReadinessItems(parsed.readinessItems);
        if (parsed.integrations) setIntegrations(parsed.integrations);
        if (parsed.agents) setAgents(parsed.agents);
        if (parsed.routes) setRoutes(parsed.routes);
        if (parsed.scripts) setScripts(parsed.scripts);
        if (parsed.approvals) setApprovals(parsed.approvals);
        if (parsed.auditLogs) setAuditLogs(parsed.auditLogs);

        logAction('استعادة حالة النظام من ملف JSON خارجي بنجاح', 'Security & Recovery', 'security');
        return true;
      } catch (e) {
        console.error('Failed to import JSON state:', e);
        return false;
      }
    },
    [logAction]
  );

  const resetToBlueprintDefaults = useCallback(() => {
    setCharacters(initialCharacters);
    setUniverses(initialUniverses);
    setProjects(initialProjects);
    setVaultAssets(initialVaultAssets);
    setMemoryEntries(initialMemoryEntries);
    setSandboxExperiments(initialSandboxExperiments);
    setReadinessItems(initialReadinessItems);
    setIntegrations(initialIntegrations);
    setAgents(initialAgents);
    setRoutes(initialRoutes);
    setScripts(initialScripts);
    setApprovals(initialApprovals);
    setAuditLogs(initialAuditLogs);
    setCurrentRole('OWNER');
    localStorage.removeItem(STORAGE_KEY);
    logAction('إعادة ضبط النظام إلى إعدادات وثيقة المرجع الموحد 3.0', 'Security & Recovery', 'critical');
  }, [logAction]);

  // NADA Instant Project Reader query engine (< 2s retrieval)
  const queryInstantMemory = useCallback(
    (query: string) => {
      const start = performance.now();
      const q = query.trim().toLowerCase();

      if (!q) {
        const end = performance.now();
        return {
          results: memoryEntries.slice(0, 5),
          executionTimeMs: Math.round(end - start) || 2,
          summary: 'عرض آخر الإدخالات المرجعية في ذاكرة المنظومة.',
        };
      }

      const matched = memoryEntries.filter(
        (m) =>
          m.title.toLowerCase().includes(q) ||
          m.content.toLowerCase().includes(q) ||
          m.tags.some((t) => t.toLowerCase().includes(q))
      );

      const end = performance.now();
      const timeMs = Math.round(end - start) || 4;

      const summary =
        matched.length > 0
          ? `تم العثور على ${matched.length} مرجعاً ذكياً متطابقاً مع "${query}" في ${timeMs}ms.`
          : `لم يتم العثور على تطابق مباشر مع "${query}". تم استرجاع سياق السيادة العامة.`;

      return {
        results: matched.length > 0 ? matched : memoryEntries.slice(0, 3),
        executionTimeMs: timeMs,
        summary,
      };
    },
    [memoryEntries]
  );

  const currentUser = ROLE_PROFILES[currentRole];

  return (
    <AppContext.Provider
      value={{
        currentRole,
        currentUser,
        characters,
        universes,
        projects,
        vaultAssets,
        memoryEntries,
        sandboxExperiments,
        readinessItems,
        integrations,
        agents,
        routes,
        scripts,
        approvals,
        auditLogs,
        dailyBudget,
        lastSaved,

        switchRole,
        approveItem,
        rejectItem,
        addCharacter,
        updateCharacter,
        deleteCharacter,
        addScript,
        updateScript,
        deleteScript,
        addProject,
        updateProject,
        addVaultAsset,
        deleteVaultAsset,
        addMemoryEntry,
        updateAgentStatus,
        restartAgent,
        testRoute,
        promoteSandboxExperiment,
        runSandboxExperiment,
        pingIntegration,
        exportStateToJson,
        importStateFromJson,
        resetToBlueprintDefaults,
        queryInstantMemory,
      }}
    >
      {children}
    </AppContext.Provider>
  );
};

// eslint-disable-next-line react-refresh/only-export-components
export const useApp = () => {
  const context = useContext(AppContext);
  if (!context) {
    throw new Error('useApp must be used within an AppProvider');
  }
  return context;
};
