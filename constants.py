# constants.py

VERSION_TYPE_RELEASE  = "release"
VERSION_TYPE_SNAPSHOT = "snapshot"
VERSION_TYPE_BETA     = "old_beta"
VERSION_TYPE_ALPHA    = "old_alpha"

DEFAULT_JVM_ARGS = (
    "-Xmx2G -XX:+UnlockExperimentalVMOptions -XX:+UseG1GC "
    "-XX:G1NewSizePercent=20 -XX:G1ReservePercent=20 "
    "-XX:MaxGCPauseMillis=50 -XX:G1HeapRegionSize=32M"
)

JAVA_PATHS = {
    8:  r"C:\Program Files\Java\jre1.8.0_491\bin\javaw.exe",
    17: r"C:\Program Files\Java\jdk-17\bin\javaw.exe",
    21: r"C:\Program Files\Java\jdk-21\bin\javaw.exe",
}