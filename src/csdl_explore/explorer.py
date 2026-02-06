"""
CSDL Metadata Explorer.

High-level exploration API for searching, comparing, and navigating
OData CSDL metadata.
"""

import re
from dataclasses import dataclass
from pathlib import Path
from typing import Optional

from .parser import CSDLParser, EntityType, Property


@dataclass
class SearchResult:
    """A single search result."""
    type: str  # 'entity', 'property', 'property_label', 'picklist', 'navigation'
    entity: str
    match: str
    property: Optional[str] = None
    prop_type: Optional[str] = None
    label: Optional[str] = None
    navigation: Optional[str] = None
    picklist: Optional[str] = None


@dataclass
class EntityComparison:
    """Comparison between two entities."""
    entity1: str
    entity2: str
    only_in_entity1: list[str]
    only_in_entity2: list[str]
    common: list[str]
    nav1: list[str]
    nav2: list[str]


class CSDLExplorer:
    """
    High-level explorer for OData CSDL metadata.

    Provides search, comparison, and navigation capabilities over
    parsed CSDL metadata from any OData service.
    """

    def __init__(self, metadata_xml: str):
        """
        Initialize explorer with raw metadata XML.

        Args:
            metadata_xml: Raw XML string from $metadata endpoint
        """
        self.parser = CSDLParser(metadata_xml)
        self.entities = self.parser.entities

    @classmethod
    def from_file(cls, metadata_path: Path) -> "CSDLExplorer":
        """
        Create explorer from a metadata XML file.

        Args:
            metadata_path: Path to metadata.xml file

        Returns:
            CSDLExplorer instance
        """
        if not metadata_path.exists():
            raise FileNotFoundError(f"Metadata not found: {metadata_path}")
        metadata_xml = metadata_path.read_text(encoding='utf-8')
        return cls(metadata_xml)

    def list_entities(self, pattern: Optional[str] = None) -> list[str]:
        """
        List all entity names, optionally filtered by pattern.

        Args:
            pattern: Optional regex pattern to filter entities

        Returns:
            Sorted list of entity names
        """
        names = list(self.entities.keys())
        if pattern:
            regex = re.compile(pattern, re.IGNORECASE)
            names = [n for n in names if regex.search(n)]
        return sorted(names)

    def get_entity(self, name: str) -> Optional[EntityType]:
        """
        Get entity by name (case-insensitive).

        Args:
            name: Entity name

        Returns:
            EntityType if found, None otherwise
        """
        # Exact match first
        if name in self.entities:
            return self.entities[name]

        # Case-insensitive search
        name_lower = name.lower()
        for entity_name, entity in self.entities.items():
            if entity_name.lower() == name_lower:
                return entity

        return None

    def search(self, term: str, include_nav: bool = True, limit: int = 100) -> list[SearchResult]:
        """
        Search for entities and properties matching term.

        Searches across entity names, property names, labels, and picklist values.

        Args:
            term: Search term
            include_nav: Whether to include navigation properties
            limit: Maximum results to return

        Returns:
            List of SearchResult objects
        """
        results = []
        term_lower = term.lower()

        for entity_name, entity in self.entities.items():
            # Search entity name
            if term_lower in entity_name.lower():
                results.append(SearchResult(
                    type='entity',
                    entity=entity_name,
                    match=entity_name,
                ))

            # Search properties
            for prop_name, prop in entity.properties.items():
                matched = False

                if term_lower in prop_name.lower():
                    results.append(SearchResult(
                        type='property',
                        entity=entity_name,
                        match=prop_name,
                        property=prop_name,
                        prop_type=prop.type,
                        label=prop.label or None,
                        picklist=prop.picklist or None,
                    ))
                    matched = True

                # Also search in label
                if prop.label and term_lower in prop.label.lower():
                    results.append(SearchResult(
                        type='property_label',
                        entity=entity_name,
                        match=prop.label,
                        property=prop_name,
                        prop_type=prop.type,
                        label=prop.label,
                        picklist=prop.picklist or None,
                    ))
                    matched = True

                # Search in picklist name
                if not matched and prop.picklist and term_lower in prop.picklist.lower():
                    results.append(SearchResult(
                        type='picklist',
                        entity=entity_name,
                        match=prop.picklist,
                        property=prop_name,
                        prop_type=prop.type,
                        label=prop.label or None,
                        picklist=prop.picklist,
                    ))

            # Search navigation properties
            if include_nav:
                for nav_name in entity.navigation.keys():
                    if term_lower in nav_name.lower():
                        results.append(SearchResult(
                            type='navigation',
                            entity=entity_name,
                            match=nav_name,
                            navigation=nav_name,
                        ))

            if len(results) >= limit:
                break

        return results[:limit]

    def get_custom_fields(self, entity_name: str) -> list[Property]:
        """
        Get custom fields (customStringXX, etc.) for an entity.

        Args:
            entity_name: Entity name

        Returns:
            List of custom Property objects, sorted by name
        """
        entity = self.get_entity(entity_name)
        if not entity:
            return []
        return entity.custom_fields

    def get_navigation_properties(self, entity_name: str) -> list[dict]:
        """
        Get navigation properties with their target entities.

        Args:
            entity_name: Entity name

        Returns:
            List of dicts with name, target_entity, relationship
        """
        entity = self.get_entity(entity_name)
        if not entity:
            return []

        return sorted([
            {
                'name': nav.name,
                'target_entity': nav.target_entity,
                'relationship': nav.relationship,
            }
            for nav in entity.navigation.values()
        ], key=lambda x: x['name'])

    def compare_entities(self, entity1_name: str, entity2_name: str) -> EntityComparison:
        """
        Compare two entities to show differences.

        Args:
            entity1_name: First entity name
            entity2_name: Second entity name

        Returns:
            EntityComparison with differences and commonalities
        """
        e1 = self.get_entity(entity1_name)
        e2 = self.get_entity(entity2_name)

        if not e1:
            raise ValueError(f"Entity not found: {entity1_name}")
        if not e2:
            raise ValueError(f"Entity not found: {entity2_name}")

        props1 = set(e1.properties.keys())
        props2 = set(e2.properties.keys())

        return EntityComparison(
            entity1=entity1_name,
            entity2=entity2_name,
            only_in_entity1=sorted(props1 - props2),
            only_in_entity2=sorted(props2 - props1),
            common=sorted(props1 & props2),
            nav1=sorted(e1.navigation.keys()),
            nav2=sorted(e2.navigation.keys()),
        )

    def suggest_json_paths(self, entity_name: str) -> list[dict]:
        """
        Suggest JSON paths for extracting data from this entity.

        Args:
            entity_name: Entity name

        Returns:
            List of suggested paths with metadata
        """
        entity = self.get_entity(entity_name)
        if not entity:
            return []

        paths = []

        # Direct properties
        for prop_name in sorted(entity.properties.keys()):
            if prop_name.startswith('_') or prop_name == '__metadata':
                continue
            paths.append({
                'property': prop_name,
                'path': f'd.results[0].{prop_name}',
                'type': 'direct',
            })

        # Navigation properties
        for nav_name, nav in entity.navigation.items():
            target = nav.target_entity or 'Unknown'
            paths.append({
                'property': nav_name,
                'path': f'd.results[0].{nav_name}.results[0].<field>',
                'type': 'navigation',
                'note': f'Navigates to {target}',
            })

        return paths

    def get_emp_entities(self) -> list[str]:
        """Get all Emp* (employment-related) entities."""
        return self.list_entities(r'^Emp')

    def get_per_entities(self) -> list[str]:
        """Get all Per* (person-related) entities."""
        return self.list_entities(r'^Per')

    @property
    def entity_count(self) -> int:
        """Number of entities in metadata."""
        return len(self.entities)
