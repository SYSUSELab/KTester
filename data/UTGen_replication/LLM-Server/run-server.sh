#!/bin/bash

source .env/bin/activate

logDir="log/"

mkdir -p $logDir
strawberry dev main > $logDir/$(date '+%Y-%m-%d-%H-%M').log