"use client";
import { useEffect, useState } from "react";
import { safeReturnTo } from "@/lib/navigation";

export function useReturnRoute() {
  const [destination, setDestination] = useState("/dashboard");
  useEffect(() => { setDestination(safeReturnTo(new URLSearchParams(window.location.search).get("next"))); }, []);
  return destination;
}
