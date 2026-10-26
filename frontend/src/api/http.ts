const API_ROOT = "/api";

export class ApiClientError extends Error {
  constructor(
    message: string,
    readonly status: number,
  ) {
    super(message);
  }
}

export async function requestJson<T>(path: string, options?: RequestInit): Promise<T> {
  const response = await fetch(`${API_ROOT}${path}`, options);
  if (!response.ok) {
    const payload = (await response.json().catch(() => null)) as { detail?: string } | null;
    throw new ApiClientError(payload?.detail ?? `请求失败（${response.status}）`, response.status);
  }
  return (await response.json()) as T;
}

export async function streamNdjson<T>(
  path: string,
  options: RequestInit,
  onPacket: (packet: T) => void,
): Promise<void> {
  const response = await fetch(`${API_ROOT}${path}`, options);
  if (!response.ok || !response.body) {
    const payload = (await response.json().catch(() => null)) as { detail?: string } | null;
    throw new ApiClientError(
      payload?.detail ?? `无法启动流式任务（${response.status}）`,
      response.status,
    );
  }

  const reader = response.body.getReader();
  const decoder = new TextDecoder();
  let buffer = "";
  const consume = (line: string) => {
    if (line.trim()) onPacket(JSON.parse(line) as T);
  };
  while (true) {
    const { value, done } = await reader.read();
    buffer += decoder.decode(value, { stream: !done });
    const lines = buffer.split("\n");
    buffer = lines.pop() ?? "";
    lines.forEach(consume);
    if (done) break;
  }
  consume(buffer);
}
