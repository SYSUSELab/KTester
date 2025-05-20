# UnitTeseGen
Automatically generate unit tests using LLM and context in the project

## Preparation
Environment for our experiments:
- Java: openjdk 17.0.12 2024-07-16
- Python: 3.13.0
- Maven: Apache Maven 3.9.9 

## Running
0. set JVM language to English:
```sh
setx _JAVA_OPTIONS "-Duser.language=en -Duser.country=US -Dfile.encoding=UTF-8"
```
1. rename `code/settings.py.template` to `code/settings.py` and compelete settings.
2. run the following commands:
```sh
cd code
# prepare datasets

# prepare workspace
python preparation.py -W
# generate unit tests
python generate_unit_test.py
# run unit test and get coverage
python evaluation.py --operation coverage
# collect baseline results:
python evaluation.py --operation baseline
```