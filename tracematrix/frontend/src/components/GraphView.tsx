import cytoscape from "cytoscape";
import { useEffect, useRef } from "react";
import type { GraphPayload } from "../lib/api";

export function GraphView({
  data,
  onSelect,
  highlight,
}: {
  data: GraphPayload;
  onSelect: (payload: Record<string, unknown>) => void;
  highlight: string[];
}) {
  const ref = useRef<HTMLDivElement>(null);
  const cyRef = useRef<cytoscape.Core | null>(null);

  useEffect(() => {
    if (!ref.current) return;
    const nodes = data.nodes.slice(0, 250).map((n) => ({
      data: { id: String(n.address), label: String(n.address).slice(0, 10), ...n },
    }));
    const edges = data.edges.map((e) => ({
      data: { id: String(e.id), source: String(e.source), target: String(e.target), ...e },
    }));
    const cy = cytoscape({
      container: ref.current,
      elements: [...nodes, ...edges],
      style: [
        {
          selector: "node",
          style: {
            label: "data(label)",
            "font-size": "10px",
            "font-family": "Inter, sans-serif",
            "font-weight": "bold",
            "text-wrap": "wrap",
            "text-max-width": "74px",
            "text-valign": "bottom",
            "text-margin-y": 7,
            "text-background-color": "#ffffff",
            "text-background-opacity": 0.92,
            "text-background-padding": "3px",
            "background-color": "#2455d6",
            "border-width": "3px",
            "border-color": "#dbeafe",
            color: "#334155",
            width: "30px",
            height: "30px",
          },
        },
        { selector: "node:active", style: { "overlay-color": "#60a5fa", "overlay-opacity": 0.16 } },
        { selector: "edge", style: { width: 2, opacity: 0.7, "line-color": "#94a3b8", "target-arrow-shape": "triangle", "target-arrow-color": "#94a3b8", "arrow-scale": 0.8, "curve-style": "bezier" } },
        { selector: ".hi", style: { "background-color": "#d97706", "border-color": "#fde68a", "line-color": "#d97706", "target-arrow-color": "#d97706", width: 3 } },
      ],
      layout: { name: "cose", animate: false, padding: 42, nodeRepulsion: 6500, idealEdgeLength: 110 },
      minZoom: 0.25,
      maxZoom: 2.5,
    });
    cy.on("tap", "node", (evt) => onSelect({ kind: "node", ...evt.target.data() }));
    cy.on("tap", "edge", (evt) => onSelect({ kind: "edge", ...evt.target.data() }));
    cyRef.current = cy;
    return () => {
      cy.destroy();
    };
  }, [data, onSelect]);

  useEffect(() => {
    const cy = cyRef.current;
    if (!cy) return;
    cy.elements().removeClass("hi");
    highlight.forEach((id) => cy.$id(id).addClass("hi"));
  }, [highlight]);

  return <div ref={ref} aria-label="Interactive transaction network graph" className="h-[420px] w-full rounded-xl border border-slate-100 bg-[#fbfdff] sm:h-[500px]" />;
}
