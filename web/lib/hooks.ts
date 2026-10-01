"use client";

import { useCallback, useEffect, useState } from "react";

import { api, ApiError, getSourceCallerToken, SemanticObject } from "./api";
import { useLocale } from "./i18n";

export function useApi<T>(path: string | null) {
  const [data, setData] = useState<T | null>(null);
  const [error, setError] = useState<ApiError | Error | null>(null);
  const [loading, setLoading] = useState(false);
  const { locale } = useLocale();   // refetch in the new language (manifests, messages)

  const reload = useCallback(() => {
    if (!path) return;
    setLoading(true);
    setError(null);
    api<T>(path)
      .then(setData)
      .catch(setError)
      .finally(() => setLoading(false));
  }, [path, locale]);

  useEffect(reload, [reload]);
  return { data, error, loading, reload };
}

const catalogCache = new Map<string, Promise<SemanticObject[]>>();

/** The caller's semantic catalog, fetched once per page load. */
export function useCatalog() {
  const [objects, setObjects] = useState<SemanticObject[]>([]);
  const [error, setError] = useState<Error | null>(null);
  useEffect(() => {
    const callerToken = getSourceCallerToken();
    let request = catalogCache.get(callerToken);
    if (!request) {
      request = api<{ objects: SemanticObject[] }>("/semantic/catalog", { callerToken }).then((c) => c.objects);
      catalogCache.set(callerToken, request);
    }
    request.then(setObjects).catch((e) => {
      catalogCache.delete(callerToken);
      setError(e);
    });
  }, []);
  const byRef = new Map(objects.map((o) => [o.ref, o]));
  return { objects, byRef, error };
}
