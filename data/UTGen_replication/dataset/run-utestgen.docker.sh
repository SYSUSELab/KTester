#!/bin/bash

export JDK_JAVA_OPTIONS="-Djdk.attach.allowAttachSelf=true"

direction=$1
javaVersion=$2

# if [ "$2" = "8" ]; then
#   sdk default java 8.0.333.fx-librca
# else
#   sdk default java 11.0.17-tem
# fi

cd "$direction"

echo "RUNNING ON THE $direction DATASET"

if [ $# -lt 4 ]; then
  fileDirectory="classes"
else
  fileDirectory="$4-classes"
fi

while IFS="," read -r proj class
do
  echo "Project: $proj"
  echo "Class: $class"
  echo ""

  cd "$proj"
  logDir="log/"
  mkdir -p $logDir

  logfile="$logDir/$class-$(date '+%Y-%m-%d-%H-%M').log"
  echo "pwd: $(pwd)" | tee -a "$logfile"

  set_inher_cmd=(
    java 
    --add-opens java.base/java.util=ALL-UNNAMED
    --add-opens java.base/java.lang=ALL-UNNAMED
    --add-opens java.base/java.lang.reflect=ALL-UNNAMED
    --add-opens java.base/sun.reflect.annotation=ALL-UNNAMED
    --add-opens java.base/java.text=ALL-UNNAMED
    --add-opens java.desktop/java.awt.font=ALL-UNNAMED
    -jar ../../lib/evosuite-1.2.0.jar
    -inheritanceTree
    -projectCP "$proj.jar"
    -setup "$class" "$proj.jar"
  )

  echo "command: ${set_inher_cmd[@]}" | tee -a "$logfile"
  "${set_inher_cmd[@]}" >> "$logfile" 2>&1
  
  generate_cmd=(
    java
    --add-opens java.base/java.util=ALL-UNNAMED
    --add-opens java.base/java.lang=ALL-UNNAMED
    --add-opens java.base/java.lang.reflect=ALL-UNNAMED
    --add-opens java.base/sun.reflect.annotation=ALL-UNNAMED
    --add-opens java.base/java.text=ALL-UNNAMED
    --add-opens java.desktop/java.awt.font=ALL-UNNAMED
    -jar "../../utestgen-$javaVersion.jar"
    -projectCP "$proj.jar"
    -class "$class"
    -Dcriterion=BRANCH:LINE:OUTPUT:METHOD:CBRANCH
    -Dinheritance_file=evosuite-files/inheritance.xml.gz
    -Dllm_graphql_entrypoint=llm-server:8000/graphql
    -Dtest_naming_strategy=llm_based
    -Dvariable_naming_strategy=HEURISTICS_BASED
    -Dassertion_timeout=600
    -Dsearch_budget=200
    -Dminimization_timeout=600
    -Dwrite_junit_timeout=600
    -Dextra_timeout=600
    -Ddefuse_debug_mode=true
    -Dtest_format=JUNIT5LLM
    -Djunit_check_timeout=600
    -Dbytecode_logging_mode=FILE_DUMP
  )

  echo "conmmand: ${generate_cmd[@]}" | tee -a "$logfile"

  "${generate_cmd[@]}" >> "$logfile" 2>&1

  cd ../
done < <(tail -n +2 "$fileDirectory.csv")
