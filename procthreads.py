"""procthreads.py: processes versus threads, observed and measured.

Run it from a terminal in the folder that holds this file:
    python procthreads.py           (Windows)   or   python3 procthreads.py   (macOS / Linux)
    python procthreads.py --quick   uses smaller tasks, for slow computers
    python procthreads.py --pause   keeps five threads alive so you can count them with an OS tool

Your work is marked with TODO. Everything else already works: run the file before you change
anything; each experiment that reaches an unwritten TODO says which one and the rest still run.
"""

import multiprocessing  # starts real, separate operating-system processes
import os  # asks the OS for process IDs: os.getpid() and os.getppid()
import sys  # reads the command-line words and the interpreter's details
import threading  # starts extra threads inside this one process
import time  # measures elapsed time and lets a task sleep
from concurrent.futures import ProcessPoolExecutor, ThreadPoolExecutor  # ready-made pools of worker processes and worker threads

SHARED = []  # a global list: the experiment checks who can see changes made to it
TASKS = 8  # the CPU experiment always splits the same total work into 8 equal tasks
TASK_SIZE = 1_200_000 if "--quick" in sys.argv else 6_000_000  # loop iterations per task; --quick makes each task 5 times smaller
WORKER_COUNTS = (1, 2, 4, 8, 16)  # B-i: test whether 16 workers help with only 8 tasks.
# the pool sizes the experiments try


class NotWrittenYet(Exception):  # a custom error the starter raises wherever a TODO has not been written yet
    pass  # it needs no extra behavior; its name and message say everything


# ---------------------------------------------------------------------------
# Experiment 1: who am I? (process ID, parent ID, thread ID)
# ---------------------------------------------------------------------------
def report_identity(kind, number):  # runs inside each new thread or process and prints its identity
    print(f"  {kind} {number}: pid={os.getpid()}  ppid={os.getppid()}  thread id={threading.get_native_id()}", flush=True)  # flush: print now, not later


def experiment_identity():  # starts three threads and three processes that each report who they are
    print("Experiment 1: identity")  # a title
    report_identity("main", 0)  # the main thread of the original process goes first
    threads = [threading.Thread(target=report_identity, args=("thread", i)) for i in range(1, 4)]  # three thread objects (not running yet)
    for t in threads:  # start each one
        t.start()  # the OS now has a new thread in this same process
    for t in threads:  # wait for each one
        t.join()  # join() returns only when that thread has finished
    # TODO 1: do the same with three PROCESSES. multiprocessing.Process takes the same target= and args= as threading.Thread,
    #         and has the same start() and join(). Label them ("process", 1), ("process", 2), ("process", 3).
    processes = [multiprocessing.Process(target=report_identity, args=("process", i)) for i in range(1, 4)]
    for process in processes:
        process.start()
    for process in processes:
        process.join()


# ---------------------------------------------------------------------------
# Experiment 2: who can see my memory?
# ---------------------------------------------------------------------------
def add_marker(label):  # runs inside a new thread or a new process
    SHARED.append(label)  # change the global list...
    print(f"  inside the {label}: SHARED = {SHARED}", flush=True)  # ...and show what this worker sees


def experiment_sharing():  # one thread and one process each try to change the global list
    print(f"\nExperiment 2: sharing   (process start method: {multiprocessing.get_start_method()})")  # a title plus how new processes are made
    SHARED.clear()  # start from an empty list in case this function runs twice
    SHARED.append("main")  # the main thread adds its own marker first
    # TODO 2: create ONE thread that runs add_marker("thread"), start it and join it.
    #         Then create ONE process that runs add_marker("process"), start it and join it.
    thread = threading.Thread(target=add_marker, args=("thread",))
    thread.start()
    thread.join()
    process = multiprocessing.Process(target=add_marker, args=("process",))
    process.start()
    process.join()
    print(f"  back in main: SHARED = {SHARED}")  # what the main thread sees after both workers finished


# ---------------------------------------------------------------------------
# Experiments 3 and 4: how long does the same work take?
# ---------------------------------------------------------------------------
def busy_work(n):  # CPU-bound: pure calculation, no waiting at all
    total = 0  # running total
    for i in range(n):  # n trips around the loop
        total += i * i % 7  # a little arithmetic, just to keep the processor busy
    return total  # the answer (the experiments only care how long it took)


def sleepy_work(seconds):  # I/O-bound stand-in: the task spends its whole life waiting
    time.sleep(seconds)  # the thread blocks, exactly as if it were waiting for a disk or the network
    return seconds  # nothing useful to return


def run_with_threads(workers, func, tasks):  # runs func on every task using a pool of threads; returns seconds taken
    start = time.perf_counter()  # a high-resolution clock reading
    with ThreadPoolExecutor(max_workers=workers) as pool:  # creates `workers` threads inside this process
        list(pool.map(func, tasks))  # hands out the tasks and waits for all results
    return time.perf_counter() - start  # elapsed seconds, pool start-up included


def run_with_processes(workers, func, tasks):  # the same, using a pool of separate processes
    # TODO 3: copy the body of run_with_threads, but use ProcessPoolExecutor instead of ThreadPoolExecutor.
    start = time.perf_counter()
    with ProcessPoolExecutor(max_workers=workers) as pool:
        list(pool.map(func, tasks))
    return time.perf_counter() - start


def amdahl_fraction(speedup, n):  # solves Amdahl's law for f, the parallel fraction, given a measured speedup on n cores
    # TODO 4b: solve speedup = 1 / ((1 - f) + f / n) for f and return it. (Do it on paper first; Problem 7 practises this.)
    return (1 - 1 / speedup) / (1 - 1 / n)


def amdahl_speedup(f, n):  # Amdahl's law: the best speedup on n cores when a fraction f of the work is parallel
    # TODO 4a: return Amdahl's speedup for parallel fraction f on n cores.
    return 1 / ((1 - f) + f / n)


def experiment_cpu():  # the same CPU-bound work with more and more workers
    print(f"\nExperiment 3: CPU-bound work ({TASKS} tasks x {TASK_SIZE:,} loop steps)")  # a title
    gil = getattr(sys, "_is_gil_enabled", lambda: True)()  # newer Pythons can report whether the global interpreter lock is on
    print(f"  Python {sys.version.split()[0]}, global interpreter lock enabled: {gil}, logical CPUs: {os.cpu_count()}")  # the facts behind the numbers
    speedups = {}  # remembers the process speedups for the Amdahl calculation
    for kind, runner in (("threads", run_with_threads), ("processes", run_with_processes)):  # try both kinds of worker
        base = None  # the one-worker time, measured first
        for workers in WORKER_COUNTS:  # 1, 2, 4, 8 workers
            seconds = runner(workers, busy_work, [TASK_SIZE] * TASKS)  # run the whole job
            base = base or seconds  # the first run (1 worker) becomes the baseline
            speedup = base / seconds  # how many times faster than one worker
            if kind == "processes":  # keep the process speedups
                speedups[workers] = speedup  # for Amdahl below
            print(f"  {kind:<10} workers={workers}  time={seconds:6.2f} s  speedup={speedup:5.2f}")  # one row of the table
    f = amdahl_fraction(speedups[4], 4)  # the parallel fraction implied by the 4-worker speedup
    print(f"  Amdahl: f from the 4-process speedup = {f:.3f}; predicted 8-process speedup = {amdahl_speedup(f, 8):.2f}; measured = {speedups[8]:.2f}")  # prediction vs reality


def experiment_io():  # the same waiting-bound work with 1 thread and with 8 threads
    print("\nExperiment 4: I/O-bound work (8 tasks, each waits 0.25 s)")  # a title
    for workers in (1, 8):  # one thread, then eight
        seconds = run_with_threads(workers, sleepy_work, [0.25] * 8)  # run the eight waiting tasks
        print(f"  threads    workers={workers}  time={seconds:6.2f} s")  # one row


# ---------------------------------------------------------------------------
# Experiment 5 (--pause): count the threads with an operating-system tool
# ---------------------------------------------------------------------------
def experiment_pause():  # keeps four extra threads alive so the OS can be asked about them
    stop = threading.Event()  # a flag the extra threads wait on
    extra = [threading.Thread(target=stop.wait, daemon=True) for _ in range(4)]  # four threads that simply wait
    for t in extra:  # start them
        t.start()  # each one is now a real thread, blocked on the event
    pid = os.getpid()  # this process's ID, needed by the OS tools
    print(f"\nExperiment 5: this process (pid {pid}) now has the main thread plus 4 waiting threads.")  # what to look for
    print(f"  macOS:   ps -M -p {pid}   (count the lines below the header)")  # macOS lists one line per thread
    print(f"  Linux:   ps -o nlwp= -p {pid}")  # nlwp = number of lightweight processes (threads)
    print(f"  Windows: (Get-Process -Id {pid}).Threads.Count   (in a second PowerShell window)")  # PowerShell counts them directly
    input("  Press Enter here when you have counted them... ")  # waits for the student
    stop.set()  # release the four threads so they finish


def main():  # runs the experiments in order
    if "--pause" in sys.argv:  # python procthreads.py --pause
        experiment_pause()  # only the thread-counting experiment
        return  # and stop
    for experiment in (experiment_identity, experiment_sharing, experiment_cpu, experiment_io):  # 1, 2, 3, 4 in order
        try:  # run one experiment
            experiment()  # if it reaches an unwritten TODO, NotWrittenYet jumps to the except below
        except NotWrittenYet as missing:  # a TODO was reached
            print(f"  -> stopped here: {missing}")  # say which one, then carry on with the next experiment


if __name__ == "__main__":  # true only in the original process; new processes on macOS and Windows re-import this file and skip this block
    main()  # start the program