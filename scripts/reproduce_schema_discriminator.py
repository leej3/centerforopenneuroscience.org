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
"""Expected-failure reproducer for a LinkML type-designator round trip.

The script exits zero only when the confirmed failure is reproduced. It exits
nonzero if loading unexpectedly succeeds or fails in a different way.
"""

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
ASSOCIATION_URI = "https://example.org/Association"
EXPECTED_ERROR = "Wrong type designator value: class Thing has no subclass"
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
imports:
  - linkml:types
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
    slots:
      - members
  Thing:
    slots:
      - schema_type
  Association:
    is_a: Thing
    class_uri: https://example.org/Association
"""


def main() -> None:
    installed = {package: version(package) for package in PINS}
    if installed != PINS:
        raise AssertionError(f"version mismatch: expected {PINS}, got {installed}")

    with TemporaryDirectory(prefix="linkml-discriminator-") as temporary:
        schema_path = Path(temporary, "schema.yaml")
        schema_path.write_text(SCHEMA, encoding="utf-8")

        pydantic_model = PydanticGenerator(str(schema_path)).compile_module()
        python_model = PythonGenerator(str(schema_path)).compile_module()

        pydantic_record = pydantic_model.Record(
            members=[pydantic_model.Association()]
        )
        payload = pydantic_record.model_dump(mode="json", exclude_none=True)
        designator = payload["members"][0]["schema_type"]
        python_class_uri = python_model.Association.class_class_uri

        if designator != ASSOCIATION_URI:
            raise AssertionError(
                f"PydanticGenerator emitted {designator!r}, expected "
                f"{ASSOCIATION_URI!r}"
            )
        if not isinstance(python_class_uri, URIRef):
            raise AssertionError(
                "PythonGenerator no longer stores class_class_uri as URIRef: "
                f"{python_class_uri!r}"
            )
        if str(python_class_uri) != designator:
            raise AssertionError(
                "The generated models refer to different class URIs: "
                f"{python_class_uri!r} versus {designator!r}"
            )

        try:
            json_loader.load(payload, target_class=python_model.Record)
        except ValueError as error:
            actual_error = str(error)
            if EXPECTED_ERROR not in actual_error:
                raise AssertionError(
                    f"unexpected ValueError instead of {EXPECTED_ERROR!r}: "
                    f"{actual_error}"
                ) from error
        else:
            raise AssertionError(
                "Expected the PythonGenerator/runtime loader to reject the "
                "PydanticGenerator payload, but it loaded successfully"
            )

    print("versions:", installed)
    print(f"Pydantic designator: {designator!r} ({type(designator).__name__})")
    print(
        "Python class_class_uri: "
        f"{python_class_uri!r} ({type(python_class_uri).__name__})"
    )
    print(f"Reproduced: {actual_error}")


if __name__ == "__main__":
    main()
