#!/bin/bash
BLUE='\033[0;34m'
RED='\033[0;31m'
GREEN='\033[0;32m'
NC='\033[0m'
virtualenv venv/
source ../venv/bin/activate

python ../setup.py install

modules=`jinni modules`
for module in $modules; do
  echo -en "${BLUE}$module: ${NC}"
  output=`jinni validate $module`
  if [ $? -eq 0 ]; then
    echo -e "${GREEN}${output}${NC}"
  else
    echo -e "${RED}Problem.${NC}"
    echo $output
  fi
done
