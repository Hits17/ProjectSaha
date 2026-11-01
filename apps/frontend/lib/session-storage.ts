/** Browser storage can be blocked or full. Authentication must still work in memory. */
export function resilientSessionStorage(storage: () => Pick<Storage, "getItem" | "setItem" | "removeItem">) {
  const memory = new Map<string, string>();
  return {
    getItem(name: string): string | null {
      try { return storage().getItem(name); } catch { return memory.get(name) ?? null; }
    },
    setItem(name: string, value: string): void {
      memory.set(name, value);
      try { storage().setItem(name, value); } catch { /* This tab retains its session. */ }
    },
    removeItem(name: string): void {
      memory.delete(name);
      try { storage().removeItem(name); } catch { /* No storage access. */ }
    },
  };
}
