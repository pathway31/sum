import os
import re
import sys
import subprocess

PATH_TO_DATA_DIR = "data"
PATH_TO_TIMES_FILE = PATH_TO_DATA_DIR + "/times.data"
PATH_TO_PLOT_SCRIPT = "plot.sh"

class InputRange:
    def __init__(self, min, max, incr):
        self.min = min
        self.max = max
        self.incr = incr

    def parse(string):
        expr = re.compile(r"(\d+):(\d+),(\d+)")
        match = expr.match(string)
        if match is None:
            return None

        min = int(match.group(1))
        max = int(match.group(2))
        incr = int(match.group(3))
        return InputRange(min, max, incr)

def get_cpus_to_run_bench_on():
    CPU_COL = 0
    CORE_COL = 1

    output = subprocess.run(["lscpu", "-p"], capture_output=True).stdout

    core_to_cpus = {}
    for line in output.decode().splitlines():
        if "#" in line:
            continue
            
        cols = line.split(",")
        cpu = int(cols[CPU_COL])
        core = int(cols[CORE_COL])
        if core in core_to_cpus:
            core_to_cpus[core].append(cpu)
        else:
            core_to_cpus[core] = [cpu]

    cores = []
    for core in core_to_cpus.keys():
        cores.append(core)
    cores.sort()

    # Try to pick the third core in the cores list if it exists, it can't ever be 
    # core 0 or core 1 because the cpus list is sorted above
    # https://manuel.bernhardt.io/posts/2023-11-16-core-pinning/
    #
    # If the CPU has a hybrid arch, there's no guarantee as to which kind of core
    # will be chosen
    DESIRED_CORE_IDX = 2
    core = None
    if len(cores) == 0: # shouldn't ever happen
        core = 0
    elif len(cores) <= DESIRED_CORE_IDX: # use core 0 or 1 only if you have to
        core = cores[-1]
    else:
        core = cores[DESIRED_CORE_IDX]

    # A single core can have more than one logical CPU if the core supports some kind of SMT
    cpus = ""
    cpus_of_core = core_to_cpus[core]
    for i in range(0, len(cpus_of_core)):
        cpus += str(cpus_of_core[i])
        if i != len(cpus_of_core)-1:
            cpus += ","

    return cpus

# This function allows the benchmark to function correctly even if some of the desired
# perf events are typo'd or unsupported by the CPU. Passing an event to perf, when the
# event isn't found in 'sudo perf list', like this:
#     perf record -e <some unrecognized event name>
# will error out and the benchmark won't be run at all.
def filter_perf_events(desired_perf_events):
    # --no-desc is broken on some newer versions of perf, which means
    # the regex will never match and all perf events will get filtered 
    # out
    #
    # https://patchew.org/linux/20240517141427.1905691-1-leitao@debian.org/  
    #
    # "sudo perf list" reports all available perf events, "perf list" reports 
    # only a small subset due to security reasons
    #available_perf_events = subprocess.run(
    #    ["sudo", "perf", "list", "--no-desc"], 
    #    capture_output=True
    #).stdout.decode()
    #events = []
    #event_expr = re.compile(r"\s*([\w\-\.]+)\s+\[")
    #for line in available_perf_events.splitlines():
        #match = event_expr.match(line)
        #if match is None:
            #continue
        #event = match.group(1)
        #if event not in desired_perf_events:
            #continue
        #events.append(event)
    #return events

    # Coarser but still works
    available_perf_events = subprocess.run(
        ["sudo", "perf", "list"], 
        capture_output=True
    ).stdout.decode()

    events = []
    for event in desired_perf_events:
        if available_perf_events.find(event) != -1:
            events.append(event)

    return events

def create_perf_event_string(perf_event_names):
    if perf_event_names == "":
        return ""

    string = ""
    for event in perf_event_names:
        string += event
        string += ","
    string = string[:-1] # remove the trailing ','

    return string

# Both the user and perf report can add whitespace to function names,
# so strip all whitespace to normalize them
def normalize_function_name(function_name):
    return function_name.replace(" ", "")

def parse_perf_report(perf_report, function_names):    
    cols_expr = re.compile(r"\s*(\d+\.\d+)%\s*[\S+\s+]+\[\S+\]\s*(\S+)")
    header_expr = re.compile(r"#[\s\S]*of event \'([\s\S]+)\'[\s\S]*")
    
    event_name = None
    name_to_percent = None
    event_name_to_row = {}
    no_headers_encountered_yet = True
    for line in perf_report.splitlines():

        match = header_expr.match(line)
        if match is not None:

            # Write out the data that's been gathered for the event
            if no_headers_encountered_yet is False:
                row = ""
                for name in function_names:
                    row += str(name_to_percent[name]) + " "
                event_name_to_row[event_name] = row

            # Update which event the upcoming data will be associated with
            event_name = match.group(1)

            # Reset (or initialize) name_to_percent map
            # 0.0 percent is used as the initial value because a function name 
            # may not appear in the perf report output because it was was under 
            # the threshold of perf's reporting, got inlined, or was typo'd by
            # the user
            name_to_percent = {}
            for name in function_names:
                name_to_percent[name] = 0.0 

            no_headers_encountered_yet = False
            continue

        match = cols_expr.match(line)
        if match is None:
            continue

        percent = match.group(1)
        function_name = normalize_function_name(match.group(2))
        if function_name not in name_to_percent:
            continue
        name_to_percent[function_name] = percent;

    if no_headers_encountered_yet is False:
        row = ""
        for name in function_names:
            row += str(name_to_percent[name]) + " "
        event_name_to_row[event_name] = row

    return event_name_to_row

def get_gnuplot_cmds_to_plot_times(time_unit, input_name, input_display_name, min_input, safe_to_fit):
    FROM_SECONDS_TO_OTHER_UNIT = {
        "s": 1.0,
        "ms": 1000.0,
        "us": 1000000.0,
    }
    from_s_to_unit = FROM_SECONDS_TO_OTHER_UNIT[time_unit]

    cmds = ""
    cmds += "set title noenhanced;\n"
    cmds += "set title 'Time to Find the Sum of All Integers\nin an Array and a Linked List';\n"
    cmds += "set datafile missing '0';\n"
    cmds += "set pointsize 0.5;\n"
    cmds += "set key noenhanced;\n"; # means that snake_case function names don't get subscripted
    cmds += "set key outside;\n"
    cmds += "set xtics rotate;\n" # stops larger input ranges from crowding horizontally
    cmds += "set xlabel noenhanced;\n"
    cmds += "set xlabel '" + input_display_name + "';\n";
    cmds += "set ylabel 'Time (" + time_unit + ")';\n";
    if safe_to_fit:
        cmds += "set fit quiet;\n"  
        cmds += "set fit maxiter 300;\n"    
    cmds += "\n"

    with open(PATH_TO_TIMES_FILE, "r") as file:
        header = file.readline()
        function_names = header.split()
        assert(function_names[0] == "#")
        assert(function_names[1] == input_name)
    
        for i in range(2, len(function_names)):
            if safe_to_fit:
                # x-min_input adjusts the fitting so it works correctly
                # https://stackoverflow.com/questions/66645523/linear-fit-with-gnuplot-producing-incorrect-results
                cmds += "f" + str(i) + "(x) = a" + str(i) + "*(x-" + str(min_input) + ") + b" + str(i) + ";\n"
                cmds += "fit f" + str(i) + "(x) '" + PATH_TO_TIMES_FILE + "' u 1:(\\$" + str(i) + "*" + str(from_s_to_unit) + ") via a" + str(i) + ", b" + str(i) + ";\n"
                cmds += "\n"

        cmds += "plot "
        for i in range(2, len(function_names)):
            cmds += "'" + PATH_TO_TIMES_FILE +"' u " + "1:(\\$" + str(i) + "*" + str(from_s_to_unit) + ") title '" + function_names[i] + "' with points pointtype 5"
            if safe_to_fit:
                cmds += ", f" + str(i) + "(x) notitle"

            if i != len(function_names)-1:
                cmds += ", "
            else:
                cmds += ";"

    return cmds

def get_gnuplot_cmds_to_plot_speedup(input_display_name, safe_to_fit):
    cmds = ""
    cmds += "set title noenhanced;\n"
    cmds += "set title 'How Many Times Faster It Is to Sum All Integers\nin an Array Than All Integers in a Linked List';\n"
    cmds += "set datafile missing '0';\n"
    cmds += "set pointsize 0.5;\n"
    cmds += "set key noenhanced;\n"
    cmds += "set key outside;\n"
    cmds += "set xtics rotate;\n" 
    cmds += "set xlabel '" + input_display_name + "';\n";
    cmds += "set ylabel 'Times faster';\n"
    cmds += "set format y '%16.1fx';\n"
    if safe_to_fit:
        cmds += "set fit quiet;\n"
        cmds += "set fit maxiter 300;\n"
    cmds += "\n"
    cmds += "f(x) = a*x + b;\n"
    cmds += "speedup(arr_time, ll_time) = ll_time/arr_time < 1.0 ? -arr_time/ll_time : ll_time/arr_time;\n"
    if safe_to_fit:
        cmds += "fit f(x) 'data/times.data' u 1:(speedup(\\$2, \\$3)) via a, b;\n"
        cmds += "\n"
    cmds += "plot 'data/times.data' u 1:(speedup(\\$2, \\$3)) notitle with points pointtype 5, f(x) notitle;"
    return cmds

def get_gnuplot_cmds_to_plot_events(input_name, input_display_name, min_input, event_name, safe_to_fit):    
    cmds = ""
    cmds += "set title noenhanced;\n"
    cmds += "set title 'Frequency of Perf Event ''" + event_name + "''\nWhile Summing All Integers in an Array and a Linked List';\n"
    cmds += "set datafile missing '0';\n"
    cmds += "set pointsize 0.5;\n"
    cmds += "set key noenhanced;\n" # means that snake_case function names don't get subscripted
    cmds += "set key outside;\n"
    cmds += "set xtics rotate;\n" # stops larger input ranges from crowding horizontally 
    cmds += "set xlabel noenhanced;\n"
    cmds += "set xlabel '" + input_display_name + "';\n"
    cmds += "set ylabel noenhanced;\n"
    cmds += "set ylabel 'Percentage of all samples';\n"
    cmds += r"set format y '%16.1f\\%%';" + "\n"
    if safe_to_fit:
        cmds += "set fit quiet;\n"
        cmds += "set fit maxiter 300;\n"
    cmds += "\n"

    path_to_event_file = PATH_TO_DATA_DIR + "/" + event_name + ".data"
    with open(path_to_event_file, "r") as file:
        header = file.readline()
        function_names = header.split()
        assert(function_names[0] == "#")
        assert(function_names[1] == input_name)
    
        if safe_to_fit:
            for i in range(2, len(function_names)):
                cmds += "f" + str(i) + "(x) = a" + str(i) + "*(x-" + str(min_input) + ") + b" + str(i) + ";\n"
                cmds += "fit f" + str(i) + "(x) '" + path_to_event_file + "' u 1:" + str(i) + " via a" + str(i) + ", b" + str(i) + ";\n"
                cmds += "\n"

        cmds += "plot "
        for i in range(2, len(function_names)):
            cmds += "'" + path_to_event_file + "' u " + "1:" + str(i) + " title '" + function_names[i] + "' with points pointtype 5"
            if safe_to_fit:
                cmds += ", f" + str(i) + "(x) notitle"

            if i != len(function_names)-1:
                cmds += ", "
            else:
                cmds += ";"

    return cmds

def get_plot_script(time_unit, input_name, input_display_name, input_range, perf_event_names, record_perf_events):
    cmds = ""
    safe_to_fit = input_range.min + input_range.incr <= input_range.max # can fit if there's more than one input

    gp_time_cmds = get_gnuplot_cmds_to_plot_times(time_unit, input_name, input_display_name, input_range.min, safe_to_fit)
    cmds += "gnuplot -p -e \"" + gp_time_cmds + "\"" 
    cmds += "\n"
    cmds += "\n"

    gp_speedup_cmds = get_gnuplot_cmds_to_plot_speedup(input_display_name, safe_to_fit)
    cmds += "gnuplot -p -e \"" + gp_speedup_cmds + "\""
    cmds += "\n"
    cmds += "\n"

    if record_perf_events:
        for event_name in perf_event_names:
            gp_event_cmds = get_gnuplot_cmds_to_plot_events(input_name, input_display_name, input_range.min, event_name, safe_to_fit)
            cmds += "gnuplot -p -e \"" + gp_event_cmds + "\""
            cmds += "\n"
            cmds += "\n"
    
    cmds += "rm -f fit.log"
    return cmds

PROGRAM_NAME_ARGPOS       = 1
INPUT_RANGE_ARGPOS        = 2
NUM_RUNS_ARGPOS           = 3
TIME_UNIT_NAME_ARGPOS     = 4
INPUT_NAME_ARGPOS         = 5
INPUT_DISPLAY_NAME_ARGPOS = 6
FUNCTION_NAMES_ARGPOS     = 7
RECORD_PERF_EVENTS_ARGPOS = 8
PERF_EVENT_NAMES_ARGPOS   = 9
PERF_RECORD_FREQ          = 10
EXPECTED_NUM_ARGS         = 10+1 # +1 because the name of the script is the 0th arg

if len(sys.argv) < EXPECTED_NUM_ARGS:
    print("Error: Not enough arguments. Expected " + EXPECTED_NUM_ARGS-1 + " arguments, only got " + str(len(sys.argv)-1) )
    exit()

program            = sys.argv[PROGRAM_NAME_ARGPOS]
input_range        = InputRange.parse(sys.argv[INPUT_RANGE_ARGPOS])
num_runs           = int(sys.argv[NUM_RUNS_ARGPOS])
time_unit          = sys.argv[TIME_UNIT_NAME_ARGPOS]
input_name         = sys.argv[INPUT_NAME_ARGPOS]
input_display_name = sys.argv[INPUT_DISPLAY_NAME_ARGPOS]

# '/' is used to separate function names because it's not allowed in 
# identifiers for most (all?) programming languages
function_names = []
for name in sys.argv[FUNCTION_NAMES_ARGPOS].split("/"):
    normalized = normalize_function_name(name) 
    function_names.append(normalized)

record_perf_events = None
if sys.argv[RECORD_PERF_EVENTS_ARGPOS] == "true":
    record_perf_events = True
else:
    record_perf_events = False

perf_events = sys.argv[PERF_EVENT_NAMES_ARGPOS].split(",")
perf_events = filter_perf_events(perf_events)

perf_record_freq = sys.argv[PERF_RECORD_FREQ] # can be an integer or the string 'max'

os.system("gcc " + program + ".c -Wall -O3 -o " + program)
os.system("rm -rf " + PATH_TO_DATA_DIR)
os.system("mkdir " + PATH_TO_DATA_DIR)

# Create the headers for each data file
header = "# "
header += input_name + " "
for function_name in function_names:
    header += function_name + " "
header += "\n"

# Write headers to each data file
with open(PATH_TO_TIMES_FILE, "a") as file:
    file.write(header)
if record_perf_events:
    for event in perf_events:
        path = PATH_TO_DATA_DIR + "/" + event + ".data"
        with open(path, "a") as file:
            file.write(header)

# Run the benchmarked program
# 
# * Pinning the benchmarked program to one core makes the results 
#   more consistent across runs. If the program isn't pinned, then 
#   the scheduler can move it to different cores throughout its 
#   execution, or keep it on the core that the OS is using for all 
#   of its other tasks. Either happening can extend the program's 
#   runtime indeterminately and contaminate perf event data related
#   to cache usage.
#
# * perf's sampling does introduce some additional overhead, but
#   not a noticeable amount- benchmarks run with and without perf 
#   record seem to have identical runtimes, so any overhead doesn't 
#   seem to be distinguishable from noise.
# 
cpus = get_cpus_to_run_bench_on()
input = input_range.min
while input <= input_range.max:
    print("Running with len = " + str(input))
    if not record_perf_events:
        cmds = ["taskset", "-c", cpus, "./" + program, str(input)]
        for run in range(0, num_runs):
            with open(PATH_TO_TIMES_FILE, "a") as times_file:
                subprocess.run(cmds, stdout=times_file)
    else:
        cmds = ["sudo", "perf", "record", "-F", perf_record_freq]
        perf_event_string = create_perf_event_string(perf_events)
        if perf_event_string != "":
            cmds.append("-e")
            cmds.append(perf_event_string)
        cmds.extend(["--", "taskset", "-c", cpus, "./" + program, str(input)])

        for run in range(0, num_runs):
            with open(PATH_TO_TIMES_FILE, "a") as times_file:
                subprocess.run(cmds, stdout=times_file)

            perf_report = subprocess.run(
                ["sudo", "perf", "report", "--stdio"], 
                capture_output=True
            ).stdout.decode()

            event_names_to_data_rows = parse_perf_report(perf_report, function_names)
            for (event_name, row) in event_names_to_data_rows.items():
                    filename = str(event_name) + ".data"
                    path = PATH_TO_DATA_DIR + "/" + filename
                    with open(path, "a") as file:
                        file.write(str(input) + " " + row + "\n")

    input += input_range.incr

# Clean up any files produced from benchmarking
os.system("rm -f " + program)
os.system("rm -f perf.data")
os.system("rm -f perf.data.old")

# Generate the plot script and execute it
os.system("rm -f " + PATH_TO_PLOT_SCRIPT)
with open(PATH_TO_PLOT_SCRIPT, "a") as script:
    cmds = get_plot_script(time_unit, input_name, input_display_name, input_range, perf_events, record_perf_events)
    script.write(cmds)
os.system("chmod +x " + PATH_TO_PLOT_SCRIPT)
os.system("./" + PATH_TO_PLOT_SCRIPT)