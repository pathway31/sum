#!/bin/bash
input_range='10000:100000,10000'
num_runs='100'
time_unit='us'
record_perf_events='false'
perf_event_names='none'
perf_record_freq='none'
./run.sh $input_range $num_runs $time_unit $record_perf_events $perf_event_names $perf_record_freq