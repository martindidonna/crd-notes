export class ApiError extends Error {
  constructor(
    message: string,
    public readonly detail?: unknown
  ) {
    super(message);
    this.name = "ApiError";
  }
}

export async function api<T>(path: string, options: RequestInit = {}): Promise<T> {
  const response = await fetch(path, options);
  if (!response.ok) {
    const data = await response.json().catch(() => ({}));
    throw new ApiError(apiErrorMessage(data), data.detail);
  }
  if (response.status === 204) {
    return undefined as T;
  }
  return (await response.json()) as T;
}

function apiErrorMessage(data: unknown): string {
  if (!data || typeof data !== "object") {
    return "Richiesta non riuscita.";
  }
  const record = data as Record<string, unknown>;
  if (typeof record.message === "string" && record.message.trim()) {
    return record.message;
  }
  if (typeof record.detail === "string" && record.detail.trim()) {
    return record.detail;
  }
  if (Array.isArray(record.detail)) {
    return record.detail
      .map((item) => {
        if (typeof item === "string") return item;
        if (!item || typeof item !== "object") return JSON.stringify(item);
        const detail = item as Record<string, unknown>;
        const loc = Array.isArray(detail.loc) ? detail.loc.join(".") : "";
        const message = detail.msg || detail.message || JSON.stringify(detail);
        return [loc, message].filter(Boolean).join(": ");
      })
      .join("; ");
  }
  return "Richiesta non riuscita.";
}
