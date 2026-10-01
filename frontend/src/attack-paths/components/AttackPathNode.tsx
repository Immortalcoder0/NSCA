import React from "react";
import { Server, Globe, Target } from "lucide-react";
import type { AttackPathNodeModel } from "../types";
import { cn } from "../../shared/lib/utils";

interface AttackPathNodeProps {
  node: AttackPathNodeModel;
  x: number;
  y: number;
  width?: number;
  height?: number;
  isSelected?: boolean;
  onClick?: () => void;
}

export const AttackPathNode: React.FC<AttackPathNodeProps> = ({
  node,
  x,
  y,
  width = 220,
  height = 80,
  isSelected = false,
  onClick,
}) => {
  return (
    <g
      transform={`translate(${x - width / 2}, ${y - height / 2})`}
      onClick={onClick}
      className="cursor-pointer select-none transition-transform hover:scale-[1.02]"
    >
      {/* Node Outer Rect */}
      <rect
        width={width}
        height={height}
        rx={10}
        className={cn(
          "fill-card stroke-border stroke-[1.5]",
          node.is_entry && "stroke-amber-500 fill-amber-50/20 dark:fill-amber-950/20",
          node.is_target && "stroke-red-500 fill-red-50/20 dark:fill-red-950/20",
          isSelected && "stroke-primary stroke-2"
        )}
      />

      {/* Top Banner Tag */}
      {node.is_entry && (
        <g transform="translate(10, -8)">
          <rect width={90} height={18} rx={4} className="fill-amber-600" />
          <text x={45} y={13} textAnchor="middle" className="fill-white text-[10px] font-bold font-mono">
            ENTRY POINT
          </text>
        </g>
      )}

      {node.is_target && (
        <g transform="translate(10, -8)">
          <rect width={90} height={18} rx={4} className="fill-red-600" />
          <text x={45} y={13} textAnchor="middle" className="fill-white text-[10px] font-bold font-mono">
            CORE TARGET
          </text>
        </g>
      )}

      {/* Node Icon */}
      <foreignObject x={12} y={16} width={32} height={32}>
        <div
          className={cn(
            "w-8 h-8 rounded-lg flex items-center justify-center text-white",
            node.is_entry ? "bg-amber-600" : node.is_target ? "bg-red-600" : "bg-primary"
          )}
        >
          {node.is_entry ? (
            <Globe size={16} />
          ) : node.is_target ? (
            <Target size={16} />
          ) : (
            <Server size={16} />
          )}
        </div>
      </foreignObject>

      {/* Node Text */}
      <text x={52} y={32} className="fill-foreground font-mono font-bold text-xs">
        {node.hostname}
      </text>

      <text x={52} y={48} className="fill-muted-foreground font-mono text-[10px]">
        {node.ip} · {node.role}
      </text>

      <text x={52} y={64} className="fill-muted-foreground text-[10px] italic">
        Zone: {node.zone}
      </text>
    </g>
  );
};
