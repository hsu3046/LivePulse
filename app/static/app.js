const LivePulse = (() => {
  const statusText = {
    DRAFT: '준비 중', LOBBY: '참가 접수 중', RUNNING: '진행 중', ENDED: '종료',
    READY: '준비됨', OPEN: '응답 중', CLOSED: '마감', REVEALED: '결과 공개'
  };

  async function api(url, options = {}) {
    const headers = { ...(options.headers || {}) };
    if (options.body && typeof options.body !== 'string') {
      headers['Content-Type'] = 'application/json';
      options.body = JSON.stringify(options.body);
    }
    const response = await fetch(url, { ...options, headers });
    if (!response.ok) {
      let detail = `요청에 실패했습니다. (${response.status})`;
      try {
        const body = await response.json();
        if (body.detail) detail = Array.isArray(body.detail)
          ? body.detail.map(item => item.msg).join('\n')
          : body.detail;
      } catch (_) {}
      throw new Error(detail);
    }
    if (response.status === 204) return null;
    const type = response.headers.get('content-type') || '';
    return type.includes('application/json') ? response.json() : response.text();
  }

  function escapeHtml(value = '') {
    return String(value)
      .replaceAll('&', '&amp;')
      .replaceAll('<', '&lt;')
      .replaceAll('>', '&gt;')
      .replaceAll('"', '&quot;')
      .replaceAll("'", '&#039;');
  }

  function formatDate(value) {
    if (!value) return '';
    return new Intl.DateTimeFormat('ko-KR', {
      year: 'numeric', month: 'short', day: 'numeric', hour: '2-digit', minute: '2-digit'
    }).format(new Date(value));
  }

  function toast(message, type = 'success') {
    const area = document.querySelector('#toast-area') || (() => {
      const node = document.createElement('div');
      node.id = 'toast-area';
      document.body.appendChild(node);
      return node;
    })();
    const item = document.createElement('div');
    item.className = `toast ${type}`;
    item.textContent = message;
    area.appendChild(item);
    setTimeout(() => item.classList.add('show'), 10);
    setTimeout(() => {
      item.classList.remove('show');
      setTimeout(() => item.remove(), 250);
    }, 2800);
  }

  function wsUrl(path) {
    const protocol = location.protocol === 'https:' ? 'wss:' : 'ws:';
    return `${protocol}//${location.host}${path}`;
  }

  function openSocket(path, onState, onStatus) {
    let socket;
    let stopped = false;
    let retry = 700;
    let pingTimer;

    const connect = () => {
      if (stopped) return;
      onStatus?.('connecting');
      socket = new WebSocket(wsUrl(path));
      socket.addEventListener('open', () => {
        retry = 700;
        onStatus?.('connected');
        pingTimer = setInterval(() => {
          if (socket.readyState === WebSocket.OPEN) socket.send('ping');
        }, 20000);
      });
      socket.addEventListener('message', event => {
        try {
          const message = JSON.parse(event.data);
          if (message.type === 'STATE_SNAPSHOT') onState(message.state);
        } catch (error) {
          console.error(error);
        }
      });
      socket.addEventListener('close', () => {
        clearInterval(pingTimer);
        onStatus?.('disconnected');
        if (!stopped) {
          setTimeout(connect, retry);
          retry = Math.min(retry * 1.7, 8000);
        }
      });
      socket.addEventListener('error', () => socket.close());
    };
    connect();
    return () => {
      stopped = true;
      clearInterval(pingTimer);
      socket?.close();
    };
  }

  function bars(stats, { showCount = true, large = false } = {}) {
    if (!stats) return '';
    const max = Math.max(1, ...stats.options.map(item => item.count));
    return `<div class="bars ${large ? 'bars-large' : ''}">${stats.options.map((item, index) => {
      const width = stats.total ? Math.max(item.count ? 3 : 0, item.count / max * 100) : 0;
      return `<div class="bar-row">
        <div class="bar-label"><span>${escapeHtml(item.text)}</span><strong>${item.percentage}%${showCount ? ` · ${item.count}명` : ''}</strong></div>
        <div class="bar-track"><div class="bar-fill palette-${index % 8}" style="width:${width}%"></div></div>
      </div>`;
    }).join('')}</div>`;
  }

  function pie(stats) {
    if (!stats) return '';
    let cursor = 0;
    const segments = stats.options.map((item, index) => {
      const start = cursor;
      cursor += item.percentage;
      return `var(--chart-${index % 8}) ${start}% ${cursor}%`;
    }).join(', ');
    return `<div class="pie-layout">
      <div class="pie" style="background:conic-gradient(${segments || 'var(--surface-3) 0 100%'})">
        <div class="pie-center"><strong>${stats.total}</strong><span>응답</span></div>
      </div>
      <div class="pie-legend">${stats.options.map((item, index) => `
        <div><i class="legend-dot palette-bg-${index % 8}"></i><span>${escapeHtml(item.text)}</span><strong>${item.percentage}% · ${item.count}명</strong></div>`).join('')}
      </div>
    </div>`;
  }

  function renderStats(question, stats, options = {}) {
    if (!question || !stats) return '<div class="empty-state small">아직 응답이 없습니다.</div>';
    const average = question.type === 'RATING' && stats.average !== null
      ? `<div class="average-card"><span>평균 평점</span><strong>${stats.average}</strong><em>/ 5</em></div>` : '';
    const visual = question.chart_type === 'PIE' && question.type === 'SINGLE'
      ? pie(stats)
      : bars(stats, options);
    return `${average}${visual}<div class="stats-total">총 ${stats.total}명 응답</div>`;
  }

  async function copy(text, success = '복사했습니다.') {
    await navigator.clipboard.writeText(text);
    toast(success);
  }

  return { api, escapeHtml, formatDate, toast, statusText, openSocket, renderStats, bars, pie, copy };
})();
