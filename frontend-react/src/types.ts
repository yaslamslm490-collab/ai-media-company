export type ViewKey =
  | 'owner_center'
  | 'dashboard'
  | 'assistant'
  | 'characters'
  | 'universes'
  | 'projects'
  | 'content_pipeline'
  | 'voice_studio'
  | 'omniroute'
  | 'approvals'
  | 'vault'
  | 'memory'
  | 'security'
  | 'future_engineer'
  | 'readiness'
  | 'daily_report';

export type UserRole = 'OWNER' | 'ADMIN' | 'AGENT' | 'GUEST';

export interface UserProfile {
  name: string;
  role: UserRole;
  title: string;
  email: string;
  avatar: string;
  canApprove: boolean;
  canModifySystem: boolean;
  canDeploy: boolean;
  canManageBudgets: boolean;
  canAccessSandbox: boolean;
}

export interface PersonaBibleIdentity {
  name: string;
  code: string;
  role: string;
  tone: string;
  audience: string;
  personality: string;
  backstory: string;
}

export interface PersonaBibleRules {
  do: string[];
  dont: string[];
}

export interface PersonaBiblePrompt {
  name: string;
  template: string;
}

export interface VoiceSignature {
  gender: 'male' | 'female';
  toneDescription: string;
  pitch: number; // 0.5 to 1.5
  rate: number;  // 0.5 to 1.5
  samplePhrase: string;
}

export interface CharacterBible {
  identity: PersonaBibleIdentity;
  rules: PersonaBibleRules;
  prompts: PersonaBiblePrompt[];
  voice: VoiceSignature;
  visualTraits: string[];
  continuityRules: string[];
}

export interface Character {
  id: string;
  code: string; // e.g. CHAR-001
  name: string;
  archetype: string;
  audience: string;
  tone: string;
  platforms: string[];
  contentCount: number;
  engagement: number;
  status: 'active' | 'drafting' | 'paused';
  avatarColor: string;
  image?: string;
  bible: CharacterBible;
}

export interface StatCard {
  id: string;
  label: string;
  value: string;
  subValue: string;
  trend: number;
  trendUp: boolean;
  icon: string;
  color: 'accent' | 'info' | 'warning' | 'error';
}

export interface AgentInfo {
  id: string;
  name: string;
  role: string;
  status: 'active' | 'idle' | 'error' | 'offline';
  task: string;
  progress: number;
  lastActive: string;
  department: string;
}

export type PipelineStage =
  | 'IDEA'
  | 'RESEARCH'
  | 'SCRIPT'
  | 'REVIEW'
  | 'STORYBOARD'
  | 'PRODUCTION'
  | 'EDITING'
  | 'QUALITY_CHECK'
  | 'APPROVAL'
  | 'PUBLISHING'
  | 'ANALYTICS'
  | 'ARCHIVED';

export interface QualityGateCheck {
  languageChecked: boolean;
  factChecked: boolean;
  rightsVerified: boolean;
  audioQualityVerified: boolean;
  visualConsistencyVerified: boolean;
  technicalSpecsPassed: boolean;
}

export interface Script {
  id: string;
  title: string;
  characterId: string;
  characterName: string;
  platform: string;
  stage: PipelineStage;
  wordCount: number;
  updatedAt: string;
  hook: string;
  body: string;
  cta: string;
  targetDuration: string;
  qualityGate: QualityGateCheck;
}

export interface Route {
  id: string;
  name: string;
  type: 'input' | 'output' | 'transform';
  source: string;
  destination: string;
  status: 'running' | 'paused' | 'error';
  throughput: string;
  latency: string;
  costPer1kTokens?: string;
  modelTarget?: string;
}

export interface ApprovalItem {
  id: string;
  type: 'content' | 'script' | 'campaign' | 'character' | 'budget' | 'deployment';
  title: string;
  submittedBy: string;
  submittedAt: string;
  priority: 'low' | 'medium' | 'high' | 'urgent';
  status: 'pending' | 'approved' | 'rejected';
  summary: string;
  requiresOwnerApproval: boolean;
  decidedBy?: string;
  decidedAt?: string;
  decisionNotes?: string;
}

export interface Universe {
  id: string;
  name: string;
  code: string;
  theme: string;
  description: string;
  charactersCount: number;
  activeSeriesCount: number;
  characters: string[];
  status: 'active' | 'in_development' | 'archived';
}

export interface Project {
  id: string;
  title: string;
  code: string;
  department: string;
  manager: string;
  progress: number;
  budgetAllocated: number;
  budgetSpent: number;
  deadline: string;
  riskLevel: 'low' | 'medium' | 'high';
  status: 'planning' | 'in_progress' | 'review' | 'completed' | 'on_hold';
  dependencies: string[];
}

export interface VaultAsset {
  id: string;
  name: string;
  type: 'image' | 'voice' | 'script' | 'video' | 'storyboard' | 'document';
  characterOrProject: string;
  format: string;
  fileSize: string;
  createdDate: string;
  version: string;
  license: string;
  reviewStatus: 'verified' | 'draft' | 'archived';
  url?: string;
}

export type MemoryComponentKey =
  | 'core'
  | 'project'
  | 'experience'
  | 'timeline'
  | 'research'
  | 'character'
  | 'technical'
  | 'future_engineer'
  | 'recovery'
  | 'decision'
  | 'cost'
  | 'lessons_learned';

export interface MemoryEntry {
  id: string;
  component: MemoryComponentKey;
  title: string;
  content: string;
  tags: string[];
  confidence: number;
  updatedAt: string;
  author: string;
}

export interface SandboxExperiment {
  id: string;
  title: string;
  code: string;
  technology: string;
  hypothesis: string;
  status: 'isolated_testing' | 'evaluating' | 'passed_benchmarks' | 'rejected';
  metrics: {
    qualityScore: number;
    costEfficiency: number;
    latencyMs: number;
  };
  isolationSecured: boolean;
  logs: string[];
  createdAt: string;
}

export interface ReadinessItem {
  id: string;
  moduleName: string;
  code: string;
  status: 'NOT PREPARED' | 'IN PREPARATION' | 'READY FOR IMPLEMENTATION';
  requirementsReady: boolean;
  architectureReady: boolean;
  securityPlanReady: boolean;
  testPlanReady: boolean;
  rollbackPlanReady: boolean;
  costEstimate: string;
}

export interface IntegrationConnector {
  id: string;
  name: string;
  provider: string;
  category: 'code' | 'agent' | 'models' | 'audio' | 'video' | 'database';
  status: 'connected' | 'needs_keys' | 'offline';
  latency: string;
  lastPing: string;
  hasApiSecret: boolean;
}

export interface AuditLogEntry {
  id: string;
  timestamp: string;
  actor: string;
  action: string;
  module: string;
  level: 'info' | 'warn' | 'security' | 'critical';
  details: string;
}
