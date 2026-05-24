#!/bin/sh

mode="all"
TEMP_OUTPUT_FILE=$(mktemp)

trap 'rm -f "$TEMP_OUTPUT_FILE"' EXIT

while [ $# -gt 0 ]; do
  case "$1" in
    --src-only)
      mode="src"
      shift
      ;;
    --inc-only)
      mode="inc"
      shift
      ;;
    *)
      break
      ;;
  esac
done

expand() {
  for file in "$@"; do
    if [ ! -f "$file" ] || [ ! -r "$file" ]; then
      echo "Error: File not found or not readable: $file" >&2
      continue
    fi

    while IFS= read -r line || [ -n "$line" ]; do
      line=$(echo "$line" | sed 's/^[[:space:]]*//;s/[[:space:]]*$//')

      [ -z "$line" ] && continue

      case "$line" in
        *.list)
          expand "$line"
          ;;
        *)
          case "$mode" in
            src)
              [ "${line#-I}" = "$line" ] && echo "$line" >> "$TEMP_OUTPUT_FILE"
              ;;
            inc)
              if [ "${line#-I}" != "$line" ]; then
                echo "${line#-I}" >> "$TEMP_OUTPUT_FILE"
              fi
              ;;
            all)
              echo "$line" >> "$TEMP_OUTPUT_FILE"
              ;;
          esac
          ;;
      esac
    done < "$file"
  done
}

expand "$@"

awk '!a[$0]++' "$TEMP_OUTPUT_FILE"
