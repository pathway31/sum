# Overview

This benchmark creates arrays and linked lists of identical lengths, then takes the following measurements:
   1) The time it takes to sum up all integers in the array
   2) The frequency of `perf` events as the array is being summed
   3) The time it takes to sum up all integers in the linked list
   4) The frequency of `perf` events as the linked list is being summed

and stores them.

All measurements are displayed in a series of charts once the benchmark is finished running.

### Core Files
+ `sum.c`
   + The benchmarked program, creates and sums an array and linked list of a specified length
+ `run.sh`
   + The script that initiates the benchmark
+ `run.py`
   + The script that handles the higher-level orchestration of the benchmark
+ `example*.sh`
   + A series of scripts demonstrating different ways to use the `run.sh` script

# Requirements
+ `gcc`
+ `perf`
+ `gnuplot`
+ `python3`

# Usage
The benchmark is run by executing the `run.sh` script.

`run.sh` requires six arguments:
1) `input_range`<br>
   A string containing a sequence of three unsigned integers which enumerates all of the inputs that the benchmarked program (`sum.c`) will be run with.
   The sequence is formatted as '\<min\>\:\<max\>,\<inc\>', where:
   + min - the minimum input the program will be run with
   + max - the maximum input the program will be run with
   + inc - the increment between consecutive inputs
        
   So, for example, an `input_range` of `'10:100,30'` will run the program with the inputs of 10, 40, 70, and 100.

   These inputs are the lengths of the array and linked lists that will be created and then summed.

2) `num_runs`<br>
   An unsigned integer that determines how many times the program will be run with each input. Doing multiple runs means more samples and more representative data.

3) `time_unit`<br>
   A string with a value of 's' (seconds), 'ms' (milliseconds), or 'us' (microseconds). Specifies which unit of time that the benchmark's times will be displayed in.

   Times are always stored in seconds, this argument only affects how they're displayed.

4) `record_perf_events`<br>
   A string with a value of 'true' or 'false'. A value of 'true' runs the benchmark with `perf` and records both time and `perf` event data, a value of 'false' only records time data.

5) `perf_event_names`<br>
   A string containing a comma-separated list of `perf` events to record data for, formatted as: '\<name1\>,\<name2\>,\<name3\>'

   The list of available `perf` events can be found by running `sudo perf list -v`

   If `record_perf_events` has a value of 'false', then this argument's value is ignored. It can be any non-empty string.

6) `perf_record_freq`<br>
   An unsigned integer or the string 'max'. Dictates how many times per second `perf` will sample the program for data. A value of 'max' tells `perf` to use the maximum frequency supported by the system. Higher frequencies gather more data at the cost of larger `perf` report files and more time spent writing data.

   If `record_perf_events` has a value of 'false', then this argument's value is ignored. It can be any non-empty string.
   <br><br>

Getting representative `perf` event data may require increasing `num_runs` and `perf_record_freq`. Depending on CPU speed and the length of the array/linked list being summed, it's possible for the summing to start and finish inbetween `perf` samples.

# Output Files
Running the benchmark will create a collection of `*.data` files stored in a folder named `data`. It will also create a script called `plot.sh`. Any output files from a previous run will be deleted or overwritten.

## `times.data`
The times of each run are stored in the `times.data` file.

`times.data` look like this:
```
# len sum_array sum_linked_list
1000 0.00001 0.00003
1000 0.00001 0.00002
2000 0.00002 0.00004
2000 0.00002 0.00004
```

The first line is a header with the names of each column of data, prepended with a '#' to stop `gnuplot` from trying to interpret the line as data. 

Every line after the first represents one run of the benchmarked program. Each line has three data values which are, from left to right:
   1) The length of the array and linked list that were summed
   2) The time it took to sum the array, in seconds
   3) The time it took to sum the linked list, in seconds

## `<perf event>.data`

If `run.sh` was run with `record_perf_events='true'`, then `<perf event name>.data` files will be created, one for each valid event name in `perf_event_names`. Each file stores how often the event occurred while the array and linked list were being summed.

A `<perf event>.data` file looks like this:
```
# len sum_array sum_linked_list
1000 0.03 15.2
1000 0.00 17.3
2000 0.00 16.0
2000 0.01 18.9
```

Like `times.data`, the first line is a header with the names of each column, along with a '#' to stop `gnuplot` from trying to interpret the line as data.

Every line after the first represents one run of the benchmarked program. Each line has three data values which are, from left to right:
   1) The length of the array and linked list that were summed
   2) Of all the `perf` samples that included the event, what percentage of
   them were taken while the program was summing the array
   3) Of all the `perf` samples that included the event, what percentage of
   them were taken while the program was summing the linked list

## `plot.sh`
This script generates charts to visualize the data files in the `data` folder.

Two charts are generated for `times.data`. The first has the length of the array and linked list on the x-axis, and times it took to sum each of them on the y-axis. The second has the length of the array and linked list on the x-axis, and how many times faster it was to sum the array than the linked list on the y-axis.

One chart is also generated for every `<perf event>.data` file. Each of these charts has the length of the array and linked list on the x-axis, and the frequency of the `perf` event on the y-axis. Event frequency is expressed as a percentage: out of all `perf` samples that included the event (across that one run of the program), what percentage of those samples were taken while the program was summing the array/linked list.