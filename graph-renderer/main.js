/*
 * Adapted from things-graph-renderer at
 * 04f6241e37532fdb03b6f95d2dbe304e7171d504.
 *
 * The graph contract and Graphology/Sigma renderer are retained. Host and data
 * URLs come from the Hugo partial so the same bundle works at a Pages prefix.
 */
import Graph from "graphology";
import forceAtlas2 from "graphology-layout-forceatlas2";
import Sigma from "sigma";

const nodeStyles = {
  dataset: { color: "#33dbff" },
  instrument: { color: "#f08324" },
  objective: { color: "#f7b983" },
  organization: { color: "#2491f0" },
  person: { color: "#24a86c" },
  project: { color: "#8324f0" },
  publication: { color: "#79502d" },
  topic: { color: "#e924f0" }
};

function pruneToImmediateNeighborhood(graph, rootId) {
  if (!rootId || !graph.hasNode(rootId)) return;
  const keep = new Set([rootId]);
  graph.forEachNeighbor(rootId, (neighbor) => keep.add(neighbor));
  graph.forEachNode((node) => {
    if (!keep.has(node)) graph.dropNode(node);
  });
}

function setVisibility(graph, renderer) {
  graph.forEachEdge((edge) => {
    const hidden =
      graph.getNodeAttribute(graph.source(edge), "hidden") ||
      graph.getNodeAttribute(graph.target(edge), "hidden");
    graph.setEdgeAttribute(edge, "hidden", hidden);
  });
  renderer.refresh();
}

function buildControls(host, graph, renderer) {
  const controls = host.querySelector("[data-graph-controls]");
  const types = new Map();
  graph.forEachNode((_node, attributes) => {
    const type = attributes.domainType || "unknown";
    types.set(type, nodeStyles[type]?.color || "#737373");
  });
  [...types].sort(([left], [right]) => left.localeCompare(right)).forEach(([type, color]) => {
    const label = document.createElement("label");
    const input = document.createElement("input");
    const swatch = document.createElement("span");
    input.type = "checkbox";
    input.checked = true;
    swatch.style.cssText = `width:.7rem;height:.7rem;border-radius:50%;background:${color}`;
    label.append(input, swatch, document.createTextNode(type.charAt(0).toUpperCase() + type.slice(1)));
    controls.append(label);
    input.addEventListener("change", () => {
      graph.forEachNode((node, attributes) => {
        if (attributes.domainType === type) {
          graph.setNodeAttribute(node, "hidden", !input.checked);
        }
      });
      setVisibility(graph, renderer);
    });
  });
}

function buildAccessibleLinks(host, graph) {
  const list = host.querySelector("[data-graph-links]");
  if (!list) return;
  list.replaceChildren();
  if (graph.size === 0) {
    const item = document.createElement("li");
    item.textContent = "No relationships are available for this record.";
    list.append(item);
    return;
  }
  graph.forEachEdge((_edge, attributes, source, target) => {
    const item = document.createElement("li");
    const sourceLink = document.createElement("a");
    const targetLink = document.createElement("a");
    sourceLink.textContent = graph.getNodeAttribute(source, "label");
    sourceLink.href = graph.getNodeAttribute(source, "url");
    targetLink.textContent = graph.getNodeAttribute(target, "label");
    targetLink.href = graph.getNodeAttribute(target, "url");
    const connector = attributes.symmetric ? " ↔ " : " → ";
    const relation = (attributes.label || "related to").replaceAll("_", " ");
    item.append(sourceLink, document.createTextNode(` — ${relation}${connector}`), targetLink);
    list.append(item);
  });
}

function labelColor() {
  return document.documentElement.classList.contains("dark") ? "#f5f5f5" : "#171717";
}

async function initialize(host) {
  if (host.dataset.graphReady === "true") return;
  host.dataset.graphReady = "true";
  const status = host.querySelector("[data-graph-status]");
  try {
    const response = await fetch(host.dataset.graphUrl, { credentials: "same-origin" });
    if (!response.ok) throw new Error(`graph request returned ${response.status}`);
    const data = await response.json();
    const graph = new Graph({ type: "directed", multi: true });
    const rootId = host.dataset.rootNode || "";

    data.nodes.forEach((node, index) => {
      const style = nodeStyles[node.type] || { color: "#737373" };
      const angle = (2 * Math.PI * index) / Math.max(data.nodes.length, 1);
      graph.addNode(node.id, {
        label: node.label || node.id,
        size: Math.log(Math.max(Number(node.size) || 1, 1) * 10) + 1,
        color: style.color,
        domainType: node.type || "unknown",
        url: node.url || null,
        root: node.id === rootId,
        x: Math.cos(angle),
        y: Math.sin(angle)
      });
    });
    data.edges.forEach((edge) => {
      graph.addDirectedEdgeWithKey(edge.id, edge.source, edge.target, {
        label: edge.type,
        color: "#71716f88",
        size: 1,
        domainType: edge.type,
        symmetric: edge.symmetric === true
      });
    });
    pruneToImmediateNeighborhood(graph, rootId);
    forceAtlas2.assign(graph, {
      iterations: 250,
      settings: {
        adjustSizes: true,
        barnesHutOptimize: true,
        outboundAttractionDistribution: true,
        strongGravityMode: true
      }
    });

    const container = host.querySelector("[data-graph-canvas]");
    container.replaceChildren();
    container.setAttribute("aria-hidden", "true");
    const renderer = new Sigma(graph, container, {
      renderLabels: true,
      labelColor: { color: labelColor() },
      nodeReducer: (_node, attributes) => ({
        ...attributes,
        size: attributes.size * (attributes.highlight ? 1.6 : 1)
      }),
      edgeReducer: (_edge, attributes) => ({
        ...attributes,
        color: attributes.highlight ? "#ffcc00" : attributes.color,
        size: attributes.size * (attributes.highlight ? 2 : 1)
      })
    });
    buildAccessibleLinks(host, graph);

    const themeObserver = new MutationObserver(() => {
      renderer.setSetting("labelColor", { color: labelColor() });
      renderer.refresh();
    });
    themeObserver.observe(document.documentElement, {
      attributes: true,
      attributeFilter: ["class"]
    });

    renderer.on("clickNode", ({ node }) => {
      const url = graph.getNodeAttribute(node, "url");
      if (url) window.location.assign(url);
    });
    renderer.on("enterNode", ({ node }) => {
      graph.forEachNode((candidate) => {
        graph.setNodeAttribute(candidate, "highlight", candidate === node || graph.areNeighbors(candidate, node));
      });
      graph.forEachEdge((edge, _attributes, source, target) => {
        graph.setEdgeAttribute(edge, "highlight", source === node || target === node);
      });
      renderer.refresh();
    });
    renderer.on("leaveNode", () => {
      graph.forEachNode((node) => graph.removeNodeAttribute(node, "highlight"));
      graph.forEachEdge((edge) => graph.removeEdgeAttribute(edge, "highlight"));
      renderer.refresh();
    });
    buildControls(host, graph, renderer);
  } catch (error) {
    const container = host.querySelector("[data-graph-canvas]");
    if (container) {
      const failure = document.createElement("p");
      failure.className = "metadata-graph-status";
      failure.textContent = "The relationship graph is unavailable in this build.";
      container.replaceChildren(failure);
    } else if (status) {
      status.textContent = "The relationship graph is unavailable in this build.";
    }
    const links = host.querySelector("[data-graph-links]");
    if (links) {
      const failure = document.createElement("li");
      failure.textContent = "Relationship links are unavailable in this build.";
      links.replaceChildren(failure);
    }
    console.warn("Unable to load metadata graph", error);
  }
}

document.querySelectorAll(".metadata-graph").forEach(initialize);
