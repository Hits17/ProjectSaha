"use client";
import { Button } from "@/components/ui";
export default function ErrorPage({ reset }: { error: Error & { digest?: string }; reset: () => void }) {
  return <div role="alert" className="mx-auto max-w-lg py-20 text-center"><p className="eyebrow">Something went wrong</p><h1 className="mt-4 text-3xl font-semibold">We couldn’t load this page.</h1><p className="mt-4 text-muted">Try again in a moment. Your navigation is still available if you want to continue exploring.</p><div className="mt-7 flex justify-center gap-3"><Button onClick={reset}>Try again</Button><Button href="/" variant="secondary">Back to home</Button></div></div>;
}
