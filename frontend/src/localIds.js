let fallbackCounter = 0;

export function createLocalId() {
  const cryptoApi = globalThis.crypto;

  if (typeof cryptoApi?.randomUUID === "function") {
    return cryptoApi.randomUUID();
  }

  if (typeof cryptoApi?.getRandomValues === "function") {
    const values = new Uint32Array(4);
    cryptoApi.getRandomValues(values);
    return `local-${Array.from(values, (value) => value.toString(36)).join("-")}`;
  }

  fallbackCounter += 1;
  return `local-${Date.now().toString(36)}-${fallbackCounter.toString(36)}`;
}
