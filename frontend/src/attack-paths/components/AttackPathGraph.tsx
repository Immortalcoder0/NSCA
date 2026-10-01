import React, { useMemo } from "react";
import dagre from "dagre";
import { AttackPathNode } from "./AttackPathNode";
import type { AttackPathModel } from "../types";
import { cn } from "../../shared/lib/utils";

interface AttackPathGraphProps {
  path: AttackPathModel;
  selectedNodeId?: string;
  onSelectNode?: (nodeId: string) => void;
  selectedLinkId?: string;
  onSelectLink?: (linkId: string) => void;
  className?: string;
}

interface LayoutNode {
  id: string;
  x: number;
  y: number;
  width: number;
  height: number;
}

interface LayoutEdge {
  id: string;
  source: string;
  target: string;
  points: Array<{ x: number; y: number }>;
}

export const AttackPathGraph: React.FC<AttackPathGraphProps> = ({
  path,
  selectedNodeId,
  onSelectNode,
  selectedLinkId,
  onSelectLink,
  className,
}) => {
  const NODE_WIDTH = 220;
  const NODE_HEIGHT = 80;

  // Compute Dagre Layout deterministically
  const { layoutNodes, layoutEdges, graphWidth, graphHeight } = useMemo(() => {
    const g = new dagre.graphlib.Graph();
    g.setGraph({
      rankdir: "TB", // Top to Bottom chain
      nodesep: 50,
      ranksep: 90,
      marginx: 40,
      marginy: 40,
    });
    g.setDefaultEdgeLabel(() => ({}));

    path.nodes.forEach((n) => {
      g.setNode(n.id, { width: NODE_WIDTH, height: NODE_HEIGHT });
    });

    path.links.forEach((l) => {
      g.setEdge(l.source, l.target);
    });

    dagre.layout(g);

    const nodes: Record<string, LayoutNode> = {};
    path.nodes.forEach((n) => {
      const nodeLayout = g.node(n.id);
      if (nodeLayout) {
        nodes[n.id] = {
          id: n.id,
          x: nodeLayout.x,
          y: nodeLayout.y,
          width: NODE_WIDTH,
          height: NODE_HEIGHT,
        };
      }
    });

    const edges: LayoutEdge[] = path.links.map((l) => {
      const edgeLayout = g.edge(l.source, l.target);
      return {
        id: l.id,
        source: l.source,
        target: l.target,
        points: edgeLayout ? edgeLayout.points : [],
      };
    });

    const graphInfo = g.graph();
    return {
      layoutNodes: nodes,
      layoutEdges: edges,
      graphWidth: Math.max(graphInfo.width || 600, 600),
      graphHeight: Math.max(graphInfo.height || 500, 500),
    };
  }, [path]);

  return (
    <div className={cn("rounded-xl border border-border bg-card/60 p-4 overflow-x-auto shadow-inner", className)}>
      <svg
        width={graphWidth}
        height={graphHeight}
        viewBox={`0 0 ${graphWidth} ${graphHeight}`}
        className="mx-auto block select-none"
      >
        <defs>
          {/* Arrowhead Marker */}
          <marker
            id="arrowhead-red"
            viewBox="0 0 10 10"
            refX="9"
            refY="5"
            markerWidth="7"
            markerHeight="7"
            orient="auto-start-reverse"
          >
            <path d="M 0 1 L 10 5 L 0 9 z" className="fill-red-500" />
          </marker>
          <marker
            id="arrowhead-default"
            viewBox="0 0 10 10"
            refX="9"
            refY="5"
            markerWidth="7"
            markerHeight="7"
            orient="auto-start-reverse"
          >
            <path d="M 0 1 L 10 5 L 0 9 z" className="fill-border" />
          </marker>
        </defs>

        {/* Render Edges */}
        {layoutEdges.map((edge) => {
          const linkData = path.links.find((l) => l.id === edge.id);
          const isLinkSelected = selectedLinkId === edge.id;

          if (!edge.points || edge.points.length < 2) return null;

          const pathD = edge.points.reduce((acc, pt, idx) => {
            return idx === 0 ? `M ${pt.x} ${pt.y}` : `${acc} L ${pt.x} ${pt.y}`;
          }, "");

          const midPoint = edge.points[Math.floor(edge.points.length / 2)];

          return (
            <g key={edge.id} className="cursor-pointer group" onClick={() => onSelectLink?.(edge.id)}>
              {/* Thick hit area for edge click */}
              <path d={pathD} fill="none" stroke="transparent" strokeWidth="20" />
              {/* Rendered Edge */}
              <path
                d={pathD}
                fill="none"
                markerEnd="url(#arrowhead-red)"
                className={cn(
                  "stroke-red-500 stroke-[2] transition-colors stroke-dasharray-[4,4] animate-pulse",
                  isLinkSelected && "stroke-[3] stroke-primary"
                )}
              />

              {/* Edge Finding Label Badge */}
              {linkData && midPoint && (
                <g transform={`translate(${midPoint.x}, ${midPoint.y})`}>
                  <rect
                    x="-75"
                    y="-12"
                    width="150"
                    height="24"
                    rx="6"
                    className="fill-background stroke-red-400 stroke-[1.5] shadow"
                  />
                  <text
                    x="0"
                    y="4"
                    textAnchor="middle"
                    className="fill-red-600 dark:fill-red-400 text-[10px] font-mono font-bold"
                  >
                    {linkData.control_id} ({linkData.protocol || "TCP"}/{linkData.port || 23})
                  </text>
                </g>
              )}
            </g>
          );
        })}

        {/* Render Nodes */}
        {path.nodes.map((node) => {
          const lNode = layoutNodes[node.id];
          if (!lNode) return null;
          return (
            <AttackPathNode
              key={node.id}
              node={node}
              x={lNode.x}
              y={lNode.y}
              width={lNode.width}
              height={lNode.height}
              isSelected={selectedNodeId === node.id}
              onClick={() => onSelectNode?.(node.id)}
            />
          );
        })}
      </svg>
    </div>
  );
};
