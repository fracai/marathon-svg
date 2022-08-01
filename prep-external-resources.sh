#!/usr/bin/env bash

set -e

WNUMB=740c52102acdbed17a5b4c3746600dfb116356c1
NOUISLIDER=ab25fad2918ae796c2f401aedfce9accdafa19ce

FILES=(
    https://raw.githubusercontent.com/leongersen/wnumb/${WNUMB}/wNumb.min.js
    https://raw.githubusercontent.com/leongersen/noUiSlider/${NOUISLIDER}/dist/nouislider.min.js
    https://raw.githubusercontent.com/leongersen/noUiSlider/${NOUISLIDER}/dist/nouislider.min.css
)

mkdir -p output/resources/external/

chmod 777 output/resources/external/

for FILE in "${FILES[@]}"
do
    echo -e "url = \"${FILE}\"\n-O\n--output-dir output/resources/external\n"
done
