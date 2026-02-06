"""Entity tree widget for navigating CSDL entities."""

from textual.widgets import Tree

from ..explorer import CSDLExplorer
from ..themes import VERCEL_THEME


class EntityTree(Tree):
    """Tree widget for navigating entities.

    Builds a categorised tree from the explorer's entity list, grouping
    entities into Emp*, Per*, and alphabetical buckets.
    """

    def __init__(self, explorer: CSDLExplorer, **kwargs):
        """Initialise the entity tree.

        Args:
            explorer: The CSDL explorer instance providing entity data.
            **kwargs: Extra keyword arguments forwarded to ``Tree``.
        """
        super().__init__("CSDL Metadata", **kwargs)
        self.explorer = explorer
        self._build_tree()

    def _build_tree(self):
        """Build the tree with Entities and Picklists as top-level branches."""
        root = self.root
        root.expand()

        # Use default theme colors for Rich markup (Tree labels go through
        # Rich's Text.from_markup, so Textual $-tokens don't work here).
        pc = VERCEL_THEME.primary
        ac = VERCEL_THEME.accent
        sc = VERCEL_THEME.success
        wc = VERCEL_THEME.warning

        # ── Entities branch ──────────────────────────────────────
        all_entity_names = self.explorer.list_entities()
        entities_node = root.add(
            f"[{pc}]Entities[/] ({len(all_entity_names)})", expand=True
        )

        emp_entities = self.explorer.get_emp_entities()
        per_entities = self.explorer.get_per_entities()
        other_entities = sorted(
            set(all_entity_names) - set(emp_entities) - set(per_entities)
        )

        if emp_entities:
            emp_node = entities_node.add(f"[{pc}]Emp*[/] ({len(emp_entities)})", expand=False)
            for entity in emp_entities:
                emp_node.add_leaf(entity, data={"type": "entity", "name": entity})

        if per_entities:
            per_node = entities_node.add(f"[{sc}]Per*[/] ({len(per_entities)})", expand=False)
            for entity in per_entities:
                per_node.add_leaf(entity, data={"type": "entity", "name": entity})

        if len(other_entities) > 50:
            current_letter = None
            current_node = None
            letter_count = {}
            for entity in other_entities:
                letter = entity[0].upper()
                letter_count[letter] = letter_count.get(letter, 0) + 1
            for entity in other_entities:
                letter = entity[0].upper()
                if letter != current_letter:
                    current_letter = letter
                    current_node = entities_node.add(
                        f"[{ac}]{letter}[/] ({letter_count[letter]})",
                        expand=False,
                    )
                current_node.add_leaf(entity, data={"type": "entity", "name": entity})
        else:
            other_node = entities_node.add(f"[{ac}]Other[/] ({len(other_entities)})", expand=False)
            for entity in other_entities:
                other_node.add_leaf(entity, data={"type": "entity", "name": entity})

        # ── Picklists branch ─────────────────────────────────────
        picklists: dict[str, list[str]] = {}
        for entity_name in all_entity_names:
            entity = self.explorer.get_entity(entity_name)
            if not entity:
                continue
            for prop in entity.properties.values():
                if prop.picklist:
                    picklists.setdefault(prop.picklist, []).append(entity_name)

        if picklists:
            pick_node = root.add(
                f"[{wc}]Picklists[/] ({len(picklists)})", expand=False
            )
            for name in sorted(picklists):
                count = len(picklists[name])
                pick_node.add_leaf(
                    f"{name} [dim]({count} entities)[/]",
                    data={"type": "picklist", "name": name, "entities": picklists[name]},
                )
