"""Inter-page context accumulator — tracks variables, sections, conventions."""

from dataclasses import dataclass, field


@dataclass
class DocumentContext:
    """Accumulated context passed to Claude for inter-page coherence."""

    document_title: str = ""
    current_chapter: str = ""
    current_section: str = ""
    chapter_number: int = 0
    variables: dict[str, str] = field(default_factory=dict)
    notation_conventions: list[str] = field(default_factory=list)
    defined_labels: list[str] = field(default_factory=list)
    page_number: int = 0

    def to_yaml_block(self) -> str:
        """Serialize context to a YAML block for inclusion in prompts."""
        lines = ["---", "# Document context (accumulated from previous pages)"]
        if self.document_title:
            lines.append(f"document_title: \"{self.document_title}\"")
        if self.chapter_number:
            lines.append(f"chapter_number: {self.chapter_number}")
        if self.current_chapter:
            lines.append(f"current_chapter: \"{self.current_chapter}\"")
        if self.current_section:
            lines.append(f"current_section: \"{self.current_section}\"")
        if self.variables:
            lines.append("variables:")
            for var, desc in self.variables.items():
                lines.append(f"  {var}: \"{desc}\"")
        if self.notation_conventions:
            lines.append("notation_conventions:")
            for conv in self.notation_conventions:
                lines.append(f"  - \"{conv}\"")
        if self.defined_labels:
            lines.append("defined_labels:")
            for label in self.defined_labels:
                lines.append(f"  - \"{label}\"")
        lines.append(f"page_number: {self.page_number}")
        lines.append("---")
        return "\n".join(lines)

    def update_from_claude_response(self, context_block: str) -> None:
        """Parse context updates returned by Claude and merge them."""
        import yaml

        try:
            data = yaml.safe_load(context_block)
            if not isinstance(data, dict):
                return
        except yaml.YAMLError:
            return

        if "document_title" in data and data["document_title"]:
            self.document_title = data["document_title"]
        if "chapter_number" in data and data["chapter_number"]:
            try:
                self.chapter_number = int(data["chapter_number"])
            except (ValueError, TypeError):
                pass
        if "chapter_title" in data and data["chapter_title"]:
            self.current_chapter = data["chapter_title"]
        if "current_chapter" in data and data["current_chapter"]:
            self.current_chapter = data["current_chapter"]
        if "current_section" in data and data["current_section"]:
            self.current_section = data["current_section"]
        if "variables" in data and isinstance(data["variables"], dict):
            self.variables.update(data["variables"])
        if "new_variables" in data and isinstance(data["new_variables"], dict):
            self.variables.update(data["new_variables"])
        if "notation_conventions" in data and isinstance(data["notation_conventions"], list):
            for conv in data["notation_conventions"]:
                if conv not in self.notation_conventions:
                    self.notation_conventions.append(conv)
        if "new_conventions" in data and isinstance(data["new_conventions"], list):
            for conv in data["new_conventions"]:
                if conv not in self.notation_conventions:
                    self.notation_conventions.append(conv)
