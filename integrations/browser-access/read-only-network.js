// Runs before public page scripts in the anonymous research browser. This is
// defense in depth; the MCP tool filter and egress policy remain authoritative.
(() => {
  const blocked = () => { throw new DOMException("Read-only research blocks network writes", "NetworkError"); };
  const readMethod = method => ["GET", "HEAD"].includes(String(method || "GET").toUpperCase());

  const nativeFetch = window.fetch.bind(window);
  Object.defineProperty(window, "fetch", {
    configurable: false,
    writable: false,
    value: (input, init = {}) => {
      let method = init.method;
      if (!method && input && typeof input === "object" && "method" in input) method = input.method;
      return readMethod(method) ? nativeFetch(input, init) : Promise.reject(new DOMException("Read-only research blocks network writes", "NetworkError"));
    },
  });

  const xhrOpen = XMLHttpRequest.prototype.open;
  Object.defineProperty(XMLHttpRequest.prototype, "open", {
    configurable: false,
    writable: false,
    value: function(method, ...args) {
      if (!readMethod(method)) return blocked();
      return xhrOpen.call(this, method, ...args);
    },
  });

  try {
    Object.defineProperty(navigator, "sendBeacon", {configurable: false, value: () => false});
  } catch (_) {}
  for (const name of ["WebSocket", "EventSource"]) {
    try { Object.defineProperty(window, name, {configurable: false, value: blocked}); } catch (_) {}
  }
  for (const name of ["submit", "requestSubmit"]) {
    try { Object.defineProperty(HTMLFormElement.prototype, name, {configurable: false, value: blocked}); } catch (_) {}
  }
  document.addEventListener("submit", event => event.preventDefault(), true);
})();
