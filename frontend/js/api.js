/**
 * API Client — centralized fetch wrapper for all backend endpoints.
 *
 * Configurable BASE_URL, error handling, and streaming support.
 */

class ApiClient {
  constructor() {
    // If loaded over HTTP/S (e.g. from Docker/Server), use the current host/port origin.
    // Fall back to http://localhost:8000 if opened directly from local disk (file:// protocol).
    const isLocalFile = window.location.protocol === 'file:';
    const serverUrl = 'http://localhost:8000';
    this.baseUrl = (isLocalFile ? serverUrl : window.location.origin).replace(/\/+$/, '');
  }

  // ── Internal helpers ──────────────────────────────────────────────

  async _request(method, path, { body, headers = {}, timeout = 60000 } = {}) {
    const url = `${this.baseUrl}${path}`;
    const controller = new AbortController();
    const timer = setTimeout(() => controller.abort(), timeout);

    const opts = {
      method,
      headers: { ...headers },
      signal: controller.signal,
    };

    if (body instanceof FormData) {
      opts.body = body;
      // Don't set Content-Type — browser sets multipart boundary automatically
    } else if (body) {
      opts.headers['Content-Type'] = 'application/json';
      opts.body = JSON.stringify(body);
    }

    try {
      const response = await fetch(url, opts);
      clearTimeout(timer);

      if (!response.ok) {
        const errorData = await response.json().catch(() => ({}));
        const message = errorData.detail || `HTTP ${response.status}: ${response.statusText}`;
        if (message === 'UNMOUNTED') {
          document.dispatchEvent(new CustomEvent('unmounted-state'));
        }
        throw new ApiError(message, response.status);
      }

      return await response.json();
    } catch (err) {
      clearTimeout(timer);
      if (err instanceof ApiError) throw err;
      if (err.name === 'AbortError') {
        throw new ApiError('Request timed out', 408);
      }
      throw new ApiError(`Network error: ${err.message}`, 0);
    }
  }

  // ── Health ────────────────────────────────────────────────────────

  async getHealth() {
    return this._request('GET', '/health');
  }

  // ── Ingestion ─────────────────────────────────────────────────────

  async ingestManual(file) {
    const formData = new FormData();
    formData.append('file', file);
    return this._request('POST', '/ingest', {
      body: formData,
      timeout: 600000, // 10 minutes — ingestion can be slow
    });
  }

  async listManuals() {
    return this._request('GET', '/ingest/manuals');
  }

  async deleteManual(manualId) {
    return this._request('DELETE', `/ingest/manuals/${encodeURIComponent(manualId)}`);
  }

  // ── Config / Dynamic Mount ─────────────────────────────────────────

  async getMountConfig() {
    return this._request('GET', '/config/mount');
  }

  async mountDataDirectory(path) {
    return this._request('POST', '/config/mount', { body: { path } });
  }

  // ── Query ─────────────────────────────────────────────────────────

  async query(request) {
    return this._request('POST', '/query', { body: request, timeout: 120000 });
  }

  /**
   * Streaming query via SSE — reads the /query/stream endpoint
   * and dispatches typed events to callbacks.
   *
   * Events:
   *   - sources: array of source references (arrives first)
   *   - token:   a text chunk from the LLM
   *   - done:    object with processing_time_seconds
   *
   * @param {Object}   request          - { query, manual_filter?, top_k? }
   * @param {Function} onSources        - Called with array of source objects
   * @param {Function} onToken          - Called with each text chunk
   * @param {Function} onDone           - Called with { processing_time_seconds }
   * @param {Function} [onError]        - Called on error
   * @param {AbortSignal} [signal]      - Optional abort signal
   */
  async queryStream(request, onSources, onToken, onDone, onError, signal) {
    const url = `${this.baseUrl}/query/stream`;

    try {
      const response = await fetch(url, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(request),
        signal,
      });

      if (!response.ok) {
        const errorData = await response.json().catch(() => ({}));
        const message = errorData.detail || `HTTP ${response.status}`;
        if (message === 'UNMOUNTED') {
          document.dispatchEvent(new CustomEvent('unmounted-state'));
        }
        throw new ApiError(message, response.status);
      }

      const reader = response.body.getReader();
      const decoder = new TextDecoder();

      let buffer = '';
      let currentEvent = '';
      let currentData = '';

      console.log('SSE Stream: Starting reader loop');

      while (true) {
        const { done, value } = await reader.read();
        if (done) {
          console.log('SSE Stream: Reader complete (done=true)');
          break;
        }

        const chunk = decoder.decode(value, { stream: true });
        console.log(`SSE Stream: Received chunk of size ${value.length} bytes`);
        buffer += chunk;

        // Process complete lines from the buffer
        const lines = buffer.split('\n');
        // Keep the last (potentially incomplete) line in the buffer
        buffer = lines.pop() || '';

        console.log(`SSE Stream: Processing ${lines.length} lines from buffer. Remaining buffer size: ${buffer.length}`);

        for (const line of lines) {
          const cleanLine = line.replace(/\r$/, '');
          console.log(`SSE Stream: Parsing line: "${cleanLine}"`);
          if (cleanLine.startsWith('event: ')) {
            currentEvent = cleanLine.slice(7).trim();
            currentData = '';
            console.log(`SSE Stream: Set currentEvent to "${currentEvent}"`);
          } else if (cleanLine.startsWith('data:')) {
            // SSE data line — 'data: payload' or bare 'data:'
            const payload = cleanLine.length > 5 ? cleanLine.slice(cleanLine.charAt(5) === ' ' ? 6 : 5) : '';
            currentData += (currentData ? '\n' : '') + payload;
            console.log(`SSE Stream: Appended to currentData. New length: ${currentData.length}`);
          } else if (cleanLine === '') {
            // Empty line = end of event — dispatch
            if (currentEvent) {
              console.log(`SSE Stream: Dispatching event "${currentEvent}" with ${currentData.length} chars of data`);
              try {
                this._dispatchSSE(currentEvent, currentData, onSources, onToken, onDone);
              } catch (e) {
                console.error('Error dispatching SSE event:', currentEvent, e);
              }
            } else {
              console.log('SSE Stream: Empty line but no currentEvent set');
            }
            currentEvent = '';
            currentData = '';
          }
        }
      }

      // Process any remaining data in buffer
      if (currentEvent && currentData !== '') {
        console.log(`SSE Stream: Final dispatch of event "${currentEvent}" with ${currentData.length} chars of data`);
        this._dispatchSSE(currentEvent, currentData, onSources, onToken, onDone);
      }

    } catch (err) {
      console.error('SSE Stream: Error in reader loop:', err);
      if (err.name === 'AbortError') return;
      const apiErr = err instanceof ApiError ? err : new ApiError(err.message, 0);
      if (onError) onError(apiErr);
      else throw apiErr;
    }
  }

  /**
   * Dispatch a parsed SSE event to the appropriate callback.
   */
  _dispatchSSE(event, data, onSources, onToken, onDone) {
    switch (event) {
      case 'sources':
        try {
          const parsed = JSON.parse(data);
          const sources = Array.isArray(parsed) ? parsed : [];
          if (onSources && sources.length > 0) onSources(sources);
        } catch (e) {
          console.error("Error parsing sources JSON:", e, data);
        }
        break;
      case 'token':
        if (onToken) onToken(data);
        break;
      case 'done':
        try {
          const doneData = JSON.parse(data);
          if (onDone) onDone(doneData);
        } catch (e) {
          console.error("Error parsing done JSON:", e, data);
          if (onDone) onDone({});
        }
        break;
    }
  }
}

class ApiError extends Error {
  constructor(message, status) {
    super(message);
    this.name = 'ApiError';
    this.status = status;
  }
}

// Singleton export
const api = new ApiClient();
