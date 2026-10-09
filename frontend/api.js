const API_ROOT = '/api';

export class ApiError extends Error {
  constructor(message, status, code, details = {}) {
    super(message);
    this.name = 'ApiError';
    this.status = status;
    this.code = code;
    this.details = details;
  }
}

async function request(path, {method = 'GET', body, publicEndpoint = false, query = {}} = {}) {
  const url = new URL(`${API_ROOT}${path}`, window.location.origin);
  Object.entries(query).forEach(([key, value]) => {
    if (value !== undefined && value !== null && String(value).trim() !== '') url.searchParams.set(key, String(value));
  });
  const headers = {Accept: 'application/json'};
  if (body !== undefined) headers['Content-Type'] = 'application/json';
  let response;
  try {
    response = await fetch(url, {method, headers, body: body === undefined ? undefined : JSON.stringify(body), credentials: 'same-origin', cache: 'no-store'});
  } catch (error) {
    throw new ApiError('تعذّر الاتصال بالخادم الخلفي.', 0, 'network_error');
  }
  const payload = await response.json().catch(() => ({}));
  if (!response.ok) {
    const problem = payload.error || {};
    throw new ApiError(problem.message || `فشل الطلب (${response.status}).`, response.status, problem.code || 'request_failed', problem.details || {});
  }
  return payload;
}

async function mediaBlob(generationId, kind) {
  const url = new URL(`${API_ROOT}/external-integrations/generations/${encodeURIComponent(generationId)}/${kind}`, window.location.origin);
  let response;
  try {
    response = await fetch(url, {headers: {Accept: '*/*'}, credentials: 'same-origin', cache: 'no-store'});
  } catch (error) {
    throw new ApiError('تعذّر الاتصال بالخادم الخلفي.', 0, 'network_error');
  }
  if (!response.ok) {
    const payload = await response.json().catch(() => ({}));
    const problem = payload.error || {};
    throw new ApiError(problem.message || `تعذّر جلب الملف (${response.status}).`, response.status, problem.code || 'media_download_failed', problem.details || {});
  }
  return response.blob();
}

export const api = {
  health: () => request('/health', {publicEndpoint: true}),
  sendCommand: (body) => request('/commands', {method: 'POST', body}),
  serviceIntegrations: () => request('/service-integrations'),
  saveServiceIntegration: (body) => request('/service-integrations', {method: 'POST', body}),
  login: (body) => request('/auth/login', {method: 'POST', body, publicEndpoint: true}),
  logout: () => request('/auth/logout', {method: 'POST', publicEndpoint: true}),
  changeOwnerPassword: (body) => request('/auth/change-password', {method: 'POST', body}),
  resetOwnerPassword: (body) => request('/auth/reset-password', {method: 'POST', body}),
  modules: () => request('/modules', {publicEndpoint: true}),
  dashboard: () => request('/dashboard'),
  pages: () => request('/pages'),
  executionReports: () => request('/execution-reports'),
  restoreExecutionReport: (id) => request(`/execution-reports/${id}/restore`, {method: 'POST', body: {confirm: true}}),
  company: () => request('/company'),
  tasks: (query = {}) => request('/tasks', {query}),
  createTask: (body) => request('/tasks', {method: 'POST', body}),
  updateTask: (id, body) => request(`/tasks/${encodeURIComponent(id)}`, {method: 'PATCH', body}),
  approvals: (query = {}) => request('/approvals', {query}),
  createApproval: (body) => request('/approvals', {method: 'POST', body}),
  decideApproval: (id, body) => request(`/approvals/${encodeURIComponent(id)}`, {method: 'PATCH', body}),
  activity: (query = {}) => request('/activity', {query}),
  companyBuilderSummary: () => request('/company-builder/summary'),
  companyStructure: () => request('/company/structure'),
  departments: () => request('/departments'),
  createDepartment: (body) => request('/departments', {method: 'POST', body}),
  updateDepartment: (id, body) => request(`/departments/${encodeURIComponent(id)}`, {method: 'PATCH', body}),
  deleteDepartment: (id) => request(`/departments/${encodeURIComponent(id)}`, {method: 'DELETE'}),
  employees: (query = {}) => request('/ai-employees', {query}),
  employee: (id) => request(`/ai-employees/${encodeURIComponent(id)}`),
  createEmployee: (body) => request('/ai-employees', {method: 'POST', body}),
  updateEmployee: (id, body) => request(`/ai-employees/${encodeURIComponent(id)}`, {method: 'PATCH', body}),
  deleteEmployee: (id) => request(`/ai-employees/${encodeURIComponent(id)}`, {method: 'DELETE'}),
  setEmployeePermissions: (id, permissions) => request(`/ai-employees/${encodeURIComponent(id)}/permissions`, {method: 'PATCH', body: {permissions}}),
  testEmployee: (id, message) => request(`/ai-employees/${encodeURIComponent(id)}/test`, {method: 'POST', body: {message}}),
  createEmployeeTask: (id, body) => request(`/ai-employees/${encodeURIComponent(id)}/tasks`, {method: 'POST', body}),
  roles: () => request('/roles'),
  createRole: (body) => request('/roles', {method: 'POST', body}),
  updateRole: (id, body) => request(`/roles/${encodeURIComponent(id)}`, {method: 'PATCH', body}),
  deleteRole: (id) => request(`/roles/${encodeURIComponent(id)}`, {method: 'DELETE'}),
  permissions: () => request('/permissions'),
  tools: () => request('/tools'),
  createTool: (body) => request('/tools', {method: 'POST', body}),
  knowledgeSources: () => request('/knowledge-sources'),
  createKnowledgeSource: (body) => request('/knowledge-sources', {method: 'POST', body}),
  workflows: () => request('/workflows'),
  createWorkflow: (body) => request('/workflows', {method: 'POST', body}),
  externalIntegrations: (query = {}) => request('/external-integrations', {query}),
  createExternalAccount: (body) => request('/external-integrations/accounts', {method: 'POST', body}),
  updateExternalAccount: (id, body) => request(`/external-integrations/accounts/${encodeURIComponent(id)}`, {method: 'PATCH', body}),
  deleteExternalAccount: (id) => request(`/external-integrations/accounts/${encodeURIComponent(id)}`, {method: 'DELETE'}),
  rotateExternalAccount: (body) => request('/external-integrations/rotate', {method: 'POST', body}),
  testExternalAccount: (id) => request(`/external-integrations/accounts/${encodeURIComponent(id)}/test`, {method: 'POST'}),
  executeMediaPipeline: (body) => request('/external-integrations/pipeline', {method: 'POST', body}),
  generateAudio: (body) => request('/external-integrations/generate/audio', {method: 'POST', body}),
  generateVideo: (body) => request('/external-integrations/generate/video', {method: 'POST', body}),
  pollMediaGeneration: (id) => request(`/external-integrations/generations/${encodeURIComponent(id)}`),
  mediaBlob,
};
