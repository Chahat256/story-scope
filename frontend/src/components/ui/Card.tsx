import { cn } from "@/lib/utils";

interface Props {
  children: React.ReactNode;
  className?: string;
}

export default function Card({ children, className }: Props) {
  return (
    <div
      className={cn(
        "bg-white border border-ink-200 rounded-2xl overflow-hidden",
        className
      )}
    >
      {children}
    </div>
  );
}
