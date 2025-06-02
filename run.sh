#!/bin/bash
program='sum'
input_range="$1"
num_runs="$2"
time_unit="$3"
input_name='len'
input_display_name='Length of array and linked list'
function_names='sum_array/sum_linked_list'
record_perf_events="$4"
perf_event_names="$5"
perf_record_freq="$6"
python run.py "$program" "$input_range" "$num_runs" "$time_unit" "$input_name" "$input_display_name" "$function_names" "$record_perf_events" "$perf_event_names" "$perf_record_freq"