"""
CSDL (Common Schema Definition Language) parser for OData metadata.

Parses $metadata XML from OData services into typed Python dataclasses.
Supports standard OData and SAP-specific annotations (sap:label, sap:picklist, etc.).
"""

import xml.etree.ElementTree as ET
from dataclasses import dataclass, field
from typing import Optional


# Known EDMX namespace URIs (across OData/EF versions)
KNOWN_EDMX_NAMESPACES = [
    'http://schemas.microsoft.com/ado/2009/11/edmx',   # EDMX v3 / EF6
    'http://schemas.microsoft.com/ado/2007/06/edmx',   # EDMX v1 / OData v2
    'http://docs.oasis-open.org/odata/ns/edmx',        # OData v4
]

# Known EDM (conceptual model) namespace URIs
KNOWN_EDM_NAMESPACES = [
    'http://schemas.microsoft.com/ado/2009/11/edm',    # EF6 / CSDL v3
    'http://schemas.microsoft.com/ado/2008/09/edm',    # EF4 / CSDL v2
    'http://schemas.microsoft.com/ado/2006/04/edm',    # EF1 / CSDL v1
    'http://docs.oasis-open.org/odata/ns/edm',         # OData v4
]

# Fallback static namespaces (OData v2 defaults)
NAMESPACES = {
    'edmx': 'http://schemas.microsoft.com/ado/2007/06/edmx',
    'edm': 'http://schemas.microsoft.com/ado/2008/09/edm',
    'm': 'http://schemas.microsoft.com/ado/2007/08/dataservices/metadata',
    'd': 'http://schemas.microsoft.com/ado/2007/08/dataservices',
    'sap': 'http://www.sap.com/Protocols/SAPData',
}

# Known annotation namespace URIs
ANNOTATION_NAMESPACES = [
    'http://www.sap.com/Protocols/SAPData',
    'http://www.successfactors.com/edm/sap',
]


@dataclass
class Property:
    """Represents an OData entity property."""
    name: str
    type: str
    nullable: bool = True
    label: str = ""
    filterable: bool = True
    sortable: bool = True
    required: bool = False
    creatable: bool = False
    updatable: bool = False
    upsertable: bool = False
    visible: bool = True
    picklist: str = ""
    max_length: str = ""

    @property
    def is_custom(self) -> bool:
        """Check if this is a custom field (customStringXX, etc.)."""
        name_lower = self.name.lower()
        return (
            name_lower.startswith('customstring') or
            name_lower.startswith('customdate') or
            name_lower.startswith('customlong') or
            name_lower.startswith('customdouble') or
            name_lower.startswith('cust_')
        )


@dataclass
class NavigationProperty:
    """Represents an OData navigation property."""
    name: str
    relationship: str
    from_role: str
    to_role: str
    target_entity: Optional[str] = None


@dataclass
class EntityType:
    """Represents an OData entity type."""
    name: str
    namespace: str = ""
    base_type: Optional[str] = None
    keys: list[str] = field(default_factory=list)
    properties: dict[str, Property] = field(default_factory=dict)
    navigation: dict[str, NavigationProperty] = field(default_factory=dict)

    @property
    def custom_fields(self) -> list[Property]:
        """Get all custom fields for this entity."""
        return sorted(
            [p for p in self.properties.values() if p.is_custom],
            key=lambda p: p.name
        )


@dataclass
class Association:
    """Represents an OData association."""
    name: str
    ends: list[dict] = field(default_factory=list)


class CSDLParser:
    """
    Parser for OData CSDL (Common Schema Definition Language) metadata.

    Extracts entity types, properties, navigation properties, and associations
    from an OData $metadata XML document. Supports SAP-specific annotations.
    """

    def __init__(self, metadata_xml: str):
        """
        Initialize parser with raw metadata XML.

        Args:
            metadata_xml: Raw XML string from $metadata endpoint
        """
        self.root = ET.fromstring(metadata_xml)
        self.entities: dict[str, EntityType] = {}
        self.associations: dict[str, Association] = {}
        self._ns = self._detect_namespaces()
        self._annotation_ns = self._detect_annotation_namespace()
        self._parse()

    def _detect_namespaces(self) -> dict[str, str]:
        """Auto-detect EDMX and EDM namespace versions from the document.

        Returns:
            Namespace dict with 'edmx' and 'edm' keys set to the versions
            found in the document, falling back to the static NAMESPACES.
        """
        ns = dict(NAMESPACES)

        # Detect EDMX namespace from root element
        root_tag = self.root.tag
        for edmx_ns in KNOWN_EDMX_NAMESPACES:
            if root_tag == f'{{{edmx_ns}}}Edmx':
                ns['edmx'] = edmx_ns
                break

        # Detect EDM namespace by scanning for Schema elements.
        # Prefer ConceptualModels schemas over StorageModels (SSDL).
        for elem in self.root.iter():
            tag = elem.tag
            for edm_ns in KNOWN_EDM_NAMESPACES:
                if tag == f'{{{edm_ns}}}Schema':
                    # Check if this Schema is inside ConceptualModels
                    # (we'll accept any match but prefer conceptual)
                    ns['edm'] = edm_ns
                    return ns

        return ns

    def _detect_annotation_namespace(self) -> str:
        """Detect which annotation namespace is used in this metadata document.

        Different OData providers use different namespaces for property annotations.
        We scan Property element attributes to find which one is actually in use.
        """
        for elem in self.root.iter():
            if elem.tag.endswith('}Property') or elem.tag == 'Property':
                for attr_key in elem.attrib:
                    for ns in ANNOTATION_NAMESPACES:
                        if attr_key.startswith(f'{{{ns}}}'):
                            return ns

        return NAMESPACES['sap']

    def _parse(self):
        """Parse the CSDL metadata document."""
        ns = self._ns
        edm_ns = ns['edm']
        edmx_ns = ns['edmx']

        # For EDMX files with ConceptualModels (EF-style), only parse that
        # section to avoid mixing SSDL storage types with conceptual types.
        conceptual = self.root.find(
            f'.//{{{edmx_ns}}}ConceptualModels'
        )
        search_root = conceptual if conceptual is not None else self.root

        for schema in search_root.iter(f'{{{edm_ns}}}Schema'):
            schema_ns = schema.get('Namespace', '')

            for entity_elem in schema.findall(f'{{{edm_ns}}}EntityType'):
                entity = self._parse_entity_type(entity_elem, schema_ns)
                self.entities[entity.name] = entity

            for assoc_elem in schema.findall(f'{{{edm_ns}}}Association'):
                assoc = self._parse_association(assoc_elem)
                self.associations[assoc.name] = assoc

        # Resolve navigation property targets
        self._resolve_navigation_targets()

    def _parse_entity_type(self, elem: ET.Element, namespace: str) -> EntityType:
        """Parse a single EntityType element."""
        edm = self._ns['edm']
        entity = EntityType(
            name=elem.get('Name', ''),
            namespace=namespace,
            base_type=elem.get('BaseType'),
        )

        # Parse Key
        key_elem = elem.find(f'{{{edm}}}Key')
        if key_elem is not None:
            for prop_ref in key_elem.findall(f'{{{edm}}}PropertyRef'):
                entity.keys.append(prop_ref.get('Name', ''))

        # Parse Properties
        for prop_elem in elem.findall(f'{{{edm}}}Property'):
            prop = self._parse_property(prop_elem)
            entity.properties[prop.name] = prop

        # Parse NavigationProperties
        for nav_elem in elem.findall(f'{{{edm}}}NavigationProperty'):
            nav = self._parse_navigation(nav_elem)
            entity.navigation[nav.name] = nav

        return entity

    def _parse_property(self, elem: ET.Element) -> Property:
        """Parse a Property element, including vendor-specific annotations."""
        ns = self._annotation_ns

        def ann_attr(name: str, default: str = '') -> str:
            """Get an annotation-namespaced attribute value."""
            return elem.get(f'{{{ns}}}{name}', default)

        return Property(
            name=elem.get('Name', ''),
            type=elem.get('Type', ''),
            nullable=elem.get('Nullable', 'true') == 'true',
            label=ann_attr('label'),
            filterable=ann_attr('filterable', 'true') == 'true',
            sortable=ann_attr('sortable', 'true') == 'true',
            required=ann_attr('required', 'false') == 'true',
            creatable=ann_attr('creatable', 'false') == 'true',
            updatable=ann_attr('updatable', 'false') == 'true',
            upsertable=ann_attr('upsertable', 'false') == 'true',
            visible=ann_attr('visible', 'true') == 'true',
            picklist=ann_attr('picklist'),
            max_length=elem.get('MaxLength', ''),
        )

    def _parse_navigation(self, elem: ET.Element) -> NavigationProperty:
        """Parse a NavigationProperty element."""
        return NavigationProperty(
            name=elem.get('Name', ''),
            relationship=elem.get('Relationship', ''),
            from_role=elem.get('FromRole', ''),
            to_role=elem.get('ToRole', ''),
        )

    def _parse_association(self, elem: ET.Element) -> Association:
        """Parse an Association element."""
        assoc = Association(name=elem.get('Name', ''))

        for end in elem.findall(f'{{{self._ns["edm"]}}}End'):
            assoc.ends.append({
                'type': end.get('Type', ''),
                'multiplicity': end.get('Multiplicity', ''),
                'role': end.get('Role', ''),
            })

        return assoc

    def _resolve_navigation_targets(self):
        """Resolve navigation property target entities from associations."""
        for entity in self.entities.values():
            for nav in entity.navigation.values():
                # Extract association name from relationship
                assoc_name = nav.relationship.split('.')[-1] if nav.relationship else None

                if assoc_name and assoc_name in self.associations:
                    assoc = self.associations[assoc_name]
                    for end in assoc.ends:
                        if end['role'] == nav.to_role:
                            nav.target_entity = end['type'].split('.')[-1]
                            break
