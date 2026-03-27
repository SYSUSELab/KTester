# UTGen Replication for HITS Dataset
This is a replication of the UTGen for the HITS dataset. Source code of UTGEN is avaliable at https://github.com/amirdeljouyi/UTGen .

## Enviroments for Our Replication
Docker or
```c++
Requirements = (Ollama && Java=17 && Python>=3.11 && LLM_Interface)
LLM_Interface = Nvidia tookits? if you want to run model localy else Ollama_API
```
you can install requirements following these links:
- [Docker](https://docs.docker.com/engine/install/)
- [Ollama](https://ollama.ai/docs/install)
- [Nvidia tookits](https://developer.nvidia.com/cuda-downloads)

## Setting up and Running Experiments:
### Setting up UTGen
1. Setting up UTGen's workspace:
```bash
git clone https://github.com/amirdeljouyi/UTGen.git
cd UTGen
```
2. Replace the files in this repository's [/Docker directory](/Docker/)  with those in `UTGen/Docker`.
3. Setting up **UTGen-LLMServer**:
```bash
cd UTGen\Docker
docker-compose -f docker-compose.yml up ollama -d
docker-compose -f docker-compose.nvidia.yml up llm-server 
```
4. Replace [run-server.sh](/LLM-Server/run-server.sh) and [run-docker-server](/LLM-Server/run-docker-server.sh) in `UTGen/Docker/llm-server/app/LLM-Server`.
5. Setting up **UTGen-Client**:
```bash
cd UTGen\Docker
docker-compose -f docker-compose.nvidia.yml up utgen-client
```
6. Load HITS Dataset into the `UTGEN-Client` Container:
    1. Load [/dataset/projects_binary](/dataset/projects_binary) into `/app/dataset/projects_binary` inside the container.
    2. Add [evosuite-1.2.0.jar]("/dataset/evosuite-1.2.0.jar") to `/app/dataset/lib`.
    3. Replace the scripts with [run-experiment.sh](/dataset) and [run-utestgen.docker.sh](/dataset) in `app/dataset`.

### Running Expriments
1. Run the following in the host terminal:
```bash
docker exec ollama ollama pull codellama:7b-instruct
# check if the ollama is able to work
docker exec -it ollama ollama run codellama:7b-instruct /bye
```
2. Execute `./run-docker-server.sh` in the `UTGen-LLMServer` container.
3. Execute `run-experiment.sh` in the `UTGen-Client` container.


## Help: How to runing UTGen for my own dataset?
1. Refer to [classes.csv](https://github.com/amirdeljouyi/UTGen-replication-package-dataset/blob/main/SF110-binary/classes.csv), collect target classes from your dataset, and create your own `classes.csv`.
2. Package each target project as a jar file, and ensure the JAR includes all dependent classes.
3. Generate `evosuite-files` for each project.
4. Organize your dataset by following the structure in [\dataset](\dataset).

### Generate evosuite files for your projects
Use the following command to generate `evosuite-file` for the target project and target class:
```bash
    java -jar ../../lib/evosuite-1.2.0.jar -inheritanceTree -projectCP "<project>.jar" -setup "<target class>" "<project>.jar"
```
EvoSuite supports up to Java 11 by default. If you want to support higher versions, add extra JVM options. The following is a reference command for Java 17:
```bash
    java 
    --add-opens java.base/java.util=ALL-UNNAMED
    --add-opens java.base/java.lang=ALL-UNNAMED
    --add-opens java.base/java.lang.reflect=ALL-UNNAMED
    --add-opens java.base/sun.reflect.annotation=ALL-UNNAMED
    --add-opens java.base/java.text=ALL-UNNAMED
    --add-opens java.desktop/java.awt.font=ALL-UNNAMED
    -jar ../../lib/evosuite-1.2.0.jar
    -inheritanceTree
    -projectCP "<project>.jar"
    -setup "<target class>" "<project>.jar"
```