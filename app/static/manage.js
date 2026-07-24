const eventId = location.pathname.split('/').filter(Boolean).at(-1);
let liveState = null;
let editingQuestionId = null;
let selectedQuestionId = null;
let activeTab = 'questions';

const $ = selector => document.querySelector(selector);
const statusLabel = value => LivePulse.statusText[value] || value;

function participantUrl() {
  return liveState ? `${location.origin}/e/${liveState.event.code}` : '';
}
function presentationUrl() {
  return liveState ? `${location.origin}/present/${liveState.event.presentation_token}` : '';
}

function setSocketStatus(status) {
  const node = $('#socket-status');
  node.classList.toggle('connected', status === 'connected');
  node.querySelector('span').textContent = status === 'connected' ? '실시간 연결됨' : status === 'connecting' ? '연결 중' : '재연결 중';
}

function renderHero() {
  if (!liveState) return;
  const { event, counts } = liveState;
  $('#event-title').textContent = event.title;
  $('#event-description').textContent = event.description || '행사 설명 없음';
  $('#event-code').textContent = `행사 코드 ${event.code}`;
  $('#participant-summary').textContent = `참가자 ${counts.participants_total}명 · 현재 접속 ${counts.participants_connected}명`;
  const badge = $('#event-status');
  badge.className = `status-badge ${event.status}`;
  badge.innerHTML = `<i class="status-dot"></i>${statusLabel(event.status)}`;
  $('#open-lobby').textContent = event.status === 'DRAFT' ? '참가 열기' : 'QR 화면 표시';
  $('#open-lobby').disabled = event.status === 'ENDED';
  $('#end-event').disabled = event.status === 'ENDED';
  $('#download-csv').href = `/api/events/${eventId}/export.csv`;
  document.title = `${event.title} · LivePulse`;
}

function renderQuestionList() {
  const list = $('#question-list');
  const questions = liveState?.questions || [];
  $('#question-count').textContent = `${questions.length}개`;
  if (!questions.length) {
    list.innerHTML = `<div class="empty-state small"><p>아직 질문이 없습니다.<br>첫 질문을 추가해 보세요.</p></div>`;
    return;
  }
  if (!selectedQuestionId) selectedQuestionId = questions[0].id;
  list.innerHTML = questions.map((question, index) => `
    <article class="question-item ${selectedQuestionId === question.id ? 'active' : ''}" data-question-id="${question.id}">
      <div class="question-number">${index + 1}</div>
      <div class="question-copy" data-action="select">
        <strong>${LivePulse.escapeHtml(question.text)}</strong>
        <span>${question.type === 'RATING' ? '1~5점 평점' : '단일 선택'} · ${statusLabel(question.status)} · 응답 ${question.response_count || 0}</span>
      </div>
      <div class="question-controls">
        <button class="icon-btn" data-action="up" title="위로 이동" ${index === 0 ? 'disabled' : ''}>↑</button>
        <button class="icon-btn" data-action="down" title="아래로 이동" ${index === questions.length - 1 ? 'disabled' : ''}>↓</button>
        <button class="icon-btn" data-action="edit" title="수정" ${!['READY','DRAFT'].includes(question.status) ? 'disabled' : ''}>✎</button>
        <button class="icon-btn" data-action="delete" title="삭제" ${!['READY','DRAFT'].includes(question.status) ? 'disabled' : ''}>×</button>
      </div>
    </article>
  `).join('');
}

function clearEditor() {
  editingQuestionId = null;
  $('#editor-title').textContent = '새 질문';
  $('#editor-help').textContent = '질문과 선택지를 입력해 주세요.';
  $('#question-form').reset();
  $('#question-type').value = 'SINGLE';
  $('#min-label').value = '매우 낮음';
  $('#max-label').value = '매우 높음';
  $('#cancel-edit').classList.add('hidden');
  $('#save-question').textContent = '질문 저장';
  updateQuestionTypeFields();
}

function editQuestion(questionId) {
  const question = liveState.questions.find(item => item.id === questionId);
  if (!question || !['READY','DRAFT'].includes(question.status)) return;
  editingQuestionId = question.id;
  selectedQuestionId = question.id;
  $('#editor-title').textContent = '질문 수정';
  $('#editor-help').textContent = '응답을 시작하기 전 질문만 수정할 수 있습니다.';
  $('#question-type').value = question.type;
  $('#question-text').value = question.text;
  $('#chart-type').value = question.chart_type;
  $('#question-options').value = question.type === 'SINGLE' ? question.options.map(option => option.text).join('\n') : '';
  $('#min-label').value = question.min_label || '매우 낮음';
  $('#max-label').value = question.max_label || '매우 높음';
  $('#cancel-edit').classList.remove('hidden');
  $('#save-question').textContent = '수정 저장';
  updateQuestionTypeFields();
  renderQuestionList();
  $('#question-text').focus();
}

function updateQuestionTypeFields() {
  const rating = $('#question-type').value === 'RATING';
  $('#single-fields').classList.toggle('hidden', rating);
  $('#rating-fields').classList.toggle('hidden', !rating);
}

function questionActionButtons(question) {
  const ended = liveState.event.status === 'ENDED';
  if (ended) return '';
  if (question.status === 'READY') {
    return `<button class="btn btn-primary btn-small" data-live-action="open" data-id="${question.id}">질문 열기</button>`;
  }
  if (question.id === liveState.event.current_question_id && question.status === 'OPEN') {
    return `<button class="btn btn-danger btn-small" data-live-action="close" data-id="${question.id}">응답 마감</button>`;
  }
  if (question.id === liveState.event.current_question_id && question.status === 'CLOSED') {
    return `<button class="btn btn-secondary btn-small" data-live-action="open" data-id="${question.id}">다시 열기</button>
      <button class="btn btn-primary btn-small" data-live-action="reveal" data-id="${question.id}">결과 공개</button>`;
  }
  return '';
}

function renderLiveQuestionList() {
  const list = $('#live-question-list');
  const questions = liveState?.questions || [];
  if (!questions.length) {
    list.innerHTML = `<div class="empty-state small">질문 관리에서 질문을 먼저 추가해 주세요.</div>`;
    return;
  }
  list.innerHTML = questions.map((question, index) => `
    <article class="live-question ${question.id === liveState.event.current_question_id ? 'current' : ''}">
      <div class="live-question-head">
        <div class="question-number">${index + 1}</div>
        <div class="live-question-text">${LivePulse.escapeHtml(question.text)}<br><small style="color:var(--muted)">${statusLabel(question.status)} · 응답 ${question.response_count || 0}</small></div>
      </div>
      <div class="live-question-actions">${questionActionButtons(question)}</div>
    </article>
  `).join('');
}

function renderLiveMain() {
  const panel = $('#live-main');
  const question = liveState?.current_question;
  if (!question) {
    panel.innerHTML = `<div class="empty-state" style="margin:auto">
      <div class="empty-icon">▶</div>
      <h2>진행할 질문을 선택하세요.</h2>
      <p>왼쪽 목록에서 ‘질문 열기’를 누르면 참가자 화면이 자동으로 전환됩니다.</p>
    </div>`;
    return;
  }
  const optionPreview = question.type === 'RATING'
    ? `<div class="rating-options" style="margin-top:12px">${question.options.map(o => `<div class="option-preview" style="text-align:center">${o.text}</div>`).join('')}</div>
       <div class="rating-labels"><span>${LivePulse.escapeHtml(question.min_label)}</span><span>${LivePulse.escapeHtml(question.max_label)}</span></div>`
    : question.options.map((option, index) => `<div class="option-preview"><b style="color:var(--brand);margin-right:8px">${index + 1}</b>${LivePulse.escapeHtml(option.text)}</div>`).join('');
  panel.innerHTML = `
    <div class="eyebrow">현재 질문 · ${statusLabel(question.status)}</div>
    <h2>${LivePulse.escapeHtml(question.text)}</h2>
    <div>${optionPreview}</div>
    <div class="live-action-zone">${questionActionButtons(question)}</div>
  `;
}

function renderLiveStats() {
  const counts = liveState?.counts || { participants_connected: 0, participants_total: 0 };
  $('#connected-count').textContent = counts.participants_connected;
  $('#total-count').textContent = counts.participants_total;
  $('#response-count').textContent = liveState?.current_response_count || 0;
  const content = $('#live-stats-content');
  if (!liveState?.current_question) {
    content.className = 'empty-state small';
    content.innerHTML = '질문을 열면 응답 통계가 표시됩니다.';
  } else {
    content.className = '';
    content.innerHTML = LivePulse.renderStats(liveState.current_question, liveState.stats);
  }
}

function renderAll() {
  if (!liveState) return;
  renderHero();
  renderQuestionList();
  renderLiveQuestionList();
  renderLiveMain();
  renderLiveStats();
}

async function loadInitialState() {
  try {
    liveState = await LivePulse.api(`/api/events/${eventId}/state`);
    renderAll();
    connectRealtime();
  } catch (error) {
    document.querySelector('.manage-shell').innerHTML = `<div class="card empty-state"><h2>행사를 불러오지 못했습니다.</h2><p>${LivePulse.escapeHtml(error.message)}</p><a class="btn btn-secondary" href="/host" style="margin-top:18px">행사 목록으로</a></div>`;
  }
}

function connectRealtime() {
  LivePulse.openSocket(
    `/ws/events/${eventId}?role=host`,
    state => { liveState = state; renderAll(); },
    setSocketStatus
  );
}

async function postAction(url, message) {
  try {
    await LivePulse.api(url, { method: 'POST' });
    if (message) LivePulse.toast(message);
  } catch (error) {
    LivePulse.toast(error.message, 'error');
  }
}

function switchTab(tab) {
  activeTab = tab;
  document.querySelectorAll('.tab').forEach(button => button.classList.toggle('active', button.dataset.tab === tab));
  $('#questions-tab').classList.toggle('hidden', tab !== 'questions');
  $('#live-tab').classList.toggle('hidden', tab !== 'live');
}

document.querySelectorAll('.tab').forEach(button => button.addEventListener('click', () => switchTab(button.dataset.tab)));
$('#question-type').addEventListener('change', updateQuestionTypeFields);
$('#new-question').addEventListener('click', () => { clearEditor(); $('#question-text').focus(); });
$('#cancel-edit').addEventListener('click', clearEditor);

$('#question-form').addEventListener('submit', async event => {
  event.preventDefault();
  const type = $('#question-type').value;
  const options = $('#question-options').value.split('\n').map(item => item.trim()).filter(Boolean);
  const payload = {
    text: $('#question-text').value.trim(),
    type,
    options: type === 'SINGLE' ? options : [],
    chart_type: type === 'SINGLE' ? $('#chart-type').value : 'BAR',
    min_label: $('#min-label').value.trim() || '매우 낮음',
    max_label: $('#max-label').value.trim() || '매우 높음'
  };
  const button = $('#save-question');
  button.disabled = true;
  try {
    const result = await LivePulse.api(
      editingQuestionId ? `/api/questions/${editingQuestionId}` : `/api/events/${eventId}/questions`,
      { method: editingQuestionId ? 'PUT' : 'POST', body: payload }
    );
    selectedQuestionId = result.id;
    LivePulse.toast(editingQuestionId ? '질문을 수정했습니다.' : '질문을 추가했습니다.');
    clearEditor();
    renderQuestionList();
  } catch (error) {
    LivePulse.toast(error.message, 'error');
  } finally {
    button.disabled = false;
  }
});

$('#question-list').addEventListener('click', async event => {
  const item = event.target.closest('[data-question-id]');
  if (!item) return;
  const questionId = item.dataset.questionId;
  const action = event.target.closest('[data-action]')?.dataset.action || 'select';
  selectedQuestionId = questionId;
  if (action === 'select') {
    renderQuestionList();
    return;
  }
  if (action === 'edit') return editQuestion(questionId);
  if (action === 'delete') {
    const question = liveState.questions.find(q => q.id === questionId);
    if (!confirm(`“${question.text}” 질문을 삭제하시겠습니까?`)) return;
    try {
      await LivePulse.api(`/api/questions/${questionId}`, { method: 'DELETE' });
      if (editingQuestionId === questionId) clearEditor();
      selectedQuestionId = null;
      LivePulse.toast('질문을 삭제했습니다.');
    } catch (error) { LivePulse.toast(error.message, 'error'); }
    return;
  }
  if (action === 'up' || action === 'down') {
    const ids = liveState.questions.map(q => q.id);
    const index = ids.indexOf(questionId);
    const target = action === 'up' ? index - 1 : index + 1;
    if (target < 0 || target >= ids.length) return;
    [ids[index], ids[target]] = [ids[target], ids[index]];
    try {
      await LivePulse.api(`/api/events/${eventId}/questions/reorder`, { method: 'POST', body: { question_ids: ids } });
    } catch (error) { LivePulse.toast(error.message, 'error'); }
  }
});

$('#live-tab').addEventListener('click', async event => {
  const button = event.target.closest('[data-live-action]');
  if (!button) return;
  const questionId = button.dataset.id;
  const action = button.dataset.liveAction;
  if (action === 'close') {
    const count = liveState.current_response_count || 0;
    if (!confirm(`현재 ${count}명이 응답했습니다. 응답을 마감하시겠습니까?`)) return;
  }
  if (action === 'reveal' && !confirm('결과를 참가자와 발표 화면에 공개하시겠습니까?')) return;
  button.disabled = true;
  await postAction(`/api/questions/${questionId}/actions/${action}`,
    action === 'open' ? '질문을 열었습니다.' : action === 'close' ? '응답을 마감했습니다.' : '결과를 공개했습니다.');
});

$('#open-lobby').addEventListener('click', () => postAction(`/api/events/${eventId}/actions/lobby`, 'QR 로비 화면을 표시했습니다.'));
$('#show-waiting').addEventListener('click', () => postAction(`/api/events/${eventId}/actions/waiting`, '대기 화면으로 전환했습니다.'));
$('#open-presentation').addEventListener('click', () => window.open(presentationUrl(), '_blank', 'noopener'));
$('#copy-link').addEventListener('click', () => LivePulse.copy(participantUrl(), '참가 링크를 복사했습니다.'));
$('#show-qr').addEventListener('click', () => {
  $('#qr-image').src = `/api/events/${eventId}/qr.png?ts=${Date.now()}`;
  $('#qr-code-text').textContent = liveState.event.code;
  $('#qr-modal').classList.remove('hidden');
});
$('#close-qr').addEventListener('click', () => $('#qr-modal').classList.add('hidden'));
$('#qr-present').addEventListener('click', () => window.open(presentationUrl(), '_blank', 'noopener'));
$('#qr-modal').addEventListener('click', event => { if (event.target.id === 'qr-modal') $('#qr-modal').classList.add('hidden'); });
$('#end-event').addEventListener('click', async () => {
  if (!confirm('행사를 종료하시겠습니까? 종료 후에는 새 답변을 받을 수 없습니다.')) return;
  await postAction(`/api/events/${eventId}/actions/end`, '행사를 종료했습니다.');
});

document.addEventListener('keydown', event => {
  if (activeTab !== 'live' || !liveState?.current_question) return;
  const target = event.target;
  if (['INPUT','TEXTAREA','SELECT'].includes(target.tagName)) return;
  const q = liveState.current_question;
  if (event.code === 'Space') {
    event.preventDefault();
    if (q.status === 'OPEN') postAction(`/api/questions/${q.id}/actions/close`);
    else if (q.status === 'READY' || q.status === 'CLOSED') postAction(`/api/questions/${q.id}/actions/open`);
  }
  if (event.key.toLowerCase() === 'r' && q.status === 'CLOSED') postAction(`/api/questions/${q.id}/actions/reveal`);
});

clearEditor();
loadInitialState();
