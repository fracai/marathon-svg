#!/usr/bin/env bash

WNUMB=740c52102acdbed17a5b4c3746600dfb116356c1
NOUISLIDER=ab25fad2918ae796c2f401aedfce9accdafa19ce

FILES=(
    https://raw.githubusercontent.com/leongersen/wnumb/${WNUMB}/wNumb.min.js
    https://raw.githubusercontent.com/leongersen/noUiSlider/${NOUISLIDER}/dist/nouislider.min.js
    https://raw.githubusercontent.com/leongersen/noUiSlider/${NOUISLIDER}/dist/nouislider.min.css
)

for FILE in "${FILES[@]}"
do
    echo "$FILE"
    curl -o "site/resources/external/$(basename "$FILE")" "$FILE"
done
