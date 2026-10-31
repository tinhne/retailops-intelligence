import { vi } from "vitest";

/**
 * A scriptable XMLHttpRequest for upload tests (jsdom sends no requests). Each `send` registers
 * the request; the test then drives it: upload progress, end of upload, then the answer.
 */
export class FakeXhr {
  static requests: FakeXhr[] = [];

  method = "";
  url = "";
  headers: Record<string, string> = {};
  body: Document | XMLHttpRequestBodyInit | null = null;
  status = 0;
  responseText = "";
  upload: { onprogress: ((event: ProgressEvent) => void) | null; onload: (() => void) | null } = { onprogress: null, onload: null };
  onload: (() => void) | null = null;
  onerror: (() => void) | null = null;
  onabort: (() => void) | null = null;

  open(method: string, url: string) {
    this.method = method;
    this.url = url;
  }

  setRequestHeader(name: string, value: string) {
    this.headers[name] = value;
  }

  getAllResponseHeaders() {
    return "content-type: application/json\r\n";
  }

  send(body: Document | XMLHttpRequestBodyInit | null) {
    this.body = body;
    FakeXhr.requests.push(this);
  }

  abort() {
    this.onabort?.();
  }

  progress(loaded: number, total: number) {
    this.upload.onprogress?.({ lengthComputable: true, loaded, total } as ProgressEvent);
  }

  finishUpload() {
    this.upload.onload?.();
  }

  respond(status: number, body: unknown) {
    this.status = status;
    this.responseText = JSON.stringify(body);
    this.onload?.();
  }

  failNetwork() {
    this.onerror?.();
  }
}

export function mockXhr() {
  FakeXhr.requests = [];
  vi.stubGlobal("XMLHttpRequest", FakeXhr);
  return FakeXhr;
}
