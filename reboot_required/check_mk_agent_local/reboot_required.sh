#!/bin/bash
# Check if the node needs a reboot (kernel, services, containers).
# Uses needrestart if available, falls back to kernel comparison.

reboot_required=0
services_count=0
containers_count=0
reason=""

# Method 1: needrestart (preferred, comprehensive)
if command -v needrestart >/dev/null 2>&1; then
    nr_output=$(needrestart -b 2>/dev/null)
    kcur=$(echo "$nr_output" | grep "^NEEDRESTART-KCUR:" | awk '{print $2}')
    kexp=$(echo "$nr_output" | grep "^NEEDRESTART-KEXP:" | awk '{print $2}')
    uccur=$(echo "$nr_output" | grep "^NEEDRESTART-UCCUR:" | awk '{print $2}')
    ucexp=$(echo "$nr_output" | grep "^NEEDRESTART-UCEXP:" | awk '{print $2}')

    # Reboot needed if kernel or microcode differs
    if [ -n "$kcur" ] && [ -n "$kexp" ] && [ "$kcur" != "$kexp" ]; then
        reboot_required=1
        reason="kernel $kcur -> $kexp"
    fi
    if [ -n "$uccur" ] && [ -n "$ucexp" ] && [ "$uccur" != "$ucexp" ]; then
        reboot_required=1
        if [ -n "$reason" ]; then reason="$reason, "; fi
        reason="${reason}microcode $uccur -> $ucexp"
    fi

    # Count services needing restart
    services_count=$(echo "$nr_output" | grep -c "^NEEDRESTART-SVC:" 2>/dev/null)
    services_count=${services_count:-0}
    containers_count=$(echo "$nr_output" | grep -c "^NEEDRESTART-CONT:" 2>/dev/null)
    containers_count=${containers_count:-0}
# Method 2: /run/reboot-required (fallback)
elif [ -f /run/reboot-required ] || [ -f /var/run/reboot-required ]; then
    reboot_required=1
    reason="reboot-required file present"
    if [ -f /run/reboot-required.pkgs ] || [ -f /var/run/reboot-required.pkgs ]; then
        pkgs=$(cat /run/reboot-required.pkgs /var/run/reboot-required.pkgs 2>/dev/null | tr '\n' ',' | sed 's/,$//')
        reason="$reason ($pkgs)"
    fi
# Method 3: kernel comparison (fallback)
else
    running=$(uname -r)
    newest=$(ls /boot/vmlinuz-* 2>/dev/null | sed 's|/boot/vmlinuz-||' | sort -V | tail -1)
    if [ -n "$newest" ] && [ "$running" != "$newest" ]; then
        reboot_required=1
        reason="kernel $running -> $newest"
    fi
fi

# Build message
msg="No reboot required"
if [ $reboot_required -eq 1 ]; then
    msg="Reboot required: $reason"
    if [ "$services_count" -gt 0 ]; then
        msg="$msg; $services_count service(s) need restart"
    fi
    if [ "$containers_count" -gt 0 ]; then
        msg="$msg; $containers_count container(s) need restart"
    fi
else
    if [ "$services_count" -gt 0 ]; then
        msg="$services_count service(s) need restart (no full reboot needed)"
    fi
fi

echo "$reboot_required Reboot_Required reboot_required=$reboot_required $services_count - $msg"
