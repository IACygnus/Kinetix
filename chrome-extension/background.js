// SQA Kinetix Pro Recorder — Background Service Worker

const STATIC_EXTENSIONS = [
  '.js', '.css', '.png', '.jpg', '.jpeg', '.gif', '.svg',
  '.woff', '.woff2', '.ico', '.map'
];

const SKIP_SCHEMES = ['chrome-extension://', 'chrome://'];

function shouldSkipUrl(url) {
  for (const scheme of SKIP_SCHEMES) {
    if (url.startsWith(scheme)) return true;
  }
  try {
    const pathname = new URL(url).pathname.toLowerCase();
    for (const ext of STATIC_EXTENSIONS) {
      if (pathname.endsWith(ext)) return true;
    }
  } catch (_) {
    return true;
  }
  return false;
}

function generateUUID() {
  return 'xxxxxxxx-xxxx-4xxx-yxxx-xxxxxxxxxxxx'.replace(/[xy]/g, c => {
    const r = (Math.random() * 16) | 0;
    return (c === 'x' ? r : (r & 0x3) | 0x8).toString(16);
  });
}

// In-memory map of pending requests (requestId -> partial data)
const pendingRequests = new Map();

// Listener references so we can add/remove them
let onBeforeRequestListener = null;
let onBeforeSendHeadersListener = null;
let onCompletedListener = null;
let onErrorOccurredListener = null;

function startListeners() {
  // Capture request body
  onBeforeRequestListener = (details) => {
    if (shouldSkipUrl(details.url)) return;

    let body = null;
    if (details.requestBody) {
      if (details.requestBody.raw && details.requestBody.raw.length > 0) {
        try {
          const decoder = new TextDecoder('utf-8');
          const parts = details.requestBody.raw.map(part => {
            if (part.bytes) return decoder.decode(part.bytes);
            return '';
          });
          body = parts.join('');
        } catch (_) {
          body = '[binary data]';
        }
      } else if (details.requestBody.formData) {
        body = JSON.stringify(details.requestBody.formData);
      }
    }

    pendingRequests.set(details.requestId, {
      url: details.url,
      method: details.method,
      type: details.type,
      timestamp: Date.now(),
      requestBody: body,
      requestHeaders: [],
      tabId: details.tabId
    });
  };

  // Capture request headers
  onBeforeSendHeadersListener = (details) => {
    if (shouldSkipUrl(details.url)) return;
    const pending = pendingRequests.get(details.requestId);
    if (pending && details.requestHeaders) {
      pending.requestHeaders = details.requestHeaders;
    }
  };

  // Capture response on completion
  onCompletedListener = (details) => {
    if (shouldSkipUrl(details.url)) return;
    const pending = pendingRequests.get(details.requestId);
    if (!pending) return;
    pendingRequests.delete(details.requestId);

    const captured = {
      url: pending.url,
      method: pending.method,
      type: pending.type,
      timestamp: pending.timestamp,
      requestBody: pending.requestBody,
      requestHeaders: pending.requestHeaders || [],
      responseStatus: details.statusCode,
      responseHeaders: details.responseHeaders || [],
      duration: Date.now() - pending.timestamp
    };

    // Push to storage
    chrome.storage.local.get({ requests: [] }, (data) => {
      data.requests.push(captured);
      chrome.storage.local.set({ requests: data.requests });
    });
  };

  // Clean up on error
  onErrorOccurredListener = (details) => {
    pendingRequests.delete(details.requestId);
  };

  chrome.webRequest.onBeforeRequest.addListener(
    onBeforeRequestListener,
    { urls: ['<all_urls>'] },
    ['requestBody']
  );

  chrome.webRequest.onBeforeSendHeaders.addListener(
    onBeforeSendHeadersListener,
    { urls: ['<all_urls>'] },
    ['requestHeaders']
  );

  chrome.webRequest.onCompleted.addListener(
    onCompletedListener,
    { urls: ['<all_urls>'] },
    ['responseHeaders']
  );

  chrome.webRequest.onErrorOccurred.addListener(
    onErrorOccurredListener,
    { urls: ['<all_urls>'] }
  );
}

function stopListeners() {
  if (onBeforeRequestListener) {
    chrome.webRequest.onBeforeRequest.removeListener(onBeforeRequestListener);
    onBeforeRequestListener = null;
  }
  if (onBeforeSendHeadersListener) {
    chrome.webRequest.onBeforeSendHeaders.removeListener(onBeforeSendHeadersListener);
    onBeforeSendHeadersListener = null;
  }
  if (onCompletedListener) {
    chrome.webRequest.onCompleted.removeListener(onCompletedListener);
    onCompletedListener = null;
  }
  if (onErrorOccurredListener) {
    chrome.webRequest.onErrorOccurred.removeListener(onErrorOccurredListener);
    onErrorOccurredListener = null;
  }
  pendingRequests.clear();
}

// Message handler
chrome.runtime.onMessage.addListener((message, _sender, sendResponse) => {
  switch (message.action) {
    case 'START_RECORDING': {
      const sessionId = generateUUID();
      chrome.storage.local.set({
        recording: true,
        sessionId: sessionId,
        requests: []
      }, () => {
        startListeners();
        sendResponse({ success: true, sessionId });
      });
      return true; // async
    }

    case 'STOP_RECORDING': {
      stopListeners();
      chrome.storage.local.set({ recording: false }, () => {
        sendResponse({ success: true });
      });
      return true;
    }

    case 'GET_STATUS': {
      chrome.storage.local.get(
        { recording: false, sessionId: null, requests: [], serverUrl: 'http://localhost:8001' },
        (data) => {
          sendResponse({
            recording: data.recording,
            sessionId: data.sessionId,
            requestCount: data.requests.length,
            serverUrl: data.serverUrl
          });
        }
      );
      return true;
    }

    case 'CLEAR_REQUESTS': {
      chrome.storage.local.set({ requests: [], sessionId: null }, () => {
        sendResponse({ success: true });
      });
      return true;
    }

    case 'SET_SERVER_URL': {
      chrome.storage.local.set({ serverUrl: message.serverUrl }, () => {
        sendResponse({ success: true });
      });
      return true;
    }

    case 'PUSH_TO_SERVER': {
      chrome.storage.local.get(
        { requests: [], sessionId: null, serverUrl: 'http://localhost:8001' },
        async (data) => {
          if (!data.requests.length) {
            sendResponse({ success: false, error: 'No requests to push' });
            return;
          }
          const url = `${data.serverUrl}/api/v1/import/chrome/push`;
          try {
            const resp = await fetch(url, {
              method: 'POST',
              headers: { 'Content-Type': 'application/json' },
              credentials: 'include',
              body: JSON.stringify({
                session_id: data.sessionId,
                requests: data.requests
              })
            });
            if (!resp.ok) {
              const text = await resp.text();
              sendResponse({ success: false, error: `Server returned ${resp.status}: ${text}` });
            } else {
              const result = await resp.json();
              sendResponse({ success: true, result });
            }
          } catch (err) {
            sendResponse({ success: false, error: err.message });
          }
        }
      );
      return true;
    }

    default:
      sendResponse({ success: false, error: 'Unknown action' });
  }
});

// Restore recording state on service worker startup
chrome.storage.local.get({ recording: false }, (data) => {
  if (data.recording) {
    startListeners();
  }
});
