"""Parse filters for miscellaneous error messages."""

FILTERS: dict[str, str] = {
    r"CBENCH WARNING:\s+(.*)$":
        "CBENCH WARNING: $1",

    r"HPL ERROR from process #\s*(\d+), on line":
        "HPL ERROR from process #$1",

    r">>> \[.*\] Memory allocation failed for A, x and b.":
        "HPL Memory allocation failure",

    r">>> Illegal input in file HPL.dat":
        "Illegal input in file HPL.dat",

    r"Memory allocation failed\..*tried to alloc.\s+(\d+)\s+bytes":
        "Memory allocation failed, tried to alloc $1 bytes",

    r"forrtl:\s+error\s+\((\S+)\):\s+process\s+killed\s+\((\S+)\)":
        "FORRTL: error $1, process killed via $2",

    r"^(.*): error while loading shared libraries:\s+(\S+):\s+cannot open shared object file:(.*)$":
        "ERROR loading shared library: $2",

    r"MX: assertion: <<Bailing out>>  failed at line 1125, file ./../mx__lib.c":
        "MYRINET MX ASSERTION: <<Bailing out>>",
}
