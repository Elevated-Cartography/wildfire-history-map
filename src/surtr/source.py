import dataclasses
import tomllib
from dataclasses import dataclass, field
from pathlib import Path
from typing import Dict, List, Optional, Union


@dataclass
class Layer:
    """An ArcGIS FeatureServer layer that we download."""

    name: str
    url: str
    title: str = ""
    homepage: str = ""
    where: str = "1=1"

    def out_fields(self) -> List[str]:
        raise NotImplementedError

    @property
    def return_geometry(self) -> bool:
        return True

    def raw_path(self, data_dir: Path) -> Path:
        return data_dir / "raw" / f"{self.name}.geojsonl"


@dataclass
class CauseConfig:
    # Fields on the layer itself holding (FireCause, General, Specific)
    fields: List[str] = field(default_factory=list)
    # Name of a lookup table to find those fields in, keyed by IRWIN ID
    lookup: Optional[str] = None
    # Translates text in the mapped `cause` field to cause codes (see
    # ReasonCode in reason.py), for sources with their own cause names
    values: Dict[str, int] = field(default_factory=dict)


@dataclass
class PrescribedConfig:
    # Features where `field` has one of `values` are prescribed burns
    field: str = ""
    # (dataclasses.field, since `field` is shadowed by the attribute above)
    values: List[str] = dataclasses.field(default_factory=list)


@dataclass
class Source(Layer):
    """A layer of fire perimeters."""

    # Output property -> layer field, or a list of fields to take the first
    # non-empty one from
    fields: Dict[str, Union[str, List[str]]] = field(default_factory=dict)
    size_field: str = ""
    size_unit: str = "acre"
    irwinid_field: str = ""
    cause: CauseConfig = field(default_factory=CauseConfig)
    prescribed: PrescribedConfig = field(default_factory=PrescribedConfig)

    def __post_init__(self):
        if isinstance(self.cause, dict):
            self.cause = CauseConfig(**self.cause)
        if isinstance(self.prescribed, dict):
            self.prescribed = PrescribedConfig(**self.prescribed)

    def out_fields(self):
        names = [
            name
            for value in self.fields.values()
            for name in (value if isinstance(value, list) else [value])
        ]
        names += self.cause.fields
        names += [
            f
            for f in (self.size_field, self.irwinid_field, self.prescribed.field)
            if f
        ]
        return sorted(set(names))


@dataclass
class Lookup(Layer):
    """An attribute-only layer joined onto perimeters by IRWIN ID."""

    key_field: str = "IrwinID"
    fields: List[str] = field(default_factory=list)

    def out_fields(self):
        return sorted(set([self.key_field] + self.fields))

    @property
    def return_geometry(self):
        return False


@dataclass
class Config:
    sources: List[Source]
    lookups: Dict[str, Lookup]
    # Natural Earth admin-1 (states/provinces) zip
    boundaries_url: str

    def boundaries_path(self, data_dir: Path) -> Path:
        return data_dir / "reference" / "admin1.zip"

    @property
    def layers(self) -> List[Layer]:
        return [*self.sources, *self.lookups.values()]

    def layer(self, name) -> Layer:
        for layer in self.layers:
            if layer.name == name:
                return layer
        raise KeyError(f"No source or lookup named {name!r}")


def load_config(path) -> Config:
    with open(path, "rb") as f:
        raw = tomllib.load(f)
    sources = [Source(**s) for s in raw.get("sources", [])]
    lookups = {l["name"]: Lookup(**l) for l in raw.get("lookups", [])}
    for source in sources:
        if source.cause.lookup and source.cause.lookup not in lookups:
            raise ValueError(
                f"Source {source.name!r} uses unknown lookup {source.cause.lookup!r}"
            )
    return Config(sources, lookups, raw["boundaries"]["url"])
