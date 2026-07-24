const eventCode = location.pathname.split('/').filter(Boolean).at(-1).toUpperCase();
const sessionKey = `livepulse:${eventCode}:participant`;
let participantId = localStorage.getItem(sessionKey);
let eventId = null;
let state = null;
let selectedOptionId = null;
let showingConfirmation = false;
let stopSocket = null;

const main = document.querySelector('#participant-main');
const submitBar = document.querySelector('#submit-bar');
const submitButton = document.querySelector('#submit-answer');
const titleNode = document.querySelector('#participant-event-title');
const statusNode = document.querySelector('#participant-status');

function stateView(icon, title, description, extra = '') {
  submitBar.classList.add('hidden');
  main.innerHTML = `<div class="participant-state"><div>
    <div class="state-icon">${icon}</div>
    <h1>${LivePulse.escapeHtml(title)}</h1>
    <p>${LivePulse.escapeHtml(description)}</p>
    ${extra}
  </div></div>`;
}

function selectedOption(question) {
  const id = state?.my_response?.option_id || selectedOptionId;
  return question?.options.find(option => option.id === id);
}

function renderQuestion(question) {
  const currentSelection = state.my_response?.option_id || selectedOptionId;
  selectedOptionId = currentSelection || null;
  showingConfirmation = showingConfirmation && Boolean(state.my_response);

  if (showingConfirmation && state.my_response) {
    const answer = selectedOption(question);
    submitBar.classList.add('hidden');
    main.innerHTML = `<div class="participant-state"><div>
      <div class="state-icon">✓</div>
      <h1>답변을 제출했습니다.</h1>
      <p>응답이 마감되기 전까지 답변을 변경할 수 있습니다.</p>
      <div class="my-answer">내 답변: ${LivePulse.escapeHtml(answer?.text || '')}</div>
      <button class="btn btn-secondary btn-large" id="change-answer">답변 변경</button>
    </div></div>`;
    document.querySelector('#change-answer').addEventListener('click', () => {
      showingConfirmation = false;
      render();
    });
    return;
  }

  const isRating = question.type === 'RATING';
  const optionsHtml = question.options.map(option => `
    <div class="answer-option">
      <input type="radio" name="answer" id="answer-${option.id}" value="${option.id}" ${currentSelection === option.id ? 'checked' : ''}>
      <label for="answer-${option.id}">${LivePulse.escapeHtml(option.text)}</label>
    </div>
  `).join('');

  main.innerHTML = `
    <div class="participant-eyebrow">질문 ${question.position}</div>
    <h1>${LivePulse.escapeHtml(question.text)}</h1>
    <div class="${isRating ? 'rating-options' : 'answer-list'}">${optionsHtml}</div>
    ${isRating ? `<div class="rating-labels"><span>${LivePulse.escapeHtml(question.min_label)}</span><span>${LivePulse.escapeHtml(question.max_label)}</span></div>` : ''}
    ${state.my_response ? `<div class="my-answer">현재 답변: ${LivePulse.escapeHtml(selectedOption(question)?.text || '')}</div>` : ''}
  `;
  submitBar.classList.remove('hidden');
  submitButton.textContent = state.my_response ? '답변 변경' : '답변 제출';
  submitButton.disabled = !currentSelection;
  main.querySelectorAll('input[name="answer"]').forEach(input => input.addEventListener('change', event => {
    selectedOptionId = event.target.value;
    submitButton.disabled = false;
  }));
}

function renderClosed(question) {
  const answered = Boolean(state.my_response);
  stateView(
    answered ? '✓' : '–',
    '응답이 마감되었습니다.',
    answered ? '답변이 정상적으로 반영되었습니다. 결과 공개를 기다려 주세요.' : '이번 질문에는 답변이 제출되지 않았습니다.'
  );
}

function renderResult(question) {
  submitBar.classList.add('hidden');
  const answer = selectedOption(question);
  main.innerHTML = `
    <div class="participant-eyebrow">결과</div>
    <h1>${LivePulse.escapeHtml(question.text)}</h1>
    ${LivePulse.renderStats(question, state.stats, { showCount: false })}
    ${answer ? `<div class="my-answer">내가 선택한 답변: ${LivePulse.escapeHtml(answer.text)}</div>` : ''}
    <p style="color:var(--muted);text-align:center;margin-top:22px">다음 질문을 기다려 주세요.</p>
  `;
}

function render() {
  if (!state) return;
  const { event, current_question: question } = state;
  titleNode.textContent = event.title;
  statusNode.textContent = LivePulse.statusText[event.status] || event.status;
  statusNode.className = `status-badge ${event.status}`;
  document.title = `${event.title} · LivePulse`;

  if (event.status === 'ENDED') {
    stateView('♥', '참여해 주셔서 감사합니다.', '행사가 종료되었습니다.');
    return;
  }
  if (event.status === 'DRAFT') {
    stateView('◷', '아직 참가가 열리지 않았습니다.', '진행자가 참가를 시작하면 이 화면이 자동으로 변경됩니다.');
    return;
  }
  if (!question) {
    stateView('✓', '참가가 완료되었습니다.', '질문이 곧 시작됩니다. 화면을 닫지 말고 기다려 주세요.');
    return;
  }
  if (question.status === 'OPEN') return renderQuestion(question);
  if (question.status === 'CLOSED') return renderClosed(question);
  if (question.status === 'REVEALED') return renderResult(question);
  stateView('◷', '다음 질문을 준비하고 있습니다.', '잠시만 기다려 주세요.');
}

async function refreshState() {
  state = await LivePulse.api(`/api/public/events/${eventCode}/state?participant_session_id=${encodeURIComponent(participantId)}`);
  render();
}

function connectRealtime() {
  stopSocket?.();
  stopSocket = LivePulse.openSocket(
    `/ws/events/${eventId}?role=participant&participant_id=${encodeURIComponent(participantId)}`,
    nextState => {
      const previousQuestion = state?.current_question?.id;
      state = nextState;
      if (previousQuestion !== nextState.current_question?.id) {
        showingConfirmation = false;
        selectedOptionId = null;
      }
      render();
    },
    status => document.querySelector('#network-banner').classList.toggle('hidden', status !== 'disconnected')
  );
}

submitButton.addEventListener('click', async () => {
  if (!state?.current_question || !selectedOptionId) return;
  submitButton.disabled = true;
  submitButton.textContent = '제출 중…';
  try {
    await LivePulse.api(`/api/public/questions/${state.current_question.id}/responses`, {
      method: 'POST',
      body: {
        participant_session_id: participantId,
        option_id: selectedOptionId,
        idempotency_key: crypto.randomUUID?.() || String(Date.now())
      }
    });
    showingConfirmation = true;
    await refreshState();
  } catch (error) {
    LivePulse.toast(error.message, 'error');
    try { await refreshState(); } catch (_) {}
  } finally {
    submitButton.disabled = false;
  }
});

async function join() {
  try {
    const result = await LivePulse.api(`/api/public/events/${eventCode}/join`, {
      method: 'POST', body: { participant_session_id: participantId }
    });
    participantId = result.participant_session_id;
    eventId = result.event_id;
    localStorage.setItem(sessionKey, participantId);
    state = result.state;
    render();
    connectRealtime();
  } catch (error) {
    stateView('!', '행사에 참가할 수 없습니다.', error.message, `<button class="btn btn-secondary btn-large" id="retry-join" style="margin-top:20px">다시 시도</button>`);
    document.querySelector('#retry-join')?.addEventListener('click', join);
  }
}

join();
