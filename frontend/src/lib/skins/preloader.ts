const _cache = new Map<string, Promise<HTMLImageElement>>();

export function preloadImage(
  url: string,
  timeoutMs = 5000,
): Promise<HTMLImageElement> {
  if (_cache.has(url)) return _cache.get(url)!;

  const p = new Promise<HTMLImageElement>((resolve, reject) => {
    const img = new Image();
    img.crossOrigin = "anonymous";

    const fail = (reason: Error) => {
      _cache.delete(url); // remove on failure so the next call can retry
      reject(reason);
    };

    const timer = setTimeout(
      () => fail(new Error(`preloadImage timeout: ${url}`)),
      timeoutMs,
    );

    img.onload = () => {
      clearTimeout(timer);
      resolve(img);
    };
    img.onerror = () => {
      clearTimeout(timer);
      fail(new Error(`preloadImage failed: ${url}`));
    };

    img.src = url;
  });

  _cache.set(url, p);
  return p;
}

export function _clearCacheForTesting(): void {
  _cache.clear();
}
