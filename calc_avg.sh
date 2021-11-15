#!/bin/bash
awk '{s+=$1}END{print "ave:",s/NR}' RS="\n" $1