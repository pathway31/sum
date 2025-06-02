#!/bin/bash
input_range='700000:800000,25000'
num_runs='5'
time_unit='ms'
record_perf_events='true'
perf_event_names='L1-dcache-loads,L1-dcache-load-misses,l1d_pend_miss.pending,l2_lines_out.useless_hwpf,l2_rqsts.demand_data_rd_miss'
perf_record_freq='max'
./run.sh $input_range $num_runs $time_unit $record_perf_events $perf_event_names $perf_record_freq