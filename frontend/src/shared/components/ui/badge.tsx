import * as React from "react";
import { cva, type VariantProps } from "class-variance-authority";
import { cn } from "../../lib/utils";

const badgeVariants = cva(
  "inline-flex items-center rounded-full px-2.5 py-0.5 text-xs font-semibold transition-colors focus:outline-none focus:ring-1 focus:ring-ring select-none",
  {
    variants: {
      variant: {
        default:
          "bg-[#0a0a0a] text-white dark:bg-white dark:text-[#0a0a0a] shadow-sm",
        secondary:
          "border border-border bg-[#f7f8fa] dark:bg-neutral-800 text-foreground",
        destructive:
          "bg-destructive text-destructive-foreground shadow-sm",
        outline: "text-foreground border border-border",
        // MiniMax Specific Badges from DESIGN.md
        success: "bg-[#e8ffea] text-[#1ba673] font-bold border border-[#c4f2c9]",
        new: "bg-[#ff5530] text-white font-bold shadow-sm",
        beta: "bg-[#bfdbfe] text-[#1d4ed8] font-bold",
        code: "bg-[#f2f3f5] dark:bg-neutral-800 text-[#17437d] dark:text-blue-300 font-mono rounded-sm px-1.5 py-0.5",
      },
    },
    defaultVariants: {
      variant: "default",
    },
  }
);

export interface BadgeProps
  extends React.HTMLAttributes<HTMLDivElement>,
    VariantProps<typeof badgeVariants> {}

function Badge({ className, variant, ...props }: BadgeProps) {
  return (
    <div className={cn(badgeVariants({ variant }), className)} {...props} />
  );
}

export { Badge, badgeVariants };
