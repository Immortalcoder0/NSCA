import React from "react";
import { Clock } from "lucide-react";
import { cn } from "../../shared/lib/utils";

interface QuestionProgressBarProps {
  currentIndex: number;
  totalCount: number;
  timeRemaining?: string;
  className?: string;
}

export const QuestionProgressBar: React.FC<QuestionProgressBarProps> = ({
  currentIndex,
  totalCount,
  timeRemaining = "6 min remaining",
  className,
}) => {
  return (
    <div className={cn("space-y-2 select-none", className)}>
      <div className="flex items-center justify-between text-xs">
        <span className="font-bold text-foreground font-mono">
          Question {currentIndex} of {totalCount}
        </span>
        <span className="text-muted-foreground flex items-center gap-1 font-mono text-[11px]">
          <Clock size={12} className="text-primary" />
          <span>{timeRemaining}</span>
        </span>
      </div>

      {/* Progress Dots */}
      <div className="flex items-center gap-1.5">
        {Array.from({ length: totalCount }).map((_, idx) => {
          const isCompleted = idx + 1 < currentIndex;
          const isCurrent = idx + 1 === currentIndex;

          return (
            <div
              key={idx}
              className={cn(
                "h-2 flex-1 rounded-full transition-all duration-300",
                isCompleted && "bg-purple-600 dark:bg-purple-500",
                isCurrent && "bg-purple-400 dark:bg-purple-400 animate-pulse",
                !isCompleted && !isCurrent && "bg-secondary"
              )}
            />
          );
        })}
      </div>
    </div>
  );
};
