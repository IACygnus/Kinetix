// SQA Kinetix Pro Recorder — Popup Script

const $ = (id) => document.getElementById(id);

const els = {
  statusBar: $('statusBar'),
  statusDot: $('statusDot'),
  statusText: $('statusText'),
  serverUrl: $('serverUrl'),
  sessionSection: $('sessionSection'),
  sessionId: $('sessionId'),
  requestCount: $('requestCount'),
  toggleBtn: $('toggleBtn'),
  toggleIcon: $('toggleIcon'),
  toggleText: $('toggleText'),
  pushBtn: $('pushBtn'),
  clearBtn: $('clearBtn'),
  message: $('message')
};

let isRecording = false;
let pollInterval = null;

// --- Helpers ---

function sendMsg(action, extra = {}) {
  return new Promise((resolve) => {
    chrome.runtime.sendMessage({ action, ...extra }, resolve);
  });
}

function showMessage(text, type = 'success') {
  els.message.textContent = text;
  els.message.className = 'message ' + type;
  setTimeout(() => {
    els.message.textContent = '';
    els.message.className = 'message';
  }, 4000);
}

function updateUI(status) {
  isRecording = status.recording;

  // Status bar
  if (isRecording) {
    els.statusBar.classList.add('recording');
    els.statusText.textContent = 'Recording...';
    els.toggleBtn.classList.add('is-recording');
    els.toggleIcon.innerHTML = '&#9632;'; // square stop
    els.toggleText.textContent = 'Stop Recording';
  } else {
    els.statusBar.classList.remove('recording');
    els.statusText.textContent = 'Stopped';
    els.toggleBtn.classList.remove('is-recording');
    els.toggleIcon.innerHTML = '&#9679;'; // circle record
    els.toggleText.textContent = 'Start Recording';
  }

  // Session
  if (status.sessionId) {
    els.sessionSection.style.display = 'block';
    els.sessionId.textContent = status.sessionId;
  } else {
    els.sessionSection.style.display = 'none';
    els.sessionId.textContent = '\u2014';
  }

  // Count
  const count = status.requestCount || 0;
  els.requestCount.textContent = count;

  // Server URL
  if (status.serverUrl && !els.serverUrl.dataset.userEdited) {
    els.serverUrl.value = status.serverUrl;
  }

  // Button states
  els.pushBtn.disabled = count === 0 || isRecording;
  els.clearBtn.disabled = count === 0 && !status.sessionId;
  els.serverUrl.disabled = isRecording;
}

async function refreshStatus() {
  const status = await sendMsg('GET_STATUS');
  if (status) updateUI(status);
}

// --- Event Listeners ---

els.toggleBtn.addEventListener('click', async () => {
  els.toggleBtn.disabled = true;
  if (isRecording) {
    const resp = await sendMsg('STOP_RECORDING');
    if (resp && resp.success) {
      showMessage('Recording stopped');
      stopPolling();
    }
  } else {
    // Save server URL before starting
    await sendMsg('SET_SERVER_URL', { serverUrl: els.serverUrl.value.trim() });
    const resp = await sendMsg('START_RECORDING');
    if (resp && resp.success) {
      showMessage('Recording started');
      startPolling();
    }
  }
  await refreshStatus();
  els.toggleBtn.disabled = false;
});

els.pushBtn.addEventListener('click', async () => {
  els.pushBtn.disabled = true;
  els.pushBtn.textContent = 'Pushing...';
  showMessage('');

  const resp = await sendMsg('PUSH_TO_SERVER');
  if (resp && resp.success) {
    showMessage('Pushed successfully!', 'success');
  } else {
    showMessage(resp ? resp.error : 'Push failed', 'error');
  }

  els.pushBtn.textContent = 'Push to Server';
  await refreshStatus();
});

els.clearBtn.addEventListener('click', async () => {
  const resp = await sendMsg('CLEAR_REQUESTS');
  if (resp && resp.success) {
    showMessage('Cleared');
  }
  await refreshStatus();
});

els.serverUrl.addEventListener('input', () => {
  els.serverUrl.dataset.userEdited = 'true';
});

els.serverUrl.addEventListener('change', () => {
  sendMsg('SET_SERVER_URL', { serverUrl: els.serverUrl.value.trim() });
});

// --- Polling for live count during recording ---

function startPolling() {
  stopPolling();
  pollInterval = setInterval(refreshStatus, 1000);
}

function stopPolling() {
  if (pollInterval) {
    clearInterval(pollInterval);
    pollInterval = null;
  }
}

// --- Init ---

(async () => {
  await refreshStatus();
  if (isRecording) startPolling();
})();
