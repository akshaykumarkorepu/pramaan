import { Skeleton } from "@/components/ui/skeleton";
import { cn } from "@/lib/utils";

/** shadcn Skeleton with a travelling highlight. */
export function ShimmerSkeleton({ className }: { className?: string }) {
  return (
    <Skeleton className={cn("relative overflow-hidden bg-slate-200/70", className)}>
      <span className="absolute inset-0 -translate-x-full bg-gradient-to-r from-transparent via-white/70 to-transparent motion-safe:animate-shimmer" />
    </Skeleton>
  );
}
