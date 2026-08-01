# Full-URI `uriorcurie` type designators do not round-trip between generated models on LinkML 1.11.1

## Summary

With `linkml==1.11.1` and `linkml-runtime==1.11.1`, a
`PydanticGenerator` model emits the full class URI as the default value of a
`uriorcurie` type-designator field. Loading that JSON-compatible payload with
the corresponding `PythonGenerator` model fails:

> `Wrong type designator value: class Thing has no subclass with
> ['class_class_curie', 'class_class_uri',
> 'class_model_uri']='https://example.org/Association'`

Both generated models identify the same class URI. The Pydantic payload holds
it as a string, while the Python model's `class_class_uri` is an
`rdflib.URIRef`. This prevents a validation-to-loading round trip for native
subclasses and affects applications that use both generated model families.

## Reproduction

The repository's locked Pixi environment contains the exact reproduction
versions. Run `pixi install --locked`, then
`pixi run --locked python scripts/reproduce_schema_discriminator.py`. It exits
zero only when the expected defect is reproduced and exits nonzero on an
unexpected success or different failure. The embedded dependency metadata also
makes the copied script independently reproducible, but it is not a second
project environment.

```python
#!/usr/bin/env python3
# /// script
# requires-python = "==3.12.*"
# dependencies = [
#   "linkml==1.11.1",
#   "linkml-runtime==1.11.1",
#   "pydantic==2.13.4",
#   "rdflib==7.6.0",
# ]
# ///
from importlib.metadata import version
from pathlib import Path
from tempfile import TemporaryDirectory

from linkml.generators import PydanticGenerator, PythonGenerator
from linkml_runtime.loaders import json_loader
from rdflib import URIRef

PINS = {
    "linkml": "1.11.1",
    "linkml-runtime": "1.11.1",
    "pydantic": "2.13.4",
    "rdflib": "7.6.0",
}
URI = "https://example.org/Association"
EXPECTED = "Wrong type designator value: class Thing has no subclass"
SCHEMA = """\
id: https://example.org/discriminator-test
name: discriminator_test
prefixes:
  ex:
    prefix_prefix: ex
    prefix_reference: https://example.org/
  linkml:
    prefix_prefix: linkml
    prefix_reference: https://w3id.org/linkml/
default_prefix: ex
imports: [linkml:types]
slots:
  schema_type:
    range: uriorcurie
    designates_type: true
  members:
    range: Thing
    multivalued: true
    inlined: true
    inlined_as_list: true
classes:
  Record:
    slots: [members]
  Thing:
    slots: [schema_type]
  Association:
    is_a: Thing
    class_uri: https://example.org/Association
"""

installed = {package: version(package) for package in PINS}
assert installed == PINS, (PINS, installed)

with TemporaryDirectory(prefix="linkml-discriminator-") as temporary:
    schema_path = Path(temporary, "schema.yaml")
    schema_path.write_text(SCHEMA, encoding="utf-8")
    pydantic_model = PydanticGenerator(str(schema_path)).compile_module()
    python_model = PythonGenerator(str(schema_path)).compile_module()

    record = pydantic_model.Record(members=[pydantic_model.Association()])
    payload = record.model_dump(mode="json", exclude_none=True)
    designator = payload["members"][0]["schema_type"]
    class_uri = python_model.Association.class_class_uri
    assert designator == URI
    assert isinstance(class_uri, URIRef)
    assert str(class_uri) == designator

    try:
        json_loader.load(payload, target_class=python_model.Record)
    except ValueError as error:
        actual = str(error)
        if EXPECTED not in actual:
            raise AssertionError(f"unexpected ValueError: {actual}") from error
    else:
        raise AssertionError("payload unexpectedly loaded; defect not reproduced")

print("versions:", installed)
print(f"Pydantic designator: {designator!r} ({type(designator).__name__})")
print(f"Python class_class_uri: {class_uri!r} ({type(class_uri).__name__})")
print(f"Reproduced: {actual}")
```

## Actual behavior

The pinned run exits zero after confirming this output:

```text
versions: {'linkml': '1.11.1', 'linkml-runtime': '1.11.1', 'pydantic': '2.13.4', 'rdflib': '7.6.0'}
Pydantic designator: 'https://example.org/Association' (str)
Python class_class_uri: rdflib.term.URIRef('https://example.org/Association') (URIRef)
Reproduced: Wrong type designator value: class Thing has no subclass with ['class_class_curie', 'class_class_uri', 'class_model_uri']='https://example.org/Association'
```

For comparison, the Python generator explicitly converts string values to
`URIRef` when the designator range is `uri`, but not when it is
`uriorcurie`. The reproduced mismatch may be related to that difference; this
is an observation, not a claimed root cause.

## Expected behavior

The JSON-compatible payload produced by `PydanticGenerator` should load with
the `PythonGenerator` model as an `Association`. A full URI is valid for a
`uriorcurie` designator and should compare equal after the necessary
normalization.

## Strategies and trade-offs

| Strategy | Advantages | Costs and risks | Decision |
| --- | --- | --- | --- |
| Pin the current tuple and use one generic downstream projection | Keeps the direct Dump Things publication gate, `qri`, graph navigation, and a deterministic Milestone 1 build. Raw source/predicate/target assertions remain attached to every projected edge. | Native relation containers and typed DOI/ISSN subclasses are still unavailable. The specific source role qualifiers remain migration provenance until conversion. | Chosen only as the bounded Milestone 1 bridge. |
| Fix URI/CURIE comparison in LinkML Runtime and pin the resulting compatible release | Addresses the minimal cross-generator mismatch at the lowest reusable layer and could restore normal generated-model dispatch for every consumer. | The comparison must be normalized without conflating distinct URI/CURIE values; all affected generated models and Dump Things endpoints need regression tests. It may expose additional schema-specific failures after this first mismatch is fixed. | Preferred durable direction, subject to an upstream-tested fix. |
| Change the schema designator range or aliases and regenerate the service models | Could keep the correction in schema evolution so a normal pin update regenerates records and API models together. | It changes a shared unreleased schema contract and may break other clients. Alias, full-URI, and omission probes already fail with the current generated-model tuple, so a schema-only spelling change is not yet demonstrated. | Viable only with end-to-end fixture evidence and schema-owner review. |
| Add a service/client-specific coercion before the internal loader | Can be narrowly deployed without waiting for a general LinkML release. | Creates an Orinoco-specific interpretation layer and risks making API validation disagree with other LinkML consumers. It is another compatibility branch to maintain. | Fallback upstream patch, not a preferred CON-site workaround. |
| Bypass Dump Things or flatten qualified semantics permanently | Simplifies the immediate payload. | Abandons the upstream publication contract or permanently discards the relationships the site is intended to expose. | Rejected. |

The current projection is deliberately generic rather than a sequence of
record-specific fixes: every configured relationship predicate must target a
record in the loaded PID set, independent of PID syntax. It contains no CON
PID/label/asset table and records unchanged assertions as evidence. Taxonomy
terms follow the normalized forward edge (both ways only when symmetric),
while Hugo derives reverse backlinks from the target term's `.Data.Pages`.
This allows a compatible schema/toolchain update to recreate native relations
from canonical metadata and structured migration provenance instead of
reverse-engineering HTML.

## Pin-update discipline

Schema, Dump Things service and client, `qri`, LinkML, and LinkML Runtime must
be tested as one tuple. Before changing the checked-in pins, post native
Association, Attribution, Generation, DOI, and ISSN fixtures through Dump
Things and round-trip them through `qri`. A successful update should change
the Pixi lock and schema checksum together, migrate the YAML records to native
structures, and delete compatibility normalization. It should not add a new
version branch or PID-specific mapping.

## Downstream removal condition

The downstream normalization can be removed after a pinned LinkML toolchain
loads this Pydantic payload as `Association` and native `Association`,
`Attribution`, `Generation`, `DOI`, and `ISSN` fixtures pass both the direct
service post and `qri` round trip. The canonical assertions and source roles
can then be migrated to native structures, while generic routing, Hugo
taxonomies, reverse backlinks, and graph generation remain. At that point this
expected-failure script should become a positive regression test.

## References

- Reproduced with LinkML and LinkML Runtime 1.11.1, Pydantic 2.13.4, RDFLib
  7.6.0, and Python 3.12.
- The downstream observation used Dump Things Service commit
  `9f101d97c7f15d491f602db5a9c33ad9a19ad8bf` and things-schemas commit
  `d26ea4135e28c25b134c64de1cdc15d15cd2f9f0`.
- [`uriorcurie` dispatch in PythonGenerator 1.11.1](https://github.com/linkml/linkml/blob/v1.11.1/packages/linkml/src/linkml/generators/pythongen.py#L882-L918)
  and [strict `_class_for` equality in LinkML Runtime
  1.11.1](https://github.com/linkml/linkml/blob/v1.11.1/packages/linkml_runtime/src/linkml_runtime/utils/yamlutils.py#L276-L285).
- Tracker searches for `"Wrong type designator value"`,
  `class_class_uri URIRef`, and `PydanticGenerator PythonGenerator designator`
  found no exact duplicate on 2026-07-31. Related but distinct reports are
  [#2107](https://github.com/linkml/linkml/issues/2107),
  [#2399](https://github.com/linkml/linkml/issues/2399), and
  [#3701](https://github.com/linkml/linkml/issues/3701).
