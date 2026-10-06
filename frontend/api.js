const API_ROOT = '/api';
let ownerToken = sessionStorage.getItem('ai-media-owner-token') || '';

export class ApiError extends Error {
  constructor(message, status, code) {
    super(message);
    this.name = 'ApiError';
    this.status = status;
    this.code = code;
  }
}

async function request(path, {method = 'GET', body, publicEndpoint = false, query = {}} = {}) {
  const url = new URL(`${API_ROOT}${path}`, window.location.origin);
  Object.entries(query).forEach(([key, value]) => {
    if (value !== undefined && value !== null && String(value).trim() !== '') url.searchParams.set(key, String(value));
  });
  const headers = {Accept: 'application/json'};
  if (body !== undefined) headers['Content-Type'] = 'application/json';
  if (!publicEndpoint && ownerToken) headers['X-Owner-Token'] = ownerToken;
  let response;
  try {
    response = await fetch(url, {method, headers, body: body === undefined ? undefined : JSON.stringify(body), cache: 'no-store'});
  } catch (error) {
    throw new ApiError('تعذّر الاتصال بالخادم الخلفي.', 0, 'network_error');
  }
  const payload = await response.json().catch(() => ({}));
  if (!response.ok) {
    const problem = payload.error || {};
    throw new ApiError(problem.message || `فشل الطلب (${response.status}).`, response.status, problem.code || 'request_failed');
  }
  return payload;
}

export const api = {
  get hasToken() { return Boolean(ownerToken); },
  setToken(token) { ownerToken = token.trim(); if (ownerToken) sessionStorage.setItem('ai-media-owner-token', ownerToken); else sessionStorage.removeItem('ai-media-owner-token'); },
  clearToken() { this.setToken(''); },
  health: () => request('/health', {publicEndpoint: true}),
  modules: () => request('/modules', {publicEndpoint: true}),
  dashboard: () => request('/dashboard'),
  company: () => request('/company'),
  tasks: (query = {}) => request('/tasks', {query}),
  createTask: (body) => request('/tasks', {method: 'POST', body}),
  updateTask: (id, body) => request(`/tasks/${encodeURIComponent(id)}`, {method: 'PATCH', body}),
  approvals: (query = {}) => request('/approvals', {query}),
  createApproval: (body) => request('/approvals', {method: 'POST', body}),
  decideApproval: (id, body) => request(`/approvals/${encodeURIComponent(id)}`, {method: 'PATCH', body}),
  activity: (query = {}) => request('/activity', {query}),
};
