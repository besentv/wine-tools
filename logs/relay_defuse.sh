# This skrip was directly taken from the Wine wiki.

# Make grep go fast
LANG=C
# Find top ten calls
freq=`grep ':Ret ' | sed 's/(.*//;s/.* //' | sort | uniq -c | sort -n | tail -n 100 | awk '{print $2}' | tr '\012' ';'`
cat > quiet.reg << _EOF
REGEDIT4

[HKEY_CURRENT_USER\Software\Wine\Debug]
"RelayExclude"="ntdll.RtlEnterCriticalSection;ntdll.RtlTryEnterCriticalSection;ntdll.RtlLeaveCriticalSection;kernel32.48;kernel32.49;kernel32.94;kernel32.95;kernel32.96;kernel32.97;kernel32.98;kernel32.TlsGetValue;kernel32.TlsSetValue;kernel32.FlsGetValue;kernel32.FlsSetValue;kernel32.SetLastError;$freq"

_EOF

./build/x64/wine regedit quiet.reg
