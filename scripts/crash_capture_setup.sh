#!/usr/bin/env bash
# Crash capture setup for the CachyOS box, after the 2026-08-18 03:19 hard lockup.
#
# WHY: the freeze left no record at all, because three switches were independently off:
#   1. `nowatchdog` on the kernel cmdline  -> hardlockup detector never armed, so a
#      wedged CPU sat frozen instead of panicking (matches what was observed:
#      found frozen, power button held).
#   2. CONFIG_EFI_VARS_PSTORE_DEFAULT_DISABLE=y -> pstore support is compiled in but
#      inert unless efi_pstore.pstore_disable=0 is passed. `dmesg | grep pstore` was empty.
#   3. systemd-pstore.service disabled -> even a captured record would not be harvested
#      off NVRAM into /var/lib/systemd/pstore.
# Fixing any one alone still yields silence. All three are needed.
#
# SAFE BY DEFAULT: dry-run unless --apply is passed. Every file touched is backed up
# to <file>.bak-<timestamp> and the rollback is printed at the end.
#
# Run as root:  sudo bash crash_capture_setup.sh            (preview)
#               sudo bash crash_capture_setup.sh --apply    (commit)
set -euo pipefail

APPLY=0
[ "${1:-}" = "--apply" ] && APPLY=1
STAMP=$(date +%Y%m%d-%H%M%S)
BACKUPS=()

if [ "$(id -u)" -ne 0 ]; then
  echo "ERROR: must run as root (sudo bash $0 ${1:-})" >&2
  exit 1
fi

say()  { printf '\n\033[1m%s\033[0m\n' "$*"; }
note() { printf '  %s\n' "$*"; }
act()  { if [ "$APPLY" -eq 1 ]; then printf '  \033[32mAPPLY\033[0m %s\n' "$*"; else printf '  \033[33mWOULD\033[0m %s\n' "$*"; fi; }

backup() {
  local f="$1"
  [ -e "$f" ] || return 0
  if [ "$APPLY" -eq 1 ]; then
    cp -a "$f" "$f.bak-$STAMP"
    BACKUPS+=("$f.bak-$STAMP")
    note "backed up: $f -> $f.bak-$STAMP"
  else
    # say WOULD, not "backup:" — in a dry run no file is written, and a message
    # that reads like it happened is exactly the kind of thing that gets trusted later
    note "WOULD back up: $f -> $f.bak-$STAMP"
  fi
}

# ---------------------------------------------------------------- 1. cmdline

# What we want changed on the kernel command line:
#   remove  nowatchdog                  -> arm the hardlockup detector
#   add     efi_pstore.pstore_disable=0 -> activate the EFI pstore backend
#   remove  quiet splash                -> a panic is legible ON SCREEN. For a box that
#                                          freezes with no disk record, the monitor is
#                                          the only channel left; this is the single
#                                          highest-value change here.
CMDLINE_ADD="efi_pstore.pstore_disable=0"
CMDLINE_DROP_RE='(^|[[:space:]])(nowatchdog|quiet|splash)([[:space:]]|$)'

rewrite_cmdline() {
  # stdin: original cmdline string; stdout: rewritten
  local s
  s=$(cat)
  while [[ "$s" =~ $CMDLINE_DROP_RE ]]; do
    s=$(printf '%s' "$s" | sed -E "s/$CMDLINE_DROP_RE/\1\3/")
  done
  printf '%s' "$s" | grep -q -- "$CMDLINE_ADD" || s="$s $CMDLINE_ADD"
  # squeeze whitespace
  printf '%s' "$s" | tr -s ' ' | sed -E 's/^ +| +$//g'
}

say "[1/4] Kernel command line"
note "current: $(cat /proc/cmdline)"

BOOTLOADER="unknown"
if [ -d /boot/loader/entries ] && compgen -G "/boot/loader/entries/*.conf" >/dev/null; then
  BOOTLOADER="systemd-boot"
elif [ -f /etc/default/limine ] || [ -f /boot/limine.conf ]; then
  BOOTLOADER="limine"
elif [ -f /etc/default/grub ]; then
  BOOTLOADER="grub"
fi
note "detected bootloader: $BOOTLOADER"

case "$BOOTLOADER" in
  systemd-boot)
    # CachyOS often manages entries via sdboot-manage; if its config drives the
    # options line, edit THAT, or the next regeneration silently reverts us.
    if [ -f /etc/sdboot-manage.conf ] && grep -qE '^\s*LINUX_OPTIONS=' /etc/sdboot-manage.conf; then
      note "sdboot-manage owns the options line — editing /etc/sdboot-manage.conf"
      cur=$(grep -E '^\s*LINUX_OPTIONS=' /etc/sdboot-manage.conf | head -1 | sed -E 's/^\s*LINUX_OPTIONS="?(.*)"?\s*$/\1/' | sed 's/"$//')
      new=$(printf '%s' "$cur" | rewrite_cmdline)
      note "  from: $cur"
      note "    to: $new"
      backup /etc/sdboot-manage.conf
      act "rewrite LINUX_OPTIONS in /etc/sdboot-manage.conf, then run: sdboot-manage gen"
      if [ "$APPLY" -eq 1 ]; then
        sed -i -E "s|^\s*LINUX_OPTIONS=.*|LINUX_OPTIONS=\"$new\"|" /etc/sdboot-manage.conf
        sdboot-manage gen
      fi
    else
      for e in /boot/loader/entries/*.conf; do
        grep -qE '^\s*options\s' "$e" || continue
        case "$e" in *fallback*) note "skipping fallback entry: $e"; continue;; esac
        cur=$(grep -E '^\s*options\s' "$e" | head -1 | sed -E 's/^\s*options\s+//')
        new=$(printf '%s' "$cur" | rewrite_cmdline)
        note "entry: $e"
        note "  from: $cur"
        note "    to: $new"
        backup "$e"
        act "rewrite options line in $e"
        [ "$APPLY" -eq 1 ] && sed -i -E "s|^\s*options\s+.*|options $new|" "$e"
      done
    fi
    ;;
  grub)
    cur=$(grep -E '^GRUB_CMDLINE_LINUX_DEFAULT=' /etc/default/grub | head -1 | sed -E 's/^GRUB_CMDLINE_LINUX_DEFAULT="(.*)"$/\1/')
    new=$(printf '%s' "$cur" | rewrite_cmdline)
    note "  from: $cur"
    note "    to: $new"
    backup /etc/default/grub
    act "rewrite GRUB_CMDLINE_LINUX_DEFAULT, then run: grub-mkconfig -o /boot/grub/grub.cfg"
    if [ "$APPLY" -eq 1 ]; then
      sed -i -E "s|^GRUB_CMDLINE_LINUX_DEFAULT=.*|GRUB_CMDLINE_LINUX_DEFAULT=\"$new\"|" /etc/default/grub
      grub-mkconfig -o /boot/grub/grub.cfg
    fi
    ;;
  limine)
    note "Limine detected. CachyOS drives this via /etc/default/limine + limine-update."
    # NOTE: the real config uses the APPEND form, KERNEL_CMDLINE[default]+="...",
    # not a plain '='. An earlier version of this script grepped for ']=' , matched
    # nothing, and — under `set -euo pipefail` — died silently right here with steps
    # 2-4 never running. Hence the '\+?' in the pattern and the '|| true' guards:
    # a no-match must be a reported condition, never an invisible exit.
    # REWRITTEN after an --apply run reported "line 34: from: 34" on a 3-line file —
    # the line number leaked into the value slot and the edit silently no-opped (sed
    # targeting a line that does not exist). The dry run one minute earlier, and a
    # direct grep afterwards, both correctly reported line 2. That discrepancy was
    # never explained, so this no longer uses line numbers, shell field-splitting, or
    # sed -i at all: python does an exact keyed substitution, and the result is VERIFIED
    # against the file on disk. If verification fails, the backup is restored and we abort.
    CONF=/etc/default/limine
    if [ -f "$CONF" ]; then
      MATCHES=$(grep -cE '^[[:space:]]*KERNEL_CMDLINE\[[^]]*\][+]?=' "$CONF" || true)
      note "KERNEL_CMDLINE lines found: ${MATCHES:-0}"
      if [ "${MATCHES:-0}" -eq 0 ]; then
        note "!! No KERNEL_CMDLINE[...] line in $CONF."
        note "   Edit by hand: drop 'nowatchdog quiet splash', add '$CMDLINE_ADD',"
        note "   then run: limine-update"
      else
        # preview (never writes)
        python3 - "$CONF" "$CMDLINE_ADD" preview <<'PY'
import re, sys
conf, add, mode = sys.argv[1], sys.argv[2], sys.argv[3]
KEY = re.compile(r'^(\s*KERNEL_CMDLINE\[[^\]]*\][+]?=)"(.*)"\s*$')
DROP = {"nowatchdog", "quiet", "splash"}
for line in open(conf):
    m = KEY.match(line.rstrip("\n"))
    if not m:
        continue
    toks = [t for t in m.group(2).split() if t not in DROP]
    if add not in toks:
        toks.append(add)
    print("  from: " + m.group(2))
    print("    to: " + " ".join(toks))
PY
        act "rewrite $CONF (keyed substitution, then verify)"
        if [ "$APPLY" -eq 1 ]; then
          backup "$CONF"
          BAK="$CONF.bak-$STAMP"
          python3 - "$CONF" "$CMDLINE_ADD" apply <<'PY'
import re, sys
conf, add, mode = sys.argv[1], sys.argv[2], sys.argv[3]
KEY = re.compile(r'^(\s*KERNEL_CMDLINE\[[^\]]*\][+]?=)"(.*)"(\s*)$')
DROP = {"nowatchdog", "quiet", "splash"}
out, changed = [], 0
for line in open(conf):
    m = KEY.match(line.rstrip("\n"))
    if not m:
        out.append(line); continue
    toks = [t for t in m.group(2).split() if t not in DROP]
    if add not in toks:
        toks.append(add)
    out.append(f'{m.group(1)}"{" ".join(toks)}"{m.group(3)}\n')
    changed += 1
open(conf, "w").write("".join(out))
print(f"  rewrote {changed} line(s)")
PY
          # ---- verify on disk; restore and abort if anything is off ----
          FAIL=""
          grep -qE 'root=UUID=' "$CONF"                  || FAIL="$FAIL root=UUID-missing"
          grep -qE 'rootflags=subvol=' "$CONF"           || FAIL="$FAIL rootflags-missing"
          grep -q  "$CMDLINE_ADD" "$CONF"                || FAIL="$FAIL pstore-param-missing"
          grep -qE '(^|[[:space:]])nowatchdog([[:space:]]|")' "$CONF" && FAIL="$FAIL nowatchdog-still-present"
          grep -qE '^[[:space:]]*ESP_PATH=' "$CONF"      || FAIL="$FAIL ESP_PATH-lost"
          if [ -n "$FAIL" ]; then
            printf '  \033[31mVERIFY FAILED:%s — restoring backup, NOT running limine-update\033[0m\n' "$FAIL"
            cp -a "$BAK" "$CONF"
            echo "  $CONF restored from $BAK. Bootloader untouched. Aborting."
            exit 1
          fi
          note "verified: root=UUID + rootflags intact, nowatchdog gone, pstore param present"
          act "run: limine-update"
          limine-update
        fi
      fi
    fi
    ;;
  *)
    note "!! Bootloader not recognised. Edit the cmdline by hand:"
    note "   drop 'nowatchdog quiet splash', add '$CMDLINE_ADD'"
    ;;
esac

# ---------------------------------------------------------------- 2. sysctl

say "[2/4] Panic behaviour (sysctl)"
SYSCTL=/etc/sysctl.d/99-crash-capture.conf
note "writing $SYSCTL"
note "  kernel.panic=30          reboot 30s after a panic instead of sitting frozen"
note "  kernel.panic_on_oops=1   turn an oops into a panic so it is captured, not survived"
note "  kernel.hardlockup_panic=1 a wedged CPU panics (this is the case that bit us)"
note "  kernel.softlockup_panic=0 DELIBERATE: soft lockups false-positive under heavy"
note "                            IO/CPU, and this box runs long local builds. Log only."
backup "$SYSCTL"
act "install $SYSCTL"
if [ "$APPLY" -eq 1 ]; then
  cat > "$SYSCTL" <<'EOF'
# Crash capture — added after the 2026-08-18 03:19 hard lockup left no record.
# See scratchpad/crash_capture_setup.sh for the reasoning behind each value.
kernel.panic = 30
kernel.panic_on_oops = 1
kernel.hardlockup_panic = 1
# Left at 0 on purpose: soft lockups false-positive under sustained IO/CPU load,
# and a spurious reboot mid-build would be worse than the thing we are diagnosing.
kernel.softlockup_panic = 0
EOF
  sysctl -q --load="$SYSCTL" 2>/dev/null || true
fi

# ---------------------------------------------------------------- 3. pstore harvest

say "[3/4] pstore harvesting"
note "systemd-pstore.service moves panic records out of NVRAM into"
note "/var/lib/systemd/pstore on boot, so they survive and are readable."
act "systemctl enable systemd-pstore.service"
[ "$APPLY" -eq 1 ] && systemctl enable systemd-pstore.service >/dev/null 2>&1 || true

# ---------------------------------------------------------------- 4. memtest

say "[4/4] memtest86+ (the actual diagnostic)"
note "The 23:10:46 'BUG: Bad page state ... mapcount:-131072' is corruption of a page"
note "struct. RAM is the first thing to rule out, and it is the cheapest to test."
if pacman -Q memtest86+-efi >/dev/null 2>&1; then
  note "already installed"
else
  act "pacman -S --noconfirm memtest86+-efi   (adds a boot menu entry)"
  [ "$APPLY" -eq 1 ] && pacman -S --noconfirm memtest86+-efi || true
fi

# ---------------------------------------------------------------- summary

say "Summary"
if [ "$APPLY" -eq 1 ]; then
  echo "  Applied. A REBOOT is required for the cmdline changes to take effect."
  echo
  echo "  Verify after reboot:"
  echo "    cat /proc/cmdline                 # no 'nowatchdog', has $CMDLINE_ADD"
  echo "    sysctl kernel.hardlockup_panic    # 1"
  echo "    dmesg | grep -i pstore            # should NOT be empty now"
  echo "    cat /sys/module/kernel/parameters/panic 2>/dev/null || sysctl kernel.panic"
  echo
  echo "  Rollback:"
  for b in "${BACKUPS[@]:-}"; do
    [ -n "$b" ] && echo "    cp -a $b ${b%.bak-$STAMP}"
  done
  echo "    rm -f $SYSCTL"
  echo "    systemctl disable systemd-pstore.service"
  echo "    # then regenerate the bootloader config (sdboot-manage gen / grub-mkconfig / limine-update)"
else
  echo "  DRY RUN — nothing was changed. Re-run with --apply to commit."
fi
