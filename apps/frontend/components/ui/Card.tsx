import type { HTMLAttributes } from "react";
import Link from "next/link";
import { cn } from "./cn";

export function Card({ className, ...props }: HTMLAttributes<HTMLDivElement>) {
  return (
    <div
      className={cn("bg-surface border border-line rounded-xl shadow-sm", className)}
      {...props}
    />
  );
}

/** A card that is a whole clickable link (lists of listings, proposals, etc.). */
export function CardLink({
  href,
  className,
  ...props
}: { href: string } & HTMLAttributes<HTMLAnchorElement>) {
  return (
    <Link
      href={href}
      className={cn(
        "block bg-surface border border-line rounded-xl shadow-sm p-5",
        "transition-all hover:border-line-strong hover:shadow-md",
        className,
      )}
      {...props}
    />
  );
}

export function CardHeader({ className, ...props }: HTMLAttributes<HTMLDivElement>) {
  return <div className={cn("px-5 pt-5 pb-3", className)} {...props} />;
}

export function CardTitle({ className, ...props }: HTMLAttributes<HTMLHeadingElement>) {
  return <h3 className={cn("text-base font-semibold text-ink", className)} {...props} />;
}

export function CardBody({ className, ...props }: HTMLAttributes<HTMLDivElement>) {
  return <div className={cn("px-5 pb-5", className)} {...props} />;
}
