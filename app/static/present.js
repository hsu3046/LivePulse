const presentationToken = location.pathname.split('/').filter(Boolean).at(-1);
let state = null;
let eventId = null;
const main = document.querySelector('#presentation-main');
const title = document.querySelector('#presentation-title');
const count = document.querySelector('#presentation-count');

function centerContent(heading, paragraph = '') {
  return `<div class="presentation-content center"><h2>${LivePulse.escapeHtml(heading)}</h2>${paragraph ? `<p>${LivePulse.escapeHtml(paragraph)}</p>` : ''}</div>`;
}

function renderLobby() {
  const event = state.event;
  main.innerHTML = `<div class="presentation-content lobby-layout">
    <div class="qr-card"><img src="/api/events/${event.id}/qr.png" alt="참가 QR코드"></div>
    <div class="lobby-copy">
      <p>휴대전화 카메라로 QR코드를 스캔하세요</p>
      <h1 style="margin-bottom:16px">${LivePulse.escapeHtml(event.title)}</h1>
      <div class="event-code">${LivePulse.escapeHtml(event.code)}</div>
      <p>행사 코드로도 참여할 수 있습니다.</p>
    </div>
  </div>`;
}

function renderQuestion() {
  const question = state.current_question;
  if (!question) {
    main.innerHTML = centerContent('질문을 준비하고 있습니다.', '잠시만 기다려 주세요.');
    return;
  }
  const options = question.options.map((option, index) => `<div class="presentation-option"><b>${index + 1}</b><span>${LivePulse.escapeHtml(option.text)}</span></div>`).join('');
  main.innerHTML = `<div class="presentation-content">
    <p style="color:#aaa0ff;font-weight:800;margin-bottom:14px">질문 ${question.position}</p>
    <h1>${LivePulse.escapeHtml(question.text)}</h1>
    <div class="presentation-options">${options}</div>
  </div>`;
}

function renderResult() {
  const question = state.current_question;
  if (!question || !state.stats) {
    main.innerHTML = centerContent('아직 공개할 결과가 없습니다.');
    return;
  }
  main.innerHTML = `<div class="presentation-content">
    <h1 style="font-size:clamp(32px,4vw,62px);margin-bottom:clamp(28px,4vw,52px)">${LivePulse.escapeHtml(question.text)}</h1>
    ${LivePulse.renderStats(question, state.stats, { large: true })}
  </div>`;
}

function render() {
  if (!state) return;
  const { event, counts } = state;
  title.textContent = event.title;
  document.title = `${event.title} · 발표 화면`;
  const responseCount = state.current_response_count || 0;
  count.textContent = event.display_mode === 'QUESTION' || event.display_mode === 'QUESTION_CLOSED'
    ? `현재 ${responseCount}명 응답`
    : `현재 참가자 ${counts.participants_connected}명`;

  if (event.status === 'ENDED' || event.display_mode === 'ENDED') {
    main.innerHTML = centerContent('참여해 주셔서 감사합니다.', `${counts.participants_total}명이 함께했습니다.`);
    return;
  }
  switch (event.display_mode) {
    case 'LOBBY': renderLobby(); break;
    case 'WAITING': main.innerHTML = centerContent('다음 질문을 준비하고 있습니다.', '잠시만 기다려 주세요.'); break;
    case 'QUESTION': renderQuestion(); break;
    case 'QUESTION_CLOSED': main.innerHTML = centerContent('응답이 마감되었습니다.', `총 ${responseCount}명이 응답했습니다.`); break;
    case 'RESULT': renderResult(); break;
    default: renderLobby();
  }
}

async function start() {
  try {
    state = await LivePulse.api(`/api/presentation/${presentationToken}/state`);
    eventId = state.event.id;
    render();
    LivePulse.openSocket(
      `/ws/events/${eventId}?role=presentation&presentation_token=${encodeURIComponent(presentationToken)}`,
      nextState => { state = nextState; render(); },
      status => {
        if (status === 'disconnected') count.textContent = '재연결 중…';
      }
    );
  } catch (error) {
    main.innerHTML = centerContent('발표 화면을 열 수 없습니다.', error.message);
  }
}

start();
