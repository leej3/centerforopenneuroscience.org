class FilterableList {
  constructor(root, config) {
    this.root = root;
    this.config = config;
    this.items = Array.from(root.querySelectorAll(config.itemSelector));
    this.search = "";
    this.filters = Object.fromEntries(config.filters.map((field) => [field, new Set()]));
    this.searchInput = root.querySelector("[data-filter-search]");
    this.count = root.querySelector("[data-filter-count]");
    this.clearButton = root.querySelector("[data-clear-filters]");
    this.buildFilters();
    this.registerEvents();
    this.render();
  }

  values(item, field) {
    if (field === "topic" || field === "author") {
      try {
        return JSON.parse(item.dataset[field] || "[]").map((value) =>
          typeof value === "object"
            ? value.display_label || value.title || value.family_name || value.pid
            : value
        ).filter(Boolean);
      } catch (_error) {
        return [];
      }
    }
    return [item.dataset[field] || "unknown"];
  }

  buildFilters() {
    this.config.filters.forEach((field) => {
      const container = this.root.querySelector(`[data-filter-group="${CSS.escape(field)}"]`);
      if (!container) return;
      const values = new Set();
      this.items.forEach((item) => this.values(item, field).forEach((value) => values.add(String(value))));
      Array.from(values).sort((a, b) => a.localeCompare(b)).forEach((value) => {
        const label = document.createElement("label");
        const input = document.createElement("input");
        input.type = "checkbox";
        input.value = value;
        input.dataset.filterField = field;
        input.addEventListener("change", () => {
          input.checked ? this.filters[field].add(value) : this.filters[field].delete(value);
          this.render();
        });
        label.append(input, document.createTextNode(` ${field === "kind" ? value.split(":").at(-1) : value}`));
        container.append(label);
      });
    });
  }

  registerEvents() {
    this.searchInput?.addEventListener("input", (event) => {
      this.search = event.target.value.trim().toLowerCase();
      this.render();
    });
    this.clearButton?.addEventListener("click", () => {
      this.search = "";
      if (this.searchInput) this.searchInput.value = "";
      Object.values(this.filters).forEach((values) => values.clear());
      this.root.querySelectorAll("[data-filter-field]").forEach((input) => { input.checked = false; });
      this.render();
    });
  }

  matches(item) {
    const matchesFilters = this.config.filters.every((field) => {
      const selected = this.filters[field];
      return selected.size === 0 || this.values(item, field).some((value) => selected.has(String(value)));
    });
    if (!matchesFilters) return false;
    if (!this.search) return true;
    const text = this.config.searchFields.flatMap((field) =>
      field === "title" ? [item.dataset.title || ""] : this.values(item, field)
    ).join(" ").toLowerCase();
    return text.includes(this.search);
  }

  render() {
    let visible = 0;
    this.items.forEach((item) => {
      const show = this.matches(item);
      item.hidden = !show;
      if (show) visible += 1;
    });
    if (this.count) this.count.textContent = `${visible} result${visible === 1 ? "" : "s"}`;
  }
}
