import React from "react";
import { Lock, ShieldAlert, CheckCircle2 } from "lucide-react";
import { cn } from "../../shared/lib/utils";

interface TwoPersonRatificationBannerProps {
  taughtBy: string;
  currentUser: string;
  onRatify?: () => void;
  className?: string;
}

export const TwoPersonRatificationBanner: React.FC<TwoPersonRatificationBannerProps> = ({
  taughtBy,
  currentUser,
  onRatify,
  className,
}) => {
  const isSelfAuthor = taughtBy.toLowerCase() === currentUser.toLowerCase();

  return (
    <div
      className={cn(
        "p-5 rounded-xl border space-y-3 text-xs shadow-sm",
        isSelfAuthor
          ? "border-amber-300 bg-amber-50/80 dark:bg-amber-950/40 dark:border-amber-800 text-amber-950 dark:text-amber-200"
          : "border-emerald-300 bg-emerald-50/80 dark:bg-emerald-950/40 dark:border-emerald-800 text-emerald-950 dark:text-emerald-200",
        className
      )}
    >
      <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-3">
        <div className="space-y-1">
          <div className="flex items-center gap-2 font-bold text-sm">
            {isSelfAuthor ? (
              <Lock size={18} className="text-amber-600 dark:text-amber-400" />
            ) : (
              <ShieldAlert size={18} className="text-emerald-600 dark:text-emerald-400" />
            )}
            <span>Two-Person Custody Gate (DM-6 Separation of Duties)</span>
          </div>

          <p className="text-[11px] leading-relaxed">
            Rulepack was authored/taught by <strong className="font-mono font-bold text-foreground">{taughtBy}</strong>. Current operator:{" "}
            <strong className="font-mono font-bold text-foreground">{currentUser}</strong>.
          </p>
        </div>

        <div>
          {isSelfAuthor ? (
            <div className="px-3 py-1.5 rounded-md bg-amber-200/80 dark:bg-amber-900/60 font-semibold text-amber-900 dark:text-amber-200 text-[11px] border border-amber-300 dark:border-amber-700 flex items-center gap-1.5">
              <Lock size={13} />
              <span>Self-Ratification Blocked</span>
            </div>
          ) : (
            <button
              onClick={onRatify}
              className="flex items-center gap-1.5 px-4 py-2 rounded-md bg-emerald-600 hover:bg-emerald-700 text-white font-bold text-xs transition-colors shadow-sm"
            >
              <CheckCircle2 size={14} />
              <span>Ratify into Certified Rulepack</span>
            </button>
          )}
        </div>
      </div>

      {isSelfAuthor && (
        <p className="text-[11px] italic text-amber-800 dark:text-amber-300 border-t border-amber-200 dark:border-amber-800/80 pt-2">
          Per audit integrity regulations, rule authors are forbidden from ratifying their own grammar proposals. A separate Lead Assessor must review the validation gates and ratify. Switch dev role to test peer ratification.
        </p>
      )}
    </div>
  );
};
