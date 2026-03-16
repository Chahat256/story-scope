import { cn } from "@/lib/utils";

interface Props {
  children: React.ReactNode;
  className?: string;
  variant?: "default" | "outline";
}

export default function Badge({ children, className, variant = "default" }: Props) {
  return (
    <span
      className={cn(
        "inline-flex items-center text-xs font-medium px-2.5 py-1 rounded-full border",
        variant === "default" ? "bg-ink-100 text-ink-700 border-ink-200" : "bg-transparent border-ink-300 text-ink-600",
        className
      )}
    >
      {children}
    </span>
  );
}
