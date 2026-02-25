export async function apiFetch<T>(
  path: string,
  getToken: () => Promise<string | null>,
  options?: RequestInit
): Promise<T> {
  const token = await getToken();
  const res = await fetch(path, {
    ...options,
    headers: {
      "Content-Type": "application/json",
      ...(token ? { Authorization: `Bearer ${token}` } : {}),
      ...options?.headers,
    },
  });

  if (!res.ok) {
    const body = await res.json().catch(() => ({ detail: res.statusText }));
    throw new Error(body.detail || `Request failed: ${res.status}`);
  }

  return res.json();
}

export async function apiUpload<T>(
  path: string,
  getToken: () => Promise<string | null>,
  file: File
): Promise<T> {
  const token = await getToken();
  const formData = new FormData();
  formData.append("file", file);

  const res = await fetch(path, {
    method: "POST",
    headers: {
      ...(token ? { Authorization: `Bearer ${token}` } : {}),
    },
    body: formData,
  });

  if (!res.ok) {
    const body = await res.json().catch(() => ({ detail: res.statusText }));
    throw new Error(body.detail || `Upload failed: ${res.status}`);
  }

  return res.json();
}
