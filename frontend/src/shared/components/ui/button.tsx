import * as React from "react";
import { Slot } from "@radix-ui/react-slot";
import { cva, type VariantProps } from "class-variance-authority";
import { cn } from "../../lib/utils";

const buttonVariants = cva(
  "inline-flex items-center justify-center whitespace-nowrap text-sm font-semibold transition-all focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring disabled:pointer-events-none disabled:opacity-50 select-none active:scale-[0.98]",
  {
    variants: {
      variant: {
        default:
          "bg-[#0a0a0a] text-white dark:bg-white dark:text-[#0a0a0a] shadow-sm hover:bg-[#222222] dark:hover:bg-neutral-200 rounded-full",
        secondary:
          "bg-transparent text-foreground border border-foreground hover:bg-secondary rounded-full",
        tertiary:
          "bg-card text-foreground border border-border hover:bg-secondary rounded-full",
        outline:
          "border border-border bg-background hover:bg-secondary hover:text-foreground rounded-full",
        destructive:
          "bg-destructive text-destructive-foreground hover:bg-destructive/90 rounded-full",
        ghost: "hover:bg-secondary hover:text-foreground rounded-full",
        link: "text-foreground underline-offset-4 hover:underline p-0 h-auto font-medium",
        // MiniMax Brand Variants from DESIGN.md
        coral: "bg-[#ff5530] text-white hover:opacity-90 rounded-full shadow-sm",
        blue: "bg-[#1456f0] text-white hover:opacity-90 rounded-full shadow-sm",
        magenta: "bg-[#ea5ec1] text-white hover:opacity-90 rounded-full shadow-sm",
        purple: "bg-[#a855f7] text-white hover:opacity-90 rounded-full shadow-sm",
      },
      size: {
        default: "h-10 px-5 text-sm",
        sm: "h-8 px-3.5 text-xs",
        lg: "h-12 px-7 text-base font-bold",
        icon: "h-9 w-9 rounded-full",
      },
    },
    defaultVariants: {
      variant: "default",
      size: "default",
    },
  }
);

export interface ButtonProps
  extends React.ButtonHTMLAttributes<HTMLButtonElement>,
    VariantProps<typeof buttonVariants> {
  asChild?: boolean;
}

const Button = React.forwardRef<HTMLButtonElement, ButtonProps>(
  ({ className, variant, size, asChild = false, ...props }, ref) => {
    const Comp = asChild ? Slot : "button";
    return (
      <Comp
        className={cn(buttonVariants({ variant, size, className }))}
        ref={ref}
        {...props}
      />
    );
  }
);
Button.displayName = "Button";

export { Button, buttonVariants };
