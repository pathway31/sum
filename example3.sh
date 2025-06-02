#!/bin/bash
input_range='500000:1000000,100000'
num_runs='10'
time_unit='ms'
record_perf_events='true'

# The perf events below point towards the array benefitting from the
# prefetching and the linked list not.
#
# These events are only valid for Intel CPUs, so AMD CPUs shouldn't record 
# any perf data, only runtimes.
#
# sudo perf list -v for detailed event descriptions
perf_event_names='L1-dcache-loads,L1-dcache-load-misses,l1d_pend_miss.pending,l2_lines_out.useless_hwpf,l2_rqsts.demand_data_rd_miss'

perf_record_freq='40000'
./run.sh $input_range $num_runs $time_unit $record_perf_events $perf_event_names $perf_record_freq