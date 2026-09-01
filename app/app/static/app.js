/**
 * Hiss Single Page Application
 * Pure vanilla JavaScript communicating with Flask REST API (/api/v1)
 */

const API_BASE = '/api/v1';

const state = {
  projects: [],
  currentProject: null, // object: { id, key, name }
  currentProjectIssues: [],
  currentIssue: null, // object: { id, title, description, status, priority, labels, ... }
  currentComments: [],
  allLabels: [],
  filters: {
    status: '',
    priority: '',
    label: ''
  },
  appVersion: '...'
};

// --- Helper Utilities ---

function escapeHtml(str) {
  if (!str) return '';
  return String(str)
    .replace(/&/g, '&amp;')
    .replace(/</g, '&lt;')
    .replace(/>/g, '&gt;')
    .replace(/"/g, '&quot;')
    .replace(/'/g, '&#039;');
}

function showAlert(message, type = 'danger', dismissible = true) {
  const container = document.getElementById('alertContainer');
  if (!container) return;

  const alertDiv = document.createElement('div');
  alertDiv.className = `alert alert-${type} alert-dismissible fade show shadow-sm`;
  alertDiv.role = 'alert';
  alertDiv.innerHTML = `
    <span>${escapeHtml(message)}</span>
    ${dismissible ? '<button type="button" class="btn-close" data-bs-dismiss="alert" aria-label="Close"></button>' : ''}
  `;
  container.appendChild(alertDiv);

  // Auto remove after 6 seconds for non-error alerts
  if (type !== 'danger') {
    setTimeout(() => {
      try {
        const bsAlert = bootstrap.Alert.getOrCreateInstance(alertDiv);
        bsAlert.close();
      } catch (e) {}
    }, 6000);
  }
}

function clearAlerts() {
  const container = document.getElementById('alertContainer');
  if (container) container.innerHTML = '';
}

async function apiRequest(url, options = {}) {
  const defaultHeaders = {
    'Accept': 'application/json'
  };
  if (options.body && typeof options.body === 'object') {
    defaultHeaders['Content-Type'] = 'application/json';
    options.body = JSON.stringify(options.body);
  }

  const mergedOptions = {
    ...options,
    headers: {
      ...defaultHeaders,
      ...(options.headers || {})
    }
  };

  try {
    const res = await fetch(url, mergedOptions);
    let data = null;
    const contentType = res.headers.get('content-type');
    if (contentType && contentType.includes('application/json')) {
      data = await res.json();
    }

    if (!res.ok) {
      const errorMsg = data && data.message ? data.message : `Request failed with status ${res.status}`;
      const errorObj = new Error(errorMsg);
      errorObj.status = res.status;
      errorObj.data = data;
      throw errorObj;
    }

    return data;
  } catch (err) {
    throw err;
  }
}

// --- Status & Priority Badges ---

function renderStatusBadge(status) {
  const s = status || 'open';
  return `<span class="badge badge-status-${s}">${escapeHtml(s.replace('_', ' '))}</span>`;
}

function renderPriorityBadge(priority) {
  const p = priority || 'medium';
  return `<span class="badge badge-priority-${p}">${escapeHtml(p)}</span>`;
}

function renderLabelBadge(label, removable = false, issueId = null) {
  return `
    <span class="label-pill">
      <span>${escapeHtml(label.name)}</span>
      ${removable && issueId ? `<button type="button" class="btn-close-custom" onclick="app.handleDetachLabel(${issueId}, '${escapeHtml(label.name)}', event)">&times;</button>` : ''}
    </span>
  `;
}

// --- Routing & Navigation ---

function parseHash() {
  const hash = window.location.hash.replace(/^#/, '');
  // Routes:
  // #/projects
  // #/projects/:key
  // #/issues/:id
  const parts = hash.split('/').filter(Boolean);
  if (parts.length === 0) {
    return { view: 'projects' };
  }
  if (parts[0] === 'projects') {
    if (parts.length >= 2) {
      return { view: 'project_issues', key: parts[1] };
    }
    return { view: 'projects' };
  }
  if (parts[0] === 'issues' && parts.length >= 2) {
    return { view: 'issue_detail', id: parseInt(parts[1], 10) };
  }
  return { view: 'projects' };
}

async function handleHashChange() {
  clearAlerts();
  const route = parseHash();

  if (route.view === 'projects') {
    await loadProjectsView();
  } else if (route.view === 'project_issues') {
    await loadProjectIssuesView(route.key);
  } else if (route.view === 'issue_detail') {
    await loadIssueDetailView(route.id);
  }
}

// --- Views Rendering ---

async function loadProjectsView() {
  try {
    const projects = await apiRequest(`${API_BASE}/projects`);
    state.projects = projects;
    renderProjectsList(projects);
  } catch (err) {
    showAlert(err.message || 'Failed to load projects');
  }
}

function renderProjectsList(projects) {
  const main = document.getElementById('mainContainer');
  let content = `
    <div class="row">
      <div class="col-12">
        <div class="d-flex justify-content-between align-items-center mb-4 pb-2 border-bottom border-secondary border-opacity-25">
          <div>
            <h2 class="h3 mb-1 text-white">Projects</h2>
            <p class="text-muted mb-0">Overview of all tracked projects and workspaces</p>
          </div>
          <button class="btn btn-primary" onclick="app.openCreateProjectModal()">
            <svg xmlns="http://www.w3.org/2000/svg" width="16" height="16" fill="currentColor" class="bi bi-plus-lg me-1" viewBox="0 0 16 16">
              <path fill-rule="evenodd" d="M8 2a.5.5 0 0 1 .5.5v5h5a.5.5 0 0 1 0 1h-5v5a.5.5 0 0 1-1 0v-5h-5a.5.5 0 0 1 0-1h5v-5A.5.5 0 0 1 8 2"/>
            </svg>
            New Project
          </button>
        </div>
      </div>
    </div>
  `;

  if (!projects || projects.length === 0) {
    content += `
      <div class="card card-custom p-5 text-center">
        <div class="mb-3 text-muted">
          <svg xmlns="http://www.w3.org/2000/svg" width="48" height="48" fill="currentColor" class="bi bi-folder2-open" viewBox="0 0 16 16">
            <path d="M1 3.5A1.5 1.5 0 0 1 2.5 2h2.764c.958 0 1.76.56 2.311 1.184l.753.816h5.173A1.5 1.5 0 0 1 15 5.5V6H1z"/>
            <path d="M.002 8a1.5 1.5 0 0 1 1.498-1.5h13a1.5 1.5 0 0 1 1.498 1.5L15 13.5A1.5 1.5 0 0 1 13.5 15h-11A1.5 1.5 0 0 1 1 13.5z"/>
          </svg>
        </div>
        <h4 class="text-white">No projects found</h4>
        <p class="text-muted mb-4">Get started by creating your first project container.</p>
        <div>
          <button class="btn btn-primary" onclick="app.openCreateProjectModal()">Create Project</button>
        </div>
      </div>
    `;
  } else {
    content += '<div class="row g-3">';
    projects.forEach(p => {
      content += `
        <div class="col-12 col-md-6 col-lg-4">
          <div class="card card-custom h-100 project-item p-3" onclick="window.location.hash='#/projects/${escapeHtml(p.key)}'">
            <div class="d-flex justify-content-between align-items-start mb-2">
              <span class="badge text-bg-primary font-monospace fs-6 px-2 py-1">${escapeHtml(p.key)}</span>
              <span class="text-muted small">#${p.id}</span>
            </div>
            <h4 class="h5 text-white mb-2">${escapeHtml(p.name)}</h4>
            <div class="mt-auto pt-3 text-muted small d-flex align-items-center">
              <span>View issues &rarr;</span>
            </div>
          </div>
        </div>
      `;
    });
    content += '</div>';
  }

  main.innerHTML = content;
}

async function loadProjectIssuesView(projectKey) {
  try {
    const projects = await apiRequest(`${API_BASE}/projects`);
    state.projects = projects;
    const project = projects.find(p => p.key === projectKey);
    if (!project) {
      showAlert(`Project '${projectKey}' not found.`);
      return;
    }
    state.currentProject = project;

    await fetchAndRenderIssues();
  } catch (err) {
    showAlert(err.message || `Failed to load project '${projectKey}'`);
  }
}

async function fetchAndRenderIssues() {
  if (!state.currentProject) return;
  const projectKey = state.currentProject.key;

  // Build query params
  const params = new URLSearchParams();
  if (state.filters.status) params.append('status', state.filters.status);
  if (state.filters.priority) params.append('priority', state.filters.priority);
  if (state.filters.label) params.append('label', state.filters.label);

  const queryString = params.toString() ? `?${params.toString()}` : '';

  try {
    const issues = await apiRequest(`${API_BASE}/projects/${projectKey}/issues${queryString}`);
    state.currentProjectIssues = issues;
    renderProjectIssuesView();
  } catch (err) {
    if (err.data && err.data.error === 'feature_disabled') {
      showAlert(err.message || 'Feature disabled: label filtering is not available.', 'warning');
      // Render the view anyway with empty or existing list
      renderProjectIssuesView();
    } else {
      showAlert(err.message || 'Failed to fetch issues');
      renderProjectIssuesView();
    }
  }
}

function renderProjectIssuesView() {
  const main = document.getElementById('mainContainer');
  const project = state.currentProject;
  const issues = state.currentProjectIssues || [];

  let content = `
    <!-- Header / Breadcrumb -->
    <div class="d-flex flex-wrap justify-content-between align-items-center mb-4 pb-2 border-bottom border-secondary border-opacity-25 gap-2">
      <div class="d-flex align-items-center gap-2">
        <a href="#/projects" class="btn btn-sm btn-outline-secondary">&larr; Back to Projects</a>
        <h2 class="h3 mb-0 text-white font-monospace">${escapeHtml(project.key)}</h2>
        <span class="text-muted fs-5">/</span>
        <span class="fs-5 text-light">${escapeHtml(project.name)}</span>
      </div>
      <div>
        <button class="btn btn-primary" onclick="app.openCreateIssueModal('${escapeHtml(project.key)}')">
          <svg xmlns="http://www.w3.org/2000/svg" width="16" height="16" fill="currentColor" class="bi bi-plus-lg me-1" viewBox="0 0 16 16">
            <path fill-rule="evenodd" d="M8 2a.5.5 0 0 1 .5.5v5h5a.5.5 0 0 1 0 1h-5v5a.5.5 0 0 1-1 0v-5h-5a.5.5 0 0 1 0-1h5v-5A.5.5 0 0 1 8 2"/>
          </svg>
          New Issue
        </button>
      </div>
    </div>

    <!-- Filters Bar -->
    <div class="card card-custom p-3 mb-4">
      <div class="row g-2 align-items-center">
        <div class="col-12 col-md-3">
          <label class="form-label small text-muted mb-1">Status</label>
          <select class="form-select form-select-sm form-select-dark" id="filterStatus" onchange="app.handleFilterChange()">
            <option value="">All Statuses</option>
            <option value="open" ${state.filters.status === 'open' ? 'selected' : ''}>Open</option>
            <option value="in_progress" ${state.filters.status === 'in_progress' ? 'selected' : ''}>In Progress</option>
            <option value="done" ${state.filters.status === 'done' ? 'selected' : ''}>Done</option>
          </select>
        </div>
        <div class="col-12 col-md-3">
          <label class="form-label small text-muted mb-1">Priority</label>
          <select class="form-select form-select-sm form-select-dark" id="filterPriority" onchange="app.handleFilterChange()">
            <option value="">All Priorities</option>
            <option value="low" ${state.filters.priority === 'low' ? 'selected' : ''}>Low</option>
            <option value="medium" ${state.filters.priority === 'medium' ? 'selected' : ''}>Medium</option>
            <option value="high" ${state.filters.priority === 'high' ? 'selected' : ''}>High</option>
          </select>
        </div>
        <div class="col-12 col-md-4">
          <label class="form-label small text-muted mb-1">Label</label>
          <div class="input-group input-group-sm">
            <input type="text" class="form-control form-control-dark" id="filterLabel" placeholder="Filter by label name" value="${escapeHtml(state.filters.label)}">
            <button class="btn btn-outline-secondary" type="button" onclick="app.handleFilterChange()">Apply</button>
          </div>
        </div>
        <div class="col-12 col-md-2 text-md-end pt-md-3">
          <button class="btn btn-sm btn-outline-secondary w-100" onclick="app.resetFilters()">Reset Filters</button>
        </div>
      </div>
    </div>

    <!-- Issues List -->
    <div class="card card-custom">
      <div class="card-header d-flex justify-content-between align-items-center py-3">
        <span class="fw-semibold">Issues (${issues.length})</span>
      </div>
  `;

  if (issues.length === 0) {
    content += `
      <div class="p-5 text-center text-muted">
        <p class="mb-2">No issues match the selected criteria.</p>
        <button class="btn btn-sm btn-outline-primary" onclick="app.openCreateIssueModal('${escapeHtml(project.key)}')">Create an Issue</button>
      </div>
    `;
  } else {
    content += '<div class="list-group list-group-flush">';
    issues.forEach(issue => {
      content += `
        <div class="list-group-item bg-transparent issue-row p-3 d-flex flex-column flex-md-row justify-content-between align-items-start align-items-md-center gap-2" style="cursor: pointer;" onclick="window.location.hash='#/issues/${issue.id}'">
          <div class="d-flex align-items-start gap-3">
            <span class="font-monospace text-muted small mt-1">#${issue.id}</span>
            <div>
              <div class="d-flex align-items-center gap-2 flex-wrap">
                <span class="fw-medium text-white">${escapeHtml(issue.title)}</span>
                ${(issue.labels || []).map(l => renderLabelBadge(l)).join(' ')}
              </div>
              ${issue.description ? `<p class="text-muted small mb-0 mt-1 text-truncate" style="max-width: 600px;">${escapeHtml(issue.description)}</p>` : ''}
            </div>
          </div>
          <div class="d-flex align-items-center gap-2 ms-auto ms-md-0">
            ${renderPriorityBadge(issue.priority)}
            ${renderStatusBadge(issue.status)}
          </div>
        </div>
      `;
    });
    content += '</div>';
  }

  content += '</div>';
  main.innerHTML = content;
}

async function loadIssueDetailView(issueId) {
  try {
    const issue = await apiRequest(`${API_BASE}/issues/${issueId}`);
    state.currentIssue = issue;

    const [comments, labels] = await Promise.all([
      apiRequest(`${API_BASE}/issues/${issueId}/comments`),
      apiRequest(`${API_BASE}/labels`)
    ]);

    state.currentComments = comments;
    state.allLabels = labels;

    renderIssueDetailView();
  } catch (err) {
    showAlert(err.message || `Failed to load issue #${issueId}`);
  }
}

function renderIssueDetailView() {
  const main = document.getElementById('mainContainer');
  const issue = state.currentIssue;
  const comments = state.currentComments || [];
  const allLabels = state.allLabels || [];

  const attachedLabelNames = new Set((issue.labels || []).map(l => l.name));
  const availableLabels = allLabels.filter(l => !attachedLabelNames.has(l.name));

  let content = `
    <!-- Header -->
    <div class="d-flex flex-wrap justify-content-between align-items-center mb-4 pb-2 border-bottom border-secondary border-opacity-25 gap-2">
      <div class="d-flex align-items-center gap-2">
        <button class="btn btn-sm btn-outline-secondary" onclick="window.history.back()">&larr; Back</button>
        <h2 class="h4 mb-0 text-white">Issue <span class="font-monospace text-primary">#${issue.id}</span></h2>
      </div>
    </div>

    <div class="row g-4">
      <!-- Left Main Column: Title, Description, Comments -->
      <div class="col-12 col-lg-8">
        <div class="card card-custom p-4 mb-4">
          <div class="d-flex justify-content-between align-items-start mb-3">
            <h3 class="h4 text-white mb-0" id="issueTitleDisplay">${escapeHtml(issue.title)}</h3>
          </div>
          <div class="p-3 bg-dark bg-opacity-50 rounded border border-secondary border-opacity-25 mb-4">
            <div class="text-muted small mb-2">Description</div>
            <div class="text-light" style="white-space: pre-wrap;">${escapeHtml(issue.description || 'No description provided.')}</div>
          </div>
          <div class="text-muted small">
            Created: ${issue.created_at ? new Date(issue.created_at).toLocaleString() : 'Unknown'}
          </div>
        </div>

        <!-- Comments Section -->
        <div class="card card-custom p-4">
          <h4 class="h5 text-white mb-3">Comments (${comments.length})</h4>
          
          <div class="d-flex flex-column gap-3 mb-4" id="commentsList">
  `;

  if (comments.length === 0) {
    content += `<p class="text-muted small mb-0">No comments yet. Add the first comment below.</p>`;
  } else {
    comments.forEach(c => {
      content += `
        <div class="comment-box p-3">
          <div class="d-flex justify-content-between align-items-center mb-2 pb-1 border-bottom border-secondary border-opacity-25">
            <span class="font-monospace text-muted small">#${c.id}</span>
            <span class="text-muted small">${c.created_at ? new Date(c.created_at).toLocaleString() : ''}</span>
          </div>
          <div class="text-light" style="white-space: pre-wrap;">${escapeHtml(c.body)}</div>
        </div>
      `;
    });
  }

  content += `
          </div>

          <!-- Add Comment Form -->
          <form onsubmit="app.handleAddComment(event, ${issue.id})">
            <div class="mb-3">
              <label for="commentBodyInput" class="form-label text-muted small">Add a Comment</label>
              <textarea class="form-control form-control-dark" id="commentBodyInput" rows="3" placeholder="Leave a comment..." required></textarea>
            </div>
            <button type="submit" class="btn btn-primary btn-sm">Post Comment</button>
          </form>
        </div>
      </div>

      <!-- Right Column: Status, Priority, Labels Metadata -->
      <div class="col-12 col-lg-4">
        <div class="card card-custom p-3 mb-4">
          <h5 class="h6 text-white mb-3 pb-2 border-bottom border-secondary border-opacity-25">Status & Priority</h5>
          
          <div class="mb-3">
            <label class="form-label text-muted small">Status</label>
            <select class="form-select form-select-sm form-select-dark" onchange="app.handleUpdateStatus(${issue.id}, this.value)">
              <option value="open" ${issue.status === 'open' ? 'selected' : ''}>Open</option>
              <option value="in_progress" ${issue.status === 'in_progress' ? 'selected' : ''}>In Progress</option>
              <option value="done" ${issue.status === 'done' ? 'selected' : ''}>Done</option>
            </select>
          </div>

          <div class="mb-2">
            <label class="form-label text-muted small">Priority</label>
            <select class="form-select form-select-sm form-select-dark" onchange="app.handleUpdatePriority(${issue.id}, this.value)">
              <option value="low" ${issue.priority === 'low' ? 'selected' : ''}>Low</option>
              <option value="medium" ${issue.priority === 'medium' ? 'selected' : ''}>Medium</option>
              <option value="high" ${issue.priority === 'high' ? 'selected' : ''}>High</option>
            </select>
          </div>
        </div>

        <div class="card card-custom p-3">
          <div class="d-flex justify-content-between align-items-center mb-3 pb-2 border-bottom border-secondary border-opacity-25">
            <h5 class="h6 text-white mb-0">Labels</h5>
            <button class="btn btn-xs btn-outline-secondary py-0 px-1" onclick="app.openManageLabelsModal(event)">Manage</button>
          </div>

          <!-- Attached Labels -->
          <div class="d-flex flex-wrap gap-2 mb-3">
            ${(issue.labels && issue.labels.length > 0)
              ? issue.labels.map(l => renderLabelBadge(l, true, issue.id)).join('')
              : '<span class="text-muted small">No labels attached.</span>'}
          </div>

          <!-- Attach Label Dropdown / Form -->
          <div>
            <label class="form-label text-muted small">Attach Label</label>
            <div class="input-group input-group-sm">
              <select class="form-select form-select-dark" id="attachLabelSelect">
                <option value="">Select a label...</option>
                ${availableLabels.map(l => `<option value="${escapeHtml(l.name)}">${escapeHtml(l.name)}</option>`).join('')}
              </select>
              <button class="btn btn-outline-primary" type="button" onclick="app.handleAttachSelectedLabel(${issue.id})">Attach</button>
            </div>
          </div>
        </div>
      </div>
    </div>
  `;

  main.innerHTML = content;
}

// --- Action Handlers ---

async function handleCreateProject(event) {
  event.preventDefault();
  const keyInput = document.getElementById('projectKeyInput');
  const nameInput = document.getElementById('projectNameInput');

  const key = keyInput.value.trim().toUpperCase();
  const name = nameInput.value.trim();

  try {
    await apiRequest(`${API_BASE}/projects`, {
      method: 'POST',
      body: { key, name }
    });

    const modalEl = document.getElementById('createProjectModal');
    const modal = bootstrap.Modal.getInstance(modalEl);
    if (modal) modal.hide();
    keyInput.value = '';
    nameInput.value = '';

    showAlert(`Project '${key}' created successfully!`, 'success');
    window.location.hash = `#/projects/${key}`;
  } catch (err) {
    showAlert(err.message || 'Failed to create project');
  }
}

async function handleCreateIssue(event) {
  event.preventDefault();
  if (!state.currentProject) return;

  const titleInput = document.getElementById('issueTitleInput');
  const descInput = document.getElementById('issueDescriptionInput');
  const prioritySelect = document.getElementById('issuePrioritySelect');

  const title = titleInput.value.trim();
  const description = descInput.value.trim();
  const priority = prioritySelect.value;

  try {
    const newIssue = await apiRequest(`${API_BASE}/projects/${state.currentProject.key}/issues`, {
      method: 'POST',
      body: { title, description, priority }
    });

    const modalEl = document.getElementById('createIssueModal');
    const modal = bootstrap.Modal.getInstance(modalEl);
    if (modal) modal.hide();
    titleInput.value = '';
    descInput.value = '';
    prioritySelect.value = 'medium';

    showAlert(`Issue #${newIssue.id} created!`, 'success');
    window.location.hash = `#/issues/${newIssue.id}`;
  } catch (err) {
    showAlert(err.message || 'Failed to create issue');
  }
}

async function handleUpdateStatus(issueId, newStatus) {
  try {
    const updated = await apiRequest(`${API_BASE}/issues/${issueId}`, {
      method: 'PATCH',
      body: { status: newStatus }
    });
    state.currentIssue = updated;
    showAlert(`Status updated to '${newStatus}'`, 'info');
  } catch (err) {
    showAlert(err.message || 'Failed to update status');
    await loadIssueDetailView(issueId);
  }
}

async function handleUpdatePriority(issueId, newPriority) {
  try {
    const updated = await apiRequest(`${API_BASE}/issues/${issueId}`, {
      method: 'PATCH',
      body: { priority: newPriority }
    });
    state.currentIssue = updated;
    showAlert(`Priority updated to '${newPriority}'`, 'info');
  } catch (err) {
    showAlert(err.message || 'Failed to update priority');
    await loadIssueDetailView(issueId);
  }
}

async function handleAddComment(event, issueId) {
  event.preventDefault();
  const commentInput = document.getElementById('commentBodyInput');
  const body = commentInput.value.trim();
  if (!body) return;

  try {
    await apiRequest(`${API_BASE}/issues/${issueId}/comments`, {
      method: 'POST',
      body: { body }
    });
    commentInput.value = '';
    await loadIssueDetailView(issueId);
    showAlert('Comment added', 'success');
  } catch (err) {
    showAlert(err.message || 'Failed to add comment');
  }
}

async function handleAttachSelectedLabel(issueId) {
  const select = document.getElementById('attachLabelSelect');
  const labelName = select.value;
  if (!labelName) return;

  try {
    await apiRequest(`${API_BASE}/issues/${issueId}/labels/${encodeURIComponent(labelName)}`, {
      method: 'POST'
    });
    await loadIssueDetailView(issueId);
    showAlert(`Label '${labelName}' attached`, 'success');
  } catch (err) {
    showAlert(err.message || 'Failed to attach label');
  }
}

async function handleDetachLabel(issueId, labelName, event) {
  if (event) event.stopPropagation();
  try {
    await apiRequest(`${API_BASE}/issues/${issueId}/labels/${encodeURIComponent(labelName)}`, {
      method: 'DELETE'
    });
    await loadIssueDetailView(issueId);
    showAlert(`Label '${labelName}' detached`, 'info');
  } catch (err) {
    showAlert(err.message || 'Failed to detach label');
  }
}

async function handleCreateLabel(event) {
  event.preventDefault();
  const input = document.getElementById('newLabelNameInput');
  const name = input.value.trim();
  if (!name) return;

  try {
    await apiRequest(`${API_BASE}/labels`, {
      method: 'POST',
      body: { name }
    });
    input.value = '';
    showAlert(`Label '${name}' created`, 'success');
    await refreshManageLabelsModal();
    if (state.currentIssue) {
      await loadIssueDetailView(state.currentIssue.id);
    }
  } catch (err) {
    showAlert(err.message || 'Failed to create label');
  }
}

async function refreshManageLabelsModal() {
  try {
    const labels = await apiRequest(`${API_BASE}/labels`);
    state.allLabels = labels;
    const container = document.getElementById('labelsListContainer');
    if (!container) return;

    if (labels.length === 0) {
      container.innerHTML = '<span class="text-muted small">No labels created yet.</span>';
    } else {
      container.innerHTML = labels.map(l => renderLabelBadge(l)).join(' ');
    }
  } catch (err) {
    console.error(err);
  }
}

function handleFilterChange() {
  const statusEl = document.getElementById('filterStatus');
  const priorityEl = document.getElementById('filterPriority');
  const labelEl = document.getElementById('filterLabel');

  state.filters.status = statusEl ? statusEl.value : '';
  state.filters.priority = priorityEl ? priorityEl.value : '';
  state.filters.label = labelEl ? labelEl.value.trim() : '';

  fetchAndRenderIssues();
}

function resetFilters() {
  state.filters = { status: '', priority: '', label: '' };
  const statusEl = document.getElementById('filterStatus');
  const priorityEl = document.getElementById('filterPriority');
  const labelEl = document.getElementById('filterLabel');

  if (statusEl) statusEl.value = '';
  if (priorityEl) priorityEl.value = '';
  if (labelEl) labelEl.value = '';

  fetchAndRenderIssues();
}

// --- Modal Helpers ---

function openCreateProjectModal() {
  const modalEl = document.getElementById('createProjectModal');
  const modal = bootstrap.Modal.getOrCreateInstance(modalEl);
  modal.show();
}

function openCreateIssueModal(projectKey) {
  const projectKeySpan = document.getElementById('createIssueProjectKey');
  if (projectKeySpan) projectKeySpan.textContent = projectKey;
  const modalEl = document.getElementById('createIssueModal');
  const modal = bootstrap.Modal.getOrCreateInstance(modalEl);
  modal.show();
}

async function openManageLabelsModal(event) {
  if (event) event.preventDefault();
  await refreshManageLabelsModal();
  const modalEl = document.getElementById('manageLabelsModal');
  const modal = bootstrap.Modal.getOrCreateInstance(modalEl);
  modal.show();
}

function navigateHome(event) {
  if (event) event.preventDefault();
  window.location.hash = '#/projects';
}

// --- Initialization ---

async function fetchAppVersion() {
  try {
    const res = await fetch('/version');
    if (res.ok) {
      const data = await res.json();
      state.appVersion = data.version || 'dev';
      const badge = document.getElementById('appVersionBadge');
      if (badge) badge.textContent = `v${state.appVersion}`;
    }
  } catch (e) {}
}

window.addEventListener('hashchange', handleHashChange);

document.addEventListener('DOMContentLoaded', async () => {
  fetchAppVersion();
  if (!window.location.hash || window.location.hash === '#') {
    window.location.hash = '#/projects';
  } else {
    handleHashChange();
  }
});

// Export app global interface for inline events
window.app = {
  navigateHome,
  openCreateProjectModal,
  openCreateIssueModal,
  openManageLabelsModal,
  handleCreateProject,
  handleCreateIssue,
  handleCreateLabel,
  handleAddComment,
  handleUpdateStatus,
  handleUpdatePriority,
  handleAttachSelectedLabel,
  handleDetachLabel,
  handleFilterChange,
  resetFilters
};
