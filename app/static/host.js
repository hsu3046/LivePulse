const eventList = document.querySelector('#event-list');
const modal = document.querySelector('#create-modal');
const form = document.querySelector('#create-event-form');
const submitButton = document.querySelector('#submit-create');

function openModal() {
  modal.classList.remove('hidden');
  setTimeout(() => document.querySelector('#event-title').focus(), 20);
}
function closeModal() {
  modal.classList.add('hidden');
  form.reset();
}

document.querySelector('#new-event-button').addEventListener('click', openModal);
document.querySelector('#new-event-button-main').addEventListener('click', openModal);
document.querySelector('#cancel-create').addEventListener('click', closeModal);
modal.addEventListener('click', event => { if (event.target === modal) closeModal(); });
document.addEventListener('keydown', event => { if (event.key === 'Escape') closeModal(); });

function renderEvents(events) {
  if (!events.length) {
    eventList.className = 'card';
    eventList.innerHTML = `<div class="empty-state">
      <div class="empty-icon">✦</div>
      <h2>아직 생성한 행사가 없습니다.</h2>
      <p>첫 행사를 만들고 QR코드를 통한 실시간 참여를 시작해 보세요.</p>
      <button class="btn btn-primary btn-large" style="margin-top:20px" id="empty-create">새 행사 만들기</button>
    </div>`;
    document.querySelector('#empty-create').addEventListener('click', openModal);
    return;
  }
  eventList.className = 'event-grid';
  eventList.innerHTML = events.map(event => `
    <article class="card event-card">
      <span class="status-badge ${event.status}"><i class="status-dot"></i>${LivePulse.statusText[event.status]}</span>
      <h2>${LivePulse.escapeHtml(event.title)}</h2>
      <p>${LivePulse.escapeHtml(event.description || '설명이 없습니다.')}</p>
      <div class="event-meta">
        <span>질문 ${event.question_count}개</span>
        <span>참가자 ${event.participant_count}명</span>
        <span>응답 ${event.response_count}건</span>
      </div>
      <div class="event-actions">
        <small>${LivePulse.formatDate(event.updated_at)} 수정</small>
        <a class="btn btn-primary" href="/host/${event.id}">${event.status === 'ENDED' ? '결과 보기' : '관리하기'} →</a>
      </div>
    </article>
  `).join('');
}

async function loadEvents() {
  eventList.innerHTML = '<div class="card empty-state">행사 목록을 불러오는 중입니다…</div>';
  try {
    renderEvents(await LivePulse.api('/api/events'));
  } catch (error) {
    eventList.className = 'card';
    eventList.innerHTML = `<div class="empty-state"><h2>목록을 불러오지 못했습니다.</h2><p>${LivePulse.escapeHtml(error.message)}</p><button class="btn btn-secondary" id="retry-events" style="margin-top:16px">다시 시도</button></div>`;
    document.querySelector('#retry-events').addEventListener('click', loadEvents);
  }
}

form.addEventListener('submit', async event => {
  event.preventDefault();
  submitButton.disabled = true;
  submitButton.textContent = '만드는 중…';
  try {
    const data = new FormData(form);
    const created = await LivePulse.api('/api/events', {
      method: 'POST',
      body: { title: data.get('title'), description: data.get('description') }
    });
    location.href = `/host/${created.id}`;
  } catch (error) {
    LivePulse.toast(error.message, 'error');
  } finally {
    submitButton.disabled = false;
    submitButton.textContent = '행사 만들기';
  }
});

loadEvents();
