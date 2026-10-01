import * as React from "react";
import { cn } from "../../lib/utils";

const Card = React.forwardRef<
  HTMLDivElement,
  React.HTMLAttributes<HTMLDivElement> & {
    variant?: "default" | "feature" | "coral" | "blue" | "purple" | "magenta" | "hero";
  }
>(({ className, variant = "default", ...props }, ref) => {
  const variantStyles = {
    default: "bg-card text-card-foreground border border-border rounded-2xl",
    feature: "bg-[#f7f8fa] dark:bg-neutral-900 text-foreground border border-border rounded-2xl",
    hero: "bg-[#0a0a0a] text-white rounded-[32px] p-8",
    coral: "bg-gradient-to-br from-[#ff5530] to-[#e03d19] text-white rounded-[32px] p-8 shadow-sm",
    blue: "bg-gradient-to-br from-[#1456f0] to-[#0e3eb8] text-white rounded-[32px] p-8 shadow-sm",
    purple: "bg-gradient-to-br from-[#a855f7] to-[#802cc9] text-white rounded-[32px] p-8 shadow-sm",
    magenta: "bg-gradient-to-br from-[#ea5ec1] to-[#c23b9b] text-white rounded-[32px] p-8 shadow-sm",
  };

  return (
    <div
      ref={ref}
      className={cn(
        "transition-all duration-200",
        variantStyles[variant],
        className
      )}
      {...props}
    />
  );
});
Card.displayName = "Card";

const CardHeader = React.forwardRef<
  HTMLDivElement,
  React.HTMLAttributes<HTMLDivElement>
>(({ className, ...props }, ref) => (
  <div
    ref={ref}
    className={cn("flex flex-col space-y-1.5 p-6", className)}
    {...props}
  />
));
CardHeader.displayName = "CardHeader";

const CardTitle = React.forwardRef<
  HTMLHeadingElement,
  React.HTMLAttributes<HTMLHeadingElement>
>(({ className, ...props }, ref) => (
  <h3
    ref={ref}
    className={cn("font-bold text-lg leading-tight tracking-tight", className)}
    {...props}
  />
));
CardTitle.displayName = "CardTitle";

const CardDescription = React.forwardRef<
  HTMLParagraphElement,
  React.HTMLAttributes<HTMLParagraphElement>
>(({ className, ...props }, ref) => (
  <p
    ref={ref}
    className={cn("text-xs text-muted-foreground leading-relaxed", className)}
    {...props}
  />
));
CardDescription.displayName = "CardDescription";

const CardContent = React.forwardRef<
  HTMLDivElement,
  React.HTMLAttributes<HTMLDivElement>
>(({ className, ...props }, ref) => (
  <div ref={ref} className={cn("p-6 pt-0", className)} {...props} />
));
CardContent.displayName = "CardContent";

const CardFooter = React.forwardRef<
  HTMLDivElement,
  React.HTMLAttributes<HTMLDivElement>
>(({ className, ...props }, ref) => (
  <div
    ref={ref}
    className={cn("flex items-center p-6 pt-0", className)}
    {...props}
  />
));
CardFooter.displayName = "CardFooter";

export { Card, CardHeader, CardFooter, CardTitle, CardDescription, CardContent };
