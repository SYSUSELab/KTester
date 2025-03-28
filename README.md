# UnitTeseGen
Automatically generate unit tests using LLM and context in the project

## Preparation
Environment for our experiments:
- Java: 21.0.5 2024-10-15 LTS
- Python: 3.13.0

**Note:** If you don't use a higher version of the Java Runtime Environment than us, please repackage the jar file in `code/java`. Take folder `project-info-extract` as example:

```sh
cd code/java/project-info-extract
jar -cvfe ../project-info-extract.jar App -C target . -C lib .
# this also work
jar cfm ../project-info-extract.jar MANIFEST.MF -C target . -C lib .
```

## (demo) Running
```sh
cd code
# prepare datasets

# generate unit tests, use argument "--prepare_workspace" for the first time
python generate_unit_test.py --prepare_workspace
# run unit test and get coverage
python evaluation.py --operation coverage
```